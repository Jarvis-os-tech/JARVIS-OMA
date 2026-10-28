"""Unit tests for JarvisIPCServer mode-0600 UNIX domain socket control plane."""
import asyncio
import json
import os
import stat
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from core.ipc import JarvisIPCServer, default_socket_path


class TestJarvisIPCServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.socket_path = Path(self.temp_dir.name) / "test_jarvis.sock"

        self.muted = False
        self.interrupted = False
        self.status_data = {
            "state": "idle",
            "muted": False,
            "active_jobs": 0,
            "model": "gemini-2.0-flash-exp",
        }

        def status_provider():
            return {**self.status_data, "muted": self.muted}

        def toggle_mute_cb():
            self.muted = not self.muted
            return self.muted

        def interrupt_cb():
            self.interrupted = True

        self.server = JarvisIPCServer(
            socket_path=self.socket_path,
            status_provider=status_provider,
            toggle_mute_cb=toggle_mute_cb,
            interrupt_cb=interrupt_cb,
        )
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.close()
        self.temp_dir.cleanup()

    async def _send_command(self, cmd_dict: dict) -> dict:
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
        try:
            req = json.dumps(cmd_dict) + "\n"
            writer.write(req.encode("utf-8"))
            await writer.drain()
            line = await reader.readline()
            return json.loads(line.decode("utf-8").strip())
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_socket_permissions_mode_0600(self):
        self.assertTrue(self.socket_path.exists())
        file_stat = os.stat(self.socket_path)
        mode = stat.S_IMODE(file_stat.st_mode)
        self.assertEqual(mode, 0o600, f"Expected socket permissions 0600, got {oct(mode)}")

    async def test_command_status(self):
        resp = await self._send_command({"command": "status"})
        self.assertEqual(resp.get("status"), "ok")
        self.assertEqual(resp.get("state"), "idle")
        self.assertFalse(resp.get("muted"))
        self.assertEqual(resp.get("model"), "gemini-2.0-flash-exp")

    async def test_fixed_voice_diagnostic_requires_callback(self):
        self.assertEqual((await self._send_command({'command': 'test_voice'}))['status'], 'unavailable')
        calls = []
        self.server.test_voice_cb = lambda: calls.append(True) or {'status': 'queued'}
        self.assertEqual((await self._send_command({'command': 'test_voice'}))['status'], 'queued')
        self.assertEqual(calls, [True])

    async def test_command_toggle_mute(self):
        resp1 = await self._send_command({"command": "toggle_mute"})
        self.assertEqual(resp1.get("status"), "ok")
        self.assertTrue(resp1.get("muted"))
        self.assertTrue(self.muted)

        resp2 = await self._send_command({"command": "toggle_mute"})
        self.assertEqual(resp2.get("status"), "ok")
        self.assertFalse(resp2.get("muted"))
        self.assertFalse(self.muted)

    async def test_command_interrupt(self):
        self.assertFalse(self.interrupted)
        resp = await self._send_command({"command": "interrupt"})
        self.assertEqual(resp.get("status"), "ok")
        self.assertTrue(resp.get("interrupted"))
        self.assertTrue(self.interrupted)

    async def test_explicit_mute_is_idempotent(self):
        calls = []
        def set_muted(value):
            calls.append(value)
            self.muted = value
            return value
        self.server.set_mute_cb = set_muted
        for value in (True, True, False, False):
            response = await self._send_command({"command": "set_mute", "muted": value})
            self.assertEqual(response, {"status": "ok", "muted": value})
            self.assertEqual(self.muted, value)
        self.assertEqual(calls, [True, True, False, False])

    async def test_explicit_mute_rejects_invalid_values(self):
        for value in (None, "false", 0, 1):
            response = await self._send_command({"command": "set_mute", "muted": value})
            self.assertEqual(response["status"], "error")
        self.assertFalse(self.muted)

    async def test_explicit_mute_without_callback_reports_unavailable(self):
        response = await self._send_command({"command": "set_mute", "muted": False})
        self.assertEqual(response["status"], "unavailable")

    async def test_unknown_command(self):
        resp = await self._send_command({"command": "unknown_xyz"})
        self.assertEqual(resp.get("status"), "error")
        self.assertIn("Unknown command", resp.get("error", ""))

    async def test_subscribe_and_broadcast(self):
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
        try:
            writer.write((json.dumps({"command": "subscribe"}) + "\n").encode("utf-8"))
            await writer.drain()

            # First message should be the initial state event
            init_line = await reader.readline()
            init_event = json.loads(init_line.decode("utf-8").strip())
            self.assertEqual(init_event.get("event"), "state_change")
            self.assertEqual(init_event.get("state"), "idle")

            # Now broadcast state change from server
            self.server.broadcast_state({"state": "speaking", "muted": False})

            # Subscriber should receive the broadcast event
            bc_line = await reader.readline()
            bc_event = json.loads(bc_line.decode("utf-8").strip())
            self.assertEqual(bc_event.get("event"), "state_change")
            self.assertEqual(bc_event.get("state"), "speaking")
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_default_socket_path_xdg_runtime_dir(self):
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"}):
            path = default_socket_path()
            self.assertEqual(path, Path("/run/user/1000/jarvis.sock"))

    async def test_agent_run_ipc_server_lifecycle(self):
        from agent import run
        from types import SimpleNamespace as NS

        socket_path = Path(self.temp_dir.name) / "agent_test.sock"
        engines = []

        class MockEngine:
            def __init__(self, *args, **kwargs):
                self.muted = False
                self.state = "idle"
                self.output_frame_bytes = 960
                self.async_input_queue = asyncio.Queue()
                self.c_output_queue = __import__('queue').SimpleQueue()
                self.on_state_change = None
                self.mute_changes = []
                engines.append(self)

            def start(self, source, sink):
                pass

            def handle_barge_in(self):
                pass

            def set_muted(self, state):
                self.mute_changes.append(state)
                self.muted = state

            def set_reconnect_buffering(self, enabled: bool):
                pass

            async def stop_speaking(self):
                pass

            async def monitor_health(self):
                await asyncio.sleep(999999)

            def terminate(self):
                pass

        class MockLiveSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        class MockLive:
            def connect(self, *args, **kwargs):
                return MockLiveSession()

        class MockClientAio:
            def __init__(self):
                self.live = MockLive()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        class MockClient:
            def __init__(self, *args, **kwargs):
                self.aio = MockClientAio()

        class Echo:
            sink = 'test-sink'
            source = 'test-source'

            async def start(self, microphone, *args, **kwargs):
                pass

            async def close(self):
                pass

        async def mock_supervise(*workers):
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write((json.dumps({"command": "status"}) + "\n").encode("utf-8"))
            await writer.drain()
            resp = json.loads((await reader.readline()).decode("utf-8").strip())
            writer.close()
            await writer.wait_closed()
            self.assertEqual(resp.get("status"), "ok")
            self.assertEqual(resp.get("model"), "test-model")
            for requested in (False, False, True, True, False):
                reader, writer = await asyncio.open_unix_connection(str(socket_path))
                writer.write((json.dumps({"command": "set_mute", "muted": requested}) + "\n").encode())
                await writer.drain()
                response = json.loads(await reader.readline())
                writer.close()
                await writer.wait_closed()
                self.assertEqual(response, {"status": "ok", "muted": requested})
            # Repeated explicit commands must not flush active playback again.
            self.assertEqual(engines[0].mute_changes, [True, False])
            for w in workers:
                w.close()
            raise asyncio.CancelledError()

        async def no_wait(d):
            pass

        args = NS(model='test-model', voice='Aoede', transcripts=False,
                  microphone=None, retries=2, no_skills=True, socket=str(socket_path), no_ipc=False)
        with patch('google.genai.Client', MockClient), \
             patch('agent.EchoCancellation', return_value=Echo()), \
             patch('agent.NativeAudioEngine', MockEngine), \
             patch('agent.supervise', side_effect=mock_supervise), \
             patch('agent.asyncio.sleep', side_effect=no_wait):
            from config import Config
            configuration = Config()
            configuration.audio.backend = 'legacy'  # This fixture replaces NativeAudioEngine.
            configuration.agent.model = 'test-model'
            with self.assertRaises(asyncio.CancelledError):
                await run(args, 'fake-key', config=configuration)

        self.assertFalse(socket_path.exists())


if __name__ == "__main__":
    unittest.main()
