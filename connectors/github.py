"""Read-only GitHub API connector with optional ``gh`` CLI authentication."""
from __future__ import annotations

import asyncio
import base64
import binascii
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

from connectors.browser import open_url
from connectors import credentials

API = 'https://api.github.com'
MAX_RESULTS = 50
MAX_BODY = 4000
MAX_FILE_CHARS = 20_000
MAX_TREE_BYTES = 7_500_000
TIMEOUT = 15
TOOLS = {
    'github_list_repositories', 'github_list_issues', 'github_list_pull_requests',
    'github_get_issue', 'github_get_pull_request', 'github_get_repository',
    'github_connection_status', 'github_authorize',
    'github_list_repository_files', 'github_read_repository_file',
    'github_find_relevant_files', 'github_read_repository_files',
    'github_analyze_repository',
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
    opened = open_url(auth_url)
    return {'success': opened,
            'message': 'Opened GitHub authorization in your browser. Approve access to connect your account.',
            'auth_url': auth_url,
            **({} if opened else {'error': 'Could not open a visible browser window.'})}


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


def _repository_path(value, *, allow_empty=False):
    if allow_empty and (value is None or value == ''):
        return ''
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError('path must be a repository-relative file or folder')
    parts = value.split('/')
    if any(part in {'', '.', '..'} or '\\' in part or any(ord(ch) < 32 for ch in part)
           for part in parts):
        raise ValueError('path must be a repository-relative file or folder')
    return '/'.join(urllib.parse.quote(part, safe='') for part in parts)


def _url(path, query=None):
    if not path.startswith('/') or '://' in path or '\\' in path:
        raise ValueError('invalid endpoint')
    return API + path + (('?' + urllib.parse.urlencode(query)) if query else '')


def _request(url, token='', max_bytes=1_000_000):
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'JARVIS-OMA'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers, method='GET')
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise RuntimeError('GitHub response is too large')
        return json.loads(body.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'GitHub request failed (HTTP {exc.code})') from None
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError('GitHub request failed') from None


