import unittest
from unittest.mock import MagicMock, patch
from jarvis_control.config import Config
from jarvis_control.tools import Executor, Result, NeedsConfirmation


class SystemPowerControlTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(dry_run=True, allow_shell=True)
        self.executor = Executor(self.config)

    def test_shutdown_held_for_confirmation(self):
        # When calling system_power with shutdown, policy should hold it
        res = self.executor.call("system_power", {"action": "shutdown"})
        self.assertFalse(res.ok)
        self.assertIn("needs spoken confirmation", res.output)
        self.assertIsNotNone(self.executor.pending)
        self.assertEqual(self.executor.pending[0], "system_power")
        self.assertEqual(self.executor.pending[1], {"action": "shutdown"})

        # Confirming pending executes it
        confirm_res = self.executor.run_pending()
        self.assertTrue(confirm_res.ok)
        self.assertIsNone(self.executor.pending)

    def test_restart_held_for_confirmation(self):
        res = self.executor.call("system_power", {"action": "restart"})
        self.assertFalse(res.ok)
        self.assertIn("needs spoken confirmation", res.output)
        self.assertIsNotNone(self.executor.pending)

        confirm_res = self.executor.run_pending()
        self.assertTrue(confirm_res.ok)
        self.assertIsNone(self.executor.pending)

    def test_lock_screen_held_for_confirmation(self):
        res = self.executor.call("system_power", {"action": "lock_screen"})
        self.assertFalse(res.ok)
        self.assertIn("needs spoken confirmation", res.output)
        self.assertIsNotNone(self.executor.pending)

        # Cancellation drops it
        dropped = self.executor.drop_pending()
        self.assertEqual(dropped, "lock screen")
        self.assertIsNone(self.executor.pending)
