"""Comprehensive tests for the proactive subsystem: EventBus, ActivityLedger,
PolicyEngine (L0-L5), SystemWatch, ProactiveMonitor, and DesktopSkills proactive adapters.
"""
import asyncio
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import pytest

from proactive.events import EventBus, EventStatus
from proactive.ledger import ActivityLedger, ActivityStatus
from proactive.policy import (
    Action,
    ActionEffect,
    AutonomyLevel,
    DecisionStatus,
    PolicyEngine,
    PolicyLimits,
    ProactivePolicy,
)
from proactive.system_watch import SystemWatch, sample_system
from proactive.monitor import ProactiveMonitor
from skills.skills import DesktopSkills


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def test_event_bus_wal_and_lifecycle(tmp_dir):
    db_path = tmp_dir / "events.db"
    bus = EventBus(db_path)

    # Verify SQLite WAL mode
    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal", f"Expected WAL mode, got {journal_mode}"

    # Verify publishing an event
    event = bus.publish("system.test_alert", {"metric": "cpu", "value": 92.5})
    assert event.id is not None
    assert event.type == "system.test_alert"
    assert event.payload == {"metric": "cpu", "value": 92.5}
    assert event.status == EventStatus.PENDING

    # Verify claim (moves pending -> processing atomically)
    claimed = bus.claim(limit=1, event_type="system.test_alert")
    assert len(claimed) == 1
    assert claimed[0].id == event.id
    assert claimed[0].status == EventStatus.PROCESSING
    assert claimed[0].attempts == 1

    # Verify completion transition
    completed = bus.transition(event.id, EventStatus.COMPLETED)
    assert completed.status == EventStatus.COMPLETED

    # Verify invalid transition from terminal state
    with pytest.raises(ValueError, match="invalid event transition"):
        bus.transition(event.id, EventStatus.PROCESSING)


def test_activity_ledger_lifecycle_and_execution_store(tmp_dir):
    db_path = tmp_dir / "activity.db"
    ledger = ActivityLedger(db_path)

    # Verify SQLite WAL mode
    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal", f"Expected WAL mode, got {journal_mode}"

    # Append activity
    act = ledger.append(
        "code_refactor",
        "Refactoring proactive runtime",
        details={"module": "policy.py"},
        status=ActivityStatus.PLANNED,
    )
    assert act.status == ActivityStatus.PLANNED
    assert act.kind == "code_refactor"

    # Save execution record
    exec_record = {
        "workspace": str(tmp_dir),
        "jobs": {"job-001": "running"},
        "outcome": None,
    }
    ledger.save_execution(act.id, exec_record)
    saved = ledger.execution(act.id)
    assert saved["jobs"] == {"job-001": "running"}

    # Transition to RUNNING then SUCCEEDED
    running = ledger.transition(act.id, ActivityStatus.RUNNING)
    assert running.status == ActivityStatus.RUNNING

    succeeded = ledger.transition(act.id, ActivityStatus.SUCCEEDED)
    assert succeeded.status == ActivityStatus.SUCCEEDED

    # List activities
    activities = ledger.list(limit=10)
    assert len(activities) >= 1
    assert activities[0].id == act.id


def test_policy_engine_autonomy_levels_l0_to_l5():
    engine = PolicyEngine(autonomy_level=AutonomyLevel.L3)
    actions = {
        "read": Action("inspect_file", ActionEffect.READ_ONLY),
        "rev": Action("make_directory", ActionEffect.LOCAL_REVERSIBLE),
        "ext": Action("send_webhook", ActionEffect.EXTERNAL),
        "dest": Action("delete_volume", ActionEffect.DESTRUCTIVE),
        "unk": Action("arbitrary_command", ActionEffect.UNKNOWN),
    }

    # L0 - Manual: Zero autonomous action execution
    engine.set_autonomy_level(AutonomyLevel.L0)
    for name, act in actions.items():
        assert not engine.classify(act), f"L0 must classify {name} as not autonomous"
        dec = engine.evaluate(f"trig-l0-{name}", act, 10.0)
        assert dec.status == DecisionStatus.APPROVAL_REQUIRED
        assert not dec.allowed

    # L1 - Assisted: Suggestions only, all require approval
    engine.set_autonomy_level(AutonomyLevel.L1)
    for name, act in actions.items():
        assert not engine.classify(act), f"L1 must classify {name} as not autonomous"

    # L2 - Partial / Read-Only
    engine.set_autonomy_level(AutonomyLevel.L2)
    assert engine.classify(actions["read"])
    assert not engine.classify(actions["rev"])
    assert not engine.classify(actions["ext"])
    assert not engine.classify(actions["dest"])
    assert not engine.classify(actions["unk"])

    # L3 - Conditional: Read-Only + Local Reversible
    engine.set_autonomy_level(AutonomyLevel.L3)
    assert engine.classify(actions["read"])
    assert engine.classify(actions["rev"])
    assert not engine.classify(actions["ext"])
    assert not engine.classify(actions["dest"])
    assert not engine.classify(actions["unk"])

    # L4 - High: Read-Only + Local Reversible + Safe External
    engine.set_autonomy_level(AutonomyLevel.L4)
    assert engine.classify(actions["read"])
    assert engine.classify(actions["rev"])
    assert engine.classify(actions["ext"])
    assert not engine.classify(actions["dest"])
    assert not engine.classify(actions["unk"])

    # L5 - Full Autonomy: All permitted
    engine.set_autonomy_level(AutonomyLevel.L5)
    for name, act in actions.items():
        assert engine.classify(act), f"L5 must classify {name} as permitted"
        dec = engine.evaluate(f"trig-l5-{name}", act, 100.0)
        assert dec.status == DecisionStatus.ALLOWED
        assert dec.allowed


