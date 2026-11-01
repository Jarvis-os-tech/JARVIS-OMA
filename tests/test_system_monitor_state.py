import time
import pytest

from core.system_monitor import (
    AlertAction,
    AlertStateManager,
    ProbeResult,
)


def test_initial_failure_triggers_alert():
    manager = AlertStateManager(cooldown_seconds=300)
    result = ProbeResult(
        name="TCP 192.168.1.100:80",
        category="server",
        status="CRITICAL",
        message="Connection refused",
        alert_type="server_down",
    )

    actions = manager.process_results([result])
    assert len(actions) == 1
    action = actions[0]
    assert action.action_type == "ALERT"
    assert action.alert_type == "server_down"
    assert "Connection refused" in action.message
    assert action.urgency == "critical"


def test_cooldown_suppresses_repeated_alert():
    manager = AlertStateManager(cooldown_seconds=300)
    result = ProbeResult(
        name="TCP 192.168.1.100:80",
        category="server",
        status="CRITICAL",
        message="Connection refused",
        alert_type="server_down",
    )

    # First check triggers alert
    actions1 = manager.process_results([result])
    assert len(actions1) == 1

    # Second check right away within cooldown is suppressed
    actions2 = manager.process_results([result])
    assert len(actions2) == 0


def test_recovery_triggers_chime_after_failure():
    manager = AlertStateManager(cooldown_seconds=300)
    fail_result = ProbeResult(
        name="WAN Internet",
        category="network",
        status="CRITICAL",
        message="Unreachable",
        alert_type="network_down",
    )

    # Fail
    actions1 = manager.process_results([fail_result])
    assert len(actions1) == 1
    assert actions1[0].action_type == "ALERT"

    # Recover
    ok_result = ProbeResult(
        name="WAN Internet",
        category="network",
        status="OK",
        message="Internet reachable",
    )
    actions2 = manager.process_results([ok_result])
    assert len(actions2) == 1
    assert actions2[0].action_type == "RECOVERY"
    assert actions2[0].alert_type == "recovery"
    assert "restored" in actions2[0].message.lower()


def test_healthy_steady_state_triggers_nothing():
    manager = AlertStateManager()
    ok_result = ProbeResult(
        name="CPU Load",
        category="resource",
        status="OK",
        message="CPU normal",
    )
    actions = manager.process_results([ok_result])
    assert len(actions) == 0
