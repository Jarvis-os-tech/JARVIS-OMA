"""Process lifecycle tests use local Python stubs, never cloud agents."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agent_orchestrator import AGENTS, AgentOrchestrator, OrchestrationError, command_for
from skills import DesktopSkills
from agent import LiveVoice


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def runner(self, code):
        runner = AgentOrchestrator({name: sys.executable for name in AGENTS},
            lambda agent, executable, prompt: [executable, '-u', '-c', code])
        self.addAsyncCleanup(runner.close)
        return runner

    async def test_real_process_output_completion_and_skill_routing(self):
        runner = self.runner("print('task completed'); print('x' * 70000)")
        with tempfile.TemporaryDirectory() as directory:
            skills = DesktopSkills()
            skills._agent_orchestrator = runner
            started = await skills.execute('delegate_agent', {
                'agent': 'hermes', 'prompt': 'Inspect this workspace', 'workspace': directory,
                'cost_profile': 'configured'})
            key = started['job']['id']
            await runner.workers[key]
            result = await skills.execute('check_agent_job', {'job_id': key})
            self.assertEqual(result['job']['state'], 'completed')
            self.assertEqual(result['job']['exit_code'], 0)
            self.assertTrue(result['job']['output_truncated'])
            self.assertLessEqual(len(result['job']['output']), 6000)
            self.assertEqual((await runner.events.get())['id'], key)

    async def test_overlapping_workspace_is_reserved_and_cancel_reaps_process(self):
        runner = self.runner("import time; print('started', flush=True); time.sleep(60)")
        with tempfile.TemporaryDirectory() as directory:
            nested = Path(directory) / 'nested'
            nested.mkdir()
            key = runner.delegate('omp', 'Work', directory)['job']['id']
            with self.assertRaisesRegex(OrchestrationError, 'reserved'):
                runner.delegate('codex', 'Conflicting work', str(nested))
            for _ in range(100):
                if key in runner.processes:
                    break
                await asyncio.sleep(.01)
            process = runner.processes[key]
            result = await runner.cancel(key)
            self.assertEqual(result['job']['state'], 'cancelled')
            self.assertIsNotNone(process.returncode)

    async def test_cancel_during_spawn_is_not_lost(self):
        runner = self.runner("import time; time.sleep(60)")
        original = asyncio.create_subprocess_exec
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return await original(*args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch('asyncio.create_subprocess_exec', delayed):
            key = runner.delegate('claude', 'Work', directory)['job']['id']
            await entered.wait()
            cancellation = asyncio.create_task(runner.cancel(key))
            await asyncio.sleep(0)
            release.set()
            result = await asyncio.wait_for(cancellation, 5)
            self.assertEqual(result['job']['state'], 'cancelled')
            self.assertNotIn(key, runner.processes)

    async def test_failed_process_and_invalid_agent(self):
        runner = self.runner("import sys; print('needs login', file=sys.stderr); sys.exit(2)")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OrchestrationError):
                runner.delegate('unknown', 'Task', directory)
            key = runner.delegate('gemini', 'Work', directory)['job']['id']
            await runner.workers[key]
            result = runner.status(key)['job']
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(result['exit_code'], 2)
            self.assertIn('needs login', result['output'])

    async def test_cli_builders_do_not_enable_permission_bypass(self):
        for name in AGENTS:
            args = command_for(name, '/installed/' + name, '--evil $(touch /tmp/nope)')
            self.assertEqual(args[0], '/installed/' + name)
            self.assertIn('--evil $(touch /tmp/nope)', args)
            self.assertFalse(set(args) & {'--yolo', '--auto-approve', '--dangerously-skip-permissions',
                                        '--dangerously-bypass-approvals-and-sandbox'})

    async def test_timeout_stops_the_worker(self):
        runner = self.runner("import time; time.sleep(60)")
        with tempfile.TemporaryDirectory() as directory:
            key = runner.delegate('codex', 'Slow task', directory, timeout_seconds=10)['job']['id']
            await asyncio.wait_for(runner.workers[key], 14)
            self.assertEqual(runner.status(key)['job']['state'], 'timed_out')
            self.assertIsNotNone(runner.status(key)['job']['exit_code'])

    async def test_completion_is_forwarded_to_voice_session(self):
        skills = DesktopSkills()
        voice = LiveVoice(None, skills=skills)
        session = AsyncMock()
        skills.agent_job_events.put_nowait({'id': 'test-id', 'agent': 'omp',
                                          'state': 'completed', 'workspace': '/tmp/test'})
        watcher = asyncio.create_task(voice.monitor_agents(session))
        sender = asyncio.create_task(voice.send_notifications(session))
        try:
            for _ in range(100):
                if session.send_client_content.called:
                    break
                await asyncio.sleep(.01)
            session.send_client_content.assert_awaited_once()
            sent = session.send_client_content.call_args.kwargs['turns'].parts[0].text
            self.assertIn('test-id', sent)
            self.assertIn('untrusted', sent)
        finally:
            watcher.cancel()
            sender.cancel()
            await asyncio.gather(watcher, sender, return_exceptions=True)

    async def test_team_runs_assignments_sequentially_in_shared_workspace(self):
        runner = self.runner("print('specialist completed')")
        with tempfile.TemporaryDirectory() as directory:
            result = runner.delegate_team('Ship the feature', [
                {'agent': 'codex', 'prompt': 'Implement it'},
                {'agent': 'claude', 'prompt': 'Review and fix it'},
            ], directory)
            team_id = result['team']['id']
            await runner.team_workers[team_id]
            team = runner.team_status(team_id)['team']
            self.assertEqual(team['state'], 'completed')
            self.assertEqual(len(team['jobs']), 2)
            first, second = (runner.jobs[key] for key in team['jobs'])
            self.assertEqual(first['state'], 'completed')
            self.assertEqual(second['state'], 'completed')
            self.assertIn('Shared team goal: Ship the feature', second['task_summary'])
