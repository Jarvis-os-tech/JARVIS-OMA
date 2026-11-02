import json
from pathlib import Path
import sys
from unittest.mock import Mock

from jarvis_control.config import Config
from jarvis_control.outcomes import classify_result
from jarvis_control.tools import Executor, Result


def focused_window():
    return {'address': '0x123', 'pid': 42, 'class': 'fixture', 'focusHistoryID': 0}


def test_typing_receipt_does_not_prove_an_app_or_message_effect(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr(executor, '_window_geometry', lambda _: (focused_window(), ''))
    monkeypatch.setattr('jarvis_control.tools.shutil.which', lambda _: '/bin/wtype')
    monkeypatch.setattr(executor, '_shell', Mock(return_value=Result(True, '')))
    result = executor.call('type_text', {'text': 'hi'})
    assert result.ok
    receipt = json.loads(result.output)
    assert receipt['dispatched'] is True
    assert receipt['verified'] is False
    assert not classify_result(result.as_tool_result()).completed
    executor._shell.assert_called_once_with(['wtype', '-d', '5', '-', '-s', '150'], input_text='hi')


def test_shortcut_delivery_is_not_message_submission_evidence(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr(executor, '_window_geometry', lambda _: (focused_window(), ''))
    monkeypatch.setattr(executor, '_dispatch_lua', Mock(return_value=Result(True, 'ok')))
    monkeypatch.setattr('jarvis_control.tools.shutil.which', lambda _: '/bin/wtype')
    monkeypatch.setattr(executor, '_shell', Mock(return_value=Result(True, '')))
    result = executor.call('send_shortcut', {'mods': '', 'key': 'Enter', 'window': 'address:0x123'})
    assert result.ok
    assert not classify_result(result.as_tool_result()).completed
    executor._shell.assert_called_once_with([
        sys.executable, str(Path(__file__).resolve().parents[2] / 'jarvis_control/wayland_keyboard.py'),
        '', 'Return'], timeout=3)


def test_typing_never_dispatches_without_a_focused_window(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr(executor, '_window_geometry', lambda _: (None, 'nothing is focused'))
    dispatch = Mock(return_value=Result(True, ''))
    monkeypatch.setattr(executor, '_shell', dispatch)
    assert not executor.call('type_text', {'text': 'hi'}).ok
    dispatch.assert_not_called()
