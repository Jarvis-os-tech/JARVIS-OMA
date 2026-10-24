"""Task execution, progress, validation, and cancellation tests."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from skills import DesktopSkills, SkillError
from task_runner import TaskRunner


class TaskRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_file_operations_complete(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.txt'
            cases = [
                ('write_file', {'path': str(path), 'content': ''}),
                ('append_file', {'path': str(path), 'content': ''}),
                ('edit_file', {'path': str(path), 'old': 'remove me', 'new': ''}),
            ]
            for tool, args in cases:
                with self.subTest(tool=tool):
                    if tool == 'edit_file':
                        path.write_text('remove me', encoding='utf-8')
                    started = await skills.execute('start_task', {
                        'description': 'Empty-file check',
                        'plan_json': json.dumps([{'tool': tool, 'args': args}])})
                    await skills._task_runner._workers[started['id']]
                    result = await skills.execute('task_status', {'task_id': started['id']})
                    self.assertEqual(result['status'], 'completed')
                    self.assertEqual(result['completed_steps'], 1)
                    self.assertEqual(path.read_text(encoding='utf-8'), '')

    async def test_missing_file_still_fails_verification(self):
        async def execute(name, args):
            return {'status': 'written'}

        with tempfile.TemporaryDirectory() as directory:
            runner = TaskRunner(execute, lambda name, args: True)
            started = runner.start('Missing-file check', json.dumps([{
                'tool': 'write_file',
                'args': {'path': str(Path(directory) / 'missing.txt'), 'content': ''}}]))
            await runner._workers[started['id']]
            self.assertEqual(runner.status(started['id'])['status'], 'failed')

    async def test_filesystem_job_records_each_result(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'note.txt'
            target = root / 'sorted' / 'note.txt'
            source.write_text('hello', encoding='utf-8')
            plan = [
                {'tool': 'make_directory', 'args': {'path': str(target.parent)}},
                {'tool': 'move_path', 'args': {'source': str(source), 'destination': str(target)}},
            ]
            started = await skills.execute('start_task', {
                'description': 'Organize one note', 'plan_json': json.dumps(plan)})
            await skills._task_runner._workers[started['id']]
            event = await asyncio.wait_for(skills.task_events.get(), timeout=.2)
            result = await skills.execute('task_status', {'task_id': started['id']})
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['completed_steps'], 2)
            self.assertEqual(result['steps'][1]['result']['destination'], str(target))
            self.assertEqual(result['steps'][1]['target']['destination'], str(target))
            self.assertTrue(target.is_file())
            self.assertEqual(event['id'], started['id'])
            self.assertEqual(event['status'], 'completed')
            self.assertEqual(event['completed_steps'], 2)

    async def test_invalid_plan_fails_before_any_file_change(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'untouched.txt'
            plan = [
                {'tool': 'write_file', 'args': {'path': str(path), 'content': 'new'}},
                {'tool': 'delete_path', 'args': {'path': str(path)}},
            ]
            with self.assertRaisesRegex(SkillError, 'step 2'):
                await skills.execute('start_task', {'description': 'Invalid job', 'plan_json': json.dumps(plan)})
            self.assertFalse(path.exists())

    async def test_cancel_stops_after_current_step(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def execute(name, args):
            calls.append(name)
            entered.set()
            await release.wait()
            return {'status': 'done'}

        runner = TaskRunner(execute, lambda name, args: True)
        started = runner.start('Cancel me', json.dumps([
            {'tool': 'make_directory', 'args': {'path': '/tmp/one'}},
            {'tool': 'make_directory', 'args': {'path': '/tmp/two'}},
        ]))
        await entered.wait()
        self.assertTrue(runner.cancel(started['id'])['cancel_requested'])
        release.set()
        await runner._workers[started['id']]
        self.assertEqual(runner.status(started['id'])['status'], 'cancelled')
        self.assertEqual(calls, ['make_directory'])
        event = await asyncio.wait_for(runner.events.get(), timeout=.2)
        self.assertEqual(event['status'], 'cancelled')

    async def test_start_returns_while_work_continues(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def execute(name, args):
            entered.set()
            await release.wait()
            return {'status': 'done'}

        runner = TaskRunner(execute, lambda name, args: True)
        started = runner.start('Keep voice responsive', json.dumps([
            {'tool': 'make_directory', 'args': {'path': '/tmp/voice-task'}},
        ]))
        self.assertEqual(started['status'], 'queued')
        await asyncio.wait_for(entered.wait(), timeout=.2)
        self.assertFalse(runner._workers[started['id']].done())
        release.set()
        await runner._workers[started['id']]

    async def test_failed_task_event_includes_error(self):
        async def execute(name, args):
            raise RuntimeError('Disk full simulation')

        runner = TaskRunner(execute, lambda name, args: True)
        started = runner.start('Failing task', json.dumps([
            {'tool': 'make_directory', 'args': {'path': '/tmp/fail-task'}},
        ]))
        await runner._workers[started['id']]
        event = await asyncio.wait_for(runner.events.get(), timeout=.2)
        self.assertEqual(event['status'], 'failed')
        self.assertIn('Disk full simulation', event.get('error', ''))

    async def test_trash_path_ground_truth_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            test_file = Path(directory) / 'to_trash.txt'
            test_file.write_text('trash me', encoding='utf-8')

            # Execution does NOT delete the file -> should fail ground truth verification
            async def execute_fake(name, args):
                return {'status': 'trashed'}

            runner = TaskRunner(execute_fake, lambda name, args: True)
            started = runner.start('Trash failure check', json.dumps([
                {'tool': 'trash_path', 'args': {'path': str(test_file)}},
            ]))
            await runner._workers[started['id']]
            status = runner.status(started['id'])
            self.assertEqual(status['status'], 'failed')
            self.assertIn('still exists after trash', status['steps'][0]['error'])

            # Real deletion -> verification succeeds
            async def execute_real(name, args):
                test_file.unlink()
                return {'status': 'trashed'}

            runner_real = TaskRunner(execute_real, lambda name, args: True)
            started_real = runner_real.start('Trash success check', json.dumps([
                {'tool': 'trash_path', 'args': {'path': str(test_file)}},
            ]))
            await runner_real._workers[started_real['id']]
            self.assertEqual(runner_real.status(started_real['id'])['status'], 'completed')

    async def test_runner_close_cancels_active_workers(self):
        entered = asyncio.Event()

        async def execute(name, args):
            entered.set()
            await asyncio.sleep(60)
            return {'status': 'done'}

        runner = TaskRunner(execute, lambda name, args: True)
        started = runner.start('Long task', json.dumps([
            {'tool': 'make_directory', 'args': {'path': '/tmp/long-task'}},
        ]))
        await asyncio.wait_for(entered.wait(), timeout=.5)
        self.assertIn(started['id'], runner._workers)
        await runner.close()
        self.assertEqual(len(runner._workers), 0)
        self.assertEqual(runner.status(started['id'])['status'], 'cancelled')
