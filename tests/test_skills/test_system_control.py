"""Tests for native Omarchy desktop and system control skills."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import system_control
from skills.skills import DesktopSkills


class SystemControlUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_type_text_empty(self):
        res = await system_control.type_text("")
        self.assertEqual(res["status"], "error")

    @patch("shutil.which", return_value=None)
    async def test_type_text_missing_wtype(self, _which):
        res = await system_control.type_text("hello")
        self.assertEqual(res["status"], "error")
        self.assertIn("wtype is not installed", res["message"])

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_single_line(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.type_text("hello world")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["method"], "typed")
        mock_run.assert_awaited_once_with("/usr/bin/wtype", "--", "hello world")

    @patch("shutil.which")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_multi_line_terminal(self, mock_run, mock_which):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_run.side_effect = [
            (0, json.dumps({"class": "foot"}), ""),
            (0, "", ""),
        ]
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc_mock = AsyncMock()
            proc_mock.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = proc_mock

            res = await system_control.type_text("line 1\nline 2")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["method"], "clipboard_paste")
            mock_run.assert_any_await("/usr/bin/wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl")

    async def test_press_key_empty(self):
        res = await system_control.press_key("")
        self.assertEqual(res["status"], "error")

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_press_key_modifiers_string_and_list(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.press_key("Return", modifiers="super+shift")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["modifiers"], ["logo", "shift"])
        mock_run.assert_awaited_once_with("/usr/bin/wtype", "-M", "logo", "-M", "shift", "-k", "Return", "-m", "shift", "-m", "logo")

        mock_run.reset_mock()
        res_list = await system_control.press_key("Return", modifiers=["super", "shift"])
        self.assertEqual(res_list["status"], "success")
        self.assertEqual(res_list["modifiers"], ["logo", "shift"])

    @patch("shutil.which", return_value="/usr/bin/wtype")
    async def test_press_key_unknown_modifier(self, _which):
        res = await system_control.press_key("Return", modifiers=["invalid_mod"])
        self.assertEqual(res["status"], "error")
        self.assertIn("unknown modifier", res["message"])

    @patch("pathlib.Path.exists", return_value=True)
    async def test_list_desktop_commands(self, _exists):
        sample_output = (
            "SUPER + RETURN                      → Terminal\texec\tomarchy-launch-terminal\n"
            "SUPER + W                           → Close window\tlua\thl.dsp.window.close()\n"
            "SUPER + MOUSE                       → Drag window\texec\tignore\n"
        )
        proc_mock = AsyncMock()
        proc_mock.communicate = AsyncMock(return_value=(sample_output.encode("utf-8"), b""))
        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            res = await system_control.list_desktop_commands(query="terminal")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["count"], 1)
            self.assertEqual(res["commands"][0]["title"], "Terminal")

    @patch("pathlib.Path.exists", return_value=True)
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_execute_desktop_command(self, mock_run, _exists):
        sample_output = "SUPER + RETURN                      → Terminal\texec\tomarchy-launch-terminal\n"
        proc_mock = AsyncMock()
        proc_mock.communicate = AsyncMock(return_value=(sample_output.encode("utf-8"), b""))
        mock_run.return_value = (0, "", "")

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            res = await system_control.execute_desktop_command("Terminal")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["executed"], "Terminal")
            mock_run.assert_awaited_once()

    @patch("shutil.which", return_value="/usr/bin/omarchy-shell")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_list_bar_panels(self, mock_run, _which):
        plugins = [
            {"id": "omarchy.audio", "name": "Audio", "enabled": True, "kinds": ["bar-widget"]},
            {"id": "dejan94.todos", "name": "Todo List", "enabled": True, "kinds": ["bar-widget"]},
        ]
        mock_run.return_value = (0, json.dumps(plugins), "")
        res = await system_control.list_bar_panels()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["panels"][0]["id"], "omarchy.audio")

    @patch("shutil.which", return_value="/usr/bin/omarchy-shell")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_open_and_close_bar_panel(self, mock_run, _which):
        mock_run.return_value = (0, "ok", "")
        res_open = await system_control.open_bar_panel("omarchy.audio")
        self.assertEqual(res_open["status"], "success")
        self.assertEqual(res_open["action"], "summoned")

        mock_run.return_value = (0, "", "")
        res_close = await system_control.close_bar_panel("omarchy.audio")
        self.assertEqual(res_close["status"], "success")
        self.assertEqual(res_close["action"], "hidden")

    @patch("shutil.which", return_value="/usr/bin/wpctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_set_volume(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.set_volume(75)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["volume_percent"], 75)
        mock_run.assert_any_await("/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.75")
        mock_run.assert_any_await("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0")

    @patch("shutil.which", return_value="/usr/bin/wpctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_control_microphone(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.control_microphone("mute")
        self.assertEqual(res["status"], "success")
        mock_run.assert_awaited_once_with("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1")

        mock_run.reset_mock()
        res_toggle = await system_control.control_microphone("toggle")
        self.assertEqual(res_toggle["status"], "success")
        mock_run.assert_awaited_once_with("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")

    @patch("shutil.which", return_value="/usr/bin/brightnessctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_set_brightness(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.set_brightness(60)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["brightness_percent"], 60)
        mock_run.assert_awaited_once_with("/usr/bin/brightnessctl", "set", "60%")

    @patch("shutil.which", return_value="/usr/bin/hyprctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_move_window_to_workspace(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.move_window_to_workspace(3)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["workspace"], 3)
        mock_run.assert_awaited_once_with("/usr/bin/hyprctl", "dispatch", "movetoworkspacesilent", "3")


class DesktopSkillsSystemControlIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_skills_manifest_and_execution(self):
        skills = DesktopSkills()
        expected_skills = [
            "type_text",
            "press_key",
            "list_desktop_commands",
            "execute_desktop_command",
            "list_bar_panels",
            "open_bar_panel",
            "close_bar_panel",
            "set_volume",
            "control_microphone",
            "set_brightness",
            "move_window_to_workspace",
        ]
        for name in expected_skills:
            self.assertIn(name, skills._skills, f"Skill {name} not found in loaded skills")

        with patch("skills.system_control.type_text", new_callable=AsyncMock) as mock_type:
            mock_type.return_value = {"status": "success", "method": "typed"}
            res = await skills.execute("type_text", {"text": "hello"})
            self.assertEqual(res["status"], "success")
            mock_type.assert_awaited_once_with("hello")

    @patch("shutil.which", return_value=None)
    async def test_skills_dynamic_exclusion_when_unavailable(self, _which):
        skills = DesktopSkills(exclude_unavailable=True)
        # Skills with dependencies on missing external commands must be dynamically excluded
        self.assertNotIn("type_text", skills._skills)
        self.assertNotIn("press_key", skills._skills)
        self.assertNotIn("set_brightness", skills._skills)
        self.assertNotIn("move_window_to_workspace", skills._skills)
        self.assertNotIn("set_volume", skills._skills)
        self.assertNotIn("control_microphone", skills._skills)
        self.assertNotIn("open_bar_panel", skills._skills)


if __name__ == "__main__":
    unittest.main()

