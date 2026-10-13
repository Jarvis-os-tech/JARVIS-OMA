"""Task execution, progress, validation, and cancellation tests."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from skills import DesktopSkills, SkillError
from task_runner import TaskRunner


class TaskRunnerTests(unittest.IsolatedAsyncioTestCase):
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
            result = await skills.execute('task_status', {'task_id': started['id']})
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['completed_steps'], 2)
            self.assertEqual(result['steps'][1]['result']['destination'], str(target))
            self.assertEqual(result['steps'][1]['target']['destination'], str(target))
            self.assertTrue(target.is_file())

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
