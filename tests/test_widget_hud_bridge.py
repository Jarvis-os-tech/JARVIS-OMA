import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from widget_engine import bridge


class TestWidgetHudBridge(unittest.TestCase):
    def test_bridge_status_check(self):
        with patch.object(bridge, "backend") as mock_backend:
            mock_backend.shell_call.return_value = {"ok": True, "engine": "composed-v1"}
            self.assertTrue(bridge.is_shell_ready())

    def test_show_mandatory_widget_renders_valid_widget(self):
        with patch.object(bridge, "backend") as mock_backend:
            mock_backend.make_widget.return_value = {
                "id": bridge.CONFIRM_WIDGET_ID,
                "kind": "text",
                "title": "⚠️ Confirmation Required",
                "data": {"text": "Confirm shutdown"},
                "floating": True,
                "expires_seconds": 60,
            }
            mock_backend.shell_call.return_value = {"ok": True}
            ok = bridge.show_mandatory_widget(bridge.CONFIRM_WIDGET_ID, "⚠️ Confirmation Required", "Confirm shutdown", expires_seconds=60)
            self.assertTrue(ok)
            mock_backend.make_widget.assert_called_once_with(
                "text",
                "⚠️ Confirmation Required",
                {"text": "Confirm shutdown"},
                widget_id=bridge.CONFIRM_WIDGET_ID,
                presentation="floating",
                expires_seconds=60,
            )

    def test_mandatory_power_confirmation_triggers_and_clears(self):
        mock_power = MagicMock()
        mock_power.get_pending.return_value = {
            "action": "shutdown",
            "friendly": "shut down the computer",
        }

        active_alerts = {}
        with patch.object(bridge, "POWER_MANAGER", mock_power), \
             patch.object(bridge, "show_mandatory_widget") as mock_show, \
             patch.object(bridge, "dismiss_widget") as mock_dismiss:

            # Action pending -> show mandatory confirmation card
            bridge.check_mandatory_events(active_alerts)
            mock_show.assert_called_once()
            self.assertEqual(active_alerts.get("power_confirm"), "shutdown")

            # Action confirmed / cleared -> dismiss confirmation card
            mock_power.get_pending.return_value = None
            bridge.check_mandatory_events(active_alerts)
            mock_dismiss.assert_called_with(bridge.CONFIRM_WIDGET_ID)
            self.assertNotIn("power_confirm", active_alerts)

    def test_mandatory_microphone_issue_triggers_and_clears(self, tmp_path=None):
        active_alerts = {}
        with patch.object(bridge, "STATE_FILE") as mock_state_file, \
             patch.object(bridge, "show_mandatory_widget") as mock_show, \
             patch.object(bridge, "dismiss_widget") as mock_dismiss:

            mock_state_file.is_file.return_value = True
            mock_state_file.read_text.return_value = json.dumps({
                "microphone": {"muted": True, "issue": "The JARVIS microphone is muted."}
            })

            bridge.check_mandatory_events(active_alerts)
            mock_show.assert_called_with(bridge.ALERT_WIDGET_ID, "🎙️ Audio Notice", "The JARVIS microphone is muted.", expires_seconds=30)
            self.assertEqual(active_alerts.get("mic_issue"), "The JARVIS microphone is muted.")

            # Mic issue resolved
            mock_state_file.read_text.return_value = json.dumps({
                "microphone": {"muted": False, "issue": ""}
            })
            bridge.check_mandatory_events(active_alerts)
            mock_dismiss.assert_called_with(bridge.ALERT_WIDGET_ID)
            self.assertNotIn("mic_issue", active_alerts)
