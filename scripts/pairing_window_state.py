"""Private, expiring pairing-window acknowledgements; contains no API keys."""
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time


def directory():
    base = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home() / '.local/state'))
    return base / 'jarvis' / 'pairing-windows'


def path_for(session, root=None):
    if not isinstance(session, str) or not re.fullmatch(r'[a-f0-9]{64}', session):
        raise ValueError('Invalid pairing session')
    return Path(root or directory()) / (session + '.json')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.session-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def create(root=None, now=None):
    session = secrets.token_hex(32)
    write(path_for(session, root), {'expires_at': (time.time() if now is None else now) + 300,
                                  'confirmed': False})
    return session


def confirm(session, root=None, now=None):
    path = path_for(session, root)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    if data['expires_at'] < (time.time() if now is None else now):
        return False
    data['confirmed'] = True
    write(path, data)
    return True


def status(session):
    data = json.loads(path_for(session).read_text())
    if data['expires_at'] < time.time():
        return 'expired'
    return 'confirmed' if data['confirmed'] else 'pending'
