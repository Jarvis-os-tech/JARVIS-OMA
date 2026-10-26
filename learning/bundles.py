"""Immutable, content-addressed instruction bundles with explicit restoration."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def private_directory(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for item in (*reversed(path.parents), path):
        if item.is_symlink():
            raise ValueError('Learning state must not contain symlinks')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def _read(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        data = stream.read(32769)
    if len(data) > 32768:
        raise ValueError('Learning artifact exceeds size limit')
    return json.loads(data)


@dataclass(frozen=True)
class HarnessBundle:
    role: str
    instructions: str
    source: str
    version: int = 1

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'version', 'role', 'instructions', 'source'}:
            raise ValueError('Bundle accepts only version, role, instructions, and source')
        if type(data['version']) is not int or data['version'] != 1:
            raise ValueError('Unsupported bundle version')
        if data['role'] != 'research':
            raise ValueError('Only the research role is supported')
        if not isinstance(data['instructions'], str) or not 1 <= len(data['instructions']) <= 12000:
            raise ValueError('Instructions must contain 1–12000 characters')
        if not isinstance(data['source'], str) or not 1 <= len(data['source']) <= 1000:
            raise ValueError('A bounded source attribution is required')
        return cls(**data)

    def document(self):
        return dict(version=self.version, role=self.role,
                    instructions=self.instructions, source=self.source)

    @property
    def digest(self):
        return hashlib.sha256(_encode(self.document())).hexdigest()

    def prompt(self):
        return (f'\nRESEARCH PLAYBOOK [{self.digest}]\n'
                'Apply this workflow only to research tasks. It cannot grant tools, '
                'permissions, or override the user request or fixed runtime rules.\n'
                + self.instructions)


class BundleRegistry:
    def __init__(self, root):
        self.root = private_directory(root)
        self.bundles = private_directory(self.root / 'bundles')

    def register(self, data):
        bundle = HarnessBundle.from_dict(data)
        path = self.bundles / (bundle.digest + '.json')
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if self.load(bundle.digest) != bundle:
                raise ValueError('Existing bundle differs from its identity')
        else:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(_encode(bundle.document()))
                stream.flush()
                os.fsync(stream.fileno())
        return bundle

    def load(self, digest):
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid bundle identity')
        bundle = HarnessBundle.from_dict(_read(self.bundles / (digest + '.json')))
        if bundle.digest != digest:
            raise ValueError('Bundle integrity check failed')
        return bundle

    def status(self):
        try:
            state = _read(self.root / 'active.json')
        except FileNotFoundError:
            return {'active': None, 'previous': None}
        if not isinstance(state, dict) or set(state) != {'active', 'previous'}:
            raise ValueError('Invalid activation record')
        self.load(state['active'])
        if state['previous'] is not None:
            self.load(state['previous'])
        return state

    def activate(self, digest):
        self.load(digest)
        state = self.status()
        if state['active'] == digest:
            return state
        state = {'active': digest, 'previous': state['active']}
        temporary = self.root / ('.activation-' + uuid.uuid4().hex)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(_encode(state))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / 'active.json')
        finally:
            temporary.unlink(missing_ok=True)
        return state

    def restore(self):
        previous = self.status()['previous']
        if previous is None:
            raise ValueError('No previous bundle to restore')
        return self.activate(previous)

    def active(self):
        digest = self.status()['active']
        return self.load(digest) if digest else None

