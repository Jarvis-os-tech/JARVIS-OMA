"""Bounded private observation events; successful delivery is not verification."""
import asyncio
from contextlib import contextmanager
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import uuid

from core.secret_env import is_secret_name
from core.workers import BoundedWorker
from .bundles import private_directory

log = logging.getLogger(__name__)


class EpisodeStore:
    def __init__(self, root):
        self.root = private_directory(root)
        self.path = self.root / 'episodes.sqlite3'
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        self.path.chmod(0o600)
        with self._connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS events ('
                               'sequence INTEGER PRIMARY KEY AUTOINCREMENT, '
                               'episode TEXT NOT NULL, kind TEXT NOT NULL, '
                               'observed_at REAL NOT NULL, payload TEXT NOT NULL)')
            connection.execute('CREATE INDEX IF NOT EXISTS episode_events ON events(episode, sequence)')

    @contextmanager
    def _connect(self):
        if self.path.is_symlink():
            raise ValueError('Symlink evidence database rejected')
        connection = sqlite3.connect(self.path, timeout=2)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def append(self, episode, kind, payload):
        with self._connect() as connection:
            connection.execute('INSERT INTO events(episode, kind, observed_at, payload) VALUES (?, ?, ?, ?)',
                               (episode, kind, time.time(), json.dumps(payload, ensure_ascii=False)))

    def read(self, episode):
        with self._connect() as connection:
            rows = connection.execute('SELECT sequence,kind,observed_at,payload FROM events '
                                      'WHERE episode=? ORDER BY sequence', (episode,)).fetchall()
        return [{'sequence': seq, 'kind': kind, 'observed_at': when, 'payload': json.loads(data)}
                for seq, kind, when, data in rows]

    def feedback(self, episode, text):
        if not self.read(episode):
            raise ValueError('Unknown episode')
        payload = sanitize({'text': text, 'authority': 'user', 'diagnosis': 'unknown'})
        self.append(episode, 'user_correction', payload)

    def recent(self):
        with self._connect() as connection:
            rows = connection.execute('SELECT episode, observed_at, payload FROM events '
                                      "WHERE kind='started' ORDER BY sequence DESC LIMIT 20").fetchall()
        return [{'episode': episode, 'observed_at': when,
                 'identity': json.loads(payload)['data']} for episode, when, payload in rows]


def sanitize(value):
    """Bound capture and remove recognized secrets; not a comprehensive DLP scanner."""
    secrets = [v for k, v in os.environ.items() if is_secret_name(k) and len(v) >= 8]
    redacted = truncated = False

    def clean(item, depth=0):
        nonlocal redacted, truncated
        if depth > 6:
            truncated = True
            return '[depth limit]'
        if isinstance(item, dict):
            out = {}
            if len(item) > 32:
                truncated = True
            for key, child in list(item.items())[:32]:
                if is_secret_name(str(key)) or str(key).lower() in {
                        'image_b64', 'image_base64', 'image_bytes', 'frame_bytes',
                        'audio_bytes', 'video_bytes', 'screenshot', 'audio', 'video'}:
                    redacted = True
                    out[str(key)[:100]] = '[redacted]'
                else:
                    out[str(key)[:100]] = clean(child, depth + 1)
            return out
        if isinstance(item, (bytes, bytearray)):
            redacted = True
            return {'omitted_binary_bytes': len(item)}
        if isinstance(item, (list, tuple)):
            if len(item) > 32:
                truncated = True
            return [clean(child, depth + 1) for child in item[:32]]
        if item is None or isinstance(item, (bool, int)):
            return item
        text = str(item)
        for secret in secrets:
            if secret in text:
                redacted = True
                text = text.replace(secret, '[redacted]')
        text, count = re.subn(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+', r'\1[redacted]', text)
        redacted |= bool(count)
        if len(text) > 4000:
            text = text[:4000]
            truncated = True
        return text

    payload = clean(value)
    if len(json.dumps(payload, ensure_ascii=False)) > 24000:
        payload = {'omitted': 'event exceeded capture limit'}
        truncated = True
    return {'data': payload, 'redacted': redacted, 'truncated': truncated}


class EpisodeCapture:
    def __init__(self, store, bundle, model, *, capacity=32):
        self.store, self.bundle, self.model = store, bundle, model
        self.capacity = capacity
        self.worker = BoundedWorker('jarvis-evidence', capacity=capacity)
        self.tasks = set()
        self.current = self.previous = None
        self.dropped = self.failed = 0
        self.closed = False
        self.pending_actions = {}
        self.incomplete = set()
        self.response_seen = False
        self.context = {}

    def configure(self, configuration, model):
        self.model = model
        self.context = {'prompt_sha256': hashlib.sha256(
            configuration['system_instruction'].encode()).hexdigest(),
            'tools_sha256': hashlib.sha256(json.dumps(configuration.get('tools', []),
                sort_keys=True).encode()).hexdigest()}

    def emit(self, episode, kind, payload):
        if self.closed or len(self.tasks) >= self.capacity:
            self.dropped += 1
            self.incomplete.add(episode)
            return
        payload = sanitize(payload)
        task = asyncio.create_task(self.worker.run(self.store.append, episode, kind, payload))
        self.tasks.add(task)

        def finished(result):
            self.tasks.discard(result)
            if result.cancelled() or result.exception() is not None:
                self.failed += 1
                self.incomplete.add(episode)
                log.warning('Learning evidence capture failed; episode is incomplete')
        task.add_done_callback(finished)

    def ensure(self):
        if self.current is None:
            self.response_seen = False
            self.current = uuid.uuid4().hex
            self.emit(self.current, 'started', {'bundle': self.bundle.digest, 'role': self.bundle.role,
                      'model': self.model, 'previous_episode': self.previous,
                      'diagnosis': 'unknown', 'verified': False, **self.context})
        return self.current

    def input(self, text):
        if text:
            self.emit(self.ensure(), 'user_input', {'text': text})

    def output(self, text):
        self.response_seen = True
        if self.current and text:
            self.emit(self.current, 'assistant_output', {'text': text})

    def action_start(self, call_id, name, arguments):
        episode = self.ensure()
        self.pending_actions[call_id] = episode
        self.emit(episode, 'action_started', {'call_id': call_id, 'tool': name, 'arguments': arguments})
        return episode

    def action_end(self, episode, call_id, response, elapsed_ms):
        self.pending_actions.pop(call_id, None)
        self.emit(episode, 'action_returned', {'call_id': call_id, 'response': response,
                                             'elapsed_ms': round(elapsed_ms, 2), 'verified': False})

    def finish(self, state):
        if self.current is None:
            return
        self.emit(self.current, 'ended', {'state': state, 'verified': False, 'diagnosis': 'unknown',
                  'pending_actions': sum(item == self.current for item in self.pending_actions.values()),
                  'dropped_events': self.dropped, 'failed_events': self.failed})
        self.previous, self.current = self.current, None
        self.response_seen = False

    async def flush(self):
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        for episode in list(self.incomplete):
            try:
                await self.worker.run(self.store.append, episode, 'capture_health', sanitize(
                    {'incomplete': True, 'dropped_events': self.dropped, 'failed_events': self.failed}))
            except Exception:
                log.warning('Could not persist incomplete learning capture status')
            else:
                self.incomplete.discard(episode)
        return {'dropped_events': self.dropped, 'failed_events': self.failed}

    async def close(self):
        self.finish('interrupted')
        await self.flush()
        self.closed = True
        await self.worker.close()

