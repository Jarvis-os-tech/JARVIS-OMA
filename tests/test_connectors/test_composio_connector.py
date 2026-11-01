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

    @patch.object(composio, 'get_client')
    async def test_connection_status_active(self, mock_get_client):
        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.toolkit.slug = 'github'
        mock_item.status = 'ACTIVE'
        mock_item.id = 'ca_123'
        mock_client.connected_accounts.list.return_value = MagicMock(items=[mock_item])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('composio_connection_status', {'toolkit': 'github'})
        self.assertTrue(res['success'])
        self.assertTrue(res['connected'])
        self.assertEqual(res['status'], 'ACTIVE')
        self.assertEqual(res['account_id'], 'ca_123')

    @patch.object(composio, 'get_client')
    async def test_connection_status_not_connected(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.connected_accounts.list.return_value = MagicMock(items=[])
        mock_get_client.return_value = mock_client

        res = await composio.dispatch('composio_connection_status', {'toolkit': 'github'})
        self.assertTrue(res['success'])
        self.assertFalse(res['connected'])
        self.assertEqual(res['status'], 'NO_ACTIVE_CONNECTION')
        self.assertTrue(res['setup_required'])

    @patch.object(composio, 'get_session')
    async def test_authorize_toolkit(self, mock_get_session):
        mock_session = MagicMock()
        mock_req = MagicMock()
        mock_req.redirect_url = 'https://connect.composio.dev/link/lk_test'
        mock_req.id = 'conn_test_id'
        mock_session.authorize.return_value = mock_req
        mock_get_session.return_value = mock_session

        res = await composio.dispatch('composio_authorize', {'toolkit': 'github'})
        self.assertTrue(res['success'])
        self.assertEqual(res['redirect_url'], 'https://connect.composio.dev/link/lk_test')
        self.assertEqual(res['connection_id'], 'conn_test_id')

    @patch.object(composio, 'get_session')
    async def test_execute_tool(self, mock_get_session):
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.error = None
        mock_res.data = {'test': 'data'}
        mock_res.log_id = 'log_123'
        mock_session.execute.return_value = mock_res
        mock_get_session.return_value = mock_session

        res = await composio.dispatch('composio_execute_tool', {
            'tool_slug': 'GITHUB_GET_A_REPOSITORY',
            'arguments': {'owner': 'octocat', 'repo': 'Hello-World'}
        })
        self.assertTrue(res['success'])
        self.assertEqual(res['data'], {'test': 'data'})
        self.assertEqual(res['log_id'], 'log_123')
