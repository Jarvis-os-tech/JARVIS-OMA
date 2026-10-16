"""Offline unit tests for NativeAudioEngine and DownstreamRouter.

No hardware audio devices, PipeWire, or network access required.
All PortAudio interactions are mocked.
"""
import asyncio
import collections
import queue
import threading
import time
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
    engine = NativeAudioEngine(loop=loop, playback_latency_ms=20)
    engine._playback_need_fade_in = False
    return engine, loop



# ---------------------------------------------------------------------------
# NativeAudioEngine tests
# ---------------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):
    def test_full_turn_finishes_without_locking_audio_threads(self):
        engine = NativeAudioEngine(loop=MagicMock())
        engine._playback_need_fade_in = False
        pcm = np.arange(480, dtype=np.int16)
        output = np.zeros((480, 1), dtype=np.int16)
        errors = []

        def play_turn():
            try:
                engine.enqueue_output(0, pcm.tobytes())
                engine.mark_turn_complete()
                engine._output_callback(output, 480, None, None)
                np.testing.assert_array_equal(output[:, 0], pcm)
                engine._output_callback(output, 480, None, None)
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=play_turn, daemon=True)
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive(), 'Playback deadlocked during state transition')
        self.assertEqual(errors, [])
        self.assertEqual(engine.state, 'listening')
        self.assertEqual(engine.playback_sample_clock, 960)

    def test_reconnect_buffer_accepts_200_frames_then_trims_old_audio(self):
        engine = NativeAudioEngine(loop=MagicMock())
        engine.set_reconnect_buffering(True)
        for i in range(220):
            engine._safe_enqueue_input(i.to_bytes(2, 'little') * 320)
        self.assertEqual(engine.async_input_queue.qsize(), 200)
        engine.set_reconnect_buffering(False)
        engine._safe_enqueue_input(b'\x00' * 640)
        self.assertEqual(engine.async_input_queue.qsize(), 50)
        self.assertEqual(engine.async_input_queue.get_nowait(), (171).to_bytes(2, 'little') * 320)

    def test_stale_output_cannot_restart_speaking(self):
        engine = NativeAudioEngine(loop=MagicMock())
        engine.handle_barge_in()
        engine.enqueue_output(0, b'\x00' * 960)
        self.assertTrue(engine.c_output_queue.empty())
        self.assertFalse(engine.speaking)


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
        self.assertIs(fn.__func__, engine._drain_capture.__func__)
        self.assertEqual(args, ())
        fn(*args)
        self.assertEqual(engine.async_input_queue.get_nowait(), data)
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
        self.assertIs(fn.__func__, engine._drain_capture.__func__)
        self.assertEqual(args, ())
        fn(*args)
        self.assertEqual(engine.async_input_queue.get_nowait(), b'\x00' * 640)
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


