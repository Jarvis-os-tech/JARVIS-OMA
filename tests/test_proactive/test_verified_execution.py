import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from proactive.ledger import ActivityLedger, ActivityStatus
from proactive.policy import Action, ActionEffect, ProactivePolicy
from proactive.runtime import ProactiveRuntime
from proactive.verification import verify_files, validate_checks


class FakeOrchestrator:
    def __init__(self):
        self.workers, self.jobs, self.calls = {}, {}, []

    def delegate(self, agent, prompt, workspace, timeout):
        self.calls.append((agent, prompt, workspace, timeout))
        job_id = f'job-{len(self.calls)}'
        self.jobs[job_id] = {'id': job_id, 'state': 'running'}
        return {'job': {'id': job_id}}

    async def cancel(self, job_id):
        self.workers.pop(job_id, None)
        self.jobs[job_id]['state'] = 'cancelled'


class VerifiedExecutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.worker = FakeOrchestrator()
        self.runtime = ProactiveRuntime(self.root / 'state', self.worker)

    async def launch(self, checks=None):
        self.runtime.enqueue('Write the artifact', str(self.root), authorized=True, verification=checks)
        result = await self.runtime.tick()
        return result['results'][0]['activity_id']

    def check(self, content=b'expected'):
        return [{'path': 'result.txt', 'sha256': hashlib.sha256(content).hexdigest()}]

    async def test_exit_zero_without_contract_remains_unverified(self):
        activity = await self.launch()
        self.worker.jobs['job-1'].update(state='completed', output='Verified successfully!')
        await self.runtime.tick()
        self.assertEqual(self.runtime.ledger.get(activity).status, ActivityStatus.UNVERIFIED)
        evidence = self.runtime.status()['recent_activity'][0]['execution']['outcome']
        self.assertEqual(evidence['status'], 'unverified')

    async def test_independent_bytes_check_persists_evidence(self):
        activity = await self.launch(self.check())
        (self.root / 'result.txt').write_bytes(b'expected')
        self.worker.jobs['job-1']['state'] = 'completed'
        await self.runtime.tick()
        restarted = ProactiveRuntime(self.root / 'state', FakeOrchestrator())
        self.assertEqual(restarted.ledger.get(activity).status, ActivityStatus.SUCCEEDED)
        self.assertTrue(restarted.ledger.execution(activity)['outcome']['checks'][0]['passed'])

    async def test_worker_success_does_not_hide_wrong_artifact(self):
        activity = await self.launch(self.check())
        (self.root / 'result.txt').write_bytes(b'wrong')
        self.worker.jobs['job-1']['state'] = 'completed'
        await self.runtime.tick()
        self.assertEqual(self.runtime.ledger.get(activity).status, ActivityStatus.FAILED)

    async def test_all_siblings_must_finish_and_failed_sibling_wins(self):
        self.runtime.bus.publish('task_requested', {'authorized': True, 'workspace': str(self.root),
                                                 'tasks': ['first', 'second']})
        activity = (await self.runtime.tick())['results'][0]['activity_id']
        self.worker.jobs['job-1']['state'] = 'completed'
        await self.runtime.tick()
        self.assertEqual(self.runtime.ledger.get(activity).status, ActivityStatus.RUNNING)
        # An evicted completed worker must retain its recorded terminal state.
        del self.worker.jobs['job-1']
        self.worker.jobs['job-2']['state'] = 'failed'
        await self.runtime.tick()
        self.assertEqual(self.runtime.ledger.get(activity).status, ActivityStatus.FAILED)

    async def test_restart_marks_lost_workers_interrupted_without_redispatch(self):
        activity = await self.launch()
        other = FakeOrchestrator()
        restarted = ProactiveRuntime(self.root / 'state', other)
        await restarted.tick()
        self.assertEqual(restarted.ledger.get(activity).status, ActivityStatus.INTERRUPTED)
        self.assertEqual(other.calls, [])

    async def test_restart_can_reconcile_known_workers(self):
        activity = await self.launch()
        restarted = ProactiveRuntime(self.root / 'state', self.worker)
        self.worker.jobs['job-1']['state'] = 'completed'
        await restarted.tick()
        self.assertEqual(restarted.ledger.get(activity).status, ActivityStatus.UNVERIFIED)

    async def test_partial_dispatch_failure_cancels_launched_worker(self):
        original = self.worker.delegate
        def fail_second(*args):
            if self.worker.calls:
                raise RuntimeError('no capacity')
            return original(*args)
        self.worker.delegate = fail_second
        self.runtime.bus.publish('task_requested', {'authorized': True, 'workspace': str(self.root),
                                                  'tasks': ['first', 'second']})
        result = await self.runtime.tick()
        self.assertEqual(result['results'][0]['status'], 'failed')
        self.assertEqual(self.worker.jobs['job-1']['state'], 'cancelled')

    async def test_unapproved_and_nonboolean_authorization(self):
        self.runtime.enqueue('Do work', str(self.root))
        self.assertEqual((await self.runtime.tick())['results'][0]['status'], 'approval_required')
        with self.assertRaises(ValueError):
            self.runtime.enqueue('Do work', str(self.root), authorized='false')
        self.assertEqual(self.worker.calls, [])

    async def test_stop_during_dispatch_prevents_next_worker(self):
        original = self.worker.delegate
        def stop_after_first(*args):
            result = original(*args)
            self.runtime.control.stop_all()
            return result
        self.worker.delegate = stop_after_first
        self.runtime.bus.publish('task_requested', {'authorized': True, 'workspace': str(self.root),
                                                  'tasks': ['first', 'second']})
        await self.runtime.tick()
        self.assertEqual(len(self.worker.calls), 1)
        self.assertEqual(self.worker.jobs['job-1']['state'], 'cancelled')
        self.assertEqual(self.runtime.status()['status'], 'stopped')


