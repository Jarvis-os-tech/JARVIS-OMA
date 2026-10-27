import asyncio
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from orchestration.desktop_execution import DesktopAgentOrchestrator, interactive_command, CLAUDE_MODELS
from orchestration.agent_orchestrator import AGENTS, OrchestrationError


class DesktopExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_visible_agent_handoff_does_not_verify_broken_code(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
        with tempfile.TemporaryDirectory() as workspace:
            async def tmux(*args):
                if args[0] == 'capture-pane':
                    return '› Ask a question'
                if args[0] == 'display-message':
                    return '1' if args[-1] == '#{session_attached}' else '0 '
                if args[0] == 'send-keys' and args[-1] == 'Enter':
                    (Path(workspace) / 'result.py').write_text('def broken(\n')
                    Path(runner.jobs[key]['completion_file']).write_text(json.dumps({
                        'state': 'completed', 'summary': 'claimed success',
                    }))
                return ''

            runner._tmux = AsyncMock(side_effect=tmux)
            launcher = AsyncMock(returncode=None)
            with patch('shutil.which', return_value='/bin/tool'), patch(
                    'asyncio.create_subprocess_exec', return_value=launcher):
                key = runner.delegate('codex', 'Write a module', workspace)['job']['id']
                await runner.workers[key]
            job = runner.jobs[key]
            self.assertEqual(job['reported_state'], 'completed')
            self.assertEqual(job['state'], 'failed')
            self.assertFalse(job['verified'])
            self.assertEqual((await runner.events.get())['state'], 'failed')

    async def test_standalone_interactive_job_finishes_from_bounded_handoff_report(self):
        for reported_state in ('completed', 'failed'):
            with self.subTest(reported_state=reported_state):
                runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
                submitted_prompts = []

                async def tmux(*args):
                    if args[0] == 'capture-pane':
                        return '› Ask a question'
                    if args[0] == 'display-message':
                        if args[-1] == '#{session_attached}':
                            return '1'
                        return '0 '
                    if args[0] == 'send-keys' and args[-1] == 'Enter':
                        completion = Path(runner.jobs[key]['completion_file'])
                        completion.write_text(json.dumps({
                            'state': reported_state,
                            'summary': 'work finished',
                        }))
                    if args[0] == 'send-keys' and args[3:4] == ('-l',):
                        submitted_prompts.append(args[-1])
                    return ''

                runner._tmux = AsyncMock(side_effect=tmux)
                launcher = AsyncMock()
                launcher.returncode = None
                with tempfile.TemporaryDirectory() as workspace, patch(
                        'shutil.which', return_value='/bin/tool'), patch(
                        'asyncio.create_subprocess_exec', return_value=launcher):
                    key = runner.delegate('codex', 'Inspect the project', workspace)['job']['id']
                    await runner.workers[key]

                job = runner.jobs[key]
                self.assertEqual(job['state'], reported_state)
                self.assertEqual(job['completion_report']['summary'], 'work finished')
                self.assertEqual(job['completion_source'],
                                 'agent report; terminal process retired for safe workspace release')
                self.assertEqual(job['terminal_state'], 'closed')
                self.assertFalse(Path(job['completion_file']).parent.exists())
                self.assertTrue(any('JARVIS handoff protocol' in prompt
                                    for prompt in submitted_prompts))
                self.assertFalse(any(c.args[0] == 'kill-session'
                                     for c in runner._tmux.call_args_list))
                self.assertEqual(sum(c.args[0] == 'respawn-pane' and c.args[1] == '-k'
                                     for c in runner._tmux.call_args_list), 2)

    async def test_completion_report_does_not_release_workspace_if_process_retirement_fails(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})

        async def tmux(*args):
            if args[0] == 'capture-pane':
                return '› Ask a question'
            if args[0] == 'display-message':
                return '1' if args[-1] == '#{session_attached}' else '0 '
            if args[0] == 'send-keys' and args[-1] == 'Enter':
                Path(runner.jobs[key]['completion_file']).write_text(json.dumps({
                    'state': 'completed', 'summary': 'work finished',
                }))
            if (args[0] == 'respawn-pane' and args[1] == '-k'
                    and args[-1].startswith('printf')):
                raise OrchestrationError('agent process still alive')
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        launcher = AsyncMock()
        launcher.returncode = None
        with tempfile.TemporaryDirectory() as workspace, patch(
                'shutil.which', return_value='/bin/tool'), patch(
                'asyncio.create_subprocess_exec', return_value=launcher):
            key = runner.delegate('codex', 'Inspect the project', workspace)['job']['id']
            await runner.workers[key]
            self.assertEqual(runner.jobs[key]['state'], 'cleanup_failed')
            self.assertEqual(runner.jobs[key]['reported_state'], 'completed')
            with self.assertRaisesRegex(OrchestrationError, 'workspace is reserved'):
                runner.delegate('codex', 'Overlap', workspace)

    def test_completion_report_rejects_oversized_or_invalid_payloads(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
        with tempfile.TemporaryDirectory() as root:
            report = Path(root) / 'result.json'
            report.write_text('x' * 4097)
            self.assertIsNone(runner._read_completion_report(report))

            report.write_text(json.dumps({'state': 'completed'}))
            self.assertIsNone(runner._read_completion_report(report))

            report.write_text(json.dumps({'state': 'unknown', 'summary': 'done'}))
            self.assertIsNone(runner._read_completion_report(report))

            report.write_text(json.dumps({'state': 'completed', 'summary': 'done'}))
            self.assertEqual(runner._read_completion_report(report), {
                'state': 'completed', 'summary': 'done',
            })

    def test_completion_report_rejects_symlink_and_cleanup_does_not_follow_replaced_parent(self):
        runner = DesktopAgentOrchestrator({'codex': '/bin/codex'})
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            payload = root / 'payload.json'
            payload.write_text(json.dumps({'state': 'completed', 'summary': 'unsafe'}))
            link = root / 'result.json'
            link.symlink_to(payload)
            self.assertIsNone(runner._read_completion_report(link))

            job = {}
            completion = runner._completion_path(job)
            completion.write_text(json.dumps({'state': 'completed', 'summary': 'done'}))
            original_parent = completion.parent
            moved_parent = original_parent.with_name(original_parent.name + '-moved')
            original_parent.rename(moved_parent)
            decoy = root / 'decoy'
            decoy.mkdir()
            decoy_report = decoy / 'result.json'
            decoy_report.write_text('do not remove')
            original_parent.symlink_to(decoy, target_is_directory=True)
            try:
                runner._cleanup_completion_path(completion, job)
                self.assertEqual(decoy_report.read_text(), 'do not remove')
                self.assertFalse(job.get('completion_directory_fd'))
            finally:
                original_parent.unlink(missing_ok=True)
                shutil.rmtree(moved_parent, ignore_errors=True)

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
        prompt_index = next(i for i, call in enumerate(calls)
                            if call[-1].startswith(
                                'Task\nReview $(echo hello)\nSecond line'))
        self.assertGreater(prompt_index, capture_index[1])
        self.assertEqual(calls[prompt_index][2], 'jarvis-' + key)
        self.assertIn('Task\nReview $(echo hello)\nSecond line', calls[prompt_index][-1])
        self.assertIn('Work only in the supplied workspace: ' + workspace,
                      calls[prompt_index][-1])
        self.assertNotIn('SHARED JARVIS MEMORY', calls[prompt_index][-1])
        self.assertNotIn('Evidence-supported lessons', calls[prompt_index][-1])
        self.assertEqual(runner.jobs[key]['submission_state'], 'submitted')
        self.assertEqual(runner.jobs[key]['state'], 'completed')
        self.assertIn(('set-option', '-t', 'jarvis-' + key, 'status', 'off'), calls)
        launch_index = next(i for i, call in enumerate(calls) if call[0] == 'respawn-pane')
        attach_index = next(i for i, call in enumerate(calls) if call[-1] == '#{session_attached}')
        self.assertGreater(launch_index, attach_index)
        self.assertIn('COLORTERM=truecolor', calls[launch_index][-1])

    async def test_visible_tmux_execution_for_all_agents(self):
        for agent in AGENTS:
            with self.subTest(agent=agent):
                runner = DesktopAgentOrchestrator({agent: f'/bin/{agent}'})
                screens = iter(['Booting...', '❯ Ready for command'])
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
                    res = runner.delegate(agent, 'Do some task', workspace, visible=True)
                    key = res['job']['id']
                    self.assertEqual(res['job']['execution_mode'], 'visible')
                    self.assertEqual(res['job']['surface'], 'terminal')
                    await runner.workers[key]
                job = runner.status(key)['job']
                self.assertEqual(job['state'], 'completed')

    async def test_background_agent_uses_existing_supervised_runner(self):
        for agent in ('opencode', 'gemini', 'hermes', 'omp'):
            with self.subTest(agent=agent):
                runner = DesktopAgentOrchestrator(
                    {agent: sys.executable},
                    lambda name, executable, prompt: [executable, '-c', "print('delegated')"])
                with tempfile.TemporaryDirectory() as workspace:
                    result = runner.delegate(agent, 'Inspect this project', workspace, visible=False)
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

    def test_interactive_commands_all_supported_agents(self):
        expected_executables = {agent: f'/bin/{agent}' for agent in AGENTS}
        for agent, exe in expected_executables.items():
            cmd = interactive_command(agent, exe)
            self.assertEqual(cmd[0], exe)

    def test_discover_shows_visible_and_background_support(self):
        runner = DesktopAgentOrchestrator({agent: f'/bin/{agent}' for agent in AGENTS})
        with patch('shutil.which', return_value='/bin/tool'):
            info = runner.discover()
            self.assertTrue(info['desktop_execution']['available'])
            self.assertEqual(len(info['agents']), len(AGENTS))
            for agent_info in info['agents']:
                self.assertTrue(agent_info['visible_supported'])
                self.assertTrue(agent_info['background_supported'])
