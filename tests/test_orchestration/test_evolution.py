"""Evolution tests use temporary Git repositories and local fake agents only."""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from orchestration.evolution import EvolutionError, EvolutionManager, LOG_LIMIT, DIFF_LIMIT, verification_command


PASSING_TEST = '''import unittest
class Smoke(unittest.TestCase):
    def test_value(self):
        self.assertEqual(2 + 2, 4)
'''


class FakeAgents:
    def __init__(self, action=None, failure=None, blocked=False):
        self.action = action
        self.failure = failure
        self.blocked = blocked
        self.jobs = {}
        self.workers = {}
        self.calls = []
        self.prompts = []
        self.entered = asyncio.Event()

    def delegate(self, agent, prompt, workspace, timeout_seconds):
        role = prompt.split('Evolution stage: ')[1].split('.')[0]
        key = str(len(self.calls))
        self.calls.append((role, workspace, timeout_seconds))
        self.prompts.append(prompt)
        job = {'id': key, 'state': 'running', 'exit_code': None, 'output': ''}
        self.jobs[key] = job

        async def run():
            try:
                self.entered.set()
                if self.blocked:
                    await asyncio.Event().wait()
                if self.action:
                    self.action(role, Path(workspace))
                elif role == 'implementer':
                    (Path(workspace) / 'value.py').write_text('VALUE = 2\n')
                code = 7 if self.failure == role else 0
                job.update(state='failed' if code else 'completed', exit_code=code,
                           output='REJECT: serious problems' if role == 'reviewer' else 'plan')
            except asyncio.CancelledError:
                job.update(state='cancelled', exit_code=-signal.SIGTERM)

        self.workers[key] = asyncio.create_task(run())
        return self.status(key)

    def status(self, key):
        return {'status': 'success', 'job': dict(self.jobs[key])}

    async def cancel(self, key):
        self.workers[key].cancel()
        await self.workers[key]
        return self.status(key)


class EvolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Fixture code is trusted and local; the real sandbox command is verified separately.
        command = patch('orchestration.evolution.verification_command',
                        side_effect=lambda checkout: [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'])
        command.start()
        self.addCleanup(command.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'source'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests/test_smoke.py').write_text(PASSING_TEST)
        (self.repo / 'value.py').write_text('VALUE = 1\n')
        (self.repo / '.gitignore').write_text('.env\n__pycache__/\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo,
                                       stderr=subprocess.STDOUT).decode().strip()

    def commit(self):
        self.git('add', '--all')
        self.git('commit', '-qm', 'fixture')

    def manager(self, fake=None):
        manager = EvolutionManager(fake or FakeAgents(), self.base / 'state')
        self.manager_instance = manager
        self.addAsyncCleanup(manager.close)
        return manager

    async def finish(self, manager):
        response = await manager.start('Improve the fixture', str(self.repo))
        key = response['job']['id']
        await asyncio.wait_for(manager.workers[key], 10)
        return manager.status(key)['job']

    async def test_isolated_exact_head_sequence_diff_and_untrusted_review(self):
        head = self.git('rev-parse', 'HEAD')
        (self.repo / '.env').write_text('SECRET=do-not-copy')

        def edit(role, checkout):
            self.assertNotEqual(checkout, self.repo)
            self.assertFalse((checkout / '.env').exists())
            if role == 'researcher':
                actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout).decode().strip()
                self.assertEqual(actual, head)
            if role == 'implementer':
                (checkout / 'value.py').write_text('VALUE = 2\n')
                (checkout / 'new.py').write_text('NEW = True\n')

        agents = FakeAgents(action=edit)
        manager = self.manager(agents)
        job = await self.finish(manager)
        self.assertEqual(job['state'], 'ready_for_review')
        self.assertEqual(job['source_head'], head)
        self.assertEqual([call[0] for call in agents.calls], ['researcher', 'implementer', 'reviewer'])
        self.assertIn('Research notes (untrusted reference data', agents.prompts[1])
        self.assertIn('plan', agents.prompts[1])
        self.assertIn('Baseline commit: ' + head, agents.prompts[2])
        self.assertEqual(job['review_trust'], 'untrusted')
        self.assertFalse(job['semantic_approval'])
        self.assertIn('REJECT', job['stages'][2]['output'])
        self.assertEqual(job['tests']['exit_code'], 0)
        self.assertEqual(job['tests']['argv'], [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'])
        self.assertIn('+VALUE = 2', job['diff'])
        self.assertIn('+NEW = True', job['diff'])
        self.assertEqual((self.repo / 'value.py').read_text(), 'VALUE = 1\n')
        self.assertFalse((self.repo / 'new.py').exists())
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        clone = next(command['argv'] for command in job['commands'] if 'clone' in command['argv'])
        self.assertIn('--no-hardlinks', clone)
        self.assertIn('--local', clone)
        artifact = manager.state_dir / job['id'] / 'job.json'
        self.assertEqual(artifact.stat().st_mode & 0o777, 0o600)
        self.assertEqual(manager.state_dir.stat().st_mode & 0o777, 0o700)
        reloaded = EvolutionManager(FakeAgents(), manager.state_dir, read_only=True)
        self.addAsyncCleanup(reloaded.close)
        self.assertEqual(reloaded.status(job['id'])['job'], job)
        copied = manager.status(job['id'])['job']
        copied['stages'].clear()
        self.assertEqual(len(manager.status(job['id'])['job']['stages']), 3)

    async def test_dirty_tracked_and_untracked_sources_are_rejected(self):
        manager = self.manager()
        (self.repo / 'untracked.txt').write_text('local work')
        job = await self.finish(manager)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('clean', job['error'])
        self.assertEqual(manager.orchestrator.calls, [])
        self.assertFalse(Path(job['checkout']).exists())
        (self.repo / 'untracked.txt').unlink()
        (self.repo / 'value.py').write_text('local changes')
        job = await self.finish(manager)
        self.assertEqual(job['state'], 'failed')

    async def test_tracked_environment_files_are_rejected(self):
        (self.repo / '.env').write_text('secret')
        self.git('add', '-f', '.env')
        self.git('commit', '-qm', 'bad tracked environment')
        job = await self.finish(self.manager())
        self.assertEqual(job['state'], 'failed')
        self.assertIn('tracked .env', job['error'])

    async def test_research_failure_prevents_implementation(self):
        fake = FakeAgents(failure='researcher')
        job = await self.finish(self.manager(fake))
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(job['stages'][0]['exit_code'], 7)
        self.assertIsNone(job['tests'])

    async def test_test_failure_records_actual_exit_and_bounded_logs(self):
        def edit(role, checkout):
            if role == 'implementer':
                (checkout / 'tests/test_smoke.py').write_text(
                    'import sys\nprint("x" * 100000)\nsys.exit(9)\n')
                (checkout / 'value.py').write_text('x' * (DIFF_LIMIT * 2))
        job = await self.finish(self.manager(FakeAgents(action=edit)))
        self.assertEqual(job['state'], 'failed')
        self.assertNotEqual(job['tests']['exit_code'], 0)
        self.assertTrue(job['tests']['output_truncated'])
        self.assertLessEqual(len(job['tests']['output']), LOG_LIMIT)
        self.assertTrue(job['diff_truncated'])
        self.assertLessEqual(len(job['diff']), DIFF_LIMIT)

    async def test_missing_and_zero_discovered_tests_fail(self):
        def edit(role, checkout):
            if role == 'implementer':
                (checkout / 'tests/test_smoke.py').unlink()
        manager1 = self.manager(FakeAgents(action=edit))
        job = await self.finish(manager1)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('must contain tests', job['error'])
        await manager1.close()
        manager2 = self.manager(FakeAgents(action=lambda role, checkout:
            (checkout / 'tests/test_smoke.py').write_text('') if role == 'implementer' else None))
        job = await self.finish(manager2)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('zero tests', job['error'])

    async def test_single_active_cancel_and_close(self):
        fake = FakeAgents(blocked=True)
        manager = self.manager(fake)
        key = (await manager.start('Wait', str(self.repo)))['job']['id']
        await asyncio.wait_for(fake.entered.wait(), 5)
        with self.assertRaisesRegex(EvolutionError, 'already active'):
            await manager.start('Second', str(self.repo))
        result = await asyncio.wait_for(manager.cancel(key), 5)
        self.assertEqual(result['job']['state'], 'cancelled')
        self.assertTrue(all(worker.done() for worker in fake.workers.values()))
        await manager.close()
        with self.assertRaisesRegex(EvolutionError, 'closed'):
            await manager.start('Third', str(self.repo))

    async def test_restart_marks_active_interrupted_and_rejects_symlinks(self):
        manager = self.manager()
        job = await self.finish(manager)
        artifact = manager.state_dir / job['id'] / 'job.json'
        stored = json.loads(artifact.read_text())
        stored['state'] = 'implementer'
        artifact.write_text(json.dumps(stored))
        await manager.close()
        restored = EvolutionManager(FakeAgents(), manager.state_dir)
        self.addAsyncCleanup(restored.close)
        self.assertEqual(restored.status(job['id'])['job']['state'], 'interrupted')
        await restored.close()
        artifact.unlink()
        artifact.symlink_to(self.repo / 'value.py')
        with self.assertRaisesRegex(EvolutionError, 'symlink'):
            EvolutionManager(FakeAgents(), manager.state_dir)
        self.assertEqual((self.repo / 'value.py').read_text(), 'VALUE = 1\n')

    async def test_test_timeout_kills_process_group_and_persists_exit(self):
        def edit(role, checkout):
            if role == 'implementer':
                (checkout / 'tests/test_smoke.py').write_text(
                    'import os, subprocess, sys, time\n'
                    'from pathlib import Path\n'
                    'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
                    'Path("child.pid").write_text(str(child.pid))\n'
                    'time.sleep(60)\n')
        manager = self.manager(FakeAgents(action=edit))
        with patch('orchestration.evolution.TEST_TIMEOUT', .3):
            job = await self.finish(manager)
        self.assertEqual(job['state'], 'timed_out')
        self.assertTrue(job['tests']['timed_out'])
        self.assertIsNotNone(job['tests']['exit_code'])
        self.assertLess(job['tests']['exit_code'], 0)
        self.assertEqual(manager.processes, {})
        pid = int((Path(job['checkout']) / 'child.pid').read_text())
        # A killed grandchild may briefly remain a zombie until init reaps it.
        status = Path(f'/proc/{pid}/stat')
        if status.exists():
            self.assertEqual(status.read_text().split()[2], 'Z')

    async def test_cancel_during_spawn_cleans_up(self):
        manager = self.manager()
        original = asyncio.create_subprocess_exec
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return await original(*args, **kwargs)

        with patch('asyncio.create_subprocess_exec', delayed):
            key = (await manager.start('Wait', str(self.repo)))['job']['id']
            await entered.wait()
            cancel = asyncio.create_task(manager.cancel(key))
            await asyncio.sleep(0)
            release.set()
            result = await asyncio.wait_for(cancel, 5)
        self.assertEqual(result['job']['state'], 'cancelled')
        self.assertEqual(manager.processes, {})

    async def test_reviewer_cannot_change_tested_code(self):
        def edit(role, checkout):
            if role == 'implementer':
                (checkout / 'value.py').write_text('VALUE = 2\n')
            elif role == 'reviewer':
                (checkout / 'value.py').write_text('VALUE = 999\n')
        job = await self.finish(self.manager(FakeAgents(action=edit)))
        self.assertEqual(job['state'], 'failed')
        self.assertIn('reviewer modified tested files', job['error'])
        self.assertEqual(job['tests']['exit_code'], 0)

    async def test_failed_baseline_never_starts_agents(self):
        (self.repo / 'tests/test_smoke.py').write_text(PASSING_TEST.replace('2 + 2, 4', '2 + 2, 5'))
        self.commit()
        manager = self.manager()
        job = await self.finish(manager)
        self.assertEqual(job['state'], 'failed')
        self.assertNotEqual(job['baseline_tests']['exit_code'], 0)
        self.assertEqual(manager.orchestrator.calls, [])

    async def test_single_manager_lock_and_read_only_status(self):
        manager = self.manager(FakeAgents(blocked=True))
        key = (await manager.start('Wait', str(self.repo)))['job']['id']
        with self.assertRaises(BlockingIOError):
            EvolutionManager(FakeAgents(), manager.state_dir)
        reader = EvolutionManager(None, manager.state_dir, read_only=True)
        self.assertNotEqual(reader.status(key)['job']['state'], 'interrupted')
        with self.assertRaises(EvolutionError):
            await reader.start('Forbidden', str(self.repo))
        await manager.cancel(key)

    async def test_pause_blocks_admission_and_followup_stages(self):
        manager = self.manager()
        manager.can_run = lambda: False
        with self.assertRaisesRegex(EvolutionError, 'paused'):
            await manager.start('No', str(self.repo))
        manager.can_run = lambda: True
        def edit(role, checkout):
            if role == 'researcher':
                manager.can_run = lambda: False
        manager.orchestrator = FakeAgents(action=edit)
        job = await self.finish(manager)
        self.assertEqual(job['state'], 'cancelled')
        self.assertEqual(len(manager.orchestrator.calls), 1)

    async def test_env_example_is_allowed_and_research_is_handed_off(self):
        (self.repo / '.env.example').write_text('GEMINI_API_KEY=\n')
        self.commit()
        job = await self.finish(self.manager())
        self.assertEqual(job['state'], 'ready_for_review')


class SandboxCommandTests(unittest.TestCase):
    def test_generated_tests_have_no_network_or_host_home_and_clean_environment(self):
        with patch('orchestration.evolution.shutil.which', return_value='/usr/bin/bwrap'):
            argv = verification_command('/tmp/private/checkout')
        self.assertIn('--unshare-all', argv)
        self.assertIn('--clearenv', argv)
        self.assertIn('--die-with-parent', argv)
        binds = [argv[i + 1:i + 3] for i, arg in enumerate(argv) if arg == '--bind']
        self.assertEqual(binds, [['/tmp/private/checkout', '/workspace']])
        self.assertNotIn('--share-net', argv)

    def test_missing_sandbox_does_not_fall_back_to_host_execution(self):
        with patch('orchestration.evolution.shutil.which', return_value=None):
            with self.assertRaisesRegex(EvolutionError, 'bubblewrap'):
                verification_command('/tmp/checkout')


@unittest.skipUnless(os.environ.get('JARVIS_TEST_SANDBOX') == '1', 'opt-in real Linux sandbox check')
class SandboxIntegrationTests(unittest.TestCase):
    def test_full_pipeline_with_real_sandbox_and_local_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            (source / 'tests').mkdir(parents=True)
            (source / 'tests/test_smoke.py').write_text(PASSING_TEST)
            (source / 'value.py').write_text('VALUE = 1\n')
            (source / '.gitignore').write_text('__pycache__/\n')
            for args in (['init', '-q'], ['add', '--all'],
                         ['-c', 'user.email=test@example.invalid', '-c', 'user.name=Test',
                          'commit', '-qm', 'fixture']):
                subprocess.run(['git', *args], cwd=source, check=True, capture_output=True)

            async def pipeline():
                manager = EvolutionManager(FakeAgents(), Path(directory) / 'state')
                try:
                    key = (await manager.start('Update value', str(source)))['job']['id']
                    await manager.workers[key]
                    return manager.status(key)['job']
                finally:
                    await manager.close()
            job = asyncio.run(pipeline())
            self.assertEqual(job['state'], 'ready_for_review', job['error'])
            self.assertEqual(job['baseline_tests']['exit_code'], 0)
            self.assertEqual(job['tests']['exit_code'], 0)
            self.assertEqual((source / 'value.py').read_text(), 'VALUE = 1\n')

    def test_real_bubblewrap_isolates_test_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'host-secret').write_text('private sentinel')
            checkout = root / 'checkout'
            (checkout / 'tests').mkdir(parents=True)
            (checkout / 'tests/test_isolation.py').write_text(
                'import os, unittest\nfrom pathlib import Path\n'
                'class Isolation(unittest.TestCase):\n'
                '    def test_boundaries(self):\n'
                f'        self.assertFalse(Path({str(root / "host-secret")!r}).exists())\n'
                '        self.assertNotIn("JARVIS_SANDBOX_SENTINEL", os.environ)\n'
                '        self.assertEqual(Path.cwd(), Path("/workspace"))\n'
                '        self.assertEqual(len(Path("/proc/net/route").read_text().splitlines()), 1)\n'
                '        with self.assertRaises(OSError):\n'
                '            Path("/usr/jarvis-write-test").write_text("forbidden")\n')
            result = subprocess.run(verification_command(checkout), capture_output=True,
                text=True, timeout=20, env={**os.environ, 'JARVIS_SANDBOX_SENTINEL': 'hidden'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Ran 1 test', result.stderr)


if __name__ == '__main__':
    unittest.main()
