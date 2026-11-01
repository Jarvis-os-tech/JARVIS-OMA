"""Unit tests for JARVIS Picture-in-Picture (PiP) Vision HUD in tests/test_vision_pip.py."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from skills.skills import DesktopSkills


class VisionPipTests(unittest.TestCase):
    def setUp(self):
        self.plugin_dir = Path("/home/g0pi/.config/omarchy/plugins/omarchy-ai.vision-pip")
        self.manifest_path = self.plugin_dir / "manifest.json"
        self.qml_path = self.plugin_dir / "VisionPip.qml"

    def test_manifest_structure(self):
        self.assertTrue(self.manifest_path.exists(), "manifest.json must exist")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("id"), "omarchy-ai.vision-pip")
        self.assertEqual(data.get("name"), "JARVIS Vision PiP")
        self.assertIn("panel", data.get("kinds", []))
        self.assertTrue(data.get("keepLoaded", False))
        self.assertEqual(data.get("entryPoints", {}).get("panel"), "VisionPip.qml")

    def test_qml_file_structure(self):
        self.assertTrue(self.qml_path.exists(), "VisionPip.qml must exist")
        content = self.qml_path.read_text(encoding="utf-8")

        # Crucial Quickshell & Wayland items
        self.assertIn("import Quickshell", content)
        self.assertIn("import Quickshell.Wayland", content)
        self.assertIn("PanelWindow", content)
        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", content)
        self.assertIn("WlrLayershell.keyboardFocus: WlrKeyboardFocus.None", content)
        self.assertIn("Region { item: pipWidget }", content)

        # High-performance double-buffered ping-pong rendering
        self.assertIn("id: imgA", content)
        self.assertIn("id: imgB", content)
        self.assertIn("id: frameRefreshTimer", content)

        # Drag & persistence features
        self.assertIn("drag.target: pipWidget", content)
        self.assertIn("vision_pip_position.json", content)

        # IPC Handler target
        self.assertIn('target: "vision-pip"', content)
        self.assertIn("setState(payloadJson", content)
        self.assertIn("toggleExpand", content)

        # Real-time frame references
        self.assertIn("jarvis_screen/live_stream.jpg", content)
        self.assertIn("jarvis_webcam/live_stream.jpg", content)

    def test_position_persistence_serialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pos_file = Path(tmpdir) / "vision_pip_position.json"
            pos_data = {"x": 1420, "y": 80}
            pos_file.write_text(json.dumps(pos_data), encoding="utf-8")

            loaded = json.loads(pos_file.read_text(encoding="utf-8"))
            self.assertEqual(loaded["x"], 1420)
            self.assertEqual(loaded["y"], 80)

    @patch("subprocess.Popen")
    def test_broadcast_vision_pip_spawns_omarchy_shell(self, mock_popen):
        skills = DesktopSkills()
        skills._broadcast_vision_pip("screen")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertEqual(args[0], "/usr/share/omarchy/bin/omarchy-shell")
        self.assertIn("vision-pip", args)
        self.assertIn("setState", args)
        self.assertIn('{"mode": "screen"}', args)

    @patch("subprocess.Popen")
    def test_control_vision_mode_updates_mode_and_broadcasts(self, mock_popen):
        skills = DesktopSkills()
        loop = asyncio.new_event_loop()
        try:
            # Start screen mode
            res = loop.run_until_complete(skills._adapter_control_vision_mode("screen", "start"))
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["mode"], "screen")
            self.assertTrue(res["active"])
            self.assertEqual(skills.vision_mode, "screen")

            # Check status
            st = loop.run_until_complete(skills._adapter_control_vision_mode("screen", "status"))
            self.assertEqual(st["mode"], "screen")
            self.assertTrue(st["active"])

            # Stop vision mode
            res_stop = loop.run_until_complete(skills._adapter_control_vision_mode("screen", "stop"))
            self.assertEqual(res_stop["status"], "ok")
            self.assertEqual(res_stop["mode"], "off")
            self.assertFalse(res_stop["active"])
            self.assertEqual(skills.vision_mode, "off")
        finally:
            loop.close()