async def _gh_request(path, max_bytes=1_000_000):
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
    if len(output) > max_bytes:
        raise RuntimeError('GitHub response is too large')
    try:
        return json.loads(output.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        raise RuntimeError('GitHub CLI returned an invalid response') from None


async def _fetch(path, query=None, *, max_bytes=1_000_000):
    url = _url(path, query)
    token = _token()
    if token:
        if max_bytes == 1_000_000:
            return await asyncio.to_thread(_request, url, token)
        return await asyncio.to_thread(_request, url, token, max_bytes)
    try:
        gh_path = path + (('?' + urllib.parse.urlencode(query)) if query else '')
        if max_bytes == 1_000_000:
            return await _gh_request(gh_path)
        return await _gh_request(gh_path, max_bytes=max_bytes)
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
    if tool == 'github_list_repository_files':
        if not isinstance(data, list):
            return {'success': False, 'error': 'GitHub path is not a folder'}
        items = [
            {key: item.get(key) for key in ('name', 'path', 'type', 'size')}
            for item in data[:100] if isinstance(item, dict)
        ]
        return {'success': True, 'count': len(items), 'truncated': len(data) > 100,
                'items': items}
    if tool == 'github_read_repository_file':
        if not isinstance(data, dict) or data.get('type') != 'file':
            return {'success': False, 'error': 'GitHub path is not a file'}
        if data.get('encoding') != 'base64' or not isinstance(data.get('content'), str):
            return {'success': False, 'error': 'GitHub file content is unavailable or too large'}
        try:
            raw = base64.b64decode(''.join(data['content'].split()), validate=True)
            content = raw.decode('utf-8')
        except (ValueError, UnicodeError, binascii.Error):
            return {'success': False, 'error': 'GitHub file is not readable text'}
        if '\x00' in content:
            return {'success': False, 'error': 'GitHub file is not readable text'}
        return {'success': True, 'path': data.get('path'), 'size': data.get('size'),
                'truncated': len(content) > MAX_FILE_CHARS,
                'content': content[:MAX_FILE_CHARS]}
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
    if tool in {'github_list_repository_files', 'github_read_repository_file'}:
        path = _repository_path(args.get('path'), allow_empty=tool == 'github_list_repository_files')
        if tool == 'github_read_repository_file' and not path:
            raise ValueError('path must be a repository-relative file')
        return base + '/contents' + (('/' + path) if path else ''), None
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


def _snapshot_ref(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{40,64}', value):
        raise ValueError('ref must be a commit SHA returned by github_find_relevant_files')
    return value.lower()


def _file_score(path, terms):
    lower = path.casefold()
    name = lower.rsplit('/', 1)[-1]
    score = sum((8 if term in name else 3 if term in lower else 0) for term in terms)
    if name in {'readme.md', 'pyproject.toml', 'package.json', 'cargo.toml',
                'go.mod', 'requirements.txt', 'config.toml'}:
        score += 2
        if '/' not in lower:
            score += 4
    if name in {'main.py', 'app.py', 'index.ts', 'index.js', 'server.py'}:
        score += 2
        if lower.count('/') <= 2:
            score += 3
    if any(segment in {'node_modules', 'vendor', 'dist', 'build', '.venv',
                       '__pycache__'} for segment in lower.split('/')):
        score -= 20
    if name.endswith(('.lock', '.min.js', '.map', '.svg', '.png', '.jpg')):
        score -= 15
    return score


async def _find_relevant_files(args):
    owner = _segment(args.get('owner'), 'owner')
    repository = _segment(args.get('repository'), 'repository')
    query = args.get('query', '')
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError('query must be at most 200 characters')
    limit = args.get('max_results', 20)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError('max_results must be between 1 and 30')
    base = f'/repos/{owner}/{repository}'
    repo = await _fetch(base)
    branch = repo.get('default_branch') if isinstance(repo, dict) else None
    if not isinstance(branch, str) or not branch:
        return {'success': False, 'error': 'Repository default branch is unavailable'}
    commit = await _fetch(base + '/commits/' + urllib.parse.quote(branch, safe=''))
    ref = _snapshot_ref(commit.get('sha') if isinstance(commit, dict) else None)
    tree = await _fetch(base + '/git/trees/' + ref, {'recursive': 1},
                        max_bytes=MAX_TREE_BYTES)
    if not isinstance(tree, dict) or not isinstance(tree.get('tree'), list):
        return {'success': False, 'error': 'Repository tree is unavailable'}
    terms = [term for term in re.findall(r'[a-z0-9_]+', query.casefold())
             if len(term) >= 2 and term not in {'the', 'and', 'for', 'with', 'this',
                                                 'that', 'repo', 'repository', 'code', 'analyze'}]
    files = []
    for item in tree['tree']:
        if not isinstance(item, dict) or item.get('type') != 'blob':
            continue
        path, size = item.get('path'), item.get('size')
        if not isinstance(path, str) or not isinstance(size, int) or size > 750_000:
            continue
        if path.casefold().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp',
                                     '.pdf', '.zip', '.gz', '.woff', '.ttf',
                                     '.mp3', '.wav', '.mp4', '.ico', '.pyc', '.class')):
            continue
        try:
            _repository_path(path)
        except ValueError:
            continue
        files.append({'path': path, 'size': size, 'score': _file_score(path, terms)})
    files.sort(key=lambda item: (-item['score'], item['path'].casefold()))
    selected = files[:limit]
    return {'success': True, 'repository': f'{owner}/{repository}', 'ref': ref,
            'files': [{'path': item['path'], 'size': item['size']} for item in selected],
            'total_readable_files': len(files), 'tree_truncated': bool(tree.get('truncated')),
            'selection': 'path-based candidates; inspect file contents before making claims'}


