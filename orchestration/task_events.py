"""Persistent task presentation facts, separate from transcripts and execution.

This journal observes authoritative jobs. Replaying it never executes work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

from jsonschema import Draft202012Validator

CONTRACT = json.loads((Path(__file__).resolve().parents[1] / 'contracts/task-event-v1.json').read_text())
VALIDATOR = Draft202012Validator(CONTRACT)
TERMINAL = frozenset(CONTRACT['x-terminal-states'])


def validate_event(event):
    VALIDATOR.validate(event)
    if event['terminal'] != (event['state'] in TERMINAL):
        raise ValueError('Terminal flag disagrees with task state')
    progress = event['progress']
    if progress and progress['completed'] > progress['total']:
        raise ValueError('Progress exceeds the measured total')
    evidence = event['evidence']
    if evidence['verified'] != (event['state'] == CONTRACT['x-verified-state']):
        raise ValueError('Only an evidenced completion may be marked verified')
    if evidence['verified'] and evidence['scope'] not in CONTRACT['x-verified-scopes']:
        raise ValueError('Completion needs a concrete verification scope')
    return event


def widget_id(task_id):
    return 'jtask_' + hashlib.sha256(task_id.encode()).hexdigest()[:24]


class TaskEventStore:
    """Atomic bounded snapshots/outbox; monotonically ordered across restarts."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError('Task journal must not be linked')
        info = self.path.parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Task journal directory must be private and user-owned')
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        self.path.chmod(0o600)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY, stream TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT);
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, signature TEXT, generation INTEGER, source_revision INTEGER,
                    revision INTEGER, sequence INTEGER, terminal INTEGER, event TEXT, acknowledged INTEGER DEFAULT 0);
            ''')
            db.execute('INSERT OR IGNORE INTO meta VALUES (1, ?)', (uuid.uuid4().hex,))
            self.stream_id = db.execute('SELECT stream FROM meta WHERE id=1').fetchone()[0]

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def publish(self, candidate, *, source_revision=0):
        """A producer generation fences retries; revisions fence delayed updates."""
        payload = json.loads(json.dumps(candidate, allow_nan=False))
        identity = payload['task_id']
        payload['widget_id'] = widget_id(identity)
        signature = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        generation = payload['generation']
        if type(source_revision) is not int or source_revision < 0:
            raise ValueError('Invalid producer revision')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT signature,generation,source_revision,revision,event FROM snapshots WHERE id=?', (identity,)).fetchone()
            if row:
                old = json.loads(row[4])
                if generation < row[1]:
                    return None
                if signature == row[0]:
                    if source_revision > row[2]:
                        db.execute('UPDATE snapshots SET source_revision=? WHERE id=?', (source_revision, identity))
                    return None
                if generation == row[1]:
                    if source_revision and row[2] and source_revision < row[2]:
                        return None
                    recovery = payload['state'] == 'interrupted' and not old['terminal']
                    if source_revision and source_revision == row[2] and not recovery:
                        return None
                    if old['terminal']:
                        # A finished attempt never becomes active again. A new
                        # attempt must carry a larger explicit owner generation.
                        return None
                    if old['state'] in {'running', 'cancelling'} and payload['state'] == 'queued':
                        return None
                    if old['state'] == 'cancelling' and payload['state'] in {'running', 'waiting_confirmation'}:
                        return None
                    if old['progress'] and payload['progress'] and payload['progress']['completed'] < old['progress']['completed']:
                        return None
                revision = row[3] + 1
            else:
                revision = 1
                if db.execute('SELECT count(*) FROM snapshots').fetchone()[0] >= 128:
                    victim = db.execute('SELECT id FROM snapshots WHERE terminal=1 AND acknowledged>=revision ORDER BY sequence LIMIT 1').fetchone()
                    if not victim:
                        raise ValueError('Task view capacity reached; pending outcomes need review')
                    db.execute('DELETE FROM snapshots WHERE id=?', victim)
            sequence = db.execute('INSERT INTO events(event) VALUES(NULL)').lastrowid
            event = dict(payload, schema_version=1, stream_id=self.stream_id, sequence=sequence,
                         revision=revision, updated_at=datetime.now(timezone.utc).isoformat())
            validate_event(event)
            encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
            db.execute('UPDATE events SET event=? WHERE sequence=?', (encoded, sequence))
            db.execute('''INSERT INTO snapshots(id,signature,generation,source_revision,revision,sequence,terminal,event)
                          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                          signature=excluded.signature,generation=excluded.generation,source_revision=excluded.source_revision,
                          revision=excluded.revision,sequence=excluded.sequence,terminal=excluded.terminal,event=excluded.event''',
                       (identity, signature, generation, source_revision, revision, sequence, event['terminal'], encoded))
            db.execute('DELETE FROM events WHERE sequence <= ?', (sequence - 256,))
            return event

    def snapshots(self):
        with self._connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT event FROM snapshots ORDER BY sequence')]

    def lookup(self, identity):
        with self._connect() as db:
            row = db.execute('SELECT event FROM snapshots WHERE id=?', (identity,)).fetchone()
            return json.loads(row[0]) if row else None

    def replay(self, after=0):
        if type(after) is not int or after < 0:
            raise ValueError('Invalid replay cursor')
        with self._connect() as db:
            first = db.execute('SELECT min(sequence) FROM events').fetchone()[0]
            resync = first is not None and after < first - 1
            rows = db.execute('SELECT event FROM snapshots ORDER BY sequence') if resync else db.execute(
                'SELECT event FROM events WHERE sequence>? ORDER BY sequence', (after,))
            return {'stream_id': self.stream_id, 'resync': resync, 'events': [json.loads(row[0]) for row in rows]}

    def notices(self, sources):
        with self._connect() as db:
            rows = db.execute('SELECT event FROM snapshots WHERE terminal=1 AND acknowledged<revision ORDER BY sequence')
            return [json.loads(row[0]) for row in rows if json.loads(row[0])['source'] in sources]

    def acknowledge(self, sequence):
        with self._connect() as db:
            # A late delivery acknowledgement cannot acknowledge a newer event.
            db.execute('UPDATE snapshots SET acknowledged=revision WHERE sequence=?', (sequence,))