class TestBoundedCapture(unittest.TestCase):
    def make_engine(self):
        loop = MagicMock()
        pending = collections.deque()
        loop.call_soon_threadsafe.side_effect = lambda fn, *args: pending.append((fn, args))
        loop.call_soon.side_effect = lambda fn, *args: pending.append((fn, args))
        return NativeAudioEngine(loop=loop), pending

    @staticmethod
    def drain(pending):
        while pending:
            fn, args = pending.popleft()
            fn(*args)

    def test_stalled_loop_bounds_frames_notifications_and_statuses(self):
        engine, pending = self.make_engine()
        with patch.object(engine, '_update_voice_gate') as voice_gate:
            for value in range(300):
                engine._input_callback(value.to_bytes(2, 'little') * 320, 320, None, 'overflow')
            self.assertEqual(len(pending), 1)
            self.assertEqual(len(engine._capture_buffer), 50)
            self.assertEqual(engine.capture_dropped_frames, 250)
            voice_gate.assert_not_called()
            self.assertEqual(engine.input_rms, 0)
            with patch('audio.engine.log.warning') as warning:
                self.drain(pending)
                warning.assert_called_once_with('PortAudio input status: %s (%d callbacks)', 'overflow', 300)
            self.assertEqual(engine.async_input_queue.qsize(), 50)
            self.assertEqual(engine.async_input_queue.get_nowait(), (250).to_bytes(2, 'little') * 320)
            self.assertFalse(engine._capture_drain_scheduled)

    def test_drain_yields_after_bounded_batch_and_accepts_arrivals(self):
        engine, pending = self.make_engine()
        for _ in range(50):
            engine._input_callback(b'\x01\x00' * 320, 320, None, None)
        fn, args = pending.popleft()
        fn(*args)
        self.assertEqual(engine.async_input_queue.qsize(), 16)
        self.assertEqual(len(pending), 1)
        engine._input_callback(b'\x02\x00' * 320, 320, None, None)
        self.assertEqual(len(pending), 1)
        self.drain(pending)
        engine._input_callback(b'\x03\x00' * 320, 320, None, None)
        self.assertEqual(len(pending), 1)
        self.drain(pending)
        self.assertFalse(engine._capture_drain_scheduled)

    def test_expired_producer_and_consumer_frames_are_discarded(self):
        engine, pending = self.make_engine()
        with patch('audio.engine.time.monotonic', return_value=100):
            engine._input_callback(b'\x01\x00' * 320, 320, None, None)
        with patch('audio.engine.time.monotonic', return_value=102):
            self.drain(pending)
        self.assertTrue(engine.async_input_queue.empty())
        self.assertEqual(engine.capture_dropped_frames, 1)
        with patch('audio.engine.time.monotonic', return_value=200):
            engine._safe_enqueue_input(b'\x02\x00' * 320)
        with patch('audio.engine.time.monotonic', return_value=202):
            with self.assertRaises(asyncio.QueueEmpty):
                engine.async_input_queue.get_nowait()
        self.assertEqual(engine.async_input_queue.expired_frames, 1)

    def test_async_reader_waits_for_fresh_audio_after_expired_frames(self):
        async def check():
            engine = NativeAudioEngine(loop=asyncio.get_running_loop())
            engine.async_input_queue.put_frame(b'old', time.monotonic() - 2)
            reader = asyncio.create_task(engine.async_input_queue.get())
            await asyncio.sleep(0)
            self.assertFalse(reader.done())
            engine._safe_enqueue_input(b'\x01\x00' * 320)
            self.assertEqual(await asyncio.wait_for(reader, 0.5), b'\x01\x00' * 320)
        asyncio.run(check())

    def test_arrival_during_last_batch_does_not_lose_notification(self):
        engine, pending = self.make_engine()
        engine._input_callback(b'\x01\x00' * 320, 320, None, None)
        def capture_again(_frame):
            engine._input_callback(b'\x02\x00' * 320, 320, None, None)
        with patch.object(engine, '_update_voice_gate', side_effect=capture_again):
            fn, args = pending.popleft()
            fn(*args)
        self.assertEqual(len(pending), 1)
        self.drain(pending)
        self.assertEqual(engine.async_input_queue.qsize(), 2)
        self.assertFalse(engine._capture_drain_scheduled)

    def test_reconnect_capacity_and_age_expand_then_shrink(self):
        engine, pending = self.make_engine()
        engine.set_reconnect_buffering(True)
        with patch('audio.engine.time.monotonic', return_value=100):
            for value in range(300):
                engine._input_callback(value.to_bytes(2, 'little') * 320, 320, None, None)
        self.assertEqual(len(engine._capture_buffer), 200)
        self.assertEqual(len(pending), 1)
        with patch('audio.engine.time.monotonic', return_value=103):
            self.drain(pending)
            self.assertEqual(engine.async_input_queue.qsize(), 200)
            engine.set_reconnect_buffering(False)
            self.assertTrue(engine.async_input_queue.empty())

    def test_mute_discards_pending_and_delivered_audio_without_extra_wakeups(self):
        engine, pending = self.make_engine()
        engine._safe_enqueue_input(b'\x01\x00' * 320)
        engine._input_callback(b'\x02\x00' * 320, 320, None, None)
        engine.set_muted(True)
        engine._input_callback(b'\x03\x00' * 320, 320, None, None)
        self.assertEqual(len(pending), 1)
        self.drain(pending)
        self.assertEqual(engine.async_input_queue.get_nowait(), b'\x00' * 640)
        engine.set_muted(False)
        self.assertTrue(engine.async_input_queue.empty())

    def test_termination_and_old_stream_callbacks_cannot_replay_audio(self):
        engine, pending = self.make_engine()
        old_epoch = engine._stream_epoch
        engine._safe_enqueue_input(b'\x01\x00' * 320)
        engine._input_callback(b'\x02\x00' * 320, 320, None, None)
        engine.terminate()
        engine._clear_capture(enabled=True)
        engine._input_callback(b'\x03\x00' * 320, 320, None, None, stream_epoch=old_epoch)
        engine._input_callback(b'\x04\x00' * 320, 320, None, None, stream_epoch=engine._stream_epoch)
        self.assertEqual(len(pending), 1)
        self.drain(pending)
        self.assertEqual(engine.async_input_queue.get_nowait(), b'\x04\x00' * 320)
        self.assertTrue(engine.async_input_queue.empty())


