"""Global stop must cover queued teams, terminal setup and follow-up stages."""
import asyncio
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from orchestration.agent_orchestrator import AgentOrchestrator, OrchestrationError
from orchestration.desktop_execution import DesktopAgentOrchestrator
from proactive.runtime import ProactiveRuntime


class StopAllTests(unittest.IsolatedAsyncioTestCase):
    def runner(self):
        runner = AgentOrchestrator({'claude': sys.executable},
            lambda agent, executable, prompt: [executable, '-c', 'import time; time.sleep(30)'])
        self.addAsyncCleanup(runner.close)
        return runner

    def assignments(self):
        return [{'agent': 'claude', 'prompt': 'First stage'},
                {'agent': 'claude', 'prompt': 'Must not launch after stop'}]

    async def test_runtime_stop_cancels_team_before_first_job_and_resume_reopens_admission(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, runner)
            self.addAsyncCleanup(runtime.close)
            key = runner.delegate_team('Queued goal', self.assignments(), root)['team']['id']
            self.assertEqual((await runtime.stop_all())['status'], 'stopped')
            self.assertEqual(runner.teams[key]['state'], 'cancelled')
            self.assertEqual(runner.teams[key]['jobs'], [])
            with self.assertRaisesRegex(OrchestrationError, 'resume'):
                runner.delegate('claude', 'New task', root)
            with self.assertRaisesRegex(OrchestrationError, 'resume'):
                runner.delegate_team('New goal', self.assignments(), root)
            await runtime.call('resume')
            job = runner.delegate('claude', 'Authorized after resume', root)['job']['id']
            await runner.cancel(job)
            self.assertEqual(runner.jobs[job]['state'], 'cancelled')

    async def test_stop_during_running_stage_prevents_followups(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as root:
            key = runner.delegate_team('Running goal', self.assignments(), root)['team']['id']
            async def wait_for_process():
                while not runner.processes:
                    await asyncio.sleep(.005)
            await asyncio.wait_for(wait_for_process(), 2)
            await runner.stop_all()
            self.assertEqual(runner.teams[key]['state'], 'cancelled')
            self.assertEqual(len(runner.teams[key]['jobs']), 1)
            self.assertFalse(runner.processes)
            self.assertFalse(any(not task.done() for task in runner.workers.values()))

    async def test_persisted_stop_tick_cancels_queued_team(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, runner)
            self.addAsyncCleanup(runtime.close)
            await runtime.call(runtime.control.stop_all)
            key = runner.delegate_team('Pending goal', self.assignments(), root)['team']['id']
            self.assertEqual((await runtime.tick())['status'], 'stopped')
            self.assertEqual(runner.teams[key]['state'], 'cancelled')
            self.assertFalse(runner.processes)

    async def test_stop_during_terminal_setup_cleans_session_without_launching_agents(self):
        runner = DesktopAgentOrchestrator({'claude': '/fake/claude'})
        self.addAsyncCleanup(runner.close)
        setup_entered = asyncio.Event()

        async def tmux(*args):
            if args[0] == 'new-session':
                setup_entered.set()
                await asyncio.Event().wait()
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root, patch('shutil.which', return_value='/fake/tool'), \
             patch('orchestration.desktop_execution.asyncio.create_subprocess_exec', new=AsyncMock()) as launch:
            key = runner.delegate_team('Terminal goal', self.assignments(), root)['team']['id']
            await asyncio.wait_for(setup_entered.wait(), 1)
            await runner.stop_all()
            self.assertEqual(runner.teams[key]['state'], 'cancelled')
            self.assertEqual(runner.teams[key]['jobs'], [])
            launch.assert_not_awaited()
            self.assertIn(('kill-session', '-t', 'jarvis-' + key),
                          [call.args for call in runner._tmux.await_args_list])

    async def test_cancelled_stop_caller_does_not_abandon_cancellation(self):
        runner = self.runner()
        entered, release = asyncio.Event(), asyncio.Event()

        async def drain():
            entered.set()
            await release.wait()

        with patch.object(runner, '_cancel_all', side_effect=drain):
            caller = asyncio.create_task(runner.stop_all())
            await asyncio.wait_for(entered.wait(), 1)
            caller.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await caller
            self.assertFalse(runner._stop_task.done())
            with self.assertRaisesRegex(OrchestrationError, 'still stopping'):
                runner.resume()
            release.set()
            await runner._stop_task

    async def test_tmux_mutation_finishes_before_cancellation_cleanup(self):
        runner = DesktopAgentOrchestrator({})
        entered, release = asyncio.Event(), asyncio.Event()
        attempts = 0

        async def communicate():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                entered.set()
                await asyncio.Event().wait()
            await release.wait()
            return b'%1', b''

        process = AsyncMock()
        process.returncode = 0
        process.communicate.side_effect = communicate
        with patch('orchestration.desktop_execution.asyncio.create_subprocess_exec', return_value=process):
            command = asyncio.create_task(runner._tmux('new-session'))
            await asyncio.wait_for(entered.wait(), 1)
            command.cancel()
            await asyncio.sleep(0)
            self.assertFalse(command.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await command
        self.assertEqual(attempts, 2)
