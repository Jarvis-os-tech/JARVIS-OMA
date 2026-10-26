"""Regression coverage for explicit, idempotent mute controls over IPC."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ipc import JarvisIPCServer
from scripts import jarvisctl


class TestExplicitMute(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.socket_path = Path(self.temp_dir.name) / "jarvis.sock"
        self.muted = False
        self.toggle_calls = 0
        self.server = JarvisIPCServer(
            socket_path=self.socket_path,
            status_provider=lambda: {"muted": self.muted, "state": "idle"},
            toggle_mute_cb=self._toggle_mute,
        )
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.close()
        self.temp_dir.cleanup()

    def _toggle_mute(self):
        self.toggle_calls += 1
        self.muted = not self.muted
        return self.muted

    async def _send(self, payload):
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
        try:
            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await writer.drain()
            return json.loads((await reader.readline()).decode("utf-8"))
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_set_mute_is_idempotent_and_toggle_still_toggles(self):
        first = await self._send({"command": "set_mute", "muted": True})
        again = await self._send({"command": "set_mute", "muted": True})
        self.assertEqual(first, {"status": "ok", "muted": True})
        self.assertEqual(again, {"status": "ok", "muted": True})
        self.assertTrue(self.muted)
        self.assertEqual(self.toggle_calls, 1)

        toggled = await self._send({"command": "toggle_mute"})
        self.assertEqual(toggled, {"status": "ok", "muted": False})
        self.assertFalse(self.muted)
        self.assertEqual(self.toggle_calls, 2)

    async def test_cli_mute_and_unmute_are_repeatable(self):
        with patch("sys.stdout"):
            for _ in range(2):
                self.assertEqual(await jarvisctl.run_async([
                    "--socket", str(self.socket_path), "mute",
                ]), 0)
                self.assertTrue(self.muted)
            self.assertEqual(self.toggle_calls, 1)

            for _ in range(2):
                self.assertEqual(await jarvisctl.run_async([
                    "--socket", str(self.socket_path), "unmute",
                ]), 0)
                self.assertFalse(self.muted)
            self.assertEqual(self.toggle_calls, 2)

    async def test_set_mute_rejects_missing_or_non_boolean_values(self):
        invalid_requests = [
            {"command": "set_mute"},
            {"command": "set_mute", "muted": "true"},
            {"command": "set_mute", "muted": 1},
            {"command": "set_mute", "muted": None},
        ]
        for request in invalid_requests:
            with self.subTest(request=request):
                response = await self._send(request)
                self.assertEqual(response["status"], "error")
                self.assertIn("boolean", response["error"])

        self.assertFalse(self.muted)
        self.assertEqual(self.toggle_calls, 0)

    async def test_set_mute_can_use_explicit_set_callback(self):
        calls = []

        def set_mute(value):
            calls.append(value)
            self.muted = value
            return self.muted

        self.server.set_mute_cb = set_mute
        response = await self._send({"command": "set_mute", "muted": True})
        self.assertEqual(response, {"status": "ok", "muted": True})
        self.assertEqual(calls, [True])
        self.assertEqual(self.toggle_calls, 0)


if __name__ == "__main__":
    unittest.main()
