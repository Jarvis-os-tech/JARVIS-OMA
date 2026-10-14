#!/usr/bin/env python3
"""Copy existing Google/GitHub credentials into private project storage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors import credentials

KEYS = ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GITHUB_CLIENT_ID',
        'GITHUB_CLIENT_SECRET', 'GITHUB_TOKEN', 'GH_TOKEN')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/home/g0pi/Projects/JARVIS-OS-1'))
    args = parser.parse_args()
    try:
        source = credentials.read_env(args.source / '.env')
        existing = credentials.read_env(credentials.SECRET_DIR / 'credentials.env')
        selected = {key: existing.get(key) or source.get(key) for key in KEYS}
        client_file = Path.home() / '.config/gws/client_secret.json'
        if client_file.is_file():
            client = json.loads(client_file.read_text(encoding='utf-8'))
            client = client.get('installed', client.get('web', {}))
            selected['GOOGLE_CLIENT_ID'] = selected.get('GOOGLE_CLIENT_ID') or client.get('client_id')
            selected['GOOGLE_CLIENT_SECRET'] = selected.get('GOOGLE_CLIENT_SECRET') or client.get('client_secret')
        if not selected.get('GITHUB_TOKEN') and not selected.get('GH_TOKEN'):
            try:
                result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    selected['GITHUB_TOKEN'] = result.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        selected = {key: value for key, value in selected.items() if value}
        if selected:
            credentials.save_env_values(selected)
        copied_tokens = credentials.token_path().is_file()
        token_candidates = [args.source / 'connectors/google_tokens.json',
                            args.source / 'connectors/tokens.json',
                            Path.home() / '.config/jarvis-os/google_tokens.json',
                            Path.home() / '.config/google-mcp/tokens.json',
                            Path.home() / '.config/friday-os/google_tokens.json']
        if not copied_tokens:
            for path in token_candidates:
                if path.is_file():
                    tokens = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(tokens, dict) or not any(tokens.get(k) for k in ('refresh_token', 'access_token', 'token')):
                        continue
                    credentials.save_tokens(tokens)
                    copied_tokens = True
                    break
        print(json.dumps({'credential_names_imported': sorted(selected),
                          'google_tokens_available': copied_tokens,
                          'github_token_available': bool(selected.get('GITHUB_TOKEN') or selected.get('GH_TOKEN')),
                          'private_directory': str(credentials.SECRET_DIR)}))
        return 0
    except (OSError, ValueError):
        print('Credential import failed; check source files and permissions (values withheld).', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
