"""Composio platform connector for JARVIS OS.

Uses Composio Platform SDK sessions to manage user connections and execute tools.
Follows Composio Platform session architecture with stable user identities.
Enables autonomous platform discovery, automatic browser authentication, and action execution.
"""
from __future__ import annotations

import asyncio
import os
import re
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


def is_native_platform(platform: str) -> Optional[str]:
    """Identify if a platform should be routed to native connectors instead of Composio."""
    if not platform or not isinstance(platform, str):
        return None
    p = platform.strip().lower()
    if p in ('github', 'gh', 'git'):
        return 'github'
    if p in (
        'google', 'google workspace', 'workspace', 'google calendar', 'gcal', 'calendar',
        'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets',
        'google docs', 'gdocs', 'docs', 'gmail', 'mail'
    ):
        return 'google'
    return None


def _check_native_github_status() -> Dict[str, Any]:
    """Check status of pre-configured native GitHub integration."""
    try:
        from connectors import github
        import asyncio
        import concurrent.futures

        def run_sync():
            return asyncio.run(github.dispatch('github_connection_status', {}))

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                res = pool.submit(run_sync).result(timeout=15)
        else:
            res = run_sync()

        login = res.get('login') if isinstance(res, dict) else None
        if res.get('success') and login:
            return {
                'success': True,
                'connected': True,
                'connecting': False,
                'toolkit': 'github',
                'status': 'ACTIVE',
                'login': login,
                'message': f"GitHub is connected natively as {login}.",
            }
        return {
            'success': True,
            'connected': False,
            'connecting': False,
            'toolkit': 'github',
            'status': 'NOT_CONNECTED',
            'setup_required': True,
            'message': "GitHub is not connected yet. Say 'authorize GitHub' to connect.",
        }
    except Exception as exc:
        return {
            'success': False,
            'connected': False,
            'connecting': False,
            'toolkit': 'github',
            'status': 'ERROR',
            'error': str(exc),
            'message': f"Could not check native GitHub connection status: {exc}",
        }


def _check_native_google_status() -> Dict[str, Any]:
    """Check status of pre-configured native Google Workspace integration."""
    try:
        from connectors import google_workspace
        res = google_workspace.google_connection_status()
        connected = bool(res.get('connected'))
        drive_ready = bool(res.get('drive_connected'))
        if connected:
            return {
                'success': True,
                'connected': True,
                'connecting': False,
                'toolkit': 'google',
                'drive_connected': drive_ready,
                'status': 'ACTIVE',
                'message': res.get('message', "Google Workspace is connected natively."),
            }
        return {
            'success': True,
            'connected': False,
            'connecting': False,
            'toolkit': 'google',
            'status': 'NOT_CONNECTED',
            'setup_required': True,
            'message': res.get('message', "Google Workspace is not connected yet. Say 'authorize Google' to connect."),
        }
    except Exception as exc:
        return {
            'success': False,
            'connected': False,
            'connecting': False,
            'toolkit': 'google',
            'status': 'ERROR',
            'error': str(exc),
            'message': f"Could not check native Google Workspace connection status: {exc}",
        }


PLATFORM_ALIASES: Dict[str, str] = {
    'google': 'google',
    'google workspace': 'google',
    'workspace': 'google',
    'google calendar': 'googlecalendar',
    'gcal': 'googlecalendar',
    'calendar': 'googlecalendar',
    'google drive': 'googledrive',
    'gdrive': 'googledrive',
    'drive': 'googledrive',
    'google sheets': 'googlesheets',
    'gsheets': 'googlesheets',
    'sheets': 'googlesheets',
    'google docs': 'googledocs',
    'gdocs': 'googledocs',
    'docs': 'googledocs',
    'gmail': 'gmail',
    'mail': 'gmail',
    'github': 'github',
    'git': 'github',
    'gh': 'github',
    'slack': 'slack',
    'notion': 'notion',
    'spotify': 'spotify',
    'linear': 'linear',
    'jira': 'jira',
    'trello': 'trello',
    'discord': 'discord',
    'twitter': 'twitter',
    'x': 'twitter',
    'asana': 'asana',
    'zoom': 'zoom',
    'airtable': 'airtable',
    'hubspot': 'hubspot',
    'salesforce': 'salesforce',
    'linkedin': 'linkedin',
    'linked in': 'linkedin',
    'figma': 'figma',
    'gitlab': 'gitlab',
    'bitbucket': 'bitbucket',
    'reddit': 'reddit',
    'youtube': 'youtube',
    'dropbox': 'dropbox',
    'clickup': 'clickup',
    'whatsapp': 'whatsapp',
    'telegram': 'telegram',
    'stripe': 'stripe',
    'zendesk': 'zendesk',
    'shopify': 'shopify',
    'supabase': 'supabase',
    'twilio': 'twilio',
    'microsoft teams': 'msteams',
    'teams': 'msteams',
    'msteams': 'msteams',
    'outlook': 'outlook',
    'google meet': 'googlemeet',
    'meet': 'googlemeet',
    'todoist': 'todoist',
}