class TestOutputCallback(unittest.TestCase):
    def test_silence_on_empty_queue(self):
        engine, loop = _make_engine()
        import numpy as np
        outdata = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(outdata, 480, None, None)
        self.assertTrue((outdata == 0).all())
        loop.close()


class TestPlaybackJitter(unittest.TestCase):
    def test_device_underflow_softens_resume_without_growing_network_cushion(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_cushion_s=0.02)
        frame = np.full(480, 12000, dtype=np.int16).tobytes()
        output = np.zeros((480, 1), dtype=np.int16)
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[-1, 0], 12000)

        engine.enqueue_output(0, frame)
        status = type('OutputStatus', (), {'output_underflow': True, '__bool__': lambda self: True})()
        engine._output_callback(output, 480, None, status)
        self.assertEqual(engine.output_underflows, 1)
        self.assertEqual(engine.playback_recoveries, 1)
        self.assertEqual(engine.playback_rebuffers, 0)
        self.assertEqual(engine._playback_prebuffer_frames, 1)
        self.assertEqual(output[0, 0], 0)
        self.assertEqual(output[-1, 0], 12000)

    def test_callback_error_fades_and_reprimes_next_audio(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_cushion_s=0.02)
        frame = np.full(480, 12000, dtype=np.int16).tobytes()
        output = np.zeros((480, 1), dtype=np.int16)
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        engine.c_output_queue.put((0, object()))
        engine._output_callback(output, 480, None, None)
        self.assertEqual(engine.output_callback_errors, 1)
        self.assertEqual(engine.playback_recoveries, 1)
        self.assertEqual(output[0, 0], 12000)
        self.assertEqual(output[engine._edge_fade_samples - 1, 0], 0)
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[0, 0], 0)
        self.assertEqual(output[-1, 0], 12000)

    def test_network_cushion_is_independent_of_device_latency(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_latency_ms=20,
                                   playback_cushion_s=0.16)
        self.assertEqual(engine._playback_prebuffer_frames, 8)
        frame = np.full(480, 800, dtype=np.int16).tobytes()
        output = np.zeros((480, 1), dtype=np.int16)
        for _ in range(7):
            engine.enqueue_output(0, frame)
            engine._output_callback(output, 480, None, None)
            self.assertTrue((output == 0).all())
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[-1, 0], 800)

    def test_speech_onset_uses_smooth_ten_millisecond_fade(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_latency_ms=20)
        frame = np.full(480, 12000, dtype=np.int16).tobytes()
        output = np.zeros((480, 1), dtype=np.int16)
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(engine._edge_fade_samples, 240)
        self.assertEqual(output[0, 0], 0)
        self.assertLess(abs(int(output[1, 0])), 10)
        self.assertEqual(output[239, 0], 12000)
        self.assertEqual(output[240, 0], 12000)
        self.assertEqual(engine.output_callback_errors, 0)

    def test_prebuffer_and_smooth_rebuffer_edges(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_latency_ms=60)
        frame = np.full(480, 1000, dtype=np.int16).tobytes()
        output = np.zeros((480, 1), dtype=np.int16)
        for count in (1, 2):
            engine.enqueue_output(0, frame)
            engine._output_callback(output, 480, None, None)
            self.assertTrue((output == 0).all())
            self.assertEqual(engine.c_output_queue.qsize(), count)
        engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[0, 0], 0)
        self.assertEqual(output[-1, 0], 1000)
        engine._output_callback(output, 480, None, None)
        engine._output_callback(output, 480, None, None)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(engine.playback_rebuffers, 1)
        self.assertEqual(engine._playback_prebuffer_frames, 7)
        self.assertEqual(output[0, 0], 1000)
        self.assertEqual(output[engine._edge_fade_samples - 1, 0], 0)
        for _ in range(engine._playback_prebuffer_frames):
            engine.enqueue_output(0, frame)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[0, 0], 0)
        self.assertEqual(output[-1, 0], 1000)

    def test_completed_short_turn_does_not_wait_for_prebuffer(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_latency_ms=60)
        engine.enqueue_output(0, np.full(480, 500, dtype=np.int16).tobytes())
        engine.mark_turn_complete()
        output = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[-1, 0], 500)
        engine._output_callback(output, 480, None, None)
        engine.enqueue_output(0, np.full(480, 500, dtype=np.int16).tobytes())
        engine._output_callback(output, 480, None, None)
        self.assertTrue((output == 0).all())

    def test_completed_full_frame_fades_nonzero_tail_to_silence(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_cushion_s=0.02)
        output = np.zeros((480, 1), dtype=np.int16)
        engine.enqueue_output(0, np.full(480, 12000, dtype=np.int16).tobytes())
        engine.mark_turn_complete()
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[-1, 0], 12000)
        engine._output_callback(output, 480, None, None)
        self.assertEqual(output[0, 0], 12000)
        self.assertEqual(output[engine._edge_fade_samples - 1, 0], 0)
        self.assertFalse(engine.speaking)
        self.assertEqual(engine.playback_rebuffers, 0)

    def test_old_batch_drain_does_not_grow_network_cushion(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_cushion_s=0.02)
        output = np.zeros((480, 1), dtype=np.int16)
        with patch('audio.engine.time.monotonic', return_value=100.0):
            engine.enqueue_output(0, np.full(480, 12000, dtype=np.int16).tobytes())
            engine._output_callback(output, 480, None, None)
        with patch('audio.engine.time.monotonic', return_value=103.0):
            engine._output_callback(output, 480, None, None)
        self.assertEqual(engine.playback_drains, 1)
        self.assertEqual(engine.playback_rebuffers, 0)
        self.assertEqual(engine._playback_prebuffer_frames, 1)
        self.assertEqual(output[0, 0], 12000)
        self.assertEqual(output[engine._edge_fade_samples - 1, 0], 0)

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

    def test_jitter_hangover_holds_speaking_state_during_minor_underflow(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.state = 'speaking'
        engine._hangover_frames = 12
        engine._turn_complete = False

        import numpy as np
        outdata = np.zeros((480, 1), dtype=np.int16)
        # Empty queue for 5 frames (< 12 hangover frames)
        for _ in range(5):
            engine._output_callback(outdata, 480, None, None)
            self.assertTrue(engine.speaking)
            self.assertEqual(engine.state, 'speaking')
            self.assertTrue((outdata == 0).all())
        loop.close()

    def test_turn_complete_and_drained_returns_to_listening(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.state = 'speaking'
        engine._turn_complete = True
        engine._hangover_frames = 12

        import numpy as np
        outdata = np.zeros((480, 1), dtype=np.int16)
        # Queue is empty and turn_complete is True -> transitions immediately to listening
        engine._output_callback(outdata, 480, None, None)
        self.assertFalse(engine.speaking)
        self.assertEqual(engine.state, 'listening')
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

    def test_self_speech_echo_does_not_trigger_barge_in(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.output_stream = MagicMock()
        callback = MagicMock()
        engine.on_barge_in = callback
        # Speaker is actively playing audio with 0.20 RMS
        engine._recent_output_rms.append(0.20)
        # Voice frame has ~6000 amplitude / 32768 = ~0.13 RMS, which is below 0.20 * 1.8 = 0.36
        frame = self.voice_frame()
        for _ in range(20):
            engine._update_voice_gate(frame)
        # Should NOT have barged in because it was identified as speaker echo
        self.assertEqual(engine.active_generation, 0)
        self.assertFalse(engine._barge_fired)
        callback.assert_not_called()
        loop.close()

    def test_double_talk_triggers_barge_in_when_user_speaks_louder(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.output_stream = MagicMock()
        callback = MagicMock()
        engine.on_barge_in = callback
        # Speaker output is quiet (0.05 RMS)
        engine._recent_output_rms.append(0.05)
        # User speaks loudly into mic (20000 amplitude / 32768 = ~0.43 RMS, above 0.05 * 1.8 = 0.09)
        t = np.arange(320) / 16000
        loud_frame = (np.sin(2 * np.pi * 700 * t) * 20000).astype(np.int16).tobytes()
        for _ in range(15):
            engine._update_voice_gate(loud_frame)
        self.assertEqual(engine.active_generation, 1)
        self.assertTrue(engine._barge_fired)
        callback.assert_called_once()
        loop.close()

    def test_allow_barge_in_false_disables_local_barge_in(self):
        engine, loop = _make_engine()
        engine.speaking = True
        engine.allow_barge_in = False
        engine.output_stream = MagicMock()
        callback = MagicMock()
        engine.on_barge_in = callback
        frame = self.voice_frame()
        for _ in range(20):
            engine._update_voice_gate(frame)
        self.assertEqual(engine.active_generation, 0)
        self.assertFalse(engine._barge_fired)
        callback.assert_not_called()
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
    def test_barge_in_fades_queued_waveform_instead_of_holding_one_sample(self):
        engine, loop = _make_engine()
        engine._last_output_sample = np.int16(1000)
        next_frame = np.arange(1000, 1480, dtype=np.int16)
        engine.enqueue_output(0, next_frame.tobytes())
        engine.handle_barge_in()
        self.assertTrue(engine.c_output_queue.empty())
        output = np.zeros((480, 1), dtype=np.int16)
        engine._output_callback(output, 480, None, None)
        expected = (next_frame[:engine._edge_fade_samples].astype(np.float32) *
                    engine._fade_out_edge).astype(np.int16)
        np.testing.assert_array_equal(output[:engine._edge_fade_samples, 0], expected)
        self.assertTrue((output[engine._edge_fade_samples:, 0] == 0).all())
        self.assertIsNone(engine._fade_out_audio)
        loop.close()

    def test_micro_fade_executed_on_barge_in(self):
        engine, loop = _make_engine()
        import numpy as np
        outdata = np.ones((480, 1), dtype=np.int16) * 1000
        engine._fade_out_pending = True
        engine._last_output_sample = np.int16(1000)
        engine._output_callback(outdata, 480, None, None)
        self.assertFalse(engine._fade_out_pending)
        # Raised-cosine release starts without a sharp slope and reaches zero.
        self.assertEqual(outdata[0, 0], 1000)
        self.assertGreater(outdata[1, 0], 990)
        self.assertLess(outdata[120, 0], 1000)
        self.assertEqual(outdata[engine._edge_fade_samples:, 0].max(), 0)
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


class TestStartLifecycle(unittest.TestCase):
    def test_playback_latency_reaches_portaudio(self):
        engine = NativeAudioEngine(loop=MagicMock(), playback_latency_ms=80)
        capture, playback = MagicMock(active=True), MagicMock(active=True)
        with patch.object(engine, 'resolve_aec_devices', return_value=(0, 1)), \
             patch.object(engine, '_bind_pipewire_streams'), \
             patch('audio.engine.sd.InputStream', return_value=capture), \
             patch('audio.engine.sd.OutputStream', return_value=playback) as output_open:
            engine.start('', '')
        self.assertEqual(output_open.call_args.kwargs['latency'], .08)
        engine.terminate()

    def test_failed_start_releases_partial_streams_and_preserves_error(self):
        for stage in ('input_open', 'output_open', 'input_start', 'output_start'):
            with self.subTest(stage=stage):
                engine = NativeAudioEngine(loop=MagicMock())
                capture, playback = MagicMock(), MagicMock()
                failure = RuntimeError(stage)
                # Cleanup failures must not replace the device startup error.
                capture.stop.side_effect = RuntimeError('cleanup stop failed')
                capture.close.side_effect = RuntimeError('cleanup close failed')
                if stage == 'input_start':
                    capture.start.side_effect = failure
                if stage == 'output_start':
                    playback.start.side_effect = failure
                with patch.object(engine, 'resolve_aec_devices', return_value=(0, 1)), \
                     patch.object(engine, '_bind_pipewire_streams') as bind, \
                     patch('audio.engine.sd.InputStream', return_value=capture,
                           side_effect=failure if stage == 'input_open' else None), \
                     patch('audio.engine.sd.OutputStream', return_value=playback,
                           side_effect=failure if stage == 'output_open' else None), \
                     patch('audio.engine.log.warning') as warning:
                    with self.assertRaises(RuntimeError) as raised:
                        engine.start('', '')
                self.assertIs(raised.exception, failure)
                self.assertIsNone(engine.input_stream)
                self.assertIsNone(engine.output_stream)
                bind.assert_not_called()
                if stage != 'input_open':
                    capture.close.assert_called_once()
                    self.assertTrue(warning.called)
                if stage in ('input_start', 'output_start'):
                    playback.close.assert_called_once()

    def test_start_requires_both_streams_to_become_active(self):
        for inactive in ('capture', 'playback'):
            with self.subTest(inactive=inactive):
                engine = NativeAudioEngine(loop=MagicMock())
                capture = MagicMock(active=inactive != 'capture')
                playback = MagicMock(active=inactive != 'playback')
                with patch.object(engine, 'resolve_aec_devices', return_value=(0, 1)), \
                     patch.object(engine, '_bind_pipewire_streams') as bind, \
                     patch('audio.engine.sd.InputStream', return_value=capture), \
                     patch('audio.engine.sd.OutputStream', return_value=playback):
                    with self.assertRaises(StreamLostError):
                        engine.start('', '')
                capture.close.assert_called_once()
                playback.close.assert_called_once()
                bind.assert_not_called()
                self.assertIsNone(engine.input_stream)
                self.assertIsNone(engine.output_stream)

    def test_duplicate_start_preserves_owned_streams(self):
        for attribute in ('input_stream', 'output_stream'):
            with self.subTest(attribute=attribute):
                engine = NativeAudioEngine(loop=MagicMock())
                stream = MagicMock()
                setattr(engine, attribute, stream)
                with patch('audio.engine.sd.InputStream') as open_input, \
                     patch.object(engine, 'resolve_aec_devices') as resolve:
                    with self.assertRaisesRegex(RuntimeError, 'already exist'):
                        engine.start('', '')
                self.assertIs(getattr(engine, attribute), stream)
                resolve.assert_not_called()
                open_input.assert_not_called()
                stream.close.assert_not_called()

    def test_can_restart_after_start_failure(self):
        engine = NativeAudioEngine(loop=MagicMock())
        failed_capture, capture, playback = MagicMock(), MagicMock(active=True), MagicMock(active=True)
        with patch.object(engine, 'resolve_aec_devices', return_value=(0, 1)), \
             patch.object(engine, '_bind_pipewire_streams') as bind, \
             patch('audio.engine.sd.InputStream', side_effect=[failed_capture, capture]), \
             patch('audio.engine.sd.OutputStream', side_effect=[RuntimeError('device gone'), playback]):
            with self.assertRaisesRegex(RuntimeError, 'device gone'):
                engine.start('', '')
            engine.start('', '')
        failed_capture.close.assert_called_once()
        capture.start.assert_called_once()
        playback.start.assert_called_once()
        self.assertIs(engine.input_stream, capture)
        self.assertIs(engine.output_stream, playback)
        bind.assert_called_once()
        engine.terminate()


class TestMonitorHealth(unittest.IsolatedAsyncioTestCase):
    async def test_raises_on_missing_streams(self):
        for missing in ('input_stream', 'output_stream'):
            with self.subTest(missing=missing):
                engine = NativeAudioEngine(loop=asyncio.get_running_loop())
                engine.input_stream = MagicMock(active=True)
                engine.output_stream = MagicMock(active=True)
                setattr(engine, missing, None)
                with patch('audio.engine.asyncio.sleep', return_value=None):
                    with self.assertRaisesRegex(StreamLostError, 'missing'):
                        await engine.monitor_health()

    async def test_raises_on_inactive_input(self):
        engine, loop = _make_engine(asyncio.get_running_loop())
        engine.input_stream = MagicMock()
        engine.output_stream = MagicMock()
        type(engine.input_stream).active = PropertyMock(return_value=False)
        type(engine.output_stream).active = PropertyMock(return_value=True)

        with self.assertRaises(StreamLostError):
            # Patch sleep to avoid waiting 2 real seconds
            with patch('audio.engine.asyncio.sleep', return_value=None):
                await engine.monitor_health()

    async def test_raises_on_inactive_output(self):
        engine, loop = _make_engine(asyncio.get_running_loop())
        engine.input_stream = MagicMock()
        engine.output_stream = MagicMock()
        type(engine.input_stream).active = PropertyMock(return_value=True)
        type(engine.output_stream).active = PropertyMock(return_value=False)

        with self.assertRaises(StreamLostError):
            with patch('audio.engine.asyncio.sleep', return_value=None):
                await engine.monitor_health()


class TestTerminate(unittest.TestCase):
    def test_terminate_closes_streams(self):
        engine, loop = _make_engine()
        capture = engine.input_stream = MagicMock()
        playback = engine.output_stream = MagicMock()
        engine.terminate()
        for stream in (capture, playback):
            stream.stop.assert_called_once()
            stream.close.assert_called_once()
        self.assertIsNone(engine.input_stream)
        self.assertIsNone(engine.output_stream)
        loop.close()

    def test_terminate_attempts_each_close_when_stop_and_close_fail(self):
        engine = NativeAudioEngine(loop=MagicMock())
        capture = engine.input_stream = MagicMock()
        playback = engine.output_stream = MagicMock()
        capture.stop.side_effect = RuntimeError('stop failed')
        capture.close.side_effect = RuntimeError('close failed')
        playback.stop.side_effect = RuntimeError('other stop failed')
        with self.assertLogs('jarvis.audio', level='WARNING'):
            engine.terminate()
        for stream in (capture, playback):
            stream.stop.assert_called_once()
            stream.close.assert_called_once()
        self.assertIsNone(engine.input_stream)
        self.assertIsNone(engine.output_stream)
        engine.terminate()
        capture.close.assert_called_once()
        playback.close.assert_called_once()

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
    def test_barge_in_discards_partial_frame_before_next_response(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(np.full(200, 1000, dtype=np.int16).tobytes())
        engine.handle_barge_in()
        router.feed(np.full(480, 2000, dtype=np.int16).tobytes())
        generation, chunk = engine.c_output_queue.get_nowait()
        self.assertEqual(generation, engine.active_generation)
        np.testing.assert_array_equal(
            np.frombuffer(chunk, dtype=np.int16), np.full(480, 2000, dtype=np.int16))
        self.assertEqual(len(router.residual), 0)
        loop.close()

    def test_barge_in_drops_stale_partial_frame_on_flush(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(np.full(200, 1000, dtype=np.int16).tobytes())
        engine.handle_barge_in()
        router.flush()
        self.assertTrue(engine.c_output_queue.empty())
        self.assertEqual(len(router.residual), 0)
        loop.close()

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

    def test_flush_tapers_loud_residual_instead_of_hard_zero(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(np.full(100, 12000, dtype=np.int16).tobytes())
        router.flush()
        _, chunk = engine.c_output_queue.get_nowait()
        samples = np.frombuffer(chunk, dtype=np.int16)
        self.assertEqual(samples[99], 12000)
        self.assertGreater(samples[100], 11000)
        self.assertEqual(samples[339], 0)
        self.assertTrue((samples[340:] == 0).all())
        loop.close()

    def test_flush_tapers_nearly_full_final_frame(self):
        engine, loop = _make_engine()
        router = DownstreamRouter(engine)
        router.feed(np.full(479, 12000, dtype=np.int16).tobytes())
        router.flush()
        _, chunk = engine.c_output_queue.get_nowait()
        samples = np.frombuffer(chunk, dtype=np.int16)
        self.assertEqual(samples[239], 12000)
        self.assertLess(samples[360], 7000)
        self.assertEqual(samples[-1], 0)
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
