"""Process lifecycle tests use local Python stubs, never cloud agents."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from agent_orchestrator import AGENTS, AgentOrchestrator, OrchestrationError, command_for, computer_command
from skills import DesktopSkills
from agent import LiveVoice


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_computer_command_keeps_permissions_and_toolset(self):
        args = computer_command('/installed/hermes', '--evil $(touch /tmp/nope)')
        self.assertEqual(args[:5], ['/installed/hermes', 'chat', '-t', 'computer_use', '-q'])
        self.assertNotIn('-z', args)
        self.assertNotIn('--yolo', args)
        self.assertIn('--evil $(touch /tmp/nope)', args[-1])

    async def test_computer_task_routing_global_reservation_and_completion(self):
        runner = self.runner("print('ordinary agent')")
        skills = DesktopSkills()
        skills._agent_orchestrator = runner
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with patch.object(runner, 'computer_status', AsyncMock(return_value={'ready': True})), \
                 patch('agent_orchestrator.computer_command', return_value=[sys.executable, '-u', '-c', "print('CUA observed'); import time; time.sleep(.1)"]):
                # Route through the actual adapter, independently of host availability.
                result = await skills._adapter_hermes_computer_task('Inspect app', first)
                key = result['job']['id']
                self.assertTrue(result['job']['computer_use'])
                with self.assertRaisesRegex(OrchestrationError, 'computer task'):
                    runner.delegate_computer('Conflicting UI work', second)
                await runner.workers[key]
                self.assertIn('CUA observed', runner.status(key)['job']['output'])
                self.assertEqual(runner.status(key)['job']['state'], 'completed')

    async def test_computer_task_not_started_when_backend_unready(self):
        skills = DesktopSkills()
        runner = self.runner("print('must not run')")
        skills._agent_orchestrator = runner
        readiness = {'ready': False, 'status': 'warning', 'summary': 'needs setup'}
        with patch.object(runner, 'computer_status', AsyncMock(return_value=readiness)):
            self.assertEqual(await skills._adapter_hermes_computer_task('Inspect app', '/tmp'), readiness)
        self.assertEqual(runner.jobs, {})

    async def test_computer_status_missing_executable(self):
        runner = AgentOrchestrator({'hermes': None})
        self.addAsyncCleanup(runner.close)
        self.assertFalse((await runner.computer_status())['ready'])

    async def test_computer_status_valid_and_failed_payloads(self):
        runner = self.runner('')
        for code, output, ready in [(0, b'{"ready":true,"checks":[]}', True),
                                    (1, b'{"ready":true}', False),
                                    (0, b'not json', False),
                                    (0, b'{"ready":"false"}', False)]:
            process = AsyncMock()
            process.returncode = code
            process.communicate.return_value = (output, b'')
            with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=process)):
                self.assertEqual((await runner.computer_status())['ready'], ready)

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
                'agent': 'hermes', 'prompt': 'Inspect this workspace', 'workspace': directory})
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
            self.assertTrue(any(item.startswith('Task delegated by JARVIS.') for item in args))
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
            await asyncio.gather(watcher, return_exceptions=True)
