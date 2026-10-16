#!/usr/bin/env python3
"""Authorize the local GitHub connector in a browser using OAuth and PKCE."""
from __future__ import annotations

import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors import credentials
from connectors.github import _NoRedirect

AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
CALLBACK_PATH = '/api/connectors/callback'
REGISTERED_REDIRECT_URI = 'http://localhost:3000' + CALLBACK_PATH
SCOPES = ('repo', 'workflow', 'notifications', 'read:user')


def _client_credentials():
    project_env = credentials.read_env(credentials.PROJECT_ROOT / '.env')
    return (
        credentials.get('GITHUB_CLIENT_ID') or project_env.get('GITHUB_CLIENT_ID', ''),
        credentials.get('GITHUB_CLIENT_SECRET') or project_env.get('GITHUB_CLIENT_SECRET', ''),
    )


def _authorization_url(client_id, state, challenge, redirect_uri=REGISTERED_REDIRECT_URI):
    return AUTHORIZE_URL + '?' + urllib.parse.urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': ' '.join(SCOPES),
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'select_account',
    })


def _exchange_code(client_id, client_secret, code, verifier, redirect_uri=REGISTERED_REDIRECT_URI):
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': verifier,
        }).encode(),
        method='POST',
        headers={'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
    )
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=15) as response:
        result = json.loads(response.read(100_000))
    if not isinstance(result, dict) or not result.get('access_token'):
        raise RuntimeError('GitHub did not return an access token')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='Print the login URL instead of opening it')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--port', type=int, default=0,
                        help='Local callback port (default: choose a free port)')
    args = parser.parse_args()
    client_id, client_secret = _client_credentials()
    if not client_id or not client_secret:
        print('GitHub OAuth client credentials are missing from .env or private connector storage.')
        return 1

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    received = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            values = urllib.parse.parse_qs(url.query)
            callback_state = values.get('state', [''])[0]
            valid = (url.path == CALLBACK_PATH and callback_state
                     and secrets.compare_digest(callback_state, state))
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid GitHub authorization callback.')
                return
            if values.get('code'):
                received['code'] = values['code'][0]
                message = b'GitHub authorization received. You may close this tab.'
            else:
                received['error'] = values.get('error', ['access_denied'])[0]
                message = b'GitHub authorization was declined.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(message)

        def log_message(self, *args):
            pass

    try:
        if args.port < 0 or args.port > 65535:
            raise OSError
        server = HTTPServer(('127.0.0.1', args.port), Callback)
    except OSError:
        print('The requested GitHub callback port is unavailable; choose another with --port.')
        return 1

    server.timeout = 1
    callback_port = server.server_address[1]
    redirect_uri = f'http://localhost:{callback_port}{CALLBACK_PATH}'
    url = _authorization_url(client_id, state, challenge, redirect_uri)
    print('Authorize GitHub access in the browser. Waiting up to ' + str(args.timeout) + ' seconds.', flush=True)
    print(url, flush=True)
    if not args.no_browser and not webbrowser.open(url):
        print('The browser could not be opened automatically; open the URL above manually.', flush=True)
    try:
        deadline = time.monotonic() + max(1, min(args.timeout, 600))
        while not received and time.monotonic() < deadline:
            server.handle_request()
    except KeyboardInterrupt:
        print('GitHub setup cancelled.')
        return 1
    finally:
        server.server_close()

    if not received.get('code'):
        print('GitHub setup requires account consent; no token was saved.')
        return 1
    try:
        token = _exchange_code(client_id, client_secret, received['code'], verifier, redirect_uri)
        credentials.save_env_values({
            'GITHUB_CLIENT_ID': client_id,
            'GITHUB_CLIENT_SECRET': client_secret,
            'GITHUB_TOKEN': token['access_token'],
        })
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
        print('GitHub token exchange failed; credential values withheld.')
        return 1

    granted = {item.strip() for item in token.get('scope', '').split(',') if item.strip()}
    missing = set(SCOPES) - granted
    if missing:
        print('GitHub account connected, but some requested permissions were not granted: '
              + ', '.join(sorted(missing)))
    else:
        print('GitHub account connected. Token saved privately in this project.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
