"""Unit tests for DownstreamRouter Raised-Cosine crossfader and local filler mixing."""
import struct
import unittest
from audio.downstream import DownstreamRouter, SAMPLE_RATE, DEFAULT_FRAME_BYTES


class MockEngine:
    def __init__(self):
        self.output_frame_bytes = DEFAULT_FRAME_BYTES
        self.active_generation = 1
        self.queue = []

    def enqueue_output(self, generation, chunk):
        self.queue.append((generation, chunk))


class TestFillerCrossfade(unittest.TestCase):
    def test_procedural_filler_fallback(self):
        router = DownstreamRouter()
        self.assertIn("generic_deep_thought", router._precharged_fillers)
        pcm = router._precharged_fillers["generic_deep_thought"]
        self.assertGreater(len(pcm), 0)
        self.assertEqual(len(pcm) % 2, 0)
        # Check first sample is 0 or close to 0 (no click start)
        first_sample = struct.unpack_from('<h', pcm, 0)[0]
        self.assertEqual(first_sample, 0)

    def test_trigger_filler_precharge(self):
        engine = MockEngine()
        router = DownstreamRouter(engine=engine, local_buffer_precharge=2)
        res = router.trigger_filler("generic_deep_thought", generation=1)
        self.assertTrue(res)
        self.assertTrue(router._is_filler_active)
        # Precharge 2 chunks
        self.assertEqual(len(engine.queue), 2)
        self.assertEqual(engine.queue[0][0], 1)
        self.assertEqual(len(engine.queue[0][1]), DEFAULT_FRAME_BYTES)

    def test_raised_cosine_ducking_crossfade(self):
        engine = MockEngine()
        router = DownstreamRouter(engine=engine, ducking_window_ms=50, local_buffer_precharge=0)
        # Trigger filler
        router.trigger_filler("generic_deep_thought", generation=1)
        self.assertTrue(router._is_filler_active)

        # Incoming Gemini audio: full amplitude sine wave
        gemini_data = b'\x50\x20' * 480  # 960 bytes (1 frame)
        router.feed(gemini_data)

        # Output frame should be emitted
        self.assertEqual(len(engine.queue), 1)
        gen, output_chunk = engine.queue[0]
        self.assertEqual(gen, 1)
        self.assertEqual(len(output_chunk), 960)

        # Filler should have transitioned (ducking completed)
        self.assertFalse(router._is_filler_active)

    def test_barge_in_clears_filler(self):
        engine = MockEngine()
        router = DownstreamRouter(engine=engine, local_buffer_precharge=1)
        router.trigger_filler("filesystem_grep", generation=1)
        self.assertTrue(router._is_filler_active)

        # User barges in -> clear called
        router.clear()
        self.assertFalse(router._is_filler_active)
        self.assertEqual(len(router._active_filler), 0)
        self.assertEqual(len(router.residual), 0)


if __name__ == '__main__':
    unittest.main()
