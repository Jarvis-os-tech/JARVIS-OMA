"""Offline unit tests for NativeAudioEngine and DownstreamRouter.

No hardware audio devices, PipeWire, or network access required.
All PortAudio interactions are mocked.
"""
import asyncio
import queue
import threading
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

import numpy as np
from audio.engine import NativeAudioEngine, StreamLostError
from audio.downstream import DownstreamRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(loop=None):
    """Create an engine with a fake event loop for testing."""
    if loop is None:
        loop = asyncio.new_event_loop()
    engine = NativeAudioEngine.__new__(NativeAudioEngine)
    engine.loop = loop
    engine.async_input_queue = asyncio.Queue(maxsize=50)
    engine.c_output_queue = queue.SimpleQueue()
    engine.input_rate = 16000
    engine.output_rate = 24000
    engine.input_block_size = 320
    engine.output_block_size = 480
    engine.output_frame_bytes = 960
    engine.active_generation = 0
    engine.muted = False
    engine.speaking = False
    engine._input_queue_capacity = 50
    engine.input_frame_ms = 20
    engine.voice_rms_threshold = 450.0
    engine.voice_band_ratio = 0.55
    engine.duck_frames = 2
    engine.barge_frames = 15
    engine.release_frames = 6
    engine.duck_gain = 0.30
    engine.fade_samples = 240
    engine._voice_frames = 0
    engine._quiet_frames = 0
    engine._barge_fired = False
    engine._gain = 1.0
    engine._target_gain = 1.0
    engine._state_lock = threading.Lock()
    engine.on_barge_in = None
    engine.on_state_change = None
    engine.state = 'listening'
    engine._fade_out_pending = False
    engine._last_output_sample = np.int16(0)
    engine.input_rms = 0.0
    engine.output_rms = 0.0
    freqs = np.fft.rfftfreq(engine.input_block_size, d=1.0 / engine.input_rate)
    engine._vocal_mask = (freqs >= 300.0) & (freqs <= 3400.0)
    engine.input_stream = None
    engine.output_stream = None
    return engine, loop


# ---------------------------------------------------------------------------
# NativeAudioEngine tests
# ---------------------------------------------------------------------------

class TestInputCallback(unittest.TestCase):
    def test_input_callback_dispatches_bytes(self):
        engine, loop = _make_engine()
        calls = []
        engine.loop = MagicMock()
        engine.loop.call_soon_threadsafe = lambda fn, *a: calls.append((fn, a))

        data = b'\x01\x00' * 320  # 640 bytes = 320 samples
        engine._input_callback(data, 320, None, None)

        self.assertEqual(len(calls), 1)
        fn, args = calls[0]
        self.assertIs(fn.__func__, engine._safe_enqueue_input.__func__)
        self.assertEqual(args, (data,))
        loop.close()

    def test_input_callback_sends_silence_when_muted(self):
        engine, loop = _make_engine()
        engine.muted = True
        engine.loop = MagicMock()
        calls = []
        engine.loop.call_soon_threadsafe = lambda fn, *a: calls.append((fn, a))

        engine._input_callback(b'\x05' * 640, 320, None, None)
        self.assertEqual(len(calls), 1)
        fn, args = calls[0]
        self.assertIs(fn.__func__, engine._safe_enqueue_input.__func__)
        self.assertEqual(args, (b'\x00' * 640,))
        loop.close()


class TestSafeEnqueueInput(unittest.TestCase):
    def test_enqueue_basic(self):
        loop = asyncio.new_event_loop()
        engine, _ = _make_engine(loop)
        engine._safe_enqueue_input(b'frame1')
        self.assertEqual(engine.async_input_queue.qsize(), 1)
        loop.close()

    def test_eviction_at_capacity(self):
        loop = asyncio.new_event_loop()
        engine, _ = _make_engine(loop)
        engine._input_queue_capacity = 3
        engine.async_input_queue = asyncio.Queue(maxsize=3)
        for i in range(3):
            engine._safe_enqueue_input(f'frame{i}'.encode())
        self.assertEqual(engine.async_input_queue.qsize(), 3)

        # Enqueue a 4th — should evict the oldest
        engine._safe_enqueue_input(b'frame3')
        self.assertEqual(engine.async_input_queue.qsize(), 3)
        # The oldest (frame0) should have been evicted
        first = engine.async_input_queue.get_nowait()
        self.assertEqual(first, b'frame1')
        loop.close()


