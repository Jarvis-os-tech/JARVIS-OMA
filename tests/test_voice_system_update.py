import pytest
from unittest.mock import patch, MagicMock
from jarvis_control.tools import Executor, Result
from jarvis_control.config import Config

def test_system_update_check():
    cfg = Config()
    executor = Executor(cfg)
    mock_res = {
        "has_update": True,
        "current_sha": "abc1234",
        "remote_sha": "def5678",
        "message": "New version available: def5678 - feat: awesome new feature"
    }
    with patch("orchestration.release_manager.ReleaseManager.check_remote_update", return_value=mock_res):
        res = executor.call("system_update", {"action": "check"})
        assert res.ok is True
        assert "def5678" in res.output
        assert "awesome new feature" in res.output

def test_system_update_check_no_update():
    cfg = Config()
    executor = Executor(cfg)
    mock_res = {
        "has_update": False,
        "current_sha": "abc1234",
        "remote_sha": "abc1234",
        "message": "System is up-to-date on abc1234."
    }
    with patch("orchestration.release_manager.ReleaseManager.check_remote_update", return_value=mock_res):
        res = executor.call("system_update", {"action": "check"})
        assert res.ok is True
        assert "up-to-date" in res.output

def test_system_update_apply():
    cfg = Config()
    executor = Executor(cfg)
    mock_meta = {
        "commit": "def567890123",
        "message": "feat: updated release"
    }
    with patch("orchestration.release_manager.ReleaseManager.apply_update", return_value=mock_meta):
        res = executor.call("system_update", {"action": "apply"})
        assert res.ok is True
        assert "def5678" in res.output
        assert "updated release" in res.output

def test_system_update_rollback():
    cfg = Config()
    executor = Executor(cfg)
    mock_meta = {
        "commit": "abc123456789",
        "message": "feat: previous release"
    }
    with patch("orchestration.release_manager.ReleaseManager.rollback", return_value=mock_meta):
        res = executor.call("system_update", {"action": "rollback"})
        assert res.ok is True
        assert "abc1234" in res.output
        assert "rolled back" in res.output.lower()
