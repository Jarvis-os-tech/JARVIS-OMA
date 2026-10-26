"""Regression coverage for bounded optional video sends sharing the audio lock."""
import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

from core.agent import LiveVoice, RenewConnection, VISION_SEND_BUDGET_SECONDS


class VisionAudioContentionTests(IsolatedAsyncioTestCase):
    async def test_stalled_video_is_cancelled_and_microphone_send_proceeds(self):
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
        await asyncio.wait_for(audio_sent.wait(), timeout=1)
        await asyncio.wait_for(video_cancelled.wait(), timeout=1)
        with self.assertRaises(RenewConnection):
            await vision

        # The optional frame was dropped; no detached send or queued video
        # backlog remains, and the regular vision worker remains manageable.
        self.assertEqual(calls, ['video', 'audio'])
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
