import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from orchestration.desktop_execution import DesktopAgentOrchestrator, visible_batch_command, native_task_command
from orchestration.personas import software_assignments


class VisibleBatchTests(unittest.IsolatedAsyncioTestCase):
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
