"""Composio domain adapters for JARVIS OS."""
from connectors import composio


ADAPTERS = {
    'composio.status': '_adapter_composio_status',
    'composio.authorize': '_adapter_composio_authorize',
    'composio.search': '_adapter_composio_search',
    'composio.execute': '_adapter_composio_execute',
}

ADAPTER_COMMANDS = {
    'composio.status': (),
    'composio.authorize': (),
    'composio.search': (),
    'composio.execute': (),
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

    async def _adapter_composio_search(self, query: str, user_id: str = 'local-user'):
        return await composio.dispatch('composio_search_tools', {'query': query, 'user_id': user_id})

    async def _adapter_composio_execute(self, tool_slug: str, arguments: dict = None, user_id: str = 'local-user'):
        return await composio.dispatch('composio_execute_tool', {
            'tool_slug': tool_slug,
            'arguments': arguments or {},
            'user_id': user_id,
        })
