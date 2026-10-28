"""Clean-turn regressions for the standalone live voice path.

These tests use only in-memory playback and SDK event objects; they never open
an audio device or spawn a playback process.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

from google.genai import types

from core.speech_turn import SpeechTurnGate
from core.stable_voice import LiveVoice, Playback


def model_audio(pcm=b"\x01\x00" * 480, *, turn_complete=False):
    return types.LiveServerMessage(server_content=types.LiveServerContent(
        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
            data=pcm, mime_type="audio/pcm;rate=24000"))]),
        turn_complete=turn_complete))


class CleanTurnBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.player = Playback("private-sink")
        self.voice = LiveVoice(self.player)

    async def asyncTearDown(self):
        await self.player.interrupt()

    async def test_unsolicited_model_audio_never_queues(self):
        self.assertFalse(self.voice._reply_authorized)
        self.assertFalse(self.voice._reply_started)

        await self.voice.handle(model_audio())

        self.assertTrue(self.player.queue.empty())

    async def test_authorized_reply_queues_then_turn_complete_consumes_permission(self):
        self.voice._reply_authorized = True

        await self.voice.handle(model_audio())
        self.assertEqual(self.player.queue.get_nowait()[1], b"\x01\x00" * 480)
        self.assertTrue(self.voice._reply_started)

        await self.voice.handle(types.LiveServerMessage(server_content=
            types.LiveServerContent(turn_complete=True)))
        self.assertFalse(self.voice._reply_authorized)

        await self.voice.handle(model_audio(b"\x02\x00" * 480))
        self.assertTrue(self.player.queue.empty())

    async def test_input_during_queued_playback_is_silence_and_does_not_open_turn(self):
        detector_inputs = []

        def detector(pcm):
            detector_inputs.append(pcm)
            return .99

        gate = SpeechTurnGate(detector=detector)
        voice = LiveVoice(self.player, speech_gate=gate)
        self.player.enqueue(b"\x10\x00" * 480)
        reader = asyncio.StreamReader()
        reader.feed_data(b"\x20\x00" * 640)
        reader.feed_eof()
        session = type("Session", (), {})()
        session.send_realtime_input = AsyncMock()

        with self.assertRaises(EOFError):
            await voice.send_audio(session, reader)

        sent = [call.kwargs["audio"] for call in session.send_realtime_input.await_args_list]
        self.assertEqual([blob.data for blob in sent], [bytes(640), bytes(640)])
        self.assertTrue(all(blob.mime_type == "audio/pcm;rate=16000" for blob in sent))
        self.assertTrue(all(not any(frame) for frame in detector_inputs))
        self.assertFalse(voice._reply_authorized)

    async def test_mute_masks_input_and_output_without_autonomous_audio(self):
        self.voice.set_muted(True)
        reader = asyncio.StreamReader()
        reader.feed_data(b"\x20\x00" * 640)
        reader.feed_eof()
        session = type("Session", (), {})()
        session.send_realtime_input = AsyncMock()

        with self.assertRaises(EOFError):
            await self.voice.send_audio(session, reader)

        sent = [call.kwargs["audio"].data
                for call in session.send_realtime_input.await_args_list]
        self.assertEqual(sent, [bytes(640), bytes(640)])

        # A startup greeting or background notice has no authorization to play.
        await self.voice.handle(model_audio())
        self.assertTrue(self.player.queue.empty())
        self.assertFalse(self.voice._reply_authorized)

    async def test_stalled_request_discards_resume_without_replaying(self):
        self.voice._reply_authorized = True
        self.voice.resume_handle = 'old-session'
        self.voice._last_progress = -1000
        with patch('core.stable_voice.asyncio.sleep', new_callable=AsyncMock):
            with self.assertRaisesRegex(ConnectionError, 'response timeout'):
                await self.voice.monitor_response()
        self.assertIsNone(self.voice.resume_handle)
        self.assertFalse(self.voice._reply_authorized)

    async def test_manual_stop_cannot_latch_the_input_filter_closed(self):
        self.voice.connected = True
        self.voice._reply_authorized = self.voice._waiting = True
        self.voice.resume_handle = 'old-session'
        self.voice.interrupt()
        self.assertTrue(self.voice._drop_response)
        self.assertFalse(self.voice.connected)
        with patch('core.stable_voice.asyncio.sleep', new_callable=AsyncMock):
            with self.assertRaisesRegex(ConnectionError, 'manual stop'):
                await self.voice.monitor_response()
        self.assertFalse(self.voice._drop_response)
        self.assertFalse(self.voice._reply_authorized)
        self.assertIsNone(self.voice.resume_handle)
