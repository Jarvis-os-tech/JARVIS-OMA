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


def test_battery_low_and_critical_escalation():
    manager = AlertStateManager(cooldown_seconds=300)

    # 1. Low battery triggers alert
    low_battery = ProbeResult(
        name="Battery",
        category="resource",
        status="WARN",
        message="Battery low: 18% remaining and discharging",
        alert_type="battery_low",
    )
    actions1 = manager.process_results([low_battery])
    assert len(actions1) == 1
    assert actions1[0].action_type == "ALERT"
    assert actions1[0].alert_type == "battery_low"
    assert actions1[0].urgency == "normal"

    # 2. Repeated check at 18% within cooldown does NOT nag frequently
    actions2 = manager.process_results([low_battery])
    assert len(actions2) == 0

    # 3. Drops to critical (9%) -> immediate escalation alert without waiting for cooldown!
    crit_battery = ProbeResult(
        name="Battery",
        category="resource",
        status="CRITICAL",
        message="Battery critically low: 9% remaining and not charging!",
        alert_type="battery_critical",
    )
    actions3 = manager.process_results([crit_battery])
    assert len(actions3) == 1
    assert actions3[0].action_type == "ALERT"
    assert actions3[0].alert_type == "battery_critical"
    assert actions3[0].urgency == "critical"
    assert "[Escalation]" in actions3[0].message

    # 4. Charger connected -> recovery
    charging_battery = ProbeResult(
        name="Battery",
        category="resource",
        status="OK",
        message="Battery charging: 11% (plugged in)",
    )
    actions4 = manager.process_results([charging_battery])
    assert len(actions4) == 1
    assert actions4[0].action_type == "RECOVERY"
    assert actions4[0].alert_type == "recovery"
    assert "Battery restored to normal state" in actions4[0].message


def test_memory_high_and_critical_alerting():
    manager = AlertStateManager(cooldown_seconds=300)

    # High RAM (82% used) triggers WARN alert
    high_mem = ProbeResult(
        name="Memory Usage",
        category="resource",
        status="WARN",
        message="Memory high: 82.0% used",
        alert_type="memory_high",
    )
    actions1 = manager.process_results([high_mem])
    assert len(actions1) == 1
    assert actions1[0].action_type == "ALERT"
    assert actions1[0].alert_type == "memory_high"

    # Repeated check within cooldown is suppressed
    actions2 = manager.process_results([high_mem])
    assert len(actions2) == 0

    # Memory spikes to 93% -> immediate critical escalation
    crit_mem = ProbeResult(
        name="Memory Usage",
        category="resource",
        status="CRITICAL",
        message="Memory critical: 93.0% used",
        alert_type="memory_critical",
    )
    actions3 = manager.process_results([crit_mem])
    assert len(actions3) == 1
    assert actions3[0].alert_type == "memory_critical"
    assert actions3[0].urgency == "critical"