class TestOutputCallback(unittest.TestCase):
    def test_silence_on_empty_queue(self):
        engine, loop = _make_engine()
        import numpy as np
        outdata = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(outdata, 480, None, None)
        self.assertTrue((outdata == 0).all())
        loop.close()

    def test_correct_data_written(self):
        engine, loop = _make_engine()
        import numpy as np
        samples = np.arange(480, dtype=np.int16)
        chunk = samples.tobytes()
        engine.c_output_queue.put_nowait((0, chunk))

        outdata = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(outdata, 480, None, None)
        np.testing.assert_array_equal(outdata[:, 0], samples)
        loop.close()

    def test_stale_generation_produces_silence(self):
        engine, loop = _make_engine()
        import numpy as np
        samples = np.ones(480, dtype=np.int16)
        engine.c_output_queue.put_nowait((0, samples.tobytes()))
        engine.active_generation = 1  # Bump past the queued chunk

        outdata = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(outdata, 480, None, None)
        self.assertTrue((outdata == 0).all())
        loop.close()

    def test_short_chunk_padded_with_silence(self):
        engine, loop = _make_engine()
        import numpy as np
        short_samples = np.arange(100, dtype=np.int16)
        engine.c_output_queue.put_nowait((0, short_samples.tobytes()))

        outdata = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(outdata, 480, None, None)
        np.testing.assert_array_equal(outdata[:100, 0], short_samples)
        self.assertTrue((outdata[100:, 0] == 0).all())
        loop.close()


class TestBargeIn(unittest.TestCase):
    def test_generation_bump_and_queue_drain(self):
        engine, loop = _make_engine()
        for i in range(10):
            engine.c_output_queue.put_nowait((0, b'\x00' * 960))
        self.assertEqual(engine.active_generation, 0)

        # Mock the output stream to avoid PortAudio calls
        engine.output_stream = MagicMock()
        engine.handle_barge_in()

        self.assertEqual(engine.active_generation, 1)
        self.assertTrue(engine.c_output_queue.empty())
        engine.output_stream.abort.assert_not_called()
        engine.output_stream.start.assert_not_called()
        loop.close()

    def test_barge_in_idempotent(self):
        engine, loop = _make_engine()
        engine.output_stream = MagicMock()
        engine.handle_barge_in()
        engine.handle_barge_in()
        engine.handle_barge_in()
        self.assertEqual(engine.active_generation, 3)
        loop.close()

    def test_barge_in_without_stream(self):
        engine, loop = _make_engine()
        engine.output_stream = None
        # Should not raise
        engine.handle_barge_in()
        self.assertEqual(engine.active_generation, 1)
        loop.close()


