import asyncio
import unittest
from unittest.mock import MagicMock, patch

from connectors import composio


class ComposioConnectorTests(unittest.IsolatedAsyncioTestCase):
    def test_unsupported_tool(self):
        async def run():
            return await composio.dispatch('unknown_tool', {})
        res = asyncio.run(run())
        self.assertFalse(res['success'])
        self.assertIn('unsupported_tool', res['error'])

    def test_invalid_arguments_type(self):
        async def run():
            return await composio.dispatch('composio_connection_status', 'not-a-dict')
        res = asyncio.run(run())
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'arguments must be an object')

    def test_resolve_platform_aliases(self):
        self.assertEqual(composio.resolve_platform('GitHub'), 'github')
        self.assertEqual(composio.resolve_platform('Google Calendar'), 'googlecalendar')
        self.assertEqual(composio.resolve_platform('slack'), 'slack')
        self.assertEqual(composio.resolve_platform('gcal'), 'googlecalendar')

    @patch.object(composio, 'get_client')
    async def test_connection_status_active(self, mock_get_client):
        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.toolkit.slug = 'slack'
        mock_item.status = 'ACTIVE'
        mock_item.id = 'ca_123'
        mock_client.connected_accounts.list.return_value = MagicMock(items=[mock_item])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('composio_connection_status', {'toolkit': 'slack'})
        self.assertTrue(res['success'])
        self.assertTrue(res['connected'])
        self.assertEqual(res['status'], 'ACTIVE')
        self.assertEqual(res['account_id'], 'ca_123')

    @patch.object(composio, 'get_client')
    async def test_connection_status_not_connected(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.connected_accounts.list.return_value = MagicMock(items=[])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('composio_connection_status', {'toolkit': 'slack'})
        self.assertTrue(res['success'])
        self.assertFalse(res['connected'])
        self.assertEqual(res['status'], 'NO_ACTIVE_CONNECTION')
        self.assertTrue(res['setup_required'])

    @patch.object(composio, 'get_client')
    async def test_check_platform_connection_in_progress(self, mock_get_client):
        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.toolkit.slug = 'linkedin'
        mock_item.status = 'INITIALIZING'
        mock_item.id = 'ca_pending'
        mock_client.connected_accounts.list.return_value = MagicMock(items=[mock_item])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('check_platform_connection', {'platform': 'linkedin'})
        self.assertTrue(res['success'])
        self.assertFalse(res['connected'])
        self.assertTrue(res['connecting'])
        self.assertEqual(res['status'], 'CONNECTING')
        self.assertIn('in progress', res['message'])

    @patch.object(composio, 'get_session')
    async def test_authorize_toolkit(self, mock_get_session):
        mock_session = MagicMock()
        mock_req = MagicMock()
        mock_req.redirect_url = 'https://connect.composio.dev/link/lk_test'
        mock_req.id = 'conn_test_id'
        mock_session.authorize.return_value = mock_req
        mock_get_session.return_value = mock_session

        res = await composio.dispatch('composio_authorize', {'toolkit': 'slack'})
        self.assertTrue(res['success'])
        self.assertEqual(res['redirect_url'], 'https://connect.composio.dev/link/lk_test')
        self.assertEqual(res['connection_id'], 'conn_test_id')

    @patch.object(composio, 'get_connection_status')
    async def test_connect_platform_already_connected(self, mock_status):
        mock_status.return_value = {'success': True, 'connected': True, 'status': 'ACTIVE', 'toolkit': 'slack'}
        res = await composio.dispatch('connect_platform', {'platform': 'slack'})
        self.assertTrue(res['success'])
        self.assertTrue(res['already_connected'])
        self.assertIn('already connected', res['message'])

    @patch.object(composio, 'get_connection_status')
    @patch.object(composio, 'authorize')
    async def test_connect_platform_initiates_and_opens_browser(self, mock_auth, mock_status):
        mock_status.return_value = {'success': True, 'connected': False, 'status': 'NO_ACTIVE_CONNECTION'}
        mock_auth.return_value = {
            'success': True,
            'redirect_url': 'https://connect.composio.dev/link/lk_test',
            'browser_opened': True,
            'connection_id': 'c_123',
        }
        res = await composio.dispatch('connect_platform', {'platform': 'slack', 'open_in_browser': True})
        self.assertTrue(res['success'])
        self.assertFalse(res['already_connected'])
        self.assertTrue(res['browser_opened'])
        self.assertEqual(res['redirect_url'], 'https://connect.composio.dev/link/lk_test')
        self.assertIn('opened the authentication page', res['message'])

    @patch.object(composio, '_check_native_google_status')
    @patch.object(composio, '_check_native_github_status')
    @patch.object(composio, 'get_client')
    async def test_list_connected_platforms(self, mock_get_client, mock_gh, mock_gw):
        mock_gh.return_value = {'connected': True}
        mock_gw.return_value = {'connected': False}
        mock_client = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.toolkit.slug = 'slack'
        mock_item1.status = 'ACTIVE'
        mock_item2 = MagicMock()
        mock_item2.toolkit.slug = 'spotify'
        mock_item2.status = 'EXPIRED'
        mock_client.connected_accounts.list.return_value = MagicMock(items=[mock_item1, mock_item2])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('list_connected_platforms', {})
        self.assertTrue(res['success'])
        self.assertEqual(res['platforms'], ['github', 'slack'])
        self.assertEqual(res['count'], 2)

    @patch.object(composio, 'get_connection_status')
    @patch.object(composio, 'authorize')
    async def test_execute_platform_action_not_connected(self, mock_auth, mock_status):
        mock_status.return_value = {'success': True, 'connected': False}
        mock_auth.return_value = {
            'success': True,
            'redirect_url': 'https://connect.composio.dev/link/lk_test',
            'browser_opened': True,
        }
        res = await composio.dispatch('execute_platform_action', {
            'platform': 'slack',
            'action': 'post message',
        })
        self.assertFalse(res['success'])
        self.assertTrue(res['setup_required'])
        self.assertTrue(res['browser_opened'])
        self.assertIn('not connected yet', res['message'])

    @patch.object(composio, 'get_connection_status')
    @patch.object(composio, 'get_session')
    async def test_execute_platform_action_success(self, mock_get_session, mock_status):
        mock_status.return_value = {'success': True, 'connected': True, 'status': 'ACTIVE'}
        mock_session = MagicMock()
        mock_search_res = MagicMock()
        mock_search_res.data = {
            'results': [{
                'primary_tool_slugs': ['SLACK_CHAT_POST_MESSAGE']
            }]
        }
        mock_exec_res = MagicMock()
        mock_exec_res.error = None
        mock_exec_res.data = [{'ok': True}]
        mock_exec_res.log_id = 'log_456'

        def session_execute(slug, arguments=None):
            if slug == 'COMPOSIO_SEARCH_TOOLS':
                return mock_search_res
            return mock_exec_res

        mock_session.execute.side_effect = session_execute
        mock_get_session.return_value = mock_session

        res = await composio.dispatch('execute_platform_action', {
            'platform': 'slack',
            'action': 'post message',
        })
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_slug'], 'SLACK_CHAT_POST_MESSAGE')
        self.assertEqual(res['data'], [{'ok': True}])
        self.assertEqual(res['log_id'], 'log_456')

    @patch.object(composio, 'authorize')
    async def test_open_platform_authorization(self, mock_auth):
        mock_auth.return_value = {
            'success': True,
            'redirect_url': 'https://connect.composio.dev/link/lk_test',
            'browser_opened': True,
        }
        res = await composio.dispatch('open_platform_authorization', {'platform': 'slack'})
        self.assertTrue(res['success'])
        self.assertTrue(res['browser_opened'])
        self.assertEqual(res['redirect_url'], 'https://connect.composio.dev/link/lk_test')
        self.assertIn('opened the Slack authorization page', res['message'])

    @patch.object(composio, 'get_connection_status')
    async def test_check_platform_connection_active_and_inactive(self, mock_status):
        mock_status.return_value = {'success': True, 'connected': True, 'status': 'ACTIVE', 'toolkit': 'slack'}
        res = await composio.dispatch('check_platform_connection', {'platform': 'slack'})
        self.assertTrue(res['success'])
        self.assertTrue(res['connected'])
        self.assertIn('connected and active', res['message'])

        mock_status.return_value = {'success': True, 'connected': False, 'status': 'NOT_CONNECTED', 'toolkit': 'slack'}
        res2 = await composio.dispatch('check_platform_connection', {'platform': 'slack'})
        self.assertTrue(res2['success'])
        self.assertFalse(res2['connected'])
        self.assertIn('not connected yet', res2['message'])

    async def test_native_github_delegation(self):
        # Native GitHub status
        with patch.object(composio, '_check_native_github_status') as mock_gh:
            mock_gh.return_value = {
                'success': True, 'connected': True, 'connecting': False,
                'toolkit': 'github', 'status': 'ACTIVE', 'login': 'Jarvis-os-tech',
                'message': 'GitHub is connected natively as Jarvis-os-tech.'
            }
            res = await composio.dispatch('check_platform_connection', {'platform': 'github'})
            self.assertTrue(res['success'])
            self.assertTrue(res['connected'])
            self.assertEqual(res['login'], 'Jarvis-os-tech')

        # Native GitHub authorize
        with patch('connectors.github.github_authorize') as mock_auth:
            mock_auth.return_value = {
                'success': True,
                'message': 'Opened GitHub authorization in your browser.',
                'auth_url': 'https://github.com/login/oauth/authorize?test=1'
            }
            res_auth = await composio.dispatch('open_platform_authorization', {'platform': 'github'})
            self.assertTrue(res_auth['success'])
            self.assertEqual(res_auth['toolkit'], 'github')
            self.assertEqual(res_auth['redirect_url'], 'https://github.com/login/oauth/authorize?test=1')

        # Action execution should direct to native tools
        res_action = await composio.dispatch('execute_platform_action', {'platform': 'github', 'action': 'list repos'})
        self.assertFalse(res_action['success'])
        self.assertIn('native', res_action['message'])

    async def test_native_google_delegation(self):
        # Native Google Workspace status
        with patch.object(composio, '_check_native_google_status') as mock_gw:
            mock_gw.return_value = {
                'success': True, 'connected': True, 'connecting': False,
                'toolkit': 'google', 'status': 'ACTIVE',
                'message': 'Google Workspace is connected natively.'
            }
            res = await composio.dispatch('check_platform_connection', {'platform': 'google calendar'})
            self.assertTrue(res['success'])
            self.assertTrue(res['connected'])

        # Native Google Workspace authorize
        with patch('connectors.google_workspace.google_authorize') as mock_auth:
            mock_auth.return_value = {
                'success': True,
                'message': 'Opened Google authorization in your browser.',
                'auth_url': 'http://localhost:8765/callback'
            }
            res_auth = await composio.dispatch('open_platform_authorization', {'platform': 'google'})
            self.assertTrue(res_auth['success'])
            self.assertEqual(res_auth['toolkit'], 'google')

        # Action execution should direct to native tools
        res_action = await composio.dispatch('execute_platform_action', {'platform': 'google', 'action': 'search drive'})
        self.assertFalse(res_action['success'])
        self.assertIn('native', res_action['message'])
