"""Unit tests for widget tool dispatch via Executor."""
import json
from unittest.mock import patch, MagicMock

from jarvis_control import Config, tools_for
from jarvis_control.tools import Executor, SHOW_WIDGET_SCHEMA, MANAGE_WIDGET_SCHEMA


def test_widget_tool_schemas_present():
    config = Config()
    schemas = tools_for(config)
    names = {s["name"] for s in schemas}
    assert "show_widget" in names
    assert "manage_widget" in names
    assert SHOW_WIDGET_SCHEMA in schemas
    assert MANAGE_WIDGET_SCHEMA in schemas


def test_executor_show_widget_success():
    config = Config()
    executor = Executor(config)

    with patch("ui.jarvis_widgets.backend.shell_call") as mock_shell_call:
        mock_shell_call.return_value = {"ok": True, "id": "test-w1"}
        res = executor.call("show_widget", {
            "kind": "text",
            "title": "System Summary",
            "data_json": json.dumps({"text": "# CPU & RAM\nAll nominal."}),
            "presentation": "floating",
            "expires_seconds": 30,
        })
        assert res.ok is True
        assert "test-w1" in res.output
        mock_shell_call.assert_called_once()
        args, kwargs = mock_shell_call.call_args
        assert args[0] == "present"
        assert args[1]["title"] == "System Summary"
        assert args[1]["kind"] == "text"


def test_executor_show_widget_handles_invalid_json():
    config = Config()
    executor = Executor(config)

    with patch("ui.jarvis_widgets.backend.shell_call") as mock_shell_call:
        mock_shell_call.side_effect = RuntimeError("Invalid JSON payload")
        res = executor.call("show_widget", {
            "kind": "text",
            "title": "Bad Card",
            "data_json": "{not valid json}",
        })
        assert res.ok is False
        assert "Failed to show widget" in res.output


def test_executor_manage_widget_dismiss():
    config = Config()
    executor = Executor(config)

    with patch("ui.jarvis_widgets.backend.shell_call") as mock_shell_call:
        mock_shell_call.return_value = {"ok": True}
        res = executor.call("manage_widget", {"action": "dismiss", "widget_id": "test-w1"})
        assert res.ok is True
        mock_shell_call.assert_called_once_with("manage", {"id": "test-w1", "action": "dismiss"})


def test_executor_manage_widget_clear_all():
    config = Config()
    executor = Executor(config)

    with patch("ui.jarvis_widgets.backend.shell_call") as mock_shell_call:
        mock_shell_call.return_value = {"ok": True, "retained": 0}
        res = executor.call("manage_widget", {"action": "clear_all"})
        assert res.ok is True
        mock_shell_call.assert_called_once_with("clearAll")
