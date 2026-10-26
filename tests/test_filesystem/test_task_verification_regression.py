"""Regression checks for task-runner executor and content verification."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from task_runner import TaskRunner


class TaskVerificationRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, tool, args, execute):
        runner = TaskRunner(execute, lambda name, values: True)
        started = runner.start('Verify file operation', json.dumps([
            {'tool': tool, 'args': args},
        ]))
        await runner._workers[started['id']]
        return runner.status(started['id'])

    async def test_error_valued_executor_result_fails_even_when_old_file_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_bytes(b'old contents')

            async def execute(name, args):
                return {'status': 'error', 'error': 'disk full'}

            status = await self._run('write_file', {
                'path': str(path), 'content': 'new contents', 'overwrite': True,
            }, execute)

            self.assertEqual(status['status'], 'failed')
            self.assertIn('disk full', status['steps'][0]['error'])
            self.assertEqual(path.read_bytes(), b'old contents')

    async def test_explicit_false_success_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'

            async def execute(name, args):
                path.write_bytes(b'not written')
                return {'success': False, 'message': 'write rejected'}

            status = await self._run('write_file', {
                'path': str(path), 'content': 'requested',
            }, execute)

            self.assertEqual(status['status'], 'failed')
            self.assertIn('write rejected', status['steps'][0]['error'])

    async def test_write_verification_compares_requested_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'

            async def write_wrong_content(name, args):
                path.write_bytes('different'.encode('utf-8'))
                return {'status': 'written'}

            status = await self._run('write_file', {
                'path': str(path), 'content': 'requested ☃',
            }, write_wrong_content)

            self.assertEqual(status['status'], 'failed')
            self.assertIn('expected content', status['steps'][0]['error'])

    async def test_empty_write_is_a_valid_exact_postcondition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.txt'

            async def write_empty(name, args):
                path.write_bytes(b'')
                return {'status': 'written'}

            status = await self._run('write_file', {'path': str(path), 'content': ''}, write_empty)
            self.assertEqual(status['status'], 'completed')
            self.assertEqual(path.read_bytes(), b'')

    async def test_append_verification_uses_pre_execution_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_bytes(b'prefix:')

            async def append(name, args):
                with path.open('ab') as stream:
                    stream.write(args['content'].encode('utf-8'))
                return {'status': 'appended'}

            status = await self._run('append_file', {
                'path': str(path), 'content': ' tail',
            }, append)
            self.assertEqual(status['status'], 'completed')
            self.assertEqual(path.read_bytes(), b'prefix: tail')

    async def test_edit_verification_checks_replacement_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_bytes('before café after'.encode('utf-8'))

            async def edit(name, args):
                path.write_bytes('before wrong after'.encode('utf-8'))
                return {'status': 'edited'}

            status = await self._run('edit_file', {
                'path': str(path), 'old': 'café', 'new': 'tea',
            }, edit)
            self.assertEqual(status['status'], 'failed')
            self.assertIn('expected content', status['steps'][0]['error'])

    async def test_edit_verification_matches_filesystem_newline_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_bytes(b'first\r\nremove\r\nlast\r\n')

            async def edit(name, args):
                # Mirrors replace_text(): read_text normalizes CRLF and write_text
                # writes the resulting text back with platform newlines.
                path.write_bytes(b'first\nkeep\nlast\n')
                return {'status': 'edited'}

            status = await self._run('edit_file', {
                'path': str(path), 'old': 'remove', 'new': 'keep',
            }, edit)
            self.assertEqual(status['status'], 'completed')

    async def test_verification_rejects_baseline_larger_than_five_mib_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.txt'
            path.write_bytes(b'x' * (5 * 1024 * 1024 + 1))
            calls = []

            async def append(name, args):
                calls.append(name)
                return {'status': 'appended'}

            status = await self._run('append_file', {
                'path': str(path), 'content': '',
            }, append)

            self.assertEqual(status['status'], 'failed')
            self.assertIn('exceeds 5 MiB', status['steps'][0]['error'])
            self.assertEqual(calls, [])

    async def test_append_that_would_exceed_five_mib_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.txt'
            path.write_bytes(b'x' * (5 * 1024 * 1024))
            calls = []

            async def append(name, args):
                calls.append(name)
                return {'status': 'appended'}

            status = await self._run('append_file', {
                'path': str(path), 'content': 'x',
            }, append)

            self.assertEqual(status['status'], 'failed')
            self.assertIn('expected file exceeds 5 MiB', status['steps'][0]['error'])
            self.assertEqual(calls, [])

    async def test_cancellation_after_execution_still_marks_current_step_complete(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'

            async def execute(name, args):
                path.write_bytes(args['content'].encode('utf-8'))
                entered.set()
                await release.wait()
                return {'status': 'written'}

            runner = TaskRunner(execute, lambda name, values: True)
            started = runner.start('Cancel after write', json.dumps([
                {'tool': 'write_file', 'args': {'path': str(path), 'content': 'done'}},
                {'tool': 'write_file', 'args': {'path': str(path), 'content': 'later'}},
            ]))
            await entered.wait()
            runner.cancel(started['id'])
            release.set()
            await runner._workers[started['id']]

            status = runner.status(started['id'])
            self.assertEqual(status['status'], 'cancelled')
            self.assertEqual(status['completed_steps'], 1)
            self.assertEqual(status['steps'][0]['status'], 'completed')
            self.assertEqual(status['steps'][1]['status'], 'pending')

