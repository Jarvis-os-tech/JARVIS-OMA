import asyncio
import base64
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from connectors import github


class GithubConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_repository_analysis_finds_and_reads_pinned_evidence(self):
        ref = 'a' * 40
        calls = []

        async def fetch(path, query=None, *, max_bytes=1_000_000):
            calls.append((path, query, max_bytes))
            if path == '/repos/acme/widgets':
                return {'default_branch': 'main'}
            if path.endswith('/commits/main'):
                return {'sha': ref}
            if '/git/trees/' in path:
                return {'truncated': False, 'tree': [
                    {'type': 'blob', 'path': 'src/audio/playback.py', 'size': 500},
                    {'type': 'blob', 'path': 'docs/README.md', 'size': 100},
                    {'type': 'tree', 'path': 'src/audio'},
                ]}
            if '/contents/' in path:
                return {'type': 'file', 'path': 'src/audio/playback.py', 'size': 24,
                        'encoding': 'base64', 'content': base64.b64encode(
                            b'def play():\n    return 1\n').decode()}
            raise AssertionError(path)

        with patch.object(github, '_fetch', side_effect=fetch):
            found = await github.dispatch('github_find_relevant_files', {
                'owner': 'acme', 'repository': 'widgets', 'query': 'audio playback'})
            self.assertTrue(found['success'])
            self.assertEqual(found['ref'], ref)
            self.assertEqual(found['files'][0]['path'], 'src/audio/playback.py')
            read = await github.dispatch('github_read_repository_files', {
                'owner': 'acme', 'repository': 'widgets', 'ref': ref,
                'paths': ['src/audio/playback.py']})
        self.assertTrue(read['success'])
        self.assertEqual(read['files'][0]['content'], '1: def play():\n2:     return 1')
        self.assertIn(f'/blob/{ref}/src/audio/playback.py#L1-L2', read['files'][0]['url'])
        self.assertTrue(any('/git/trees/' in path and max_bytes == github.MAX_TREE_BYTES
                            for path, _, max_bytes in calls))
        self.assertTrue(any(query == {'ref': ref} for _, query, _ in calls))

    async def test_repository_analysis_rejects_unpinned_or_unsafe_reads(self):
        for ref, paths in [('main', ['src/app.py']), ('a' * 40, ['../private']),
                           ('a' * 40, ['src/app.py'] * 2), ('a' * 40, ['x'] * 7)]:
            result = await github.dispatch('github_read_repository_files', {
                'owner': 'acme', 'repository': 'widgets', 'ref': ref, 'paths': paths})
            self.assertFalse(result['success'])

    async def test_token_environment_precedes_private_file_and_gh_token_environment(self):
        with patch.dict('os.environ', {'GH_TOKEN': 'env-token'}, clear=True), \
                patch.object(github.credentials, 'get', side_effect=['file-token', 'other-file']):
            self.assertEqual(github._token(), 'env-token')
        with patch.dict('os.environ', {}, clear=True), \
                patch.object(github.credentials, 'get', side_effect=['private-token']):
            self.assertEqual(github._token(), 'private-token')

    async def test_routing_and_mapping(self):
        data = [{'id': 3, 'name': 'repo', 'full_name': 'a/repo', 'description': 'x', 'private': False}]
        with patch.object(github, '_fetch', return_value=data) as fetch:
            result = await github.dispatch('github_list_repositories', {})
        self.assertEqual(result['items'][0]['full_name'], 'a/repo')
        self.assertEqual(fetch.await_args.args, ('/user/repos', {'per_page': 20, 'page': 1, 'sort': 'updated'}))
        with patch.object(github, '_fetch', return_value={'login': 'octocat'}):
            self.assertEqual(await github.dispatch('github_connection_status', {}), {'success': True, 'login': 'octocat'})
        with patch.object(github, '_fetch', return_value={'number': 4, 'body': 'x' * 4500}) as fetch:
            result = await github.dispatch('github_get_issue', {'owner': 'acme', 'repository': 'widgets', 'number': 4})
        self.assertEqual(fetch.await_args.args[0], '/repos/acme/widgets/issues/4')
        self.assertEqual(len(result['item']['body']), 4000)

    async def test_repository_files_are_available_for_code_analysis(self):
        entries = [
            {'name': 'README.md', 'path': 'README.md', 'type': 'file', 'size': 15},
            {'name': 'src', 'path': 'src', 'type': 'dir', 'size': 0},
        ]
        with patch.object(github, '_fetch', return_value=entries) as fetch:
            result = await github.dispatch('github_list_repository_files',
                                           {'owner': 'acme', 'repository': 'widgets'})
        self.assertEqual(fetch.await_args.args, ('/repos/acme/widgets/contents', None))
        self.assertEqual([item['path'] for item in result['items']], ['README.md', 'src'])

        contents = {'type': 'file', 'path': 'src/app.py', 'size': 11,
                    'encoding': 'base64', 'content': 'cHJpbnQoJ2hpJyk='}
        with patch.object(github, '_fetch', return_value=contents) as fetch:
            result = await github.dispatch('github_read_repository_file',
                                           {'owner': 'acme', 'repository': 'widgets', 'path': 'src/app.py'})
        self.assertEqual(fetch.await_args.args, ('/repos/acme/widgets/contents/src/app.py', None))
        self.assertEqual(result['content'], "print('hi')")

    async def test_repository_paths_are_encoded_and_cannot_escape(self):
        with patch.object(github, '_fetch', return_value=[]) as fetch:
            result = await github.dispatch('github_list_repository_files',
                                           {'owner': 'acme', 'repository': 'widgets', 'path': 'docs/design notes'})
        self.assertTrue(result['success'])
        self.assertEqual(fetch.await_args.args[0], '/repos/acme/widgets/contents/docs/design%20notes')
        for path in ('../private', 'src//main.py', 'src/./main.py', 'src/\\main.py', 'src/\x00main.py'):
            with self.subTest(path=path):
                result = await github.dispatch('github_read_repository_file',
                                               {'owner': 'acme', 'repository': 'widgets', 'path': path})
                self.assertFalse(result['success'])

    async def test_unreadable_repository_file_is_reported_without_raw_data(self):
        with patch.object(github, '_fetch', return_value={
            'type': 'file', 'path': 'binary.dat', 'encoding': 'base64',
            'content': 'invalid encoded private bytes!!!',
        }):
            result = await github.dispatch('github_read_repository_file',
                                           {'owner': 'acme', 'repository': 'widgets', 'path': 'binary.dat'})
        self.assertFalse(result['success'])
        self.assertNotIn('private bytes', str(result))

    async def test_github_authorize_opens_browser_with_state_and_pkce(self):
        fake_server = MagicMock()
        fake_server.server_address = ('127.0.0.1', 43123)
        with patch.object(github, '_client_credentials', return_value=('client-id', 'client-secret')), \
                patch.object(github, '_find_free_oauth_port', return_value=43123), \
                patch.object(github, 'HTTPServer', return_value=fake_server), \
                patch.object(github, '_auth_server', None), \
                patch.object(github.threading, 'Thread') as thread, \
                patch.object(github, 'open_url', return_value=True) as opened:
            result = github.github_authorize()
        self.assertTrue(result['success'])
        self.assertIn('client-id', result['auth_url'])
        self.assertIn('code_challenge', result['auth_url'])
        self.assertIn('state=', result['auth_url'])
        opened.assert_called_once_with(result['auth_url'])
        thread.return_value.start.assert_called_once()

    async def test_validation_blocks_traversal_and_flag_injection(self):
        for owner in ('..', '../acme', '-X', 'x/y'):
            result = await github.dispatch('github_get_repository', {'owner': owner, 'repository': 'repo'})
            self.assertFalse(result['success'])
        result = await github.dispatch('github_list_issues', {'owner': 'org', 'repository': '--help', 'state': 'open'})
        self.assertFalse(result['success'])
        result = await github.dispatch('github_get_issue', {'owner': 'org', 'repository': 'repo', 'number': 0})
        self.assertFalse(result['success'])
        result = await github.dispatch('github_list_issues', {'owner': 'org', 'repository': 'repo', 'state': '--help'})
        self.assertFalse(result['success'])

    async def test_http_error_body_is_never_returned(self):
        error = HTTPError('https://api.github.com/user', 403, 'denied', {}, None)
        error.read = lambda *args: b'secret-token and private response'
        with patch.object(github.urllib.request, 'build_opener') as build_opener:
            build_opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403') as caught:
                await asyncio.to_thread(github._request, 'https://api.github.com/user', 'secret-token')
        self.assertNotIn('secret-token', str(caught.exception))
        self.assertNotIn('private response', str(caught.exception))

    async def test_missing_auth_uses_gh_and_missing_cli_requires_setup(self):
        with patch.object(github, '_token', return_value=''), patch.object(github, '_gh_request', return_value={'login': 'octocat'}) as gh:
            result = await github.dispatch('github_connection_status', {})
        self.assertEqual(result['login'], 'octocat')
        gh.assert_awaited_once_with('/user')
        with patch.object(github, '_token', return_value=''), patch.object(github, '_gh_request', side_effect=FileNotFoundError):
            result = await github.dispatch('github_connection_status', {})
        self.assertIn('setup_required', result['error'])

    async def test_gh_timeout_terminates_and_reaps_child(self):
        class FakeProcess:
            returncode = None
            def __init__(self):
                self.terminated = False
                self.killed = False
                self.calls = 0
            def communicate(self):
                self.calls += 1
                if self.calls == 1:
                    import time
                    time.sleep(0.1)
                return b'', b''
            def terminate(self): self.terminated = True
            def kill(self): self.killed = True

        process = FakeProcess()
        with patch.object(github.subprocess, 'Popen', return_value=process), patch.object(github, 'TIMEOUT', 0.01):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                await github._gh_request('/user')
        self.assertTrue(process.terminated)
        self.assertEqual(process.calls, 1)

    async def test_gh_cancellation_terminates_and_reaps_child(self):
        entered = asyncio.Event()
        class FakeProcess:
            returncode = None
            terminated = False
            def communicate(self):
                entered_loop = entered
                # Popen's worker thread signals the event through the loop-safe callback below.
                loop.call_soon_threadsafe(entered_loop.set)
                import time
                time.sleep(0.15)
                return b'{}', b''
            def terminate(self): self.terminated = True
            def kill(self): pass

        loop = asyncio.get_running_loop()
        process = FakeProcess()
        with patch.object(github.subprocess, 'Popen', return_value=process):
            task = asyncio.create_task(github._gh_request('/user'))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(process.terminated)


if __name__ == '__main__':
    unittest.main()
