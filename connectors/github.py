"""Read-only GitHub API connector with optional ``gh`` CLI authentication."""
from __future__ import annotations

import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import secrets
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from connectors import credentials
from core.secret_env import sanitized_subprocess_env

API = 'https://api.github.com'
MAX_RESULTS = 50
MAX_BODY = 4000
TIMEOUT = 15
TOOLS = {
    'github_list_repositories', 'github_list_issues', 'github_list_pull_requests',
    'github_get_issue', 'github_get_pull_request', 'github_get_repository',
    'github_connection_status', 'github_authorize',
}
_SEGMENT = re.compile(r'^[A-Za-z0-9_.][A-Za-z0-9_.-]*$')
_auth_lock = threading.Lock()
_auth_server = None
_CALLBACK_PATH = '/api/connectors/callback'
_SCOPES = ('repo', 'workflow', 'notifications', 'read:user')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _token():
    # Check both environment names before asking the private-file helper, so an
    # environment GH_TOKEN takes precedence over a file GITHUB_TOKEN.
    return os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or credentials.get('GITHUB_TOKEN') or credentials.get('GH_TOKEN')


def _client_credentials():
    return credentials.get('GITHUB_CLIENT_ID'), credentials.get('GITHUB_CLIENT_SECRET')


def _find_free_oauth_port():
    server = HTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
    try:
        return server.server_address[1]
    finally:
        server.server_close()


