import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from google.genai import types
from core.ipc import JarvisIPCServer
from core.stable_voice import LiveVoice, Playback


def audio_event(pcm):
    return types.LiveServerMessage(server_content=types.LiveServerContent(
        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
            data=pcm, mime_type='audio/pcm;rate=24000'))])))


class StableControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.player = Playback('private-sink')
        self.voice = LiveVoice(self.player)

    async def asyncTearDown(self):
        await self.player.interrupt()
        await asyncio.gather(*self.voice._controls, return_exceptions=True)

    async def test_muted_input_and_output_do_not_leak(self):
        self.voice.set_muted(True)
        reader = asyncio.StreamReader()
        reader.feed_data(b'\x20\x00' * 640)
        reader.feed_eof()
        sent = []
        async def send(**kwargs):
            sent.append(kwargs['audio'].data)
        session = type('Session', (), {'send_realtime_input': staticmethod(send)})()
        with self.assertRaises(EOFError):
            await self.voice.send_audio(session, reader)
        self.assertEqual(sent, [bytes(640), bytes(640)])
        await self.voice.handle(audio_event(b'\x01\x00' * 480))
        self.assertTrue(self.player.queue.empty())
        generation = self.player.generation
        self.voice.set_muted(True)
        self.assertEqual(self.player.generation, generation)

    async def test_manual_stop_discards_only_current_response(self):
        self.voice._reply_authorized = True
        await self.voice.handle(audio_event(b'\x01\x00'))
        self.voice.interrupt()
        await self.voice.handle(audio_event(b'\x02\x00'))
        self.assertTrue(self.player.queue.empty())
        await self.voice.handle(types.LiveServerMessage(
            server_content=types.LiveServerContent(turn_complete=True)))
        self.voice._reply_authorized = True  # A fresh locally admitted request.
        await self.voice.handle(audio_event(b'\x03\x00'))
        self.assertEqual(self.player.queue.get_nowait()[1], b'\x03\x00')

    async def test_idle_stop_does_not_suppress_next_reply(self):
        self.voice.interrupt()
        self.voice._reply_authorized = True  # A fresh locally admitted request.
        await self.voice.handle(audio_event(b'\x01\x00'))
        self.assertFalse(self.player.queue.empty())

    async def test_status_reports_actual_connection_and_audio_activity(self):
        self.assertEqual(self.voice.status()['state'], 'connecting')
        self.voice.connected = True
        self.assertEqual(self.voice.status()['state'], 'idle')
        self.voice._reply_authorized = True
        await self.voice.handle(audio_event(bytes(960)))
        status = self.voice.status()
        self.assertEqual(status['state'], 'speaking')
        self.assertEqual(status['provider_audio_bytes'], 960)
        self.assertEqual(status['audio_source_revision'], '2319135')
        self.assertFalse(status['skills_enabled'])

    async def test_socket_and_subscription_share_the_voice_mute_state(self):
        self.voice.connected = True
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'voice.sock'
            server = JarvisIPCServer(socket_path=path, status_provider=self.voice.status,
                                     set_mute_cb=self.voice.set_muted,
                                     interrupt_cb=self.voice.interrupt)
            await server.start()
            reader, writer = await asyncio.open_unix_connection(str(path))
            try:
                writer.write(b'{"command":"subscribe"}\n')
                await writer.drain()
                initial = json.loads(await reader.readline())
                self.assertEqual(initial['audio_backend'], 'github-reference')
                control_reader, control_writer = await asyncio.open_unix_connection(str(path))
                control_writer.write(b'{"command":"set_mute","muted":true}\n')
                await control_writer.drain()
                self.assertTrue(json.loads(await control_reader.readline())['muted'])
                self.assertTrue(json.loads(await reader.readline())['muted'])
                self.assertTrue(self.voice.muted)
                control_writer.close()
                await control_writer.wait_closed()
            finally:
                writer.close()
                await writer.wait_closed()
                await server.close()
