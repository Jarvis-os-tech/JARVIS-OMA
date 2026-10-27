"""Regression coverage for bounded optional video sends sharing the audio lock."""
import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import AsyncMock
from types import SimpleNamespace as NS

from core.agent import LiveVoice, RenewConnection, VISION_SEND_BUDGET_SECONDS
from core.audio_scheduler import SendStalled


class VisionAudioContentionTests(IsolatedAsyncioTestCase):
    async def test_capture_from_previous_generation_is_dropped_before_transport(self):
        engine = NS(active_generation=0, async_input_queue=asyncio.Queue())
        voice = LiveVoice(engine)
        voice._schedule_camera_stream_update = lambda: None
        captured, release = asyncio.Event(), asyncio.Event()

        async def frame():
            captured.set()
            await release.wait()
            return b'old-frame'

        voice._capture_screen_frame = frame
        voice.set_vision_mode('screen')
        session = NS(send_realtime_input=AsyncMock())
        task = asyncio.create_task(voice.stream_vision(session))
        try:
            await asyncio.wait_for(captured.wait(), 1)
            engine.active_generation = 1
            release.set()
            async with asyncio.timeout(1):
                while not voice.send_lock.dropped_video_frames:
                    await asyncio.sleep(.001)
            session.send_realtime_input.assert_not_awaited()
            self.assertFalse(task.done())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_capture_is_deferred_while_microphone_frames_are_queued(self):
        engine = NS(active_generation=0, async_input_queue=asyncio.Queue())
        for _ in range(3):
            engine.async_input_queue.put_nowait(bytes(640))
        voice = LiveVoice(engine)
        voice._schedule_camera_stream_update = lambda: None
        voice._capture_screen_frame = AsyncMock(return_value=b'frame')
        voice.set_vision_mode('screen')
        session = NS(send_realtime_input=AsyncMock())
        task = asyncio.create_task(voice.stream_vision(session))
        try:
            await asyncio.sleep(.01)
            voice._capture_screen_frame.assert_not_awaited()
            session.send_realtime_input.assert_not_awaited()
            self.assertGreater(voice.send_lock.dropped_video_frames, 0)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_stalled_video_is_cancelled_before_any_more_socket_writes(self):
        engine = MagicMock()
        engine.async_input_queue = asyncio.Queue()
        voice = LiveVoice(engine)
        voice._schedule_camera_stream_update = lambda: None
        voice._capture_screen_frame = self._frame
        voice.set_vision_mode('screen')

        video_started = asyncio.Event()
        video_cancelled = asyncio.Event()
        audio_sent = asyncio.Event()
        calls = []

        async def send_realtime_input(*, video=None, audio=None):
            calls.append('video' if video is not None else 'audio')
            if video is not None:
                video_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    video_cancelled.set()
                    raise
            else:
                audio_sent.set()

        session = MagicMock(send_realtime_input=send_realtime_input)
        vision = asyncio.create_task(voice.stream_vision(session))
        await asyncio.wait_for(video_started.wait(), timeout=1)

        # Exercise the real audio sender while a video write owns the lock.
        await engine.async_input_queue.put(b'\0' * voice.input_bytes)
        audio = asyncio.create_task(voice.send_audio(session))
        await asyncio.wait_for(video_cancelled.wait(), timeout=1)
        with self.assertRaises(RenewConnection):
            await vision
        with self.assertRaises(SendStalled):
            await asyncio.wait_for(audio, 1)

        # The optional frame was dropped; no detached send or queued video
        # backlog remains, and the regular vision worker remains manageable.
        self.assertEqual(calls, ['video'])
        self.assertFalse(audio_sent.is_set())
        self.assertFalse(voice.send_lock.locked())
        self.assertTrue(vision.done())

        voice.set_vision_mode('off')
        audio.cancel()
        await asyncio.gather(vision, audio, return_exceptions=True)
        self.assertFalse(voice.send_lock.locked())

    async def test_vision_off_drops_stalled_frame_and_releases_lock(self):
        engine = MagicMock()
        engine.async_input_queue = asyncio.Queue()
        voice = LiveVoice(engine)
        voice._schedule_camera_stream_update = lambda: None
        voice._capture_screen_frame = self._frame
        voice.set_vision_mode('screen')
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def send_realtime_input(*, video=None, audio=None):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        vision = asyncio.create_task(voice.stream_vision(
            MagicMock(send_realtime_input=send_realtime_input)))
        await asyncio.wait_for(started.wait(), timeout=1)
        voice.set_vision_mode('off')
        await asyncio.wait_for(cancelled.wait(), timeout=VISION_SEND_BUDGET_SECONDS + 0.5)
        with self.assertRaises(RenewConnection):
            await vision
        self.assertFalse(voice.send_lock.locked())
        self.assertTrue(vision.done())  # worker exits so supervisor closes the session
        self.assertFalse(voice.send_lock.locked())

    async def _frame(self):
        return b'jpeg-frame'
