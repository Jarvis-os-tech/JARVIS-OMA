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
        self.orig_prod = jm.PRODUCTION_ROOT
        self.orig_test = jm.TEST_ROOT
        self.orig_dropin_dir = jm.DROPIN_DIR
        self.orig_dropin = jm.DROPIN

        jm.PRODUCTION_ROOT = self.tmp / "JARVIS-OMA"
        jm.TEST_ROOT = self.tmp / "JARVIS-OMA-dev"
        jm.DROPIN_DIR = self.tmp / "dropin.d"
        jm.DROPIN = jm.DROPIN_DIR / "mode.conf"
        jm.MODES = {
            "production": ("main", jm.PRODUCTION_ROOT),
            "test": ("dev", jm.TEST_ROOT),
        }

    def tearDown(self):
        jm.PRODUCTION_ROOT = self.orig_prod
        jm.TEST_ROOT = self.orig_test
        jm.DROPIN_DIR = self.orig_dropin_dir
        jm.DROPIN = self.orig_dropin
        jm.MODES = {
            "production": ("main", self.orig_prod),
            "test": ("dev", self.orig_test),
        }
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
        jm.PRODUCTION_ROOT.mkdir(parents=True)
        (jm.PRODUCTION_ROOT / ".git").mkdir()
        jm.TEST_ROOT.mkdir(parents=True)

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
        mock_result = {"status": "success", "mode": "test", "branch": "dev", "root": "/tmp/dev"}
        with patch("scripts.jarvis_mode.switch_mode", return_value=mock_result), \
             patch.object(skills, "_deferred_service_restart", new=AsyncMock()) as mock_restart:
            res = await skills.execute("switch_jarvis_mode", {"mode": "test", "sync": True})
            self.assertEqual(res["status"], "switching")
            self.assertEqual(res["target_mode"], "test")
            self.assertIn("Restarting JARVIS service in two seconds", res["message"])
            mock_restart.assert_called_once_with(delay=2.0)


if __name__ == "__main__":
    unittest.main()