TOOLS = {
    'composio_connection_status',
    'composio_authorize',
    'composio_search_tools',
    'composio_execute_tool',
    'connect_platform',
    'open_platform_authorization',
    'check_platform_connection',
    'execute_platform_action',
    'list_connected_platforms',
    'disconnect_platform',
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


def resolve_platform(platform: str, user_id: str = DEFAULT_USER_ID) -> str:
    """Normalize a platform name to its canonical Composio toolkit slug."""
    clean = platform.strip().lower()
    if clean in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[clean]

    # Try removing non-alphanumeric characters
    compact = re.sub(r'[^a-z0-9]', '', clean)
    if compact in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[compact]

    # Query Composio search if not in static alias map
    try:
        session = get_session(user_id=user_id)
        res = session.execute('COMPOSIO_SEARCH_TOOLS', arguments={'query': clean})
        data = getattr(res, 'data', {}) or {}
        for status_info in data.get('toolkit_connection_statuses', []):
            tk = status_info.get('toolkit')
            if tk:
                return tk.lower()
        results = data.get('results', [])
        if results and results[0].get('toolkits'):
            return results[0]['toolkits'][0].lower()
    except Exception:
        pass

    return compact or clean


def get_connection_status(toolkit: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Check if an active connection exists for the specified toolkit and user."""
    native = is_native_platform(toolkit)
    if native == 'github':
        return _check_native_github_status()
    if native == 'google':
        return _check_native_google_status()

    client = get_client()
    slug = resolve_platform(toolkit, user_id=user_id)
    try:
        response = client.connected_accounts.list(user_ids=[user_id])
        active_account = None
        pending_account = None
        items = list(getattr(response, 'items', []) or [])
        # Check for ACTIVE account first, then INITIALIZING/INITIATED/PENDING
        for item in items:
            item_slug = getattr(getattr(item, 'toolkit', None), 'slug', '')
            item_status = getattr(item, 'status', '').upper()
            if item_slug.lower() == slug:
                if item_status == 'ACTIVE':
                    active_account = item
                    break
                elif item_status in ('INITIALIZING', 'INITIATED', 'PENDING') and not pending_account:
                    pending_account = item

        if active_account:
            return {
                'success': True,
                'connected': True,
                'connecting': False,
                'toolkit': slug,
                'account_id': getattr(active_account, 'id', None),
                'status': 'ACTIVE',
                'message': f"{slug.title()} is connected and active.",
            }

        if pending_account:
            return {
                'success': True,
                'connected': False,
                'connecting': True,
                'toolkit': slug,
                'account_id': getattr(pending_account, 'id', None),
                'status': 'CONNECTING',
                'message': f"{slug.title()} is currently connecting — authorization is in progress. Please approve the prompt in your browser to complete connection.",
            }

        return {
            'success': True,
            'connected': False,
            'connecting': False,
            'toolkit': slug,
            'status': 'NO_ACTIVE_CONNECTION',
            'setup_required': True,
            'message': f"{slug.title()} is not connected yet.",
        }
    except Exception as exc:
        return {
            'success': False,
            'connected': False,
            'connecting': False,
            'toolkit': slug,
            'error': str(exc),
            'status': 'ERROR',
            'setup_required': True,
            'message': f"Could not check connection status for {slug.title()}: {exc}",
        }


def authorize(toolkit: str, user_id: str = DEFAULT_USER_ID, open_in_browser: bool = False) -> Dict[str, Any]:
    """Initiate a connection request for the requested toolkit.
    
    Returns a redirect URL for the user to complete authentication.
    """
    native = is_native_platform(toolkit)
    if native == 'github':
        from connectors import github
        res = github.github_authorize()
        return {
            'success': res.get('success', False),
            'toolkit': 'github',
            'status': 'awaiting_authorization' if res.get('success') else 'error',
            'completed': False,
            'redirect_url': res.get('auth_url'),
            'browser_opened': res.get('success', False),
            'instruction': res.get('message', 'Opened GitHub authorization in your browser.'),
            'error': res.get('error'),
        }
    if native == 'google':
        from connectors import google_workspace
        res = google_workspace.google_authorize()
        return {
            'success': res.get('success', False),
            'toolkit': 'google',
            'status': 'awaiting_authorization' if res.get('success') else 'error',
            'completed': False,
            'redirect_url': res.get('auth_url'),
            'browser_opened': res.get('success', False),
            'instruction': res.get('message', 'Opened Google authorization in your browser.'),
            'error': res.get('error'),
        }

    session = get_session(user_id=user_id)
    slug = resolve_platform(toolkit, user_id=user_id)
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

        if not redirect_url:
            return {'success': False, 'toolkit': slug,
                    'error': 'The provider returned no authorization link; connection was not established.'}

        return {
            'success': True,
            'toolkit': slug,
            'status': 'awaiting_authorization',
            'completed': False,
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


def open_platform_authorization(platform: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Directly open the authorization / login page in the user's browser for a platform."""
    toolkit = resolve_platform(platform, user_id=user_id)
    auth = authorize(toolkit, user_id=user_id, open_in_browser=True)
    if not auth.get('success'):
        return {
            'success': False,
            'toolkit': toolkit,
            'status': 'ERROR',
            'error': auth.get('error', 'Failed to generate authorization URL'),
            'message': f"Could not open authorization page for {toolkit.title()}: {auth.get('error')}",
        }

    redirect_url = auth.get('redirect_url')
    browser_opened = auth.get('browser_opened', False)
    return {
        'success': True,
        'status': 'awaiting_authorization',
        'completed': False,
        'toolkit': toolkit,
        'redirect_url': redirect_url,
        'browser_opened': browser_opened,
        'message': (
            f"I have opened the {toolkit.title()} authorization page in your browser. "
            "Please log in and approve the connection, then let me know once you are done."
            if browser_opened else
            f"Please visit this link to authorize {toolkit.title()}: {redirect_url}"
        ),
    }


def check_platform_connection(platform: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Check whether a platform is currently connected, connecting, or not connected."""
    native = is_native_platform(platform)
    if native == 'github':
        return _check_native_github_status()
    if native == 'google':
        return _check_native_google_status()

    toolkit = resolve_platform(platform, user_id=user_id)
    status = get_connection_status(toolkit, user_id=user_id)
    if status.get('connected'):
        return {
            'success': True,
            'connected': True,
            'connecting': False,
            'toolkit': toolkit,
            'status': 'ACTIVE',
            'message': f"{toolkit.title()} is connected and active.",
        }
    if status.get('connecting'):
        return {
            'success': True,
            'connected': False,
            'connecting': True,
            'toolkit': toolkit,
            'status': 'CONNECTING',
            'message': f"{toolkit.title()} is currently connecting — authorization is in progress. Please approve the prompt in your browser to complete connection.",
        }
    return {
        'success': True,
        'connected': False,
        'connecting': False,
        'toolkit': toolkit,
        'status': 'NOT_CONNECTED',
        'message': f"{toolkit.title()} is not connected yet. Would you like me to open the authorization page?",
    }


def connect_platform(platform: str, user_id: str = DEFAULT_USER_ID, reconnect: bool = False, open_in_browser: bool = True) -> Dict[str, Any]:
    """Connect to a platform: check existing status, open direct auth in browser if needed."""
    toolkit = resolve_platform(platform, user_id=user_id)
    if not reconnect:
        status = get_connection_status(toolkit, user_id=user_id)
        if status.get('connected'):
            return {
                'success': True,
                'already_connected': True,
                'connected': True,
                'connecting': False,
                'toolkit': toolkit,
                'status': 'ACTIVE',
                'browser_opened': False,
                'message': status.get('message', f'{toolkit.title()} is already connected and active.'),
            }

    auth = authorize(toolkit, user_id=user_id, open_in_browser=open_in_browser)
    if not auth.get('success'):
        return {
            'success': False,
            'connected': False,
            'connecting': False,
            'toolkit': toolkit,
            'error': auth.get('error', 'Failed to generate authorization link'),
            'message': f"Could not initiate connection to {toolkit.title()}: {auth.get('error')}",
        }

    redirect_url = auth.get('redirect_url')
    browser_opened = auth.get('browser_opened', False)
    return {
        'success': True,
        'already_connected': False,
        'connected': False,
        'connecting': True,
        'status': 'awaiting_authorization',
        'completed': False,
        'toolkit': toolkit,
        'redirect_url': redirect_url,
        'browser_opened': browser_opened,
        'message': (
            f"I have opened the authentication page for {toolkit.title()} in your browser. "
            "Please approve the connection and let me know once you are done."
            if browser_opened else
            f"Please open the following authorization link to connect {toolkit.title()}: {redirect_url}"
        ),
    }


def list_connected_platforms(user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """List all currently active connected platforms for the user."""
    active = []
    # Include native GitHub if connected
    try:
        gh = _check_native_github_status()
        if gh.get('connected'):
            active.append('github')
    except Exception:
        pass
    # Include native Google Workspace if connected
    try:
        gw = _check_native_google_status()
        if gw.get('connected'):
            active.append('google')
    except Exception:
        pass

    try:
        client = get_client()
        response = client.connected_accounts.list(user_ids=[user_id])
        for item in getattr(response, 'items', []):
            if getattr(item, 'status', '').upper() == 'ACTIVE':
                slug = getattr(getattr(item, 'toolkit', None), 'slug', '')
                if slug and slug.lower() not in ('github', 'google'):
                    active.append(slug.lower())
    except Exception as exc:
        if not active:
            return {
                'success': False,
                'error': str(exc),
                'platforms': [],
                'count': 0,
            }
    unique_platforms = sorted(set(active))
    return {
        'success': True,
        'platforms': unique_platforms,
        'count': len(unique_platforms),
        'message': f"Connected platforms ({len(unique_platforms)}): {', '.join(unique_platforms) if unique_platforms else 'None'}",
    }


def disconnect_platform(platform: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Disconnect or remove access to a specific platform."""
    client = get_client()
    toolkit = resolve_platform(platform, user_id=user_id)
    try:
        response = client.connected_accounts.list(user_ids=[user_id])
        deleted = []
        for item in getattr(response, 'items', []):
            item_slug = getattr(getattr(item, 'toolkit', None), 'slug', '')
            if item_slug.lower() == toolkit:
                item_id = getattr(item, 'id', None)
                if item_id:
                    client.connected_accounts.delete(item_id)
                    deleted.append(item_id)
        return {
            'success': True,
            'toolkit': toolkit,
            'deleted_count': len(deleted),
            'message': f"Disconnected {toolkit.title()}.",
        }
    except Exception as exc:
        return {
            'success': False,
            'toolkit': toolkit,
            'error': str(exc),
        }


def _execution_receipt(result) -> Dict[str, Any]:
    """Preserve SDK failure flags even when transport returned no error text."""
    def field(name, default=None):
        return result.get(name, default) if isinstance(result, dict) else getattr(result, name, default)
    error = field('error')
    successful = field('successful')
    success = field('success')
    failed = bool(error) or successful is False or success is False
    return {'success': not failed, 'data': field('data'), 'log_id': field('log_id'),
            'error': error or ('Remote tool reported unsuccessful execution' if failed else None)}


def search_tools(query: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Search for relevant tools and toolkits using Composio runtime discovery."""
    session = get_session(user_id=user_id)
    res = session.execute('COMPOSIO_SEARCH_TOOLS', arguments={'query': query})
    return _execution_receipt(res)


def execute_tool(tool_slug: str, arguments: Optional[Dict[str, Any]] = None, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Execute a Composio tool using the user session and capture log ID and data."""
    session = get_session(user_id=user_id)
    res = session.execute(tool_slug, arguments=arguments or {})
    return _execution_receipt(res)


def execute_platform_action(platform: str, action: str, arguments: Optional[Dict[str, Any]] = None, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """High-level action execution: checks connection, discovers tool, and runs it."""
    toolkit = resolve_platform(platform, user_id=user_id)
    status = get_connection_status(toolkit, user_id=user_id)

    if not status.get('connected'):
        auth = authorize(toolkit, user_id=user_id, open_in_browser=True)
        return {
            'success': False,
            'setup_required': True,
            'toolkit': toolkit,
            'redirect_url': auth.get('redirect_url'),
            'browser_opened': auth.get('browser_opened', False),
            'message': (
                f"{toolkit.title()} is not connected yet. "
                + ('I have opened the authentication page in your browser. ' if auth.get('browser_opened')
                   else 'The authentication page has not been opened. ')
                +
                "Please approve the connection and retry."
            ),
        }

    # Search for the right tool slug
    session = get_session(user_id=user_id)
    search_query = f"{toolkit} {action}"
    search_res = session.execute('COMPOSIO_SEARCH_TOOLS', arguments={'query': search_query})
    search_data = getattr(search_res, 'data', {}) or {}
    results = search_data.get('results', [])

    selected_tool = None
    if results:
        primary = results[0].get('primary_tool_slugs', [])
        related = results[0].get('related_tool_slugs', [])
        # A search hit from another platform is not permission to execute it.
        matching = lambda names: list(dict.fromkeys(cand for cand in names if
            isinstance(cand, str) and cand.upper().startswith(toolkit.upper() + '_')))
        candidates = matching(primary) or matching(related)
        exact = next((cand for cand in candidates if cand.casefold() == action.strip().casefold()), None)
        if exact or len(candidates) == 1:
            selected_tool = exact or candidates[0]
        elif len(candidates) > 1:
            return {'success': False, 'status': 'blocked', 'toolkit': toolkit,
                    'candidates': candidates,
                    'error': 'Multiple actions match; inspect their schemas and select the exact tool. No action was executed.'}

    if not selected_tool:
        return {
            'success': False,
            'toolkit': toolkit,
            'error': f'No matching tool found for action: {action}',
            'message': f"I could not find a tool in {toolkit.title()} to perform '{action}'.",
        }

    exec_res = session.execute(selected_tool, arguments=arguments or {})
    return {
        **_execution_receipt(exec_res),
        'toolkit': toolkit,
        'tool_slug': selected_tool,
    }


async def dispatch(tool: str, arguments: dict) -> Dict[str, Any]:
    """Async dispatcher matching the connector convention in JARVIS OS."""
    if tool not in TOOLS:
        return {'success': False, 'error': f'unsupported_tool: {tool}'}
    if not isinstance(arguments, dict):
        return {'success': False, 'error': 'arguments must be an object'}

    loop = asyncio.get_running_loop()
    user_id = arguments.get('user_id', DEFAULT_USER_ID)

    if tool == 'open_platform_authorization':
        platform = arguments.get('platform', '')
        return await loop.run_in_executor(None, open_platform_authorization, platform, user_id)

    if tool == 'check_platform_connection':
        platform = arguments.get('platform', '')
        return await loop.run_in_executor(None, check_platform_connection, platform, user_id)

    if tool == 'connect_platform':
        platform = arguments.get('platform', '')
        reconnect = arguments.get('reconnect', False)
        open_in_browser = arguments.get('open_in_browser', True)
        return await loop.run_in_executor(None, connect_platform, platform, user_id, reconnect, open_in_browser)

    if tool == 'execute_platform_action':
        platform = arguments.get('platform', '')
        action = arguments.get('action', '')
        args = arguments.get('arguments', {})
        native = is_native_platform(platform)
        if native:
            return {
                'success': False,
                'toolkit': native,
                'error': f"{native.title()} is integrated natively on JARVIS OS.",
                'message': (
                    f"{native.title()} is integrated natively. Please use native {native.title()} tools "
                    "(e.g. for GitHub: github_list_repositories, github_list_issues; "
                    "for Google: gmail_search, calendar_list_events, drive_search_files) rather than Composio."
                ),
            }
        return await loop.run_in_executor(None, execute_platform_action, platform, action, args, user_id)

    if tool == 'list_connected_platforms':
        return await loop.run_in_executor(None, list_connected_platforms, user_id)

    if tool == 'disconnect_platform':
        platform = arguments.get('platform', '')
        return await loop.run_in_executor(None, disconnect_platform, platform, user_id)

    if tool == 'composio_connection_status':
        toolkit = arguments.get('toolkit') or arguments.get('platform', '')
        return await loop.run_in_executor(None, get_connection_status, toolkit, user_id)

    if tool == 'composio_authorize':
        toolkit = arguments.get('toolkit') or arguments.get('platform', '')
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