def github_authorize():
    """Open GitHub OAuth in the browser and receive the callback locally."""
    global _auth_server
    client_id, client_secret = _client_credentials()
    if not client_id or not client_secret:
        return {'success': False, 'error': 'GitHub OAuth client credentials are not configured.',
                'setup_required': True}

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    port = _find_free_oauth_port()
    redirect_uri = f'http://localhost:{port}{_CALLBACK_PATH}'

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            values = urllib.parse.parse_qs(url.query)
            callback_state = values.get('state', [''])[0]
            valid = (url.path == _CALLBACK_PATH and callback_state
                     and secrets.compare_digest(callback_state, state))
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid GitHub authorization callback.')
                return
            success = False
            code = values.get('code', [''])[0]
            if code:
                request = urllib.request.Request(
                    'https://github.com/login/oauth/access_token',
                    data=urllib.parse.urlencode({
                        'client_id': client_id, 'client_secret': client_secret,
                        'code': code, 'redirect_uri': redirect_uri,
                        'code_verifier': verifier,
                    }).encode(),
                    method='POST',
                    headers={'Accept': 'application/json',
                             'Content-Type': 'application/x-www-form-urlencoded'},
                )
                try:
                    with urllib.request.build_opener(_NoRedirect).open(request, timeout=15) as response:
                        token = json.loads(response.read(100_000))
                    if isinstance(token, dict) and token.get('access_token'):
                        credentials.save_env_values({
                            'GITHUB_CLIENT_ID': client_id,
                            'GITHUB_CLIENT_SECRET': client_secret,
                            'GITHUB_TOKEN': token['access_token'],
                        })
                        success = True
                except Exception:
                    success = False
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            if success:
                self.wfile.write(
                    b"<html><body style='font-family:sans-serif;text-align:center;padding-top:50px'>"
                    b"<h2>GitHub authorization successful</h2>"
                    b"<p>JARVIS is connected. You may close this tab.</p></body></html>")
            else:
                self.wfile.write(
                    b"<html><body style='font-family:sans-serif;text-align:center;padding-top:50px'>"
                    b"<h2>GitHub authorization failed</h2>"
                    b"<p>No token was saved. Return to JARVIS and try again.</p></body></html>")

        def log_message(self, *args):
            pass

    with _auth_lock:
        if _auth_server is not None:
            try:
                _auth_server.server_close()
            except Exception:
                pass
            _auth_server = None
        try:
            server = HTTPServer(('127.0.0.1', port), CallbackHandler)
            server.timeout = 300
            _auth_server = server
        except OSError:
            return {'success': False, 'error': 'GitHub authorization callback could not start.'}

        def _run_server():
            global _auth_server
            try:
                server.handle_request()
            finally:
                with _auth_lock:
                    if _auth_server == server:
                        server.server_close()
                        _auth_server = None

        threading.Thread(target=_run_server, daemon=True).start()

    auth_url = 'https://github.com/login/oauth/authorize?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': redirect_uri,
        'scope': ' '.join(_SCOPES), 'state': state,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
        'prompt': 'select_account',
    })
    opened = False
    try:
        opened = webbrowser.open(auth_url)
    except Exception:
        pass
    if not opened:
        try:
            subprocess.Popen(['xdg-open', auth_url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=sanitized_subprocess_env())
            opened = True
        except Exception:
            pass
    return {'success': True,
            'message': 'Opened GitHub authorization in your browser. Approve access to connect your account.',
            'auth_url': auth_url}


def _segment(value, name):
    if not isinstance(value, str) or not _SEGMENT.fullmatch(value) or value in {'.', '..'}:
        raise ValueError(f'invalid {name}')
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 2_147_483_647:
        raise ValueError('number must be a positive integer within range')
    return value


def _limit(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_RESULTS:
        raise ValueError(f'max_results must be between 1 and {MAX_RESULTS}')
    return value


def _url(path, query=None):
    if not path.startswith('/') or '://' in path or '\\' in path:
        raise ValueError('invalid endpoint')
    return API + path + (('?' + urllib.parse.urlencode(query)) if query else '')


def _request(url, token=''):
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'JARVIS-OMA'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers, method='GET')
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            body = response.read(1_000_000)
        return json.loads(body.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'GitHub request failed (HTTP {exc.code})') from None
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError('GitHub request failed') from None


async def _gh_request(path):
    """Use gh's existing auth without reading or exposing its token."""
    process = subprocess.Popen(
        ['gh', 'api', '--method', 'GET', path], stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, env=None,
    )
    communicate = asyncio.create_task(asyncio.to_thread(process.communicate))
    try:
        output, _ = await asyncio.wait_for(asyncio.shield(communicate), TIMEOUT)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(communicate), 2)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await communicate
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise RuntimeError('GitHub request timed out') from None
    if process.returncode:
        raise RuntimeError('setup_required: configure GITHUB_TOKEN or authenticate with gh')
    try:
        return json.loads(output.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        raise RuntimeError('GitHub CLI returned an invalid response') from None


async def _fetch(path, query=None):
    url = _url(path, query)
    token = _token()
    if token:
        return await asyncio.to_thread(_request, url, token)
    try:
        return await _gh_request(path + (('?' + urllib.parse.urlencode(query)) if query else ''))
    except FileNotFoundError:
        raise RuntimeError('setup_required: configure GITHUB_TOKEN or authenticate with gh') from None


def _body(data):
    if not isinstance(data, str):
        return ''
    return data[:MAX_BODY]


def _repo_fields(item):
    return {key: item.get(key) for key in ('id', 'name', 'full_name', 'description', 'private', 'html_url', 'default_branch', 'language', 'stargazers_count', 'forks_count')}


def _issue_fields(item):
    return {key: item.get(key) for key in ('number', 'title', 'state', 'html_url', 'created_at', 'updated_at') } | {
        'user': (item.get('user') or {}).get('login'), 'body': _body(item.get('body')),
    }


def _pr_fields(item):
    result = _issue_fields(item)
    result.update({'draft': item.get('draft'), 'base': (item.get('base') or {}).get('ref'), 'head': (item.get('head') or {}).get('ref')})
    return result


def _mapped(tool, data):
    if tool == 'github_connection_status':
        return {'success': True, 'login': data.get('login')}
    if tool in {'github_list_repositories', 'github_list_issues', 'github_list_pull_requests'}:
        values = data if isinstance(data, list) else []
        mapper = _repo_fields if tool == 'github_list_repositories' else _issue_fields if tool == 'github_list_issues' else _pr_fields
        return {'success': True, 'count': min(len(values), MAX_RESULTS), 'truncated': len(values) > MAX_RESULTS,
                'items': [mapper(item) for item in values[:MAX_RESULTS] if isinstance(item, dict)]}
    mapper = _repo_fields if tool == 'github_get_repository' else _pr_fields if tool == 'github_get_pull_request' else _issue_fields
    return {'success': True, 'item': mapper(data) if isinstance(data, dict) else {}}


def _route(tool, args):
    if tool == 'github_connection_status':
        return '/user', None
    if tool == 'github_list_repositories':
        limit = _limit(args.get('max_results', 20))
        return '/user/repos', {'per_page': limit, 'page': 1, 'sort': 'updated'}
    owner, repository = _segment(args.get('owner'), 'owner'), _segment(args.get('repository'), 'repository')
    base = f'/repos/{owner}/{repository}'
    if tool in {'github_list_issues', 'github_list_pull_requests'}:
        limit = _limit(args.get('max_results', 20))
        state = args.get('state', 'open')
        if state not in {'open', 'closed', 'all'}:
            raise ValueError('state must be open, closed, or all')
        suffix = '/issues' if tool == 'github_list_issues' else '/pulls'
        return base + suffix, {'state': state, 'per_page': limit, 'page': 1}
    if tool == 'github_get_repository':
        return base, None
    number = _number(args.get('number'))
    return base + ('/issues/' if tool == 'github_get_issue' else '/pulls/') + str(number), None


async def dispatch(tool: str, arguments: dict):
    if tool not in TOOLS:
        return {'success': False, 'error': 'unsupported_tool'}
    try:
        if not isinstance(arguments, dict):
            raise ValueError('arguments must be an object')
        if tool == 'github_authorize':
            return github_authorize()
        path, query = _route(tool, arguments)
        data = await _fetch(path, query)
        return _mapped(tool, data)
    except ValueError as exc:
        return {'success': False, 'error': str(exc)}
    except Exception as exc:
        message = str(exc)
        if message.startswith('setup_required:'):
            safe_error = message
        elif re.fullmatch(r'GitHub request failed \(HTTP [0-9]{3}\)', message):
            safe_error = message
        elif message == 'GitHub request timed out':
            safe_error = message
        else:
            safe_error = 'GitHub request failed'
        return {'success': False, 'error': safe_error,
                'setup_required': message.startswith('setup_required:') or 'HTTP 401' in safe_error}
