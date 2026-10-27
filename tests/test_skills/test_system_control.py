"""Tests for native Omarchy desktop and system control skills."""
import asyncio
import json
import unittest
from unittest.mock import ANY, AsyncMock, patch

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

    def test_clean_window_target(self):
        self.assertEqual(system_control._clean_window_target("antigravity textbar"), "antigravity")
        self.assertEqual(system_control._clean_window_target("the antigravity textbar"), "antigravity")
        self.assertEqual(system_control._clean_window_target("textbar in antigravity"), "antigravity")
        self.assertEqual(system_control._clean_window_target("chrome address bar"), "chrome")
        self.assertEqual(system_control._clean_window_target("terminal input"), "terminal")
        self.assertEqual(system_control._clean_window_target("textbar"), "")

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_with_app_textbar_query(self, mock_run, _which):
        sample_clients = [
            {"address": "0x555a", "class": "antigravity", "title": "Analyzing GitHub Repo"}
        ]
        sample_active = {"address": "0x555a", "class": "antigravity", "title": "Analyzing GitHub Repo"}

        async def fake_run(*args, **kwargs):
            if "clients" in args:
                return (0, json.dumps(sample_clients), "")
            if "activewindow" in args:
                return (0, json.dumps(sample_active), "")
            return (0, "", "")

        mock_run.side_effect = fake_run
        res = await system_control.type_text("hello antigravity", target_window="antigravity textbar")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_window"], "antigravity textbar")

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_with_target_window_success(self, mock_run, _which):
        sample_clients = [
            {"address": "0x1234", "class": "google-chrome", "title": "Google Chrome"}
        ]
        sample_active = {"address": "0x1234", "class": "google-chrome", "title": "Google Chrome"}

        async def fake_run(*args, **kwargs):
            if "clients" in args:
                return (0, json.dumps(sample_clients), "")
            if "activewindow" in args:
                return (0, json.dumps(sample_active), "")
            return (0, "", "")

        mock_run.side_effect = fake_run
        res = await system_control.type_text("hello chrome", target_window="chrome textbar")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_window"], "chrome textbar")

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_blocks_keystrokes_when_focus_stuck_in_terminal(self, mock_run, _which):
        sample_clients = [
            {"address": "0x1234", "class": "JarvisInputBar", "title": "JARVIS Input Bar"},
            {"address": "0x9999", "class": "foot", "title": "terminal"}
        ]
        # Active window remains terminal (e.g. mouse cursor prevented focus or compositor failed)
        sample_active = {"address": "0x9999", "class": "foot", "title": "terminal"}

        async def fake_run(*args, **kwargs):
            if "clients" in args:
                return (0, json.dumps(sample_clients), "")
            if "activewindow" in args:
                return (0, json.dumps(sample_active), "")
            return (0, "", "")

        mock_run.side_effect = fake_run
        res = await system_control.type_text("should not type in terminal", target_window="textbar")
        self.assertEqual(res["status"], "error")
        self.assertIn("Pre-action focus verification failed", res["message"])
        self.assertIn("Blocked keystrokes to prevent typing into the wrong window", res["message"])
        # Ensure wtype -- text was NEVER dispatched
        for call_args in mock_run.call_args_list:
            self.assertNotIn("should not type in terminal", call_args[0])

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_type_text_target_window_not_found(self, mock_run, _which):
        mock_run.return_value = (0, json.dumps([]), "")
        res = await system_control.type_text("hello", target_window="nonexistent_window")
        self.assertEqual(res["status"], "error")
        self.assertIn("target window 'nonexistent_window' not found", res["message"])

    @patch("shutil.which", return_value="/usr/bin/wtype")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_press_key_with_target_window(self, mock_run, _which):
        sample_clients = [{"address": "0x1234", "class": "JarvisInputBar", "title": "JARVIS Input Bar"}]
        sample_active = {"address": "0x1234", "class": "JarvisInputBar", "title": "JARVIS Input Bar"}

        async def fake_run(*args, **kwargs):
            if "clients" in args:
                return (0, json.dumps(sample_clients), "")
            if "activewindow" in args:
                return (0, json.dumps(sample_active), "")
            return (0, "", "")

        mock_run.side_effect = fake_run
        res = await system_control.press_key("Return", target_window="textbar")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_window"], "textbar")

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

    @patch("shutil.which", return_value="/usr/bin/hyprctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_execute_desktop_voice_window_commands(self, mock_run, _which):
        mock_run.return_value = (0, "ok", "")
        # Test tile left
        res1 = await system_control.execute_desktop_command("tile left")
        self.assertEqual(res1["status"], "unverified")
        self.assertFalse(res1["verified"])
        self.assertEqual(res1["action"], "movewindow l")

        # Supported aliases share the exact-target verifier and preserve failure.
        for status in ("success", "error", "unverified"):
            result = {"status": status, "verified": status == "success", "action": "fullscreen"}
            with patch("system_control.manage_window", new=AsyncMock(return_value=result)) as manage:
                res2 = await system_control.execute_desktop_command("fullscreen")
            self.assertEqual(res2, {**result, "command": "fullscreen"})
            manage.assert_awaited_once_with("fullscreen")

            result = {"status": status, "verified": status == "success", "target_workspace": 2}
            with patch("system_control.switch_workspace", new=AsyncMock(return_value=result)) as switch:
                res3 = await system_control.execute_desktop_command("new workspace")
            self.assertEqual(res3, {**result, "command": "new workspace"})
            switch.assert_awaited_once_with("next")

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

    @patch("system_control.get_control_panel_script", return_value=None)
    @patch("shutil.which", return_value="/usr/bin/wpctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_set_volume(self, mock_run, _which, _plugin):
        mock_run.side_effect = [(0, "", ""), (0, "", ""), (0, "Volume: 0.75", "")]
        res = await system_control.set_volume(75)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["volume_percent"], 75)
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.75", env=ANY)
        mock_run.assert_any_await("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0", env=ANY)

    @patch("system_control.get_control_panel_script", return_value=None)
    @patch("shutil.which", return_value="/usr/bin/wpctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_control_microphone(self, mock_run, _which, _plugin):
        mock_run.side_effect = [(0, "", ""), (0, "Volume: 0.50 [MUTED]", "")]
        res = await system_control.control_microphone("mute")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1", env=ANY)
        mock_run.assert_any_await("/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@", env=ANY)

        mock_run.reset_mock()
        mock_run.side_effect = [(0, "Volume: 0.50 [MUTED]", ""), (0, "", ""), (0, "Volume: 0.50", "")]
        res_toggle = await system_control.control_microphone("toggle")
        self.assertEqual(res_toggle["status"], "success")
        self.assertFalse(res_toggle["muted"])
        self.assertTrue(res_toggle["verified"])
        mock_run.assert_any_await("/usr/bin/wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0", env=ANY)

    @patch("system_control.get_control_panel_script", return_value=None)
    @patch("shutil.which", return_value="/usr/bin/brightnessctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_set_brightness(self, mock_run, _which, _plugin):
        mock_run.side_effect = [(0, "", ""), (0, "60", ""), (0, "100", "")]
        res = await system_control.set_brightness(60)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["brightness_percent"], 60)
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/usr/bin/brightnessctl", "set", "60%", env=ANY)
        mock_run.assert_any_await("/usr/bin/brightnessctl", "get", env=ANY)
        mock_run.assert_any_await("/usr/bin/brightnessctl", "max", env=ANY)

    @patch("shutil.which", return_value="/usr/bin/hyprctl")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_move_window_to_workspace(self, mock_run, _which):
        mock_run.return_value = (0, "", "")
        res = await system_control.move_window_to_workspace(3)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["workspace"], 3)
        mock_run.assert_awaited_once_with("/usr/bin/hyprctl", "dispatch", "movetoworkspacesilent", "3")


class ControlPanelPluginUnitTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests verifying direct integration with the ac.control-panel plugin scripts."""

    def setUp(self):
        # All native observations are mocked. No installed CLI is called by tests.
        which = patch("shutil.which", side_effect=lambda name: "/usr/bin/" + name)
        which.start()
        self.addCleanup(which.stop)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_volume_exact_and_relative(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/system-control.sh"
        mock_run.side_effect = [(0, "", ""), (0, "", ""), (0, "Volume: 0.80", "")]

        # Exact percent
        res = await system_control.set_volume(percent=80)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["volume_percent"], 80)
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "audio-set-volume", "80", env=ANY)

        # Raise
        mock_run.reset_mock()
        mock_run.side_effect = [(0, "Volume: 0.50", ""), (0, "", ""), (0, "", ""), (0, "Volume: 0.60", "")]
        res_raise = await system_control.set_volume(action="raise", amount=10)
        self.assertEqual(res_raise["status"], "success")
        self.assertEqual(res_raise["volume_percent"], 60)
        self.assertTrue(res_raise["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "audio-set-volume", "60", env=ANY)

        # Mute / unmute / toggle
        mock_run.reset_mock()
        mock_run.side_effect = [(0, "", ""), (0, "Volume: 0.60 [MUTED]", "")]
        res_mute = await system_control.set_volume(action="mute")
        self.assertEqual(res_mute["status"], "success")
        self.assertTrue(res_mute["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "audio-set-mute", "1", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_microphone(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/system-control.sh"
        mock_run.side_effect = [(0, "", ""), (0, "Volume: 0.50 [MUTED]", "")]

        res_mute = await system_control.control_microphone("mute")
        self.assertEqual(res_mute["status"], "success")
        self.assertTrue(res_mute["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "audio-set-input-mute", "1", env=ANY)

        mock_run.reset_mock()
        mock_run.side_effect = [(0, "", ""), (0, "Volume: 0.70 [MUTED]", "")]
        res_vol = await system_control.control_microphone("volume", volume=70)
        self.assertEqual(res_vol["status"], "success")
        self.assertTrue(res_vol["verified"])
        self.assertEqual(res_vol["input_volume_percent"], 70)
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "audio-set-input-volume", "70", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_brightness(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/display-control.sh"
        mock_run.side_effect = [(0, "", ""), (0, "70", ""), (0, "100", "")]

        # Exact percent
        res = await system_control.set_brightness(percent=70)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["brightness_percent"], 70)
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/display-control.sh", "set-brightness", "70", env=ANY)

        # Relative lower
        mock_run.reset_mock()
        mock_run.side_effect = [(0, "40", ""), (0, "100", ""), (0, "", ""), (0, "25", ""), (0, "100", "")]
        res_lower = await system_control.set_brightness(direction="lower", amount=15)
        self.assertEqual(res_lower["status"], "success")
        self.assertEqual(res_lower["brightness_percent"], 25)
        self.assertTrue(res_lower["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/display-control.sh", "set-brightness", "25", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_night_light(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/display-control.sh"
        mock_run.return_value = (0, "4000", "")

        res_status = await system_control.control_night_light("status")
        self.assertEqual(res_status["status"], "success")
        self.assertEqual(res_status["nightlight"], {"enabled": True, "temperature": 4000})
        self.assertTrue(res_status["verified"])
        mock_run.assert_awaited_once_with("/usr/bin/hyprctl", "hyprsunset", "temperature", env=ANY)

        mock_run.reset_mock()
        mock_run.side_effect = [(0, "", ""), (0, "3500", "")]
        res_temp = await system_control.control_night_light("temperature", temperature=3500)
        self.assertEqual(res_temp["status"], "success")
        self.assertTrue(res_temp["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/display-control.sh", "set-nightlight-temp", "3500", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_wifi(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/network-control.sh"
        mock_run.return_value = (0, "enabled", "")

        res_status = await system_control.control_wifi("status")
        self.assertEqual(res_status["status"], "success")
        self.assertTrue(res_status["enabled"])
        self.assertTrue(res_status["verified"])
        mock_run.assert_awaited_once_with("/usr/bin/nmcli", "radio", "wifi", env=ANY)

        mock_run.reset_mock()
        mock_run.return_value = (0, "", "")
        res_conn = await system_control.control_wifi("connect", ssid="Office_5G", password="secretpassword")
        self.assertEqual(res_conn["status"], "unverified")
        self.assertFalse(res_conn["verified"])
        self.assertEqual(res_conn["requested_ssid"], "Office_5G")
        mock_run.assert_awaited_once_with("/mock/plugins/scripts/network-control.sh", "wifi-connect", "Office_5G", "secretpassword", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_bluetooth(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/bluetooth-control.sh"
        mock_run.return_value = (0, "Controller AA:BB:CC:DD:EE:00\n\tPowered: yes", "")

        res_status = await system_control.control_bluetooth("status")
        self.assertEqual(res_status["status"], "success")
        self.assertTrue(res_status["powered"])
        self.assertTrue(res_status["verified"])
        mock_run.assert_awaited_once_with("/usr/bin/bluetoothctl", "show", env=ANY)

        mock_run.reset_mock()
        mock_run.side_effect = [(0, "Connection successful", ""), (0, "Device AA:BB:CC:DD:EE:FF\n\tConnected: yes", "")]
        res_dev = await system_control.control_bluetooth("connect", device="AA:BB:CC:DD:EE:FF")
        self.assertEqual(res_dev["status"], "success")
        self.assertTrue(res_dev["connected"])
        self.assertTrue(res_dev["verified"])
        mock_run.assert_any_await("/usr/bin/bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF", env=ANY)
        mock_run.assert_any_await("/usr/bin/bluetoothctl", "info", "AA:BB:CC:DD:EE:FF", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_power(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/power-control.sh"
        mock_run.side_effect = [(0, "", ""), (0, "performance", "")]

        res_perf = await system_control.control_power("performance")
        self.assertEqual(res_perf["status"], "success")
        self.assertTrue(res_perf["verified"])
        self.assertEqual(res_perf["profile"], "performance")
        mock_run.assert_any_await("/mock/plugins/scripts/power-control.sh", "set-profile", "performance", env=ANY)
        mock_run.assert_any_await("/usr/bin/powerprofilesctl", "get", env=ANY)

        mock_run.reset_mock()
        res_game = await system_control.control_power("game_mode")
        self.assertEqual(res_game["status"], "error")
        self.assertFalse(res_game["verified"])
        mock_run.assert_not_awaited()

        mock_run.reset_mock()
        mock_run.side_effect = [(0, '{"enabled":false}', ""), (0, "", ""), (0, '{"enabled":true}', "")]
        res_awake = await system_control.control_power("stay_awake")
        self.assertEqual(res_awake["status"], "success")
        self.assertTrue(res_awake["verified"])
        self.assertTrue(res_awake["stay_awake"])
        mock_run.assert_any_await("/usr/bin/omarchy-toggle-idle", "stay-awake", env=ANY)
        self.assertEqual(mock_run.await_count, 3)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_notifications(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/notifications-control.sh"
        mock_run.side_effect = [(0, "off", ""), (0, "", ""), (0, "on", "")]

        res = await system_control.control_notifications("dnd_toggle")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["dnd"])
        self.assertTrue(res["verified"])
        mock_run.assert_any_await("/mock/plugins/scripts/notifications-control.sh", "set-dnd", "true", env=ANY)

    @patch("system_control.get_control_panel_script")
    @patch("system_control._run_command", new_callable=AsyncMock)
    async def test_plugin_theme(self, mock_run, mock_script):
        mock_script.return_value = "/mock/plugins/scripts/system-control.sh"
        mock_run.return_value = (0, "Nord\nTokyo Night", "")

        res = await system_control.control_theme("dark")
        self.assertEqual(res["status"], "error")
        self.assertFalse(res["verified"])
        mock_run.assert_awaited_once_with("/usr/bin/omarchy-theme-list", env=ANY)

        mock_run.reset_mock()
        mock_run.side_effect = [(0, "Nord\nTokyo Night", ""), (0, "", ""), (0, "Nord", "")]
        named = await system_control.control_theme("set", "nord")
        self.assertEqual(named["status"], "success")
        self.assertTrue(named["verified"])
        self.assertEqual(named["current"], "Nord")
        mock_run.assert_any_await("/mock/plugins/scripts/system-control.sh", "theme-set", "Nord", env=ANY)


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
            "control_power",
            "control_wifi",
            "control_bluetooth",
            "control_night_light",
            "control_notifications",
            "control_theme",
            "open_control_panel",
        ]
        for name in expected_skills:
            self.assertIn(name, skills._skills, f"Skill {name} not found in loaded skills")

        # Test aliases work transparently
        self.assertIn("toggle_wifi", skills.SKILL_ALIASES)
        self.assertIn("toggle_bluetooth", skills.SKILL_ALIASES)
        self.assertIn("system_power", skills.SKILL_ALIASES)
        self.assertIn("adjust_volume", skills.SKILL_ALIASES)
        self.assertIn("adjust_brightness", skills.SKILL_ALIASES)

        with patch("skills.system_control.type_text", new_callable=AsyncMock) as mock_type, \
             patch("skills.system_control._query_active_window", return_value={"address": "0x123", "pid": 42}):
            mock_type.return_value = {"status": "success", "method": "typed"}
            res = await skills.execute("type_text", {"text": "hello"})
            self.assertEqual(res["status"], "unverified_effect")
            self.assertTrue(res["post_action_focus_verified"])
            mock_type.assert_awaited_once_with("hello", target_window=None, press_enter=False)

    async def test_skills_execute_type_text_targeting_app(self):
        skills = DesktopSkills()
        with patch("skills.system_control.type_text", new_callable=AsyncMock) as mock_type, \
             patch("skills.system_control._query_active_window", return_value={"address": "0x123", "pid": 42}), \
             patch("skills.system_control._focus_window_target", return_value=(True, "verified_active", {"address": "0x123", "pid": 42})):
            mock_type.return_value = {"status": "success", "method": "typed", "target_window": "antigravity textbar"}

            res = await skills.execute("type_text", {"text": "hello from user", "target_window": "antigravity textbar"})
            self.assertEqual(res["status"], "unverified_effect")
            mock_type.assert_awaited_once_with("hello from user", target_window="antigravity textbar", press_enter=False)

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