class TestVoiceGate(unittest.TestCase):
    @staticmethod
    def voice_frame():
        import numpy as np
        t = np.arange(320) / 16000
        return (np.sin(2 * np.pi * 700 * t) * 6000).astype(np.int16).tobytes()

    def test_short_backchannel_ducks_without_flushing(self):
        engine, loop = _make_engine()
        engine.speaking = True
        frame = self.voice_frame()
        engine._update_voice_gate(frame)
        engine._update_voice_gate(frame)
        self.assertEqual(engine._target_gain, 0.30)
        self.assertEqual(engine.active_generation, 0)
        loop.close()

    def test_sustained_voice_flushes_without_restarting_stream(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.output_stream = MagicMock()
        callback = MagicMock()
        engine.on_barge_in = callback
        frame = self.voice_frame()
        for _ in range(15):
            engine._update_voice_gate(frame)
        self.assertEqual(engine.active_generation, 1)
        engine.output_stream.abort.assert_not_called()
        engine.output_stream.stop.assert_not_called()
        callback.assert_called_once()
        loop.close()


class TestMute(unittest.TestCase):
    def test_mute_drains_output(self):
        engine, loop = _make_engine()
        engine.output_stream = MagicMock()
        engine.c_output_queue.put_nowait((0, b'\x00' * 960))
        engine.set_muted(True)
        self.assertTrue(engine.muted)
        self.assertTrue(engine.c_output_queue.empty())
        loop.close()

    def test_unmute(self):
        engine, loop = _make_engine()
        engine.output_stream = MagicMock()
        engine.set_muted(True)
        engine.set_muted(False)
        self.assertFalse(engine.muted)
        loop.close()


class TestReconnectBuffering(unittest.TestCase):
    def test_reconnect_buffering_expands_and_resets(self):
        engine, loop = _make_engine()
        self.assertEqual(engine._input_queue_capacity, 50)
        engine.set_reconnect_buffering(True)
        self.assertEqual(engine._input_queue_capacity, 200)
        engine.set_reconnect_buffering(False)
        self.assertEqual(engine._input_queue_capacity, 50)
        loop.close()


class TestOutputMicroFade(unittest.TestCase):
    def test_micro_fade_executed_on_barge_in(self):
        engine, loop = _make_engine()
        import numpy as np
        outdata = np.ones((480, 1), dtype=np.int16) * 1000
        engine._fade_out_pending = True
        engine._last_output_sample = np.int16(1000)
        engine._output_callback(outdata, 480, None, None)
        self.assertFalse(engine._fade_out_pending)
        # First 120 samples should be a ramp fading down from 1000 towards 0
        self.assertLess(outdata[60, 0], 1000)
        self.assertEqual(outdata[120:, 0].max(), 0)
        self.assertEqual(engine._last_output_sample, 0)
        loop.close()


class TestStateTransitions(unittest.TestCase):
    def test_state_change_callback_fired(self):
        engine, loop = _make_engine()
        state_changes = []
        engine.on_state_change = lambda s: state_changes.append(s)
        engine.loop = MagicMock()
        engine.loop.call_soon_threadsafe = lambda fn, *a: fn(*a)

        engine._set_state("ducked")
        self.assertEqual(engine.state, "ducked")
        self.assertIn("ducked", state_changes)
        loop.close()


class TestEnqueuePlayback(unittest.TestCase):
    def test_enqueue_playback_slices_into_frames(self):
        engine, loop = _make_engine()
        # Enqueue 1920 bytes = exactly two 960-byte frames
        raw_pcm = b'\x02\x00' * 960
        engine.enqueue_playback(raw_pcm)
        self.assertEqual(engine.c_output_queue.qsize(), 2)
        gen1, frame1 = engine.c_output_queue.get_nowait()
        gen2, frame2 = engine.c_output_queue.get_nowait()
        self.assertEqual(len(frame1), 960)
        self.assertEqual(len(frame2), 960)
        self.assertEqual(gen1, engine.active_generation)
        self.assertEqual(gen2, engine.active_generation)
        loop.close()


class TestDeviceResolution(unittest.TestCase):
    def test_resolves_matching_devices(self):
        devices = [
            {'name': 'Built-in Audio', 'max_input_channels': 2, 'max_output_channels': 0},
            {'name': 'omachy_aec_abc123_source', 'max_input_channels': 1, 'max_output_channels': 0},
            {'name': 'Built-in Speaker', 'max_input_channels': 0, 'max_output_channels': 2},
            {'name': 'omachy_aec_abc123_sink', 'max_input_channels': 0, 'max_output_channels': 1},
        ]
        with patch('audio.engine.sd.query_devices', return_value=devices):
            in_id, out_id = NativeAudioEngine.resolve_aec_devices(
                'omachy_aec_abc123_source', 'omachy_aec_abc123_sink',
            )
        self.assertEqual(in_id, 1)
        self.assertEqual(out_id, 3)

    def test_falls_back_to_defaults(self):
        with patch('audio.engine.sd.query_devices', return_value=[]), \
             patch('audio.engine.sd.default', SimpleNamespace(device=(0, 1))), \
             patch('audio.engine.time.sleep'):
            in_id, out_id = NativeAudioEngine.resolve_aec_devices(
                'nonexistent_source', 'nonexistent_sink', retries=2, delay=0,
            )
        self.assertEqual(in_id, 0)
        self.assertEqual(out_id, 1)


class TestMonitorHealth(unittest.IsolatedAsyncioTestCase):
    async def test_raises_on_inactive_input(self):
        engine, loop = _make_engine(asyncio.get_running_loop())
        engine.input_stream = MagicMock()
        engine.output_stream = MagicMock()
        type(engine.input_stream).active = PropertyMock(return_value=False)
        type(engine.output_stream).active = PropertyMock(return_value=True)

        with self.assertRaises(StreamLostError):
            # Patch sleep to avoid waiting 2 real seconds
            with patch('audio.engine.asyncio.sleep', return_value=asyncio.sleep(0)):
                await engine.monitor_health()

    async def test_raises_on_inactive_output(self):
        engine, loop = _make_engine(asyncio.get_running_loop())
        engine.input_stream = MagicMock()
        engine.output_stream = MagicMock()
        type(engine.input_stream).active = PropertyMock(return_value=True)
        type(engine.output_stream).active = PropertyMock(return_value=False)

        with self.assertRaises(StreamLostError):
            with patch('audio.engine.asyncio.sleep', return_value=asyncio.sleep(0)):
                await engine.monitor_health()


class TestTerminate(unittest.TestCase):
    def test_terminate_closes_streams(self):
        engine, loop = _make_engine()
        engine.input_stream = MagicMock()
        engine.output_stream = MagicMock()
        engine.terminate()
        engine.input_stream is None  # cleared
        engine.output_stream is None
        loop.close()

    def test_terminate_tolerates_none_streams(self):
        engine, loop = _make_engine()
        engine.terminate()  # Should not raise
        loop.close()


# ---------------------------------------------------------------------------
# DownstreamRouter tests
# ---------------------------------------------------------------------------

class TestDownstreamFeed(unittest.TestCase):
    def test_exact_frame_emitted(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        data = b'\x01\x00' * 480  # 960 bytes = exactly 1 frame
        router.feed(data)
        self.assertTrue(engine.c_output_queue.qsize() == 1)
        gen, chunk = engine.c_output_queue.get_nowait()
        self.assertEqual(gen, 0)
        self.assertEqual(chunk, data)
        self.assertEqual(len(router.residual), 0)
        loop.close()

    def test_residual_accumulation(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        data = b'\x02\x00' * 200  # 400 bytes — less than 960
        router.feed(data)
        self.assertTrue(engine.c_output_queue.empty())
        self.assertEqual(len(router.residual), 400)
        loop.close()

    def test_multiple_frames_from_large_blob(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        # 2048 bytes = 2 full frames (1920) + 128 residual
        data = b'\x03\x00' * 1024
        router.feed(data)
        self.assertEqual(engine.c_output_queue.qsize(), 2)
        self.assertEqual(len(router.residual), 128)
        loop.close()

    def test_residual_carried_across_feeds(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        # Feed 500 bytes, then 500 more — should emit one 960-byte frame
        router.feed(b'\x00' * 500)
        self.assertTrue(engine.c_output_queue.empty())
        router.feed(b'\x00' * 500)
        self.assertEqual(engine.c_output_queue.qsize(), 1)
        self.assertEqual(len(router.residual), 40)  # 1000 - 960
        loop.close()

    def test_generation_tagging(self):
        engine, loop = _make_engine()
        engine.active_generation = 7
        router = DownstreamRouter(engine)
        router.feed(b'\x00' * 960)
        gen, _ = engine.c_output_queue.get_nowait()
        self.assertEqual(gen, 7)
        loop.close()


class TestDownstreamFlush(unittest.TestCase):
    def test_flush_pads_with_silence(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(b'\x01\x00' * 100)  # 200 bytes residual
        router.flush()
        self.assertEqual(engine.c_output_queue.qsize(), 1)
        _, chunk = engine.c_output_queue.get_nowait()
        self.assertEqual(len(chunk), 960)
        # First 200 bytes are data, rest are zero padding
        self.assertEqual(chunk[:200], b'\x01\x00' * 100)
        self.assertEqual(chunk[200:], b'\x00' * 760)
        self.assertEqual(len(router.residual), 0)
        loop.close()

    def test_flush_noop_when_empty(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.flush()
        self.assertTrue(engine.c_output_queue.empty())
        loop.close()


class TestDownstreamClear(unittest.TestCase):
    def test_clear_discards_residual(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(b'\x00' * 500)
        self.assertEqual(len(router.residual), 500)
        router.clear()
        self.assertEqual(len(router.residual), 0)
        loop.close()


if __name__ == '__main__':
    unittest.main()
