"""Tests for desktop modal detection, safe dialog handling, and focus self-healing."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from skills import modal_healing, system_control
from skills.modal_healing import DialogType, DesktopDialog
from skills.skills import DesktopSkills


class ModalHealingUnitTests(unittest.IsolatedAsyncioTestCase):
    def test_classify_auth_prompts(self):
        # Class match
        polkit_win = {
            "address": "0x123",
            "class": "polkit-gnome-authentication-agent-1",
            "title": "Authenticate",
            "floating": True,
        }
        dlg = modal_healing.classify_dialog(polkit_win)
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.dialog_type, DialogType.AUTH_PROMPT)
        self.assertTrue(dlg.requires_user_auth)
        self.assertFalse(dlg.safe_to_dismiss)

        # Title match
        title_auth = {
            "address": "0x124",
            "class": "custom-dialog",
            "title": "Authentication Required to Mount Drive",
            "floating": True,
        }
        dlg2 = modal_healing.classify_dialog(title_auth)
        self.assertIsNotNone(dlg2)
        self.assertEqual(dlg2.dialog_type, DialogType.AUTH_PROMPT)
        self.assertTrue(dlg2.requires_user_auth)

        # Pinentry
        pinentry_win = {
            "address": "0x125",
            "class": "pinentry-gtk-2",
            "title": "Pinentry",
            "floating": True,
        }
        dlg3 = modal_healing.classify_dialog(pinentry_win)
        self.assertIsNotNone(dlg3)
        self.assertEqual(dlg3.dialog_type, DialogType.AUTH_PROMPT)

    def test_classify_file_prompts(self):
        overwrite_win = {
            "address": "0x201",
            "class": "gedit",
            "title": "A file named 'output.txt' already exists. Do you want to replace it?",
            "floating": True,
        }
        dlg = modal_healing.classify_dialog(overwrite_win)
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.dialog_type, DialogType.FILE_OVERWRITE)
        self.assertFalse(dlg.requires_user_auth)
        self.assertTrue(dlg.safe_to_dismiss)
        self.assertIn("confirm", dlg.suggested_actions)

    def test_classify_confirmation_and_alerts(self):
        conf_win = {
            "address": "0x301",
            "class": "libreoffice",
            "title": "Unsaved changes: Save before closing?",
            "floating": True,
        }
        dlg = modal_healing.classify_dialog(conf_win)
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.dialog_type, DialogType.CONFIRMATION)

        alert_win = {
            "address": "0x302",
            "class": "app",
            "title": "Critical Error: connection dropped",
            "floating": True,
        }
        dlg2 = modal_healing.classify_dialog(alert_win)
        self.assertIsNotNone(dlg2)
        self.assertEqual(dlg2.dialog_type, DialogType.ALERT)

        zenity_win = {
            "address": "0x303",
            "class": "zenity",
            "title": "Choose options",
            "floating": False,
        }
        dlg3 = modal_healing.classify_dialog(zenity_win)
        self.assertIsNotNone(dlg3)
        self.assertEqual(dlg3.dialog_type, DialogType.GENERIC_MODAL)

    def test_classify_normal_windows(self):
        normal_win = {
            "address": "0x401",
            "class": "antigravity",
            "title": "Antigravity - main.py",
            "floating": False,
        }
        self.assertIsNone(modal_healing.classify_dialog(normal_win))

        terminal_win = {
            "address": "0x402",
            "class": "foot",
            "title": "foot terminal",
            "floating": False,
        }
        self.assertIsNone(modal_healing.classify_dialog(terminal_win))

    @patch("skills.modal_healing._query_clients")
    async def test_detect_desktop_dialogs(self, mock_clients):
        mock_clients.return_value = [
            {"address": "0x1", "class": "foot", "title": "term", "floating": False},
            {"address": "0x2", "class": "polkit-gnome-authentication-agent-1", "title": "Authenticate", "floating": True},
            {"address": "0x3", "class": "zenity", "title": "Progress", "floating": True},
        ]
        dialogs = await modal_healing.detect_desktop_dialogs()
        self.assertEqual(len(dialogs), 2)
        types = [d["dialog_type"] for d in dialogs]
        self.assertIn("auth_prompt", types)
        self.assertIn("generic_modal", types)

    @patch("shutil.which")
    @patch("skills.modal_healing._query_clients")
    @patch("skills.modal_healing._query_active_window")
    @patch("skills.modal_healing._run_command", new_callable=AsyncMock)
    async def test_handle_dialog_security_blocks_auth_confirm(self, mock_run, mock_active, mock_clients, mock_which):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        auth_win = {
            "address": "0xauth1",
            "class": "polkit-gnome-authentication-agent-1",
            "title": "Authenticate",
            "floating": True,
        }
        mock_clients.return_value = [auth_win]
        mock_active.return_value = auth_win

        res = await modal_healing.handle_desktop_dialog(action="confirm")
        self.assertEqual(res["status"], "blocked_by_security")
        self.assertIn("strictly blocked for security", res["message"])
        # Ensure wtype was NOT invoked to press Return
        for call_args in mock_run.call_args_list:
            self.assertNotIn("Return", call_args[0])

    @patch("shutil.which")
    @patch("skills.modal_healing._query_clients")
    @patch("skills.modal_healing._query_active_window")
    @patch("skills.modal_healing._run_command", new_callable=AsyncMock)
    async def test_handle_dialog_allows_dismiss_and_cancel(self, mock_run, mock_active, mock_clients, mock_which):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_run.return_value = (0, "", "")
        file_win = {
            "address": "0xfile1",
            "class": "gedit",
            "title": "Confirm save: file already exists",
            "floating": True,
        }
        mock_clients.side_effect = [[file_win], []]
        mock_active.side_effect = [file_win, None]

        res = await modal_healing.handle_desktop_dialog(action="dismiss")
        self.assertEqual(res["status"], "handled")
        self.assertEqual(res["action"], "dismiss")
        # Ensure Escape was sent via wtype
        mock_run.assert_any_await("/usr/bin/wtype", "-k", "Escape", timeout=2)

    @patch("shutil.which")
    @patch("skills.modal_healing._query_clients")
    @patch("skills.modal_healing._query_active_window")
    @patch("skills.modal_healing._run_command", new_callable=AsyncMock)
    async def test_heal_window_focus(self, mock_run, mock_active, mock_clients, mock_which):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_run.return_value = (0, "", "")

        antigravity_win = {"address": "0xanti", "class": "antigravity", "title": "Antigravity IDE"}
        stolen_win = {"address": "0xstolen", "class": "dunst", "title": "Notification Popup"}

        mock_clients.return_value = [antigravity_win, stolen_win]
        # Initially active window is stolen_win, after heal it becomes antigravity_win
        mock_active.side_effect = [stolen_win, antigravity_win]

        res = await modal_healing.heal_window_focus("antigravity")
        self.assertEqual(res["status"], "healed")
        self.assertTrue(res["was_stolen"])
        self.assertTrue(res["recovered"])
        self.assertEqual(res["stolen_by"]["class"], "dunst")


class DesktopSkillsModalHealingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.skills = DesktopSkills()

    def test_manifest_declares_modal_healing_skills(self):
        self.assertIn("detect_desktop_dialogs", self.skills._skills)
        self.assertIn("handle_desktop_dialog", self.skills._skills)
        self.assertIn("heal_window_focus", self.skills._skills)

    @patch("skills.system_control.detect_desktop_dialogs", new_callable=AsyncMock)
    async def test_execute_detect_desktop_dialogs(self, mock_detect):
        mock_detect.return_value = [
            {"address": "0x1", "title": "File exists", "class": "app", "dialog_type": "file_overwrite"}
        ]
        res = await self.skills.execute("detect_desktop_dialogs", {})
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["dialogs"][0]["dialog_type"], "file_overwrite")

    @patch("skills.system_control.handle_desktop_dialog", new_callable=AsyncMock)
    async def test_execute_handle_desktop_dialog(self, mock_handle):
        mock_handle.return_value = {"status": "handled", "action": "dismiss", "remaining_dialogs": 0}
        res = await self.skills.execute("handle_desktop_dialog", {"action": "dismiss"})
        self.assertEqual(res["status"], "handled")
        mock_handle.assert_awaited_once_with("dismiss", dialog_id=None)

    @patch("skills.system_control.heal_window_focus", new_callable=AsyncMock)
    async def test_execute_heal_window_focus(self, mock_heal):
        mock_heal.return_value = {"status": "healed", "was_stolen": True, "recovered": True}
        res = await self.skills.execute("heal_window_focus", {"target_window": "antigravity"})
        self.assertEqual(res["status"], "healed")
        mock_heal.assert_awaited_once_with("antigravity")
