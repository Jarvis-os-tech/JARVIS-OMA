import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ui.jarvis_widgets import backend
from scripts.install_widget_plugin import install
from skills.domains.widgets import WidgetsDomain
from skills.errors import SkillError
from ui.jarvis_widgets.view_schema import validate_view, EXAMPLE


class WidgetDataTests(unittest.TestCase):
    def test_custom_layout_is_generated_from_composable_components(self):
        item = backend.make_widget("view", "Estimator", EXAMPLE)
        self.assertTrue(item["floating"])
        self.assertEqual(item["data"]["layout"]["children"][1]["type"], "slider")

    def test_view_rejects_cycles_unbound_controls_and_executable_properties(self):
        for data in [
            {"layout": {"type": "text", "text": "A", "onClicked": "run()"}},
            {"computed": {"a": {"ref": "b"}, "b": {"ref": "a"}}, "layout": {"type": "text", "text": "A"}},
            {"state": {}, "layout": {"type": "input", "label": "Missing", "bind": "missing"}},
            {"state": {"n": 10}, "layout": {"type": "slider", "label": "Bad", "bind": "n", "min": 0, "max": 5}},
        ]:
            with self.subTest(data=data), self.assertRaises(ValueError): validate_view(data)

    def test_diagrams_accept_data_bound_geometry(self):
        data = {"state": {"position": 100}, "layout": {"type": "canvas", "shapes": [
            {"type": "circle", "x": {"ref": "position"}, "y": 500, "r": 40, "fill": "#76DDD2"}
        ]}}
        self.assertEqual(validate_view(data)["layout"]["type"], "canvas")

    def test_widget_specs_load_in_the_actual_registry_without_starting_services(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.manifest_dirs = [Path(__file__).resolve().parents[1] / "skill_manifests"]
        specs = registry._load_manifests()
        self.assertTrue({"show_widget", "manage_canvas", "manage_widget"} <= set(specs))

    def test_generated_code_and_remote_media_are_not_widgets(self):
        for kind, data in [("qml", {"code": "Qt.quit()"}), ("text", {"text": "ok", "command": "exit"}),
                           ("pip", {"path": "https://example.org/video.mp4"})]:
            with self.subTest(kind=kind), self.assertRaises((ValueError, OSError)):
                backend.make_widget(kind, "Test", data)

    def test_table_shape_and_chart_measurements_are_checked(self):
        for kind, data in [("table", {"columns": ["A"], "rows": [[1, 2]]}),
                           ("chart", {"labels": ["A"], "values": [float("nan")]}),
                           ("progress", {"value": 12, "maximum": 10})]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                backend.validate(kind, data)

    def test_updates_use_given_identity_and_unknown_progress_is_not_a_percentage(self):
        item = backend.make_widget("progress", "Research", {"text": "Reading sources"}, widget_id="research-1")
        self.assertEqual(item["id"], "research-1")
        self.assertNotIn("value", item["data"])

    def test_qr_is_generated_locally_without_payload_in_argv(self):
        if not backend.shutil.which("qrencode"):
            self.skipTest("qrencode unavailable")
        with tempfile.TemporaryDirectory(prefix="jarvis-widgets-test-") as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                actual = subprocess.run
                with patch.object(backend.subprocess, "run", wraps=actual) as run:
                    item = backend.make_widget("qr", "Example", {"content": "https://example.org"})
                self.assertNotIn("https://example.org", run.call_args.args[0])
                path = Path(item["data"]["source"].removeprefix("file://"))
                self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_unknown_ipc_targets_cannot_look_successful(self):
        with patch.object(backend.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Target not found.", "")):
            with self.assertRaises(RuntimeError): backend.shell_call("open")


class ExistingShellInstallTests(unittest.TestCase):
    def test_install_preserves_existing_island_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-plugin-config-") as directory:
            config_home = Path(directory)
            shell_config = config_home / "omarchy/shell.json"
            shell_config.parent.mkdir()
            original = {"version": 1, "plugins": [{"id": "omarchy-dynamic-island", "scale": 1.25}],
                        "bar": {"position": "top"}, "custom": "keep"}
            shell_config.write_text(json.dumps(original))
            result = install(config_home)
            updated = json.loads(shell_config.read_text())
            self.assertEqual(updated["plugins"][0], original["plugins"][0])
            self.assertEqual(updated["custom"], "keep")
            self.assertEqual(updated["plugins"][-1], {"id": "jarvis.widgets"})
            self.assertTrue((Path(result["backup"]) / "shell.json").exists())
            self.assertTrue((Path(result["plugin"]) / "Widgets.qml").exists())
            install(config_home)
            entries = json.loads(shell_config.read_text())["plugins"]
            self.assertEqual(sum(item["id"] == "jarvis.widgets" for item in entries), 1)


class WidgetAdapterTests(unittest.TestCase):
    @staticmethod
    async def inline_worker(function, *args, **kwargs):
        # Shell calls are mocked; no executor or external process is needed.
        return function(*args, **kwargs)

    def test_ipc_timeouts_are_reported_as_tool_failures(self):
        domain = WidgetsDomain()
        with patch("asyncio.to_thread", self.inline_worker), patch.object(backend, "shell_call", side_effect=subprocess.TimeoutExpired("omarchy-shell", 4)):
            with self.assertRaises(SkillError):
                asyncio.run(domain._adapter_manage_canvas("open"))

    def test_input_bar_preserves_attachments_when_canvas_is_available(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.test_bar = MagicMock()
        registry.test_bar.start.return_value = "http://127.0.0.1:12345/#test-token"
        registry._launch = AsyncMock()
        probe = MagicMock()
        probe.wait = AsyncMock(return_value=0)
        with patch.object(backend, "shell_call") as call, \
                patch("skills.skills.os.path.isfile", return_value=True), \
                patch("skills.skills.asyncio.create_subprocess_exec", AsyncMock(return_value=probe)):
            result = asyncio.run(registry._adapter_open_input_bar())
        call.assert_not_called()
        registry._launch.assert_awaited_once()
        self.assertTrue(registry._launch.call_args.args[1].endswith("overlay_client.py"))
        self.assertEqual(registry._launch.call_args.args[2], registry.test_bar.start.return_value)
        self.assertEqual(result["accepts"], ["text", "image", "audio", "pdf", "file"])

    def test_closing_input_also_closes_attachment_server_and_legacy_window(self):
        from skills.skills import DesktopSkills
        registry = DesktopSkills.__new__(DesktopSkills)
        registry.test_bar = MagicMock()
        registry.test_bar.close.return_value = True
        registry._adapter_list_windows = AsyncMock(return_value={"windows": [
            {"title": "JARVIS Input Bar", "class": "JarvisInputBar", "address": "0x123"}
        ]})
        registry._command = MagicMock(return_value="hyprctl")
        registry._run = AsyncMock()
        with patch("asyncio.to_thread", self.inline_worker), \
                patch.object(backend, "shell_call", return_value={"ok": True, "mode": "hidden"}):
            result = asyncio.run(registry._adapter_close_input_bar())
        registry.test_bar.close.assert_called_once()
        registry._run.assert_awaited_once()
        self.assertEqual(result["windows_closed"], 1)


if __name__ == "__main__": unittest.main()
