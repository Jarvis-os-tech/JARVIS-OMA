"""Offline tests for durable proactive events and their activity ledger."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import stat
import tempfile
import unittest

from proactive import ActivityLedger, ActivityStatus, EventBus, EventStatus


class ProactiveEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private" / "state"
        self.events_path = self.root / "events.sqlite"
        self.ledger_path = self.root / "activity.sqlite"

    def test_publish_reopen_pending_and_local_subscribers(self):
        bus = EventBus(self.events_path)
        observed = []
        unsubscribe = bus.subscribe("file.changed", observed.append)
        event = bus.publish("file.changed", {"path": "notes/today.md"}, event_id="evt-1")
        self.assertEqual(event.status, EventStatus.PENDING)
        self.assertEqual(observed, [event])
        unsubscribe()
        reopened = EventBus(self.events_path)
        self.assertEqual(reopened.get("evt-1"), event)
        self.assertEqual(reopened.pending(), [event])
        self.assertEqual(stat.S_IMODE(self.events_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    def test_atomic_claim_and_deterministic_transitions(self):
        bus = EventBus(self.events_path)
        events = [bus.publish("task", {"n": number}, event_id=f"evt-{number}") for number in range(24)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            claimed = [event for group in pool.map(lambda _: bus.claim(limit=4), range(8)) for event in group]
        self.assertEqual(len(claimed), len(events))
        self.assertEqual(len({event.id for event in claimed}), len(events))
        self.assertTrue(all(event.status is EventStatus.PROCESSING and event.attempts == 1 for event in claimed))
        completed = bus.transition("evt-0", EventStatus.COMPLETED)
        self.assertEqual(completed.status, EventStatus.COMPLETED)
        self.assertEqual(bus.transition("evt-0", "completed"), completed)
        with self.assertRaises(ValueError):
            bus.transition("evt-0", EventStatus.PENDING)
        failed = bus.transition("evt-1", "failed", error="synthetic failure")
        self.assertEqual(failed.error, "synthetic failure")
        retried = bus.transition("evt-1", "pending")
        self.assertEqual(retried.status, EventStatus.PENDING)

    def test_payload_and_event_input_bounds(self):
        bus = EventBus(self.events_path)
        with self.assertRaises(ValueError):
            bus.publish(" ", {})
        with self.assertRaises(ValueError):
            bus.publish("test", {"secret": object()})
        with self.assertRaises(ValueError):
            bus.publish("test", {"oversized": "x" * (64 * 1024)})
        with self.assertRaises(ValueError):
            bus.pending(limit=1001)

    def test_ledger_persists_append_only_records_and_status_history(self):
        ledger = ActivityLedger(self.ledger_path)
        item = ledger.append("observation", "A reminder is due", details={"source": "omarchy"},
                             event_id="evt-7", activity_id="act-7")
        self.assertEqual(item.status, ActivityStatus.OBSERVED)
        planned = ledger.transition(item.id, "planned")
        running = ledger.transition(item.id, "running")
        complete = ledger.transition(item.id, "succeeded")
        self.assertEqual([planned.status, running.status, complete.status],
                         [ActivityStatus.PLANNED, ActivityStatus.RUNNING, ActivityStatus.SUCCEEDED])
        with self.assertRaises(ValueError):
            ledger.transition(item.id, "failed")
        restarted = ActivityLedger(self.ledger_path)
        self.assertEqual(restarted.get("act-7"), complete)
        self.assertEqual(restarted.list(event_id="evt-7"), [complete])
        self.assertEqual(stat.S_IMODE(self.ledger_path.stat().st_mode), 0o600)

    def test_concurrent_ledger_appends_are_not_lost(self):
        ledger = ActivityLedger(self.ledger_path)
        def append(index):
            return ledger.append("worker", f"Activity {index}", activity_id=f"act-{index}")
        with ThreadPoolExecutor(max_workers=10) as pool:
            items = list(pool.map(append, range(40)))
        self.assertEqual(len(items), 40)
        self.assertEqual(len(ledger.list(limit=100)), 40)

    def test_ledger_validates_fields_and_terminal_states(self):
        ledger = ActivityLedger(self.ledger_path)
        with self.assertRaises(ValueError):
            ledger.append("kind", "x" * 4097)
        item = ledger.append("plan", "Synthetic plan", status="planned")
        with self.assertRaises(ValueError):
            ledger.transition(item.id, "observed")
        cancelled = ledger.transition(item.id, "cancelled")
        with self.assertRaises(ValueError):
            ledger.transition(item.id, "running")


if __name__ == "__main__":
    unittest.main()
