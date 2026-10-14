#!/usr/bin/env python3
"""Authorize the local Google connector with state validation and PKCE."""
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
from connectors.google_workspace import _NoRedirect

SCOPES = ('https://mail.google.com/', 'https://www.googleapis.com/auth/calendar',
          'https://www.googleapis.com/auth/tasks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='Print the login URL instead of opening it')
    parser.add_argument('--port', type=int, default=None, help='Port to listen on for OAuth callback')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    client_id, client_secret = credentials.get('GOOGLE_CLIENT_ID'), credentials.get('GOOGLE_CLIENT_SECRET')
    if not client_id or not client_secret:
        print('Google client credentials are missing; run scripts/import_connector_credentials.py first.')
        return 1
    from connectors.google_workspace import _find_free_oauth_port
    port = args.port or _find_free_oauth_port()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    redirect_uri = f'http://localhost:{port}/callback'
    received = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            values = urllib.parse.parse_qs(url.query)
            valid = url.path == '/callback' and secrets.compare_digest(values.get('state', [''])[0], state)
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid authorization callback.')
                return
            if values.get('code'):
                received['code'] = values['code'][0]
                message = b'Google authorization received. You may close this tab.'
            else:
                received['error'] = True
                message = b'Google authorization was declined.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(message)

        def log_message(self, *args):
            pass

    try:
        server = HTTPServer(('127.0.0.1', port), Callback)
    except OSError:
        print(f'Google callback port {port} is unavailable; close the other listener and retry.')
        return 1
    server.timeout = 1
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'scope': ' '.join(SCOPES), 'state': state, 'access_type': 'offline',
        'prompt': 'consent', 'code_challenge': challenge, 'code_challenge_method': 'S256'})
    print('Authorize Google account access in the browser. Waiting up to ' + str(args.timeout) + ' seconds.', flush=True)
    print(url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        deadline = time.monotonic() + max(1, min(args.timeout, 600))
        while not received and time.monotonic() < deadline:
            server.handle_request()
    except KeyboardInterrupt:
        print('Google setup cancelled.')
        return 1
    finally:
        server.server_close()
    if not received.get('code'):
        print('Google setup requires account consent; no token was saved.')
        return 1
    request = urllib.request.Request('https://oauth2.googleapis.com/token',
        data=urllib.parse.urlencode({'client_id': client_id, 'client_secret': client_secret,
            'code': received['code'], 'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri, 'code_verifier': verifier}).encode(), method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=15) as response:
            tokens = json.loads(response.read(100000))
        if not tokens.get('access_token') or not tokens.get('refresh_token'):
            print('Google did not provide reusable authorization; repeat account consent.')
            return 1
        tokens['expires_at'] = time.time() + int(tokens.get('expires_in', 3600))
        credentials.save_tokens(tokens)
    except Exception:
        print('Google token exchange failed; credential values withheld.')
        return 1
    print('Google account connected. Tokens saved privately in this project.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
