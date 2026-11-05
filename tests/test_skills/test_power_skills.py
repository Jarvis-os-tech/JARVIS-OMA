import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from skills import DesktopSkills, SkillError
from skills.system_power import POWER_MANAGER


class PowerSkillsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        POWER_MANAGER.clear_pending()
        self.skills = DesktopSkills()
        self.skills._run = AsyncMock(return_value="")

    async def asyncTearDown(self):
        POWER_MANAGER.clear_pending()

    async def test_shutdown_sequence_requires_confirmation(self):
        # 1. Unconfirmed shutdown request returns needs_confirmation
        res = await self.skills.execute("shutdown_system", {})
        self.assertEqual(res["status"], "needs_confirmation")
        self.assertEqual(res["action"], "shutdown")
        self.assertIn("shut down", res["prompt"])
        self.skills._run.assert_not_called()

        # Pending state is active
        self.assertIsNotNone(POWER_MANAGER.get_pending())
        self.assertEqual(POWER_MANAGER.get_pending()["action"], "shutdown")

        # 2. Confirm the pending shutdown
        with patch.object(self.skills, "_deferred_power_command", new=AsyncMock()) as mock_defer:
            confirm_res = await self.skills.execute("confirm_system_action", {"heard_phrase": "yes, confirm"})
            self.assertEqual(confirm_res["status"], "executing")
            self.assertEqual(confirm_res["action"], "shutdown")
            mock_defer.assert_called_once()
            args, _ = mock_defer.call_args
            self.assertIn("systemctl", args[0])
            self.assertEqual(args[1], "poweroff")

        # Pending state is cleared after confirmation
        self.assertIsNone(POWER_MANAGER.get_pending())

    async def test_restart_sequence_requires_confirmation(self):
        # 1. Unconfirmed restart request returns needs_confirmation
        res = await self.skills.execute("restart_system", {})
        self.assertEqual(res["status"], "needs_confirmation")
        self.assertEqual(res["action"], "restart")
        self.assertIn("restart", res["prompt"])
        self.skills._run.assert_not_called()

        # 2. Confirm the pending restart
        with patch.object(self.skills, "_deferred_power_command", new=AsyncMock()) as mock_defer:
            confirm_res = await self.skills.execute("confirm_system_action", {"heard_phrase": "proceed"})
            self.assertEqual(confirm_res["status"], "executing")
            self.assertEqual(confirm_res["action"], "restart")
            mock_defer.assert_called_once()
            args, _ = mock_defer.call_args
            self.assertIn("systemctl", args[0])
            self.assertEqual(args[1], "reboot")

        self.assertIsNone(POWER_MANAGER.get_pending())

    async def test_lock_screen_sequence(self):
        # 1. Unconfirmed lock screen returns needs_confirmation
        res = await self.skills.execute("lock_screen", {})
        self.assertEqual(res["status"], "needs_confirmation")
        self.assertEqual(res["action"], "lock_screen")
        self.skills._run.assert_not_called()

        # 2. Confirm the lock screen
        confirm_res = await self.skills.execute("confirm_system_action", {"heard_phrase": "do it"})
        self.assertEqual(confirm_res["status"], "locked")
        self.skills._run.assert_awaited_once_with(self.skills._commands["loginctl"], "lock-session")
        self.assertIsNone(POWER_MANAGER.get_pending())

    async def test_direct_confirmed_lock_screen(self):
        res = await self.skills.execute("lock_screen", {"confirm": True})
        self.assertEqual(res["status"], "locked")
        self.skills._run.assert_awaited_once_with(self.skills._commands["loginctl"], "lock-session")

    async def test_cancellation_sequence(self):
        await self.skills.execute("shutdown_system", {})
        self.assertIsNotNone(POWER_MANAGER.get_pending())

        cancel_res = await self.skills.execute("cancel_system_action", {})
        self.assertEqual(cancel_res["status"], "cancelled")
        self.assertEqual(cancel_res["action"], "shutdown")
        self.assertIsNone(POWER_MANAGER.get_pending())
        self.skills._run.assert_not_called()

    async def test_unrecognized_confirmation_leaves_pending(self):
        await self.skills.execute("restart_system", {})
        res = await self.skills.execute("confirm_system_action", {"heard_phrase": "what time is it"})
        self.assertEqual(res["status"], "error")
        self.assertIn("not a recognized confirmation", res["message"])
        self.assertIsNotNone(POWER_MANAGER.get_pending())
        self.skills._run.assert_not_called()
