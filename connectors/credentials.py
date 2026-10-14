"""Private connector credentials; no shell evaluation or secret logging."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECRET_DIR = Path(os.environ.get('JARVIS_CONNECTOR_SECRET_DIR', str(PROJECT_ROOT / 'connectors/.secrets')))


def read_env(path):
    values = {}
    path = Path(path)
    if not path.is_file():
        return values
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:].strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, raw = line.split('=', 1)
        key = key.strip()
        if not key.isidentifier():
            continue
        try:
            words = shlex.split(raw, comments=True)
        except ValueError:
            continue
        values[key] = ' '.join(words)
    return values


def get(name, default=''):
    """Prefer current process credentials, then the imported connector file."""
    return os.environ.get(name) or read_env(SECRET_DIR / 'credentials.env').get(name) or default


def token_path():
    return SECRET_DIR / 'google_tokens.json'


def secure_write(path, content):
    """Atomically save owner-only connector state; reject symlink destinations."""
    path = Path(path)
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('credential destination must not contain symlinks')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix='.private-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_tokens(tokens):
    secure_write(token_path(), json.dumps(tokens, indent=2))


def save_env_values(values):
    """Merge connector credentials into owner-only storage."""
    path = SECRET_DIR / 'credentials.env'
    existing = read_env(path)
    existing.update({key: value for key, value in values.items() if value})
    content = ''.join(
        key + '=' + shlex.quote(value) + '\n'
        for key, value in sorted(existing.items())
    )
    secure_write(path, content)