class ArtifactVerificationTests(unittest.TestCase):
    def test_rejects_traversal_symlinks_missing_files_and_fifos(self):
        import os
        digest = hashlib.sha256(b'ok').hexdigest()
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            (p / 'real').write_bytes(b'ok')
            (p / 'link').symlink_to(p / 'real')
            (p / 'dirlink').symlink_to(p, target_is_directory=True)
            os.mkfifo(p / 'pipe')
            for name in ('link', 'dirlink/real', 'missing', 'pipe'):
                self.assertEqual(verify_files(root, [{'path': name, 'sha256': digest}])['status'], 'failed')
            for name in ('../real', '/etc/passwd', '.', ''):
                with self.assertRaises(ValueError):
                    validate_checks([{'path': name, 'sha256': digest}])

    def test_explicit_approval_does_not_change_effect_or_bypass_pause(self):
        policy = ProactivePolicy()
        action = Action('delegate_agent', ActionEffect.UNKNOWN)
        self.assertTrue(policy.evaluate('one', action, 1, approved=True).allowed)
        self.assertEqual(action.effect, ActionEffect.UNKNOWN)
        policy.pause()
        self.assertFalse(policy.evaluate('two', action, 2, approved=True).allowed)

    def test_legacy_ledger_migration_preserves_rows_and_indexes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'activity.db'
            with sqlite3.connect(path) as db:
                db.execute("""CREATE TABLE proactive_activity (
                  id TEXT PRIMARY KEY, event_id TEXT, kind TEXT NOT NULL, summary TEXT NOT NULL,
                  details TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
                  ('observed','planned','running','succeeded','failed','cancelled')),
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
                db.execute("INSERT INTO proactive_activity VALUES ('old',NULL,'plan','Old task','{}','running','a','a')")
                db.execute('CREATE INDEX proactive_activity_created ON proactive_activity(created_at,id)')
            ledger = ActivityLedger(path)
            self.assertEqual(ledger.get('old').summary, 'Old task')
            ledger.transition('old', 'unverified')
            self.assertEqual(ActivityLedger(path).get('old').status, ActivityStatus.UNVERIFIED)
            with sqlite3.connect(path) as db:
                self.assertTrue(db.execute("SELECT name FROM sqlite_master WHERE name='proactive_activity_created'").fetchone())
