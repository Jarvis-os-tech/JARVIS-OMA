"""Extension playback uses the real, unmodified engine without opening devices."""
import unittest

from audio.engine import NativeAudioEngine
from audio.extension import ExtendedAudioEngine


class ExtensionPlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_processed_audio_is_tagged_sliced_and_marks_speaking(self):
        engine = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base_engine=engine)
        frame = b'\x01\x00' * 480
        class Processor:
            def process_output_frame(self, data):
                return data * 2 + b'\x02\x00'
        wrapper.register_processor(Processor())
        wrapper.put_processed_output(frame)
        self.assertEqual(engine.c_output_queue.get_nowait(), (0, frame))
        self.assertEqual(engine.c_output_queue.get_nowait(), (0, frame))
        self.assertEqual(engine.c_output_queue.get_nowait(), (0, b'\x02\x00'))
        self.assertTrue(engine.c_output_queue.empty())
        self.assertTrue(engine.speaking)

    async def test_barge_in_during_processing_rejects_stale_audio(self):
        engine = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base_engine=engine)
        class Processor:
            def process_output_frame(self, data):
                engine.handle_barge_in()
                return data
        wrapper.register_processor(Processor())
        wrapper.put_processed_output(b'\0\0' * 480)
        self.assertEqual(engine.active_generation, 1)
        self.assertTrue(engine.c_output_queue.empty())
        self.assertFalse(engine.speaking)

    async def test_muted_engine_does_not_queue_extension_audio(self):
        engine = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base_engine=engine)
        engine.set_muted(True)
        wrapper.put_processed_output(b'\0\0' * 480)
        self.assertTrue(engine.c_output_queue.empty())
        self.assertFalse(engine.speaking)

    async def test_processor_can_drop_audio(self):
        engine = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base_engine=engine)
        class Processor:
            def process_output_frame(self, data):
                return None
        wrapper.register_processor(Processor())
        wrapper.put_processed_output(b'\0\0' * 480)
        self.assertTrue(engine.c_output_queue.empty())
        self.assertFalse(engine.speaking)
