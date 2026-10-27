"""Offline standby controller and wake-word framing tests."""
import asyncio
import unittest
from types import SimpleNamespace

from audio.plugins.standby import OpenWakeWordDetector, StandbyController


class FakeModel:
    def __init__(self, scores):
        self.scores = iter(scores)
        self.reset_count = 0

    def predict(self, samples):
        return {'hey_jarvis_v0.1': next(self.scores)}

    def reset(self):
        self.reset_count += 1


class StandbyTests(unittest.IsolatedAsyncioTestCase):
    def test_detector_buffers_twenty_ms_frames_until_model_window(self):
        detector = OpenWakeWordDetector.__new__(OpenWakeWordDetector)
        detector.threshold = .5
        detector._pcm = bytearray()
        detector._model = FakeModel([.8])
        frame = b'\x00\x00' * 320

        for _ in range(3):
            self.assertFalse(detector.process(frame))
        self.assertTrue(detector.process(frame))
        self.assertEqual(detector._model.reset_count, 1)

    def test_weak_background_match_requires_nearby_confirmation(self):
        detector = OpenWakeWordDetector.__new__(OpenWakeWordDetector)
        detector.threshold = .05
        detector._pcm = bytearray()
        detector._model = FakeModel([.06, .06])
        window = b'\x00\x00' * detector.sample_count

        self.assertFalse(detector.process(window))
        self.assertTrue(detector.process(window))
        self.assertEqual(detector._model.reset_count, 1)

    def test_single_medium_match_does_not_wake(self):
        detector = OpenWakeWordDetector.__new__(OpenWakeWordDetector)
        detector.threshold = .05
        detector._pcm = bytearray()
        detector._model = FakeModel([.08])

        self.assertFalse(detector.process(b'\x00\x00' * detector.sample_count))

    def test_single_very_strong_match_wakes_immediately(self):
        detector = OpenWakeWordDetector.__new__(OpenWakeWordDetector)
        detector.threshold = .05
        detector._pcm = bytearray()
        detector._model = FakeModel([.16])

        self.assertTrue(detector.process(b'\x00\x00' * detector.sample_count))

    async def test_controller_keeps_audio_local_until_wake(self):
        class Detector:
            def __init__(self):
                self.frames = []
            def reset(self):
                self.frames.clear()
            def process(self, frame):
                self.frames.append(frame)
                return frame == b'wake'

        detector = Detector()
        controller = StandbyController(detector=detector, arming_delay=0)
        engine = SimpleNamespace(async_input_queue=asyncio.Queue())
        listener = asyncio.create_task(controller.listen_for_wake_word(engine))
        await asyncio.sleep(0)
        self.assertTrue(controller.active)
        await engine.async_input_queue.put(b'noise')
        await asyncio.sleep(0)
        self.assertFalse(listener.done())
        await engine.async_input_queue.put(b'wake')
        await asyncio.wait_for(listener, timeout=.2)
        self.assertFalse(controller.active)
        self.assertEqual(detector.frames, [b'noise', b'wake'])

    async def test_request_is_immediate_and_separate_from_wake_wait(self):
        controller = StandbyController(detector=FakeModel([]))
        result = await controller.request()
        self.assertEqual(result['status'], 'standby_requested')
        self.assertTrue(controller.engaged)
        await asyncio.wait_for(controller.wait_until_requested(), timeout=.2)
        self.assertTrue(controller.engaged)

    async def test_standby_remains_engaged_until_wake_completes(self):
        class Detector:
            def reset(self):
                pass
            def process(self, frame):
                return frame == b'wake'

        controller = StandbyController(detector=Detector(), arming_delay=0)
        engine = SimpleNamespace(async_input_queue=asyncio.Queue())
        await controller.request()
        await controller.wait_until_requested()
        listener = asyncio.create_task(controller.listen_for_wake_word(engine))
        await asyncio.sleep(0)
        self.assertTrue(controller.engaged)
        await engine.async_input_queue.put(b'wake')
        await asyncio.wait_for(listener, timeout=.2)
        self.assertFalse(controller.engaged)

    async def test_controller_discards_audio_that_arrives_during_arming_delay(self):
        class Detector:
            def __init__(self):
                self.frames = []
            def reset(self):
                self.frames.clear()
            def process(self, frame):
                self.frames.append(frame)
                return frame == b'wake'

        detector = Detector()
        controller = StandbyController(detector=detector, arming_delay=.02)
        engine = SimpleNamespace(async_input_queue=asyncio.Queue())
        listener = asyncio.create_task(controller.listen_for_wake_word(engine))
        await engine.async_input_queue.put(b'residual')
        await asyncio.sleep(.03)
        self.assertFalse(listener.done())
        self.assertEqual(detector.frames, [])
        await engine.async_input_queue.put(b'wake')
        await asyncio.wait_for(listener, timeout=.2)
