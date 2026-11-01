"""Composio platform connector for JARVIS OS.

Uses Composio Platform SDK sessions to manage user connections and execute tools.
Follows Composio Platform session architecture with stable user identities.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from connectors.browser import open_url
from connectors import credentials

# Ensure COMPOSIO_API_KEY is available in the environment for the Composio SDK
_api_key = credentials.get('COMPOSIO_API_KEY')
if _api_key and not os.environ.get('COMPOSIO_API_KEY'):
    os.environ['COMPOSIO_API_KEY'] = _api_key

_client = None
_sessions: Dict[str, Any] = {}

DEFAULT_USER_ID = 'local-user'

TOOLS = {
    'composio_connection_status',
    'composio_authorize',
    'composio_search_tools',
    'composio_execute_tool',
}


def get_client():
    """Lazily instantiate the Composio client."""
    global _client
    if _client is None:
        key = os.environ.get('COMPOSIO_API_KEY') or credentials.get('COMPOSIO_API_KEY')
        if not key:
            raise ValueError('COMPOSIO_API_KEY is missing from environment and credentials storage.')
        os.environ['COMPOSIO_API_KEY'] = key
        from composio import Composio
        _client = Composio()
    return _client


def get_session(user_id: str = DEFAULT_USER_ID):
    """Retrieve or create a cached Composio session for the user."""
    if user_id not in _sessions:
        client = get_client()
        session = client.create(user_id=user_id)
        _sessions[user_id] = session
    return _sessions[user_id]


def get_connection_status(toolkit: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Check if an active connection exists for the specified toolkit and user."""
    client = get_client()
    slug = toolkit.lower().strip()
    try:
        response = client.connected_accounts.list(user_ids=[user_id])
        active_account = None
        for item in getattr(response, 'items', []):
            item_slug = getattr(getattr(item, 'toolkit', None), 'slug', '')
            item_status = getattr(item, 'status', '')
            if item_slug.lower() == slug and item_status.upper() == 'ACTIVE':
                active_account = item
                break

        if active_account:
            return {
                'success': True,
                'connected': True,
                'toolkit': slug,
                'account_id': getattr(active_account, 'id', None),
                'status': 'ACTIVE',
            }

        return {
            'success': True,
            'connected': False,
            'toolkit': slug,
            'status': 'NO_ACTIVE_CONNECTION',
            'setup_required': True,
        }
    except Exception as exc:
        return {
            'success': False,
            'connected': False,
            'toolkit': slug,
            'error': str(exc),
            'setup_required': True,
        }


def authorize(toolkit: str, user_id: str = DEFAULT_USER_ID, open_in_browser: bool = False) -> Dict[str, Any]:
    """Initiate a connection request for the requested toolkit.
    
    Returns a redirect URL for the user to complete authentication.
    """
    session = get_session(user_id=user_id)
    slug = toolkit.lower().strip()
    try:
        req = session.authorize(slug)
        redirect_url = getattr(req, 'redirect_url', getattr(req, 'url', None))
        if not redirect_url:
            # Fallback to COMPOSIO_MANAGE_CONNECTIONS
            res = session.execute('COMPOSIO_MANAGE_CONNECTIONS', arguments={'toolkits': [slug]})
            res_data = getattr(res, 'data', {}) or {}
            results = res_data.get('results', {}).get(slug, {})
            redirect_url = results.get('redirect_url')

        opened = False
        if redirect_url and open_in_browser:
            opened = open_url(redirect_url)

        return {
            'success': True,
            'toolkit': slug,
            'connection_id': getattr(req, 'id', None),
            'redirect_url': redirect_url,
            'browser_opened': opened,
            'instruction': f'Open the link to authorize {slug}: {redirect_url}',
        }
    except Exception as exc:
        return {
            'success': False,
            'toolkit': slug,
            'error': str(exc),
        }


def search_tools(query: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Search for relevant tools and toolkits using Composio runtime discovery."""
    session = get_session(user_id=user_id)
    res = session.execute('COMPOSIO_SEARCH_TOOLS', arguments={'query': query})
    return {
        'success': not bool(getattr(res, 'error', None)),
        'data': getattr(res, 'data', None),
        'log_id': getattr(res, 'log_id', None),
        'error': getattr(res, 'error', None),
    }


def execute_tool(tool_slug: str, arguments: Optional[Dict[str, Any]] = None, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Execute a Composio tool using the user session and capture log ID and data."""
    session = get_session(user_id=user_id)
    res = session.execute(tool_slug, arguments=arguments or {})
    return {
        'success': not bool(getattr(res, 'error', None)),
        'data': getattr(res, 'data', None),
        'log_id': getattr(res, 'log_id', None),
        'error': getattr(res, 'error', None),
    }


async def dispatch(tool: str, arguments: dict) -> Dict[str, Any]:
    """Async dispatcher matching the connector convention in JARVIS OS."""
    if tool not in TOOLS:
        return {'success': False, 'error': f'unsupported_tool: {tool}'}
    if not isinstance(arguments, dict):
        return {'success': False, 'error': 'arguments must be an object'}

    loop = asyncio.get_running_loop()
    user_id = arguments.get('user_id', DEFAULT_USER_ID)

    if tool == 'composio_connection_status':
        toolkit = arguments.get('toolkit', '')
        return await loop.run_in_executor(None, get_connection_status, toolkit, user_id)

    if tool == 'composio_authorize':
        toolkit = arguments.get('toolkit', '')
        open_browser = arguments.get('open_in_browser', False)
        return await loop.run_in_executor(None, authorize, toolkit, user_id, open_browser)

    if tool == 'composio_search_tools':
        query = arguments.get('query', '')
        return await loop.run_in_executor(None, search_tools, query, user_id)

    if tool == 'composio_execute_tool':
        slug = arguments.get('tool_slug', '')
        args = arguments.get('arguments', {})
        return await loop.run_in_executor(None, execute_tool, slug, args, user_id)

    return {'success': False, 'error': f'unhandled_tool: {tool}'}
