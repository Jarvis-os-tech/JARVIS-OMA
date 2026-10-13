import os
import tempfile
import unittest
from pathlib import Path

from proactive.control import AutonomyControl


class AutonomyControlTests(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.tmp_path = Path(self._temporary_directory.name)

    def test_starts_enabled_and_state_persists_across_controller_instances(self):
        path = self.tmp_path / "private" / "controls.sqlite3"
        controller = AutonomyControl(path, clock=lambda: 100.0)

        initial = controller.get_state()
        self.assertTrue(initial.can_run)
        self.assertFalse(initial.paused)
        self.assertFalse(initial.stop_all)
        self.assertEqual(initial.revision, 0)

        paused = controller.pause()
        reopened = AutonomyControl(path, clock=lambda: 200.0)
        self.assertEqual(reopened.get_state(), paused)
        self.assertTrue(paused.paused)
        self.assertFalse(paused.can_run)
        self.assertEqual(paused.revision, 1)

    def test_pause_resume_and_stop_all_are_idempotent(self):
        control = AutonomyControl(self.tmp_path / "control.sqlite3", clock=lambda: 42.0)

        first_pause = control.pause()
        self.assertEqual(control.pause(), first_pause)
        self.assertEqual(first_pause.revision, 1)

        first_stop = control.stop_all()
        self.assertTrue(first_stop.stop_all)
        self.assertFalse(first_stop.can_run)
        self.assertEqual(control.stop_all(), first_stop)
        self.assertEqual(first_stop.revision, 2)

        resumed = control.resume()
        self.assertTrue(resumed.can_run)
        self.assertFalse(resumed.paused)
        self.assertFalse(resumed.stop_all)
        self.assertEqual(resumed.revision, 3)
        self.assertEqual(control.resume(), resumed)

    def test_pause_preserves_stop_all_and_resume_clears_both(self):
        control = AutonomyControl(self.tmp_path / "control.sqlite3")

        stopped = control.stop_all()
        paused = control.pause()
        self.assertTrue(paused.stop_all)
        self.assertTrue(paused.paused)
        self.assertEqual(paused.revision, stopped.revision + 1)

        resumed = control.resume()
        self.assertTrue(resumed.can_run)
        self.assertEqual(resumed.revision, paused.revision + 1)

    @unittest.skipUnless(os.name == "posix", "POSIX file mode assertions")
    def test_database_and_new_parent_directory_are_private(self):
        path = self.tmp_path / "private" / "controls.sqlite3"
        AutonomyControl(path)

        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
