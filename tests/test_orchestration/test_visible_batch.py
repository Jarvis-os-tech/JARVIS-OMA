import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from orchestration.desktop_execution import DesktopAgentOrchestrator, visible_batch_command, native_task_command
from orchestration.agent_orchestrator import OrchestrationError, TERMINAL
from orchestration.personas import software_assignments


class VisibleBatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_completion_retires_agent_process_before_releasing_workspace(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})

        async def tmux(*args):
            if args[0] == 'capture-pane':
                Path(runner.jobs['job']['completion_file']).write_text(json.dumps({
                    'state': 'completed', 'summary': 'done',
                }))
                return 'finished'
            if args[0] == 'display-message':
                return '0'
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root:
            runner.jobs['job'] = {
                'id': 'job', 'agent': 'claude', 'workspace': root, 'state': 'queued',
                'task_summary': 'test', 'updated_at': '', 'output': '',
                'output_truncated': False, 'cancel_requested': False,
                'shared_pane': '%1', 'batch': False, 'model': None, 'yolo': False,
            }
            await runner._run_shared_pane('job', 'Inspect', 10)

        self.assertEqual(runner.jobs['job']['state'], 'completed')
        self.assertEqual(runner.jobs['job']['terminal_state'], 'closed')
        retire = [c.args for c in runner._tmux.call_args_list
                  if c.args[0] == 'respawn-pane' and c.args[-1].startswith('printf')]
        self.assertEqual(len(retire), 1)
        self.assertEqual(retire[0][3], '%1')

    async def test_team_preflight_rejects_incompatible_later_stage_before_launch(self):
        runner = DesktopAgentOrchestrator({
            'claude': '/bin/claude', 'opencode': '/bin/opencode',
        })
        assignments = [
            {'agent': 'claude', 'prompt': 'Implement', 'visible': True, 'batch': False},
            {'agent': 'opencode', 'prompt': 'Test', 'visible': True, 'batch': False,
             'model': 'provider/small'},
        ]

        with tempfile.TemporaryDirectory() as root, patch('shutil.which', return_value='/bin/tool'):
            with self.assertRaisesRegex(OrchestrationError, 'per-task overrides require batch mode'):
                runner.delegate_team('Build', assignments, root)

        self.assertFalse(runner.teams)
        self.assertFalse(runner.team_workers)
        runner._tmux = AsyncMock()
        await asyncio.sleep(0)
        runner._tmux.assert_not_awaited()

    async def test_budget_opencode_plan_preflights_as_batch_before_team_creation(self):
        from orchestration.model_policy import apply_model_policy

        runner = DesktopAgentOrchestrator({
            'claude': '/bin/claude', 'opencode': '/bin/opencode',
        })
        assignments = apply_model_policy([
            {'agent': 'claude', 'prompt': 'Implement', 'visible': True, 'batch': False},
            {'agent': 'opencode', 'prompt': 'Test', 'visible': True, 'batch': False},
        ], environ={
            'JARVIS_BUDGET_MODEL_CLAUDE': 'haiku',
            'JARVIS_BUDGET_MODEL_OPENCODE': 'provider/small',
        })

        with tempfile.TemporaryDirectory() as root, patch('shutil.which', return_value='/bin/tool'):
            result = runner.delegate_team('Build', assignments, root)
            key = result['team']['id']
            runner.team_workers[key].cancel()
            await asyncio.gather(runner.team_workers[key], return_exceptions=True)

        self.assertTrue(runner.teams[key]['assignments'][1]['batch'])

    async def test_shared_pane_monitor_failure_reaps_pane_before_releasing_workspace(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})
        cleanup_states = []

        async def tmux(*args):
            if args[0] == 'respawn-pane':
                return ''
            if args[0] == 'display-message':
                return '1'
            if args[0] == 'capture-pane':
                raise OrchestrationError('capture failed')
            if args[0] == 'kill-pane':
                cleanup_states.append(runner.jobs['job']['state'])
                return ''
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        runner.jobs['job'] = {
            'id': 'job', 'agent': 'claude', 'workspace': '/tmp', 'state': 'queued',
            'task_summary': 'test', 'updated_at': '', 'output': '',
            'output_truncated': False, 'cancel_requested': False,
            'shared_pane': '%1', 'batch': True, 'model': None, 'yolo': False,
        }

        await runner._run_shared_pane('job', 'Inspect', 10)

        self.assertEqual(cleanup_states, ['running'])
        self.assertEqual(runner.jobs['job']['state'], 'failed')
        self.assertEqual(sum(c.args[0] == 'kill-pane' for c in runner._tmux.call_args_list), 1)
        event = runner.events.get_nowait()
        self.assertEqual((event['id'], event['state']), ('job', 'failed'))
        self.assertTrue(runner.events.empty())

    async def test_partial_team_setup_failure_reaps_session_and_emits_terminal_event(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})

        async def tmux(*args):
            if args[0] == 'new-session':
                return '%1\n'
            if args[0] == 'set-option':
                raise OrchestrationError('setup failed')
            if args[0] == 'kill-session':
                return ''
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root:
            assignments = [{
                'agent': 'claude', 'prompt': 'Test', 'visible': True,
                'batch': True, 'yolo': False,
            }]
            key = runner.delegate_team('Smoke test', assignments, root)['team']['id']
            await runner.team_workers[key]

        team = runner.teams[key]
        self.assertEqual(team['state'], 'failed')
        self.assertIn(team['state'], TERMINAL)
        self.assertEqual(sum(c.args[:3] == ('kill-session', '-t', 'jarvis-' + key)
                             for c in runner._tmux.call_args_list), 1)
        event = runner.events.get_nowait()
        self.assertEqual(event, {
            'kind': 'team', 'id': key, 'state': 'failed',
            'verified': False, 'completion_kind': None,
            'workspace': team['workspace'],
        })
        self.assertTrue(runner.events.empty())

    async def test_partial_team_setup_cleanup_failure_keeps_workspace_reserved(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})

        async def tmux(*args):
            if args[0] == 'new-session':
                return '%1\n'
            if args[0] == 'set-option':
                raise OrchestrationError('setup failed')
            if args[0] == 'kill-session':
                raise OrchestrationError('session still alive')
            return ''

        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root:
            assignments = [{
                'agent': 'claude', 'prompt': 'Test', 'visible': True,
                'batch': True, 'yolo': False,
            }]
            key = runner.delegate_team('Smoke test', assignments, root)['team']['id']
            await runner.team_workers[key]
            self.assertEqual(runner.teams[key]['state'], 'cleanup_failed')
            self.assertEqual(runner.teams[key]['failure_state'], 'failed')
            with self.assertRaisesRegex(OrchestrationError, 'workspace is reserved'):
                runner.delegate('claude', 'Overlap', root)

        self.assertEqual(sum(c.args[:3] == ('kill-session', '-t', 'jarvis-' + key)
                             for c in runner._tmux.call_args_list), 2)
        event = runner.events.get_nowait()
        self.assertEqual(event['state'], 'cleanup_failed')

    async def test_unconfirmed_pane_cleanup_keeps_workspace_reserved(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})

        async def tmux(*args):
            if args[0] == 'capture-pane':
                raise OrchestrationError('capture failed')
            if args[0] == 'kill-pane':
                raise OrchestrationError('pane still running')
            return '1' if args[0] == 'display-message' else ''

        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root:
            runner.jobs['job'] = {
                'id': 'job', 'agent': 'claude', 'workspace': root, 'state': 'queued',
                'task_summary': 'test', 'updated_at': '', 'output': '',
                'output_truncated': False, 'cancel_requested': False,
                'shared_pane': '%1', 'batch': True, 'model': None, 'yolo': False,
            }
            await runner._run_shared_pane('job', 'Inspect', 10)
            self.assertEqual(runner.jobs['job']['state'], 'cleanup_failed')
            with patch('shutil.which', return_value='/bin/tool'):
                with self.assertRaisesRegex(OrchestrationError, 'workspace is reserved'):
                    runner.delegate('claude', 'Overlap', root)

    async def test_team_shares_one_session_and_four_distinct_panes(self):
        runner = DesktopAgentOrchestrator({'hermes': '/bin/hermes', 'claude': '/bin/claude', 'opencode': '/bin/opencode'})
        count = 0
        async def tmux(*args):
            nonlocal count
            if args[0] in ('new-session', 'split-window'):
                count += 1
                return f'%{count}\n'
            if args[0] == 'capture-pane':
                return 'assignment evidence'
            if args[-1] == '#{pane_dead} #{pane_dead_status}':
                return '1 0'
            return ''
        runner._tmux = AsyncMock(side_effect=tmux)
        with tempfile.TemporaryDirectory() as root, patch('shutil.which', return_value='/bin/tool'), patch(
                'asyncio.create_subprocess_exec', return_value=AsyncMock()) as launch:
            assignments = [{**a, 'batch': True} for a in software_assignments(runner.executables)]
            key = runner.delegate_team('Smoke test', assignments, root)['team']['id']
            await runner.team_workers[key]
        calls = [c.args for c in runner._tmux.call_args_list]
        self.assertEqual(sum(c[0] == 'new-session' for c in calls), 1)
        self.assertEqual(sum(c[0] == 'split-window' for c in calls), 3)
        self.assertEqual(launch.await_count, 1)
        self.assertEqual(runner.teams[key]['state'], 'completed')
        self.assertEqual([runner.jobs[j]['shared_pane'] for j in runner.teams[key]['jobs']], ['%1', '%2', '%3', '%4'])

    async def test_batch_exits_and_hands_off_without_composer_detection(self):
        runner = DesktopAgentOrchestrator({'claude': '/bin/claude'})
        async def tmux(*args):
            if args[-1] == '#{session_attached}':
                return '1'
            if args[0] == 'capture-pane':
                return 'review finished'
            if args[-1] == '#{pane_dead} #{pane_dead_status}':
                return '1 0'
            return ''
        runner._tmux = AsyncMock(side_effect=tmux)
        launcher = AsyncMock()
        launcher.returncode = None
        with tempfile.TemporaryDirectory() as root, patch('shutil.which', return_value='/bin/tool'), patch(
                'asyncio.create_subprocess_exec', return_value=launcher):
            result = runner.delegate('claude', 'Write hello', root, batch=True, yolo=True)
            key = result['job']['id']
            await runner.workers[key]
        self.assertEqual(runner.jobs[key]['state'], 'completed')
        self.assertIsNone(runner.jobs[key]['model'])
        launch = next(c.args[-1] for c in runner._tmux.call_args_list if c.args[0] == 'respawn-pane')
        self.assertIn('--dangerously-skip-permissions', launch)
        self.assertNotIn('--model', launch)
        self.assertFalse(any(c.args[0] == 'send-keys' for c in runner._tmux.call_args_list))

    def test_default_goal_is_visible_sequential_yolo(self):
        tasks = software_assignments({'hermes': 'h', 'claude': 'c', 'opencode': 'o'})
        self.assertTrue(all(t['visible'] and not t['batch'] and t['yolo'] for t in tasks))
        self.assertEqual([t['agent'] for t in tasks], ['hermes', 'claude', 'opencode', 'claude'])

    def test_native_yolo_flags(self):
        for agent, flag in [('hermes', '--yolo'), ('claude', '--dangerously-skip-permissions'),
                            ('opencode', '--auto')]:
            self.assertIn(flag, visible_batch_command(agent, agent, 'Task', yolo=True))

    def test_native_interfaces_preserve_provider_and_hide_json_transport(self):
        for agent in ('claude', 'hermes', 'opencode'):
            command = native_task_command(agent, agent, 'Task', yolo=True)
            self.assertNotIn('--print', command)
            self.assertNotIn('--format', command)
            self.assertNotIn('--output-format', command)
            self.assertNotIn('--model', command)
            self.assertIn('Task', command)
