import unittest

from proactive.monitor import JobMonitor, MonitorError, ProactiveMonitor


class ProactiveMonitorTests(unittest.TestCase):
    def test_unverified_process_completion_is_only_a_received_response_notice(self):
        monitor = ProactiveMonitor()
        monitor.track('answer', timeout_seconds=10)
        monitor.update('answer', 'completed', now=1)
        notice = monitor.completion_notice('answer')
        self.assertEqual(notice['state'], 'response_received')
        self.assertFalse(notice['verified'])
        monitor.track('self-report', timeout_seconds=10)
        monitor.update('self-report', 'completed', now=1, verification={'status': 'passed'})
        self.assertEqual(monitor.completion_notice('self-report')['state'], 'response_received')

    def test_whitespace_alias_cannot_replace_running_job(self):
        monitor = ProactiveMonitor()
        original = monitor.track('job', timeout_seconds=10, max_retries=2,
                                 metadata={'original': True})
        with self.assertRaisesRegex(MonitorError, 'already tracked'):
            monitor.track(' job ', timeout_seconds=20)
        self.assertEqual(monitor.get('job'), original)
        self.assertEqual(len(monitor.list_jobs()), 1)

    def test_job_identity_is_consistent_across_operations(self):
        monitor = ProactiveMonitor()
        tracked = monitor.track(' job ', timeout_seconds=10, max_retries=1)
        self.assertEqual(tracked['id'], 'job')
        self.assertEqual(monitor.get('\tjob\n'), tracked)
        failed = monitor.update(' job ', 'failed', now=1)
        started = monitor.start_retry(' job ', now=failed['retry_at'])
        self.assertEqual(started['id'], 'job')
        self.assertEqual(started['attempt'], 2)
        for invalid in (' ', '', None, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(MonitorError):
                    monitor.get(invalid)

    def test_tracks_and_returns_defensive_snapshots(self):
        monitor = ProactiveMonitor()
        snapshot = monitor.track("job-1", timeout_seconds=10, now=5,
                                 metadata={"source": "agent"})
        snapshot["metadata"]["source"] = "changed"

        current = monitor.get("job-1")
        self.assertEqual(current["status"], "running")
        self.assertEqual(current["deadline_at"], 15)
        self.assertEqual(current["metadata"], {"source": "agent"})
        self.assertEqual(monitor.list_jobs(), [current])

    def test_detects_timeout_and_schedules_first_backoff(self):
        monitor = JobMonitor()
        monitor.track("slow", timeout_seconds=5, max_retries=2,
                      backoff_seconds=3, max_backoff_seconds=10, now=10)

        self.assertEqual(monitor.poll(now=14), [])
        changed = monitor.poll(now=15)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["status"], "retry_wait")
        self.assertEqual(changed[0]["detail"], "Job exceeded its timeout.")
        self.assertEqual(changed[0]["metadata"]["retry"], {
            "count": 1, "max_retries": 2, "delay_seconds": 3.0,
            "scheduled_at": 15.0, "retry_at": 18.0,
        })
        self.assertEqual(monitor.poll(now=20), [])

    def test_retry_becomes_available_only_after_backoff(self):
        monitor = ProactiveMonitor()
        monitor.track("retry", timeout_seconds=10, max_retries=1,
                      backoff_seconds=4, now=0)
        failed = monitor.update("retry", "failed", now=2, detail="temporary")
        self.assertEqual(failed["status"], "retry_wait")
        self.assertEqual(monitor.due_retries(now=5), [])
        with self.assertRaisesRegex(MonitorError, "not due"):
            monitor.start_retry("retry", now=5)

        due = monitor.due_retries(now=6)
        self.assertEqual([item["id"] for item in due], ["retry"])
        started = monitor.start_retry("retry", now=6)
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["attempt"], 2)
        self.assertEqual(started["deadline_at"], 16)
        self.assertEqual(started["retry_count"], 1)
        self.assertEqual(monitor.due_retries(now=100), [])

    def test_backoff_grows_exponentially_and_is_capped(self):
        monitor = ProactiveMonitor()
        monitor.track("capped", timeout_seconds=20, max_retries=4,
                      backoff_seconds=3, max_backoff_seconds=7, now=0)
        first = monitor.update("capped", "failed", now=1)
        self.assertEqual(first["retry_at"], 4)
        monitor.start_retry("capped", now=4)
        second = monitor.update("capped", "timed_out", now=5)
        self.assertEqual(second["retry_at"], 11)  # min(3 * 2, 7)
        monitor.start_retry("capped", now=11)
        third = monitor.update("capped", "failed", now=12)
        self.assertEqual(third["retry_at"], 19)  # min(3 * 4, 7)

    def test_exhausted_retries_stay_terminal(self):
        monitor = ProactiveMonitor()
        monitor.track("exhausted", timeout_seconds=1, max_retries=1,
                      backoff_seconds=2, now=0)
        monitor.update("exhausted", "failed", now=1)
        monitor.start_retry("exhausted", now=3)
        final = monitor.update("exhausted", "failed", now=4)
        self.assertEqual(final["status"], "failed")
        self.assertIsNone(final["retry_at"])
        self.assertEqual(final["retry_count"], 1)
        self.assertEqual(monitor.due_retries(now=100), [])

    def test_completion_and_cancellation_never_retry(self):
        monitor = ProactiveMonitor()
        monitor.track("done", timeout_seconds=10, max_retries=4, now=0)
        completed = monitor.update("done", "completed", now=2)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["retry_count"], 0)
        self.assertIsNone(completed["retry_at"])

        monitor.track("cancelled", timeout_seconds=10, max_retries=4, now=0)
        cancelled = monitor.update("cancelled", "cancelled", now=2)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(monitor.due_retries(now=100), [])

    def test_running_update_is_a_heartbeat(self):
        monitor = ProactiveMonitor()
        monitor.track("heartbeat", timeout_seconds=5, now=0)
        updated = monitor.update("heartbeat", "running", now=4)
        self.assertEqual(updated["deadline_at"], 9)
        self.assertEqual(monitor.poll(now=8), [])
        self.assertEqual(monitor.poll(now=9)[0]["status"], "timed_out")

    def test_validation_and_invalid_transitions(self):
        monitor = ProactiveMonitor()
        with self.assertRaises(MonitorError):
            monitor.track("bad", timeout_seconds=float("nan"))
        with self.assertRaises(MonitorError):
            monitor.track("bad", timeout_seconds=1, max_retries=-1)
        monitor.track("valid", timeout_seconds=1, now=0)
        with self.assertRaises(MonitorError):
            monitor.track("valid", timeout_seconds=1)
        with self.assertRaises(MonitorError):
            monitor.update("valid", "unknown", now=0)
        monitor.update("valid", "completed", now=1)
        with self.assertRaisesRegex(MonitorError, "not running"):
            monitor.update("valid", "failed", now=2)
        with self.assertRaisesRegex(MonitorError, "not tracked"):
            monitor.get("missing")

    def test_rejects_clock_moving_backwards(self):
        monitor = ProactiveMonitor()
        monitor.track("clock", timeout_seconds=10, now=5)
        with self.assertRaisesRegex(MonitorError, "move backwards"):
            monitor.update("clock", "completed", now=4)


if __name__ == "__main__":
    unittest.main()
