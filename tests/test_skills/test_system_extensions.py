"""Checked native controls: all mutations are mocked, never applied to desktop."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from skills import system_extensions as ext


class SystemExtensionsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.which = patch.object(ext.shutil, "which", side_effect=lambda name: "/bin/" + name)
        self.which.start()
        self.addCleanup(self.which.stop)

    async def test_missing_backend_is_unavailable(self):
        with patch.object(ext.shutil, "which", return_value=None):
            for category in ("audio_input", "user_service", "media"):
                result = await ext.system_control_extension(category, "list")
                self.assertEqual(result["status"], "unavailable")

    async def test_audio_default_verified_from_fresh_devices(self):
        devices = json.dumps([{"name": "alsa_output.usb", "index": 12}])
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            run.side_effect = [(0, devices, ""), (0, "old", ""), (0, "", ""), (0, "alsa_output.usb", "")]
            result = await ext.system_control_extension("audio_output", "set_default", "alsa_output.usb")
            self.assertTrue(result["verified"])
            self.assertEqual(result["status"], "success")
            run.assert_any_await("/bin/pactl", "set-default-sink", "alsa_output.usb")
            self.assertIn("observed_at", result)

    async def test_unknown_audio_target_is_not_executed(self):
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            run.side_effect = [(0, "[]", ""), (0, "old", "")]
            result = await ext.system_control_extension("audio_input", "set_default", "1; touch /tmp/no")
            self.assertEqual(result["status"], "error")
            self.assertEqual(run.await_count, 2)

    async def test_audio_failed_or_mismatching_readback_not_success(self):
        for readback in [(1, "", "no server"), (0, "old", "")]:
            with self.subTest(readback=readback):
                with patch.object(ext, "_run", new_callable=AsyncMock) as run:
                    run.side_effect = [(0, '[{"name":"microphone"}]', ""), (0, "old", ""), (0, "", ""), readback]
                    result = await ext.system_control_extension("audio_input", "set_default", "microphone")
                    self.assertNotEqual(result["status"], "success")
                    self.assertFalse(result["verified"])

    async def test_malformed_device_json_not_success(self):
        with patch.object(ext, "_run", new_callable=AsyncMock, return_value=(0, "{}", "")):
            result = await ext.system_control_extension("audio_input", "list")
            self.assertEqual(result["status"], "error")

    async def test_service_patterns_and_options_rejected_without_exec(self):
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            for target in ("*.service", "--all", "../foo.service", "foo.service; reboot", "foo", "-foo.service"):
                result = await ext.system_control_extension("user_service", "stop", target)
                self.assertEqual(result["status"], "error")
            run.assert_not_awaited()

    async def test_service_stop_user_scope_and_readback(self):
        initial = "Id=demo.service\nLoadState=loaded\nActiveState=active\nSubState=running"
        final = initial.replace("active", "inactive").replace("running", "dead")
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            run.side_effect = [(0, initial, ""), (0, "", ""), (0, final, "")]
            result = await ext.system_control_extension("user_service", "stop", "demo.service")
            self.assertTrue(result["verified"])
            run.assert_any_await("/bin/systemctl", "--user", "stop", "--", "demo.service")

    async def test_service_unknown_or_alias_prevents_mutation(self):
        for state in ("Id=demo.service\nLoadState=not-found", "Id=canonical.service\nLoadState=loaded"):
            with patch.object(ext, "_run", new_callable=AsyncMock, return_value=(0, state, "")) as run:
                result = await ext.system_control_extension("user_service", "restart", "demo.service")
                self.assertEqual(result["status"], "error")
                self.assertEqual(run.await_count, 1)

    async def test_service_command_failure_propagates(self):
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            run.side_effect = [(0, "Id=demo.service\nLoadState=loaded", ""), (1, "", "denied")]
            result = await ext.system_control_extension("user_service", "start", "demo.service")
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["message"], "denied")

    async def test_media_ambiguous_target_does_not_control_all_players(self):
        with patch.object(ext, "_run", new_callable=AsyncMock, return_value=(0, "mpv\nfirefox", "")) as run:
            result = await ext.system_control_extension("media", "pause")
            self.assertEqual(result["status"], "error")
            self.assertEqual(run.await_count, 1)

    async def test_media_pause_verifies_but_track_change_does_not(self):
        for action, state, expected in (("pause", "Paused", "success"), ("next", "Playing", "dispatched_unverified")):
            with patch.object(ext, "_run", new_callable=AsyncMock) as run:
                run.side_effect = [(0, "mpv", ""), (0, "", ""), (0, state, "")]
                result = await ext.system_control_extension("media", action, "mpv")
                self.assertEqual(result["status"], expected)
                run.assert_any_await("/bin/playerctl", "--player=mpv", action)

    async def test_invalid_actions_never_execute(self):
        with patch.object(ext, "_run", new_callable=AsyncMock) as run:
            for category in ("audio_input", "user_service", "media", "shell"):
                result = await ext.system_control_extension(category, "reboot")
                self.assertEqual(result["status"], "error")
            run.assert_not_awaited()


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_drains_and_rejects_oversized_output(self):
        import sys
        code, out, err = await ext._run(sys.executable, "-c", "print('x'*100000)")
        self.assertEqual(code, -1)
        self.assertEqual(out, "")
        self.assertIn("limit", err)

    async def test_runner_timeout_kills_and_reaps(self):
        import sys
        with patch.object(ext, "_TIMEOUT", .05):
            code, _, err = await ext._run(sys.executable, "-c", "import time;time.sleep(30)")
        self.assertEqual(code, -1)
        self.assertIn("timed out", err)

    async def test_runner_cancellation_reaps_child(self):
        import sys
        original = asyncio.create_subprocess_exec
        processes = []

        async def capture(*args, **kwargs):
            proc = await original(*args, **kwargs)
            processes.append(proc)
            return proc

        with patch.object(asyncio, "create_subprocess_exec", side_effect=capture):
            task = asyncio.create_task(ext._run(sys.executable, "-c", "import time;time.sleep(30)"))
            while not processes:
                await asyncio.sleep(.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(processes[0].returncode)
