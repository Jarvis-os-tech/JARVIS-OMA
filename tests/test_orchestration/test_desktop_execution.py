import asyncio
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from orchestration.desktop_execution import DesktopAgentOrchestrator, interactive_command
from orchestration.agent_orchestrator import OrchestrationError


class DesktopExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_targets_owned_pane_only_after_composer(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
        screens = iter(['Starting up', '› Ask a question'])
        dead = iter(['0 ', '1 0'])

        async def tmux(*args):
            if args[0] == 'capture-pane':
                return next(screens)
            if args[0] == 'display-message':
                if args[-1] == '#{session_attached}':
                    return '1'
                return next(dead)
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        launcher = AsyncMock()
        launcher.returncode = None
        with tempfile.TemporaryDirectory() as workspace, patch(
                'shutil.which', return_value='/bin/tool'), patch(
                'asyncio.create_subprocess_exec', return_value=launcher):
            key = runner.delegate('codex', 'Review $(echo hello)\nSecond line', workspace)['job']['id']
            await runner.workers[key]
        calls = [call.args for call in runner._tmux.call_args_list]
        capture_index = [i for i, call in enumerate(calls) if call[0] == 'capture-pane']
        prompt_index = next(i for i, call in enumerate(calls) if call[-1] == 'Review $(echo hello)\nSecond line')
        self.assertGreater(prompt_index, capture_index[1])
        self.assertEqual(calls[prompt_index][2], 'jarvis-' + key)
        self.assertEqual(runner.jobs[key]['submission_state'], 'submitted')
        self.assertEqual(runner.jobs[key]['state'], 'completed')
        self.assertIn(('set-option', '-t', 'jarvis-' + key, 'status', 'off'), calls)
        launch_index = next(i for i, call in enumerate(calls) if call[0] == 'respawn-pane')
        attach_index = next(i for i, call in enumerate(calls) if call[-1] == '#{session_attached}')
        self.assertGreater(launch_index, attach_index)
        self.assertIn('COLORTERM=truecolor', calls[launch_index][-1])

    async def test_background_agent_uses_existing_supervised_runner(self):
        for agent in ('opencode', 'gemini', 'hermes', 'omp'):
            with self.subTest(agent=agent):
                runner = DesktopAgentOrchestrator(
                    {agent: sys.executable},
                    lambda name, executable, prompt: [executable, '-c', "print('delegated')"])
                with tempfile.TemporaryDirectory() as workspace:
                    result = runner.delegate(agent, 'Inspect this project', workspace)
                    key = result['job']['id']
                    await runner.workers[key]
                job = runner.status(key)['job']
                self.assertEqual(job['execution_mode'], 'background')
                self.assertEqual(job['state'], 'completed')
                self.assertIn('delegated', job['output'])
                self.assertEqual(job['surface'], 'process')

    async def test_unknown_agents_and_terminal_controls_fail_before_launch(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
        with self.assertRaises(OrchestrationError):
            runner.delegate('unknown', 'Task', '/tmp')
        with self.assertRaises(OrchestrationError):
            runner.delegate('codex', '\x1b[201~', '/tmp')
        self.assertFalse(runner.jobs)

    def test_native_automatic_review(self):
        self.assertIn('--approve-for-me', interactive_command('codex', 'codex'))
        self.assertEqual(interactive_command('claude', 'claude')[-1], 'auto')

    def test_omniroute_model_selection(self):
        for kind, model in [('coding', 'auto/best-coding'),
                            ('reasoning', 'auto/best-reasoning'),
                            ('fast', 'auto/best-fast')]:
            command = interactive_command('claude', 'claude', kind)
            self.assertEqual(command[command.index('--model') + 1], model)
        self.assertIn('auto/best-coding', interactive_command('claude', 'claude'))
        with self.assertRaises(OrchestrationError):
            interactive_command('claude', 'claude', 'sonnet')
