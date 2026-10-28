"""Unit tests for jarvisctl CLI client."""
import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

from scripts import jarvisctl


class TestJarvisCtl(unittest.IsolatedAsyncioTestCase):
    async def test_unmute_rejection_returns_failure(self):
        with patch.object(jarvisctl, "send_command", new_callable=AsyncMock,
                          return_value={"status": "error", "error": "Unknown command: set_mute"}), \
             patch("sys.stderr", new=io.StringIO()) as output:
            code = await jarvisctl.run_async(["unmute"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown command", output.getvalue())

    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.socket_path = Path(self.temp_dir.name) / "test_jarvisctl.sock"
        self.muted = False
        self.interrupted = False
        self.server = None

    async def asyncTearDown(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.temp_dir.cleanup()

    async def _start_mock_server(self):
        async def handle_client(reader, writer):
            try:
                line = await reader.readline()
                if not line:
                    return
                req = json.loads(line.decode("utf-8").strip())
                cmd = req.get("command")
                if cmd == "status":
                    resp = {
                        "status": "ok",
                        "state": "idle",
                        "muted": self.muted,
                        "model": "gemini-3.8-live",
                        "active_jobs": 0,
                    }
                    writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                    await writer.drain()
                elif cmd == "toggle_mute":
                    self.muted = not self.muted
                    resp = {"status": "ok", "muted": self.muted}
                    writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                    await writer.drain()
                elif cmd == "interrupt":
                    self.interrupted = True
                    resp = {"status": "ok", "interrupted": True}
                    writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                    await writer.drain()
                elif cmd == "subscribe":
                    writer.write((json.dumps({"event": "state_change", "state": "idle", "muted": self.muted}) + "\n").encode("utf-8"))
                    await writer.drain()
                    # write one more event and close
                    await asyncio.sleep(0.02)
                    writer.write((json.dumps({"event": "state_change", "state": "speaking", "muted": self.muted}) + "\n").encode("utf-8"))
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        self.server = await asyncio.start_unix_server(handle_client, path=str(self.socket_path))

    async def test_status_json_output(self):
        await self._start_mock_server()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = await jarvisctl.run_async(["--socket", str(self.socket_path), "status", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue().strip())
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("state"), "idle")
            self.assertFalse(data.get("muted"))

    async def test_status_human_output(self):
        await self._start_mock_server()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = await jarvisctl.run_async(["--socket", str(self.socket_path), "status"])
            self.assertEqual(code, 0)
            output = fake_out.getvalue()
            self.assertIn("State:", output)
            self.assertIn("idle", output)
            self.assertIn("Muted:", output)

    async def test_toggle(self):
        await self._start_mock_server()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = await jarvisctl.run_async(["--socket", str(self.socket_path), "toggle"])
            self.assertEqual(code, 0)
            self.assertTrue(self.muted)
            self.assertIn("Muted: True", fake_out.getvalue())

    async def test_interrupt(self):
        await self._start_mock_server()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = await jarvisctl.run_async(["--socket", str(self.socket_path), "interrupt"])
            self.assertEqual(code, 0)
            self.assertTrue(self.interrupted)
            self.assertIn("Interrupted", fake_out.getvalue())

    async def test_subscribe_stream(self):
        await self._start_mock_server()
        events = []
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            # Run subscribe with max_events=2 to terminate test
            code = await jarvisctl.run_async(["--socket", str(self.socket_path), "subscribe", "--max-events", "2"])
            self.assertEqual(code, 0)
            lines = [line for line in fake_out.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            event1 = json.loads(lines[0])
            event2 = json.loads(lines[1])
            self.assertEqual(event1.get("state"), "idle")
            self.assertEqual(event2.get("state"), "speaking")

    async def test_daemon_not_running_error(self):
        missing_sock = Path(self.temp_dir.name) / "missing.sock"
        with patch("sys.stderr", new=io.StringIO()) as fake_err:
            code = await jarvisctl.run_async(["--socket", str(missing_sock), "status"])
            self.assertNotEqual(code, 0)
            self.assertIn("daemon not running", fake_err.getvalue().lower())

    async def test_start_and_stop_service(self):
        systemctl_calls = []

        def mock_run(cmd, *args, **kwargs):
            systemctl_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="ok", stderr="")

        with patch("subprocess.run", side_effect=mock_run):
            code1 = await jarvisctl.run_async(["start"])
            self.assertEqual(code1, 0)
            self.assertIn(["systemctl", "--user", "start", "jarvis-oma.service"], systemctl_calls)

            code2 = await jarvisctl.run_async(["stop"])
            self.assertEqual(code2, 0)
            self.assertIn(["systemctl", "--user", "stop", "jarvis-oma.service"], systemctl_calls)


if __name__ == "__main__":
    unittest.main()
