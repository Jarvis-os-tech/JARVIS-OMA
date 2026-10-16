import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_google_bridge_forwards_allowlisted_calls_without_logging_secrets(self):
        skills = DesktopSkills()
        with patch('skills.skills.google_workspace.dispatch', new=AsyncMock(
                return_value={'success': True, 'count': 0, 'messages': []})) as dispatch:
            result = await skills.execute('gmail_search', {'query': 'is:unread', 'max_results': 5})
        self.assertTrue(result['success'])
        dispatch.assert_awaited_once_with('gmail_search', {'query': 'is:unread', 'max_results': 5})

    async def test_google_bridge_does_not_allow_arbitrary_connector_tools(self):
        skills = DesktopSkills()
        with self.assertRaises(Exception):
            await skills._google('execute_shell', {})

    async def test_voice_authorization_adapters_route_to_connectors(self):
        skills = DesktopSkills()
        with patch('skills.skills.google_workspace.dispatch', new=AsyncMock(
                return_value={'success': True})) as google_dispatch, \
                patch('skills.skills.github.dispatch', new=AsyncMock(
                    return_value={'success': True})) as github_dispatch:
            self.assertTrue((await skills.execute('google_authorize', {}))['success'])
            self.assertTrue((await skills.execute('github_authorize', {}))['success'])
        google_dispatch.assert_awaited_once_with('google_authorize', {})
        github_dispatch.assert_awaited_once_with('github_authorize', {})

    async def test_voice_can_inspect_github_repository_files(self):
        skills = DesktopSkills()
        with patch('skills.skills.github.dispatch', new=AsyncMock(
                return_value={'success': True, 'items': []})) as dispatch:
            result = await skills.execute('github_list_repository_files', {
                'owner': 'acme', 'repository': 'widgets'})
        self.assertTrue(result['success'])
        dispatch.assert_awaited_once_with('github_list_repository_files', {
            'owner': 'acme', 'repository': 'widgets', 'path': ''})

        with patch('skills.skills.github.dispatch', new=AsyncMock(
                return_value={'success': True, 'content': 'hello'})) as dispatch:
            result = await skills.execute('github_read_repository_file', {
                'owner': 'acme', 'repository': 'widgets', 'path': 'README.md'})
        self.assertEqual(result['content'], 'hello')
        dispatch.assert_awaited_once_with('github_read_repository_file', {
            'owner': 'acme', 'repository': 'widgets', 'path': 'README.md'})


if __name__ == '__main__':
    unittest.main()