def test_policy_engine_quiet_hours():
    engine = PolicyEngine(
        autonomy_level=AutonomyLevel.L3,
        quiet_hours_enabled=True,
        quiet_hours_start=22,
        quiet_hours_end=7,
    )
    act = Action("read_file", ActionEffect.READ_ONLY)

    daytime = datetime(2026, 10, 31, 14, 30)
    nighttime = datetime(2026, 10, 31, 23, 15)

    assert not engine.in_quiet_hours(daytime)
    assert engine.in_quiet_hours(nighttime)

    # In quiet hours: blocked with QUIET_HOURS status
    dec_night = engine.evaluate("trig-night", act, 50.0, dt=nighttime)
    assert dec_night.status == DecisionStatus.QUIET_HOURS
    assert not dec_night.allowed

    # Outside quiet hours: allowed
    dec_day = engine.evaluate("trig-day", act, 55.0, dt=daytime)
    assert dec_day.status == DecisionStatus.ALLOWED
    assert dec_day.allowed


def test_system_watch_hysteresis_and_alerts():
    watch = SystemWatch(
        battery_low=15, battery_recover=20,
        disk_low=5, disk_recover=8,
        memory_low=10, memory_recover=15,
    )

    # 1. Critical battery discharging
    snap1 = {
        "battery_percent": 10.0,
        "battery_charging": False,
        "disk_free_percent": 40.0,
        "memory_available_percent": 50.0,
    }
    alerts1 = watch.observe(snap1, 1.0)
    assert len(alerts1) == 1
    assert alerts1[0]["kind"] == "battery"
    assert "not charging" in alerts1[0]["text"]

    # 2. Repeated observation while still low stays silent (no flapping)
    alerts2 = watch.observe(snap1, 2.0)
    assert len(alerts2) == 0

    # 3. Charger plugged in resets battery alert state
    snap_charging = {
        "battery_percent": 12.0,
        "battery_charging": True,
        "disk_free_percent": 40.0,
        "memory_available_percent": 50.0,
    }
    alerts3 = watch.observe(snap_charging, 3.0)
    assert len(alerts3) == 0

    # 4. Charger unplugged triggers a new generation alert
    alerts4 = watch.observe(snap1, 4.0)
    assert len(alerts4) == 1
    assert alerts4[0]["kind"] == "battery"


def test_proactive_monitor_tracking_and_retry():
    monitor = ProactiveMonitor()
    job = monitor.track(
        "job-abc",
        timeout_seconds=5.0,
        max_retries=2,
        backoff_seconds=1.0,
        now=10.0,
    )
    assert job["id"] == "job-abc"
    assert job["status"] == "running"
    assert job["deadline_at"] == 15.0

    # Poll at timestamp 16.0 detects deadline expiration
    timed_out = monitor.poll(now=16.0)
    assert len(timed_out) == 1
    assert timed_out[0]["id"] == "job-abc"
    assert timed_out[0]["status"] == "retry_wait"

    # Retries due after backoff (1s backoff -> 17.0)
    assert len(monitor.due_retries(now=16.5)) == 0
    due = monitor.due_retries(now=17.5)
    assert len(due) == 1
    assert due[0]["id"] == "job-abc"

    # Start retry
    retried = monitor.start_retry("job-abc", now=17.5)
    assert retried["status"] == "running"
    assert retried["attempt"] == 2



@pytest.mark.asyncio
async def test_desktop_skills_proactive_tools(tmp_dir):
    skills = DesktopSkills()

    # 1. proactive.status
    status = await skills.execute("proactive_status", {})
    assert status["status"] in ("active", "paused", "stopped")
    assert "state" in status

    # 2. proactive.enqueue
    enqueue_res = await skills.execute("proactive_task", {
        "prompt": "Run automated test task",
        "workspace": str(tmp_dir),
    })
    assert enqueue_res["status"] == "queued"
    assert "event_id" in enqueue_res

    # 3. proactive.pause
    pause_res = await skills.execute("pause_jarvis", {})
    assert pause_res["status"] == "paused"
    status_paused = await skills.execute("proactive_status", {})
    assert status_paused["status"] == "paused"

    # 4. proactive.resume
    resume_res = await skills.execute("resume_jarvis", {})
    assert resume_res["status"] == "active"
    status_resumed = await skills.execute("proactive_status", {})
    assert status_resumed["status"] == "active"

    # 5. proactive.stop
    stop_res = await skills.execute("stop_all_jarvis_work", {})
    assert stop_res["status"] == "stopped"

    # Clean resume and teardown
    await skills.execute("resume_jarvis", {})
    if skills._proactive:
        await skills._proactive.close()