async def _read_repository_files(args):
    owner = _segment(args.get('owner'), 'owner')
    repository = _segment(args.get('repository'), 'repository')
    ref = _snapshot_ref(args.get('ref'))
    paths = args.get('paths')
    if not isinstance(paths, list) or not 1 <= len(paths) <= 6:
        raise ValueError('paths must contain 1 to 6 repository files')
    if any(not isinstance(path, str) for path in paths) or len(set(paths)) != len(paths):
        raise ValueError('paths must be unique repository files')
    encoded = [_repository_path(path) for path in paths]
    semaphore = asyncio.Semaphore(3)

    async def read_one(path, encoded_path):
        async with semaphore:
            try:
                data = await _fetch(f'/repos/{owner}/{repository}/contents/{encoded_path}',
                                    {'ref': ref})
                mapped = _mapped('github_read_repository_file', data)
            except Exception:
                mapped = {'success': False, 'error': 'GitHub file read failed'}
            if not mapped.get('success'):
                return {'path': path, 'success': False, 'error': mapped.get('error', 'File unavailable')}
            content = mapped['content']
            excerpt = content[:5_000]
            numbered = '\n'.join(f'{index}: {line}' for index, line in
                                 enumerate(excerpt.splitlines(), 1))
            line_count = len(excerpt.splitlines())
            source = ('https://github.com/' + owner + '/' + repository + '/blob/' + ref +
                      '/' + urllib.parse.quote(path, safe='/') +
                      (f'#L1-L{line_count}' if line_count else ''))
            return {'path': path, 'success': True, 'content': numbered,
                    'line_start': 1, 'line_end': line_count, 'url': source,
                    'truncated': mapped['truncated'] or len(content) > len(excerpt)}

    results = await asyncio.gather(*(read_one(path, encoded_path)
                                     for path, encoded_path in zip(paths, encoded)))
    return {'success': any(item['success'] for item in results),
            'repository': f'{owner}/{repository}', 'ref': ref, 'files': results}


async def _analyze_repository(args):
    """Return code evidence in one call for a short live voice turn."""
    found = await _find_relevant_files({**args, 'max_results': 12})
    if not found.get('success'):
        return found
    candidates = found['files']
    if not candidates:
        return {'success': False, 'error': 'No readable repository files were found',
                'repository': found['repository'], 'ref': found['ref']}
    # GitHub can list a blob in a tree but decline to return its Contents API
    # representation (for example a symlink). Try the next candidates instead
    # of returning an empty analysis after the first unreadable group.
    evidence = []
    attempted = []
    for offset in range(0, len(candidates), 4):
        paths = [item['path'] for item in candidates[offset:offset + 4]]
        read = await _read_repository_files({
            'owner': args.get('owner'), 'repository': args.get('repository'),
            'ref': found['ref'], 'paths': paths,
        })
        attempted.extend(read['files'])
        evidence.extend(item for item in read['files'] if item['success'])
        if len(evidence) >= 4:
            break
    evidence = evidence[:4]
    return {'success': bool(evidence),
            **({} if evidence else {'error': 'No candidate file content could be read'}),
            'repository': found['repository'],
            'ref': found['ref'], 'files': evidence,
            'unreadable_paths': [item['path'] for item in attempted if not item['success']],
            'candidate_paths': [item['path'] for item in candidates],
            'total_readable_files': found['total_readable_files'],
            'tree_truncated': found['tree_truncated'],
            'scope': 'Up to four path-ranked files; request more files for deeper analysis'}


async def dispatch(tool: str, arguments: dict):
    if tool not in TOOLS:
        return {'success': False, 'error': 'unsupported_tool'}
    try:
        if not isinstance(arguments, dict):
            raise ValueError('arguments must be an object')
        if tool == 'github_authorize':
            return github_authorize()
        if tool == 'github_find_relevant_files':
            return await _find_relevant_files(arguments)
        if tool == 'github_read_repository_files':
            return await _read_repository_files(arguments)
        if tool == 'github_analyze_repository':
            return await _analyze_repository(arguments)
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
