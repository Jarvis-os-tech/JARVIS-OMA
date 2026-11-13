"""Offline standby controller and wake-word framing tests."""
import asyncio
import unittest
from types import SimpleNamespace

from voice_layer.standby import OpenWakeWordDetector, StandbyController


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

    async def test_controller_wakes_on_explicit_wake_signal(self):
        class BlockingDetector:
            def reset(self):
                pass
            def process(self, frame):
                return False

        controller = StandbyController(detector=BlockingDetector(), arming_delay=0)
        engine = SimpleNamespace(async_input_queue=asyncio.Queue())
        await controller.request()
        listener = asyncio.create_task(controller.listen_for_wake_word(engine))
        await asyncio.sleep(0.01)
        self.assertTrue(controller.active)
        controller.wake()
        await asyncio.wait_for(listener, timeout=0.2)
        self.assertFalse(controller.active)
        self.assertFalse(controller.engaged)

    def test_default_threshold_rejects_ambient_noise_and_detects_strong_wake(self):
        detector = OpenWakeWordDetector.__new__(OpenWakeWordDetector)
        detector.threshold = 0.50
        detector._pcm = bytearray()
        detector._model = FakeModel([0.15, 0.20, 0.45])
        window = b'\x00\x00' * detector.sample_count

        # Ambient noise and low scores below 0.50 do not trigger detection
        self.assertFalse(detector.process(window))
        self.assertFalse(detector.process(window))
        self.assertFalse(detector.process(window))

        # Real wake word score (>= 0.65) triggers detection
        detector._model = FakeModel([0.85])
        self.assertTrue(detector.process(window))

    async def test_standby_announces_before_entering_standby(self):
        from voice_layer.daemon import LiveVoice, EnterStandby
        from voice_layer.playback import Playback

        player = Playback('default')
        voice = LiveVoice(player)
        voice.connected = True

        enqueued_pcm = []
        player.enqueue = lambda data: enqueued_pcm.append(data)

        await voice.standby.request()
        with self.assertRaises(EnterStandby):
            await voice.monitor_standby()

        self.assertTrue(len(enqueued_pcm) > 0)
        self.assertEqual(len(enqueued_pcm[0]), 94080)



class StandbyReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_external_wake_releases_a_generic_blocked_audio_read(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        class Stream:
            async def read(self, size):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        detector = SimpleNamespace(reset=lambda:None, process=lambda frame:False)
        controller = StandbyController(detector=detector, arming_delay=0)
        await controller.request()
        listener = asyncio.create_task(controller.listen_for_wake_word(Stream()))
        await entered.wait()
        controller.wake()
        await asyncio.wait_for(listener, .2)
        self.assertTrue(cancelled.is_set())
        self.assertFalse(controller.engaged)

    async def test_cancelled_listener_cleans_up_pending_audio_read(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        class Stream:
            async def read(self, size):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        controller=StandbyController(detector=SimpleNamespace(reset=lambda:None),arming_delay=0)
        listener=asyncio.create_task(controller.listen_for_wake_word(Stream()))
        await entered.wait();listener.cancel()
        with self.assertRaises(asyncio.CancelledError):await listener
        self.assertTrue(cancelled.is_set())
        self.assertFalse(controller.engaged)

    async def test_wake_during_announcement_cancels_old_standby_transition(self):
        from voice_layer.daemon import LiveVoice
        from voice_layer.playback import Playback
        voice=LiveVoice(Playback('test'));voice.connected=True
        voice.standby=StandbyController(detector=SimpleNamespace(reset=lambda:None))
        voice.player.enqueue=lambda data:voice.standby.wake()
        await voice.standby.request()
        monitor=asyncio.create_task(voice.monitor_standby())
        await asyncio.sleep(.55)
        self.assertFalse(monitor.done())
        self.assertFalse(voice.standby.engaged)
        monitor.cancel()
        with self.assertRaises(asyncio.CancelledError):await monitor

    async def test_old_listener_does_not_erase_new_standby_request(self):
        controller=StandbyController(detector=SimpleNamespace(reset=lambda:None,process=lambda frame:False),arming_delay=0)
        await controller.request()
        listener=asyncio.create_task(controller.listen_for_wake_word(asyncio.Queue()))
        await asyncio.sleep(.01)
        controller.wake()
        await controller.request()
        await asyncio.wait_for(listener,.2)
        self.assertTrue(controller.engaged)
        controller.wake()

    async def test_toggle_sets_and_clears_standby_without_polling(self):
        controller=StandbyController(detector=SimpleNamespace(reset=lambda:None))
        self.assertTrue((await controller.toggle())['standby'])
        self.assertFalse((await controller.toggle())['standby'])
        self.assertFalse(controller.engaged)
