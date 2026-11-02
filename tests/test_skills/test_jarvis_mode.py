import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from skills import DesktopSkills
import scripts.jarvis_mode as jm


class JarvisModeUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.patches = []
        for name, value in {
            "PRODUCTION_ROOT": self.tmp / "runtime/current",
            "TEST_ROOT": self.tmp / "JARVIS OS",
            "DROPIN_DIR": self.tmp / "voice.d",
            "DROPIN": self.tmp / "voice.d/mode.conf",
            "BRIDGE_DROPIN_DIR": self.tmp / "bridge.d",
            "BRIDGE_DROPIN": self.tmp / "bridge.d/mode.conf",
            "SHARE_VOICE": self.tmp / "share-voice",
            "BIN_DIR": self.tmp / "bin",
            "LOCK_FILE": self.tmp / "mode.lock",
        }.items():
            item = patch.object(jm, name, value)
            item.start()
            self.patches.append(item)
        self.mode_patch = patch.object(jm, "MODES", {
            "production": ("main", jm.PRODUCTION_ROOT), "test": ("dev", jm.TEST_ROOT)})
        self.mode_patch.start()
        self.service_patch = patch.object(jm, "_service_state", return_value={"ActiveState": "inactive"})
        self.service_patch.start()
        self.patches.append(self.service_patch)
        for root in (jm.PRODUCTION_ROOT, jm.TEST_ROOT):
            (root / "bin").mkdir(parents=True)
            (root / "bin/jarvis-voice").touch()
            (root / "jarvis_voice").mkdir()
        for python in (jm.TEST_ROOT / ".venv/bin/python", jm.PRODUCTION_ROOT.parent / "venv/bin/python"):
            python.parent.mkdir(parents=True)
            python.touch()

    def tearDown(self):
        self.mode_patch.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def test_current_mode_defaults_to_production(self):
        res = jm.current_mode()
        self.assertEqual(res["mode"], "production")
        self.assertEqual(res["branch"], "main")
        self.assertEqual(res["root"], str(jm.PRODUCTION_ROOT))

    def test_current_mode_detects_test_dropin(self):
        jm.DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        jm.DROPIN.write_text(f"[Service]\nWorkingDirectory={jm.TEST_ROOT}\n")
        res = jm.current_mode()
        self.assertEqual(res["mode"], "test")
        self.assertEqual(res["branch"], "dev")
        self.assertEqual(res["root"], str(jm.TEST_ROOT))

    @patch("scripts.jarvis_mode.subprocess.run")
    def test_switch_mode_to_test_creates_dropin(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="dev\n", stderr="")
        jm.PRODUCTION_ROOT.mkdir(parents=True, exist_ok=True)
        (jm.PRODUCTION_ROOT / ".git").mkdir()
        jm.TEST_ROOT.mkdir(parents=True, exist_ok=True)

        res = jm.switch_mode("test", sync=False, restart=False)
        self.assertEqual(res["mode"], "test")
        self.assertEqual(res["branch"], "dev")
        self.assertTrue(jm.DROPIN.exists())
        content = jm.DROPIN.read_text()
        self.assertIn(str(jm.TEST_ROOT), content)
        self.assertIn("WorkingDirectory=", content)

    @patch("scripts.jarvis_mode.subprocess.run")
    def test_switch_mode_to_production_removes_dropin(self, mock_run):
        jm.DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        jm.DROPIN.write_text("dummy")

        res = jm.switch_mode("production", sync=False, restart=False)
        self.assertEqual(res["mode"], "production")
        self.assertEqual(res["branch"], "main")
        self.assertFalse(jm.DROPIN.exists())


class JarvisModeSkillIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def test_mode_skills_registered(self):
        skills = DesktopSkills()
        names = {s["name"] for s in skills.declarations}
        self.assertIn("switch_jarvis_mode", names)
        self.assertIn("get_jarvis_mode", names)
        self.assertIn("sync_jarvis_branch", names)

    async def test_get_jarvis_mode_execution(self):
        skills = DesktopSkills()
        with patch("scripts.jarvis_mode.current_mode", return_value={"mode": "production", "branch": "main"}):
            res = await skills.execute("get_jarvis_mode", {})
            self.assertEqual(res["mode"], "production")
            self.assertEqual(res["branch"], "main")

    async def test_switch_jarvis_mode_execution_schedules_deferred_restart(self):
        skills = DesktopSkills()
        mock_result = {"status": "switching", "target_mode": "test", "root": "/tmp/dev",
                       "message": "Restarting JARVIS service in two seconds"}
        with patch("scripts.jarvis_mode.schedule_mode_switch", return_value=mock_result) as schedule:
            res = await skills.execute("switch_jarvis_mode", {"mode": "test", "sync": True})
            self.assertEqual(res["status"], "switching")
            self.assertEqual(res["target_mode"], "test")
            schedule.assert_called_once_with("test")

    async def test_deferred_restart_uses_existing_function(self):
        skills = DesktopSkills()
        with patch("scripts.jarvis_mode.restart_services", return_value=True) as restart:
            await skills._deferred_service_restart(delay=0)
            restart.assert_called_once()


if __name__ == "__main__":
    unittest.main()
