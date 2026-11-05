import time
from unittest.mock import MagicMock
import pytest
from skills.system_power import SystemPowerManager, CONFIRMATION_TIMEOUT_SECONDS


def test_power_manager_shutdown_requires_confirmation():
    mock_run = MagicMock()
    mgr = SystemPowerManager(run_cmd=mock_run)

    # Request shutdown without confirmation
    res = mgr.request_action("shutdown", confirm=False)
    assert res["status"] == "needs_confirmation"
    assert res["action"] == "shutdown"
    assert "shut down" in res["prompt"]
    assert mock_run.call_count == 0

    # Confirm shutdown
    res_confirm = mgr.confirm_action("yes", delay=0)
    assert res_confirm["status"] == "executing"
    assert res_confirm["confirmed"] is True
    time.sleep(0.05)
    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert "poweroff" in args[0]


def test_power_manager_restart_sequence():
    mock_run = MagicMock()
    mgr = SystemPowerManager(run_cmd=mock_run)

    res = mgr.request_action("restart", confirm=False)
    assert res["status"] == "needs_confirmation"
    assert res["action"] == "restart"
    assert "restart" in res["prompt"]

    res_confirm = mgr.confirm_action("confirm", delay=0)
    assert res_confirm["status"] == "executing"
    time.sleep(0.05)
    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert "reboot" in args[0]


def test_power_manager_lock_screen_sequence():
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mgr = SystemPowerManager(run_cmd=mock_run)

    res = mgr.request_action("lock_screen", confirm=False)
    assert res["status"] == "needs_confirmation"
    assert res["action"] == "lock_screen"

    res_confirm = mgr.confirm_action("do it")
    assert res_confirm["status"] == "locked"
    assert res_confirm["confirmed"] is True
    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert "lock-session" in args[0]


def test_power_manager_direct_confirmation():
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mgr = SystemPowerManager(run_cmd=mock_run)

    res = mgr.request_action("lock_screen", confirm=True)
    assert res["status"] == "locked"
    mock_run.assert_called_once()


def test_power_manager_cancellation():
    mock_run = MagicMock()
    mgr = SystemPowerManager(run_cmd=mock_run)

    mgr.request_action("shutdown", confirm=False)
    assert mgr.get_pending() is not None

    res_cancel = mgr.cancel_action()
    assert res_cancel["status"] == "cancelled"
    assert "Cancelled" in res_cancel["message"]
    assert mgr.get_pending() is None
    assert mock_run.call_count == 0


def test_power_manager_unrecognized_confirmation_phrase():
    mock_run = MagicMock()
    mgr = SystemPowerManager(run_cmd=mock_run)

    mgr.request_action("restart", confirm=False)
    res = mgr.confirm_action("maybe later")
    assert res["status"] == "error"
    assert "not a recognized confirmation" in res["message"]
    # Still pending
    assert mgr.get_pending() is not None
    assert mock_run.call_count == 0


def test_power_manager_confirm_without_pending():
    mgr = SystemPowerManager()
    res = mgr.confirm_action("yes")
    assert res["status"] == "error"
    assert "No system action" in res["message"]
