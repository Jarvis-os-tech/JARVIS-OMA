"""Composio domain adapters for JARVIS OS."""
from connectors import composio


ADAPTERS = {
    'composio.status': '_adapter_composio_status',
    'composio.authorize': '_adapter_composio_authorize',
    'composio.search': '_adapter_composio_search',
    'composio.execute': '_adapter_composio_execute',
    'composio.connect_platform': '_adapter_connect_platform',
    'composio.open_auth': '_adapter_open_platform_authorization',
    'composio.check_connection': '_adapter_check_platform_connection',
    'composio.execute_action': '_adapter_execute_platform_action',
    'composio.list_platforms': '_adapter_list_connected_platforms',
    'composio.disconnect_platform': '_adapter_disconnect_platform',
}

ADAPTER_COMMANDS = {
    'composio.status': (),
    'composio.authorize': (),
    'composio.search': (),
    'composio.execute': (),
    'composio.connect_platform': (),
    'composio.open_auth': (),
    'composio.check_connection': (),
    'composio.execute_action': (),
    'composio.list_platforms': (),
    'composio.disconnect_platform': (),
}


class ComposioDomain:
    async def _adapter_composio_status(self, toolkit: str, user_id: str = 'local-user'):
        return await composio.dispatch('composio_connection_status', {'toolkit': toolkit, 'user_id': user_id})

    async def _adapter_composio_authorize(self, toolkit: str, user_id: str = 'local-user', open_in_browser: bool = False):
        return await composio.dispatch('composio_authorize', {
            'toolkit': toolkit,
            'user_id': user_id,
            'open_in_browser': open_in_browser,
        })

    async def _adapter_open_platform_authorization(self, platform: str, user_id: str = 'local-user'):
        return await composio.dispatch('open_platform_authorization', {
            'platform': platform,
            'user_id': user_id,
        })

    async def _adapter_check_platform_connection(self, platform: str, user_id: str = 'local-user'):
        return await composio.dispatch('check_platform_connection', {
            'platform': platform,
            'user_id': user_id,
        })

    async def _adapter_search_tools(self, query: str, user_id: str = 'local-user'):
        return await composio.dispatch('composio_search_tools', {'query': query, 'user_id': user_id})

    async def _adapter_execute_tool(self, tool_slug: str, arguments: dict = None, user_id: str = 'local-user'):
        return await composio.dispatch('composio_execute_tool', {
            'tool_slug': tool_slug,
            'arguments': arguments or {},
            'user_id': user_id,
        })

    async def _adapter_connect_platform(self, platform: str, reconnect: bool = False, open_in_browser: bool = True, user_id: str = 'local-user'):
        return await composio.dispatch('connect_platform', {
            'platform': platform,
            'reconnect': reconnect,
            'open_in_browser': open_in_browser,
            'user_id': user_id,
        })

    async def _adapter_execute_platform_action(self, platform: str, action: str, arguments: dict = None, user_id: str = 'local-user'):
        return await composio.dispatch('execute_platform_action', {
            'platform': platform,
            'action': action,
            'arguments': arguments or {},
            'user_id': user_id,
        })

    async def _adapter_list_connected_platforms(self, user_id: str = 'local-user'):
        return await composio.dispatch('list_connected_platforms', {'user_id': user_id})

    async def _adapter_disconnect_platform(self, platform: str, user_id: str = 'local-user'):
        return await composio.dispatch('disconnect_platform', {
            'platform': platform,
            'user_id': user_id,
        })

    # Registry names must resolve to actual domain handlers. Keep the generic
    # method names as compatibility aliases for existing callers.
    _adapter_composio_search = _adapter_search_tools
    _adapter_composio_execute = _adapter_execute_tool
