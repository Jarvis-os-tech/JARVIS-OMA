"""Sparse speech updates projected from trusted task presentation snapshots."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import time

from jsonschema import ValidationError
from .task_events import validate_event


_TERMINAL = {'completed', 'response_received', 'failed', 'cancelled', 'timed_out', 'interrupted'}


def _message(event):
    state = event.get('state')
    progress = event.get('progress')
    if state == 'waiting_confirmation':
        return 'Background work is waiting for your confirmation.'
    if state != 'running':
        return ''
    if (isinstance(progress, dict) and type(progress.get('completed')) is int
            and type(progress.get('total')) is int and 0 < progress['completed'] <= progress['total'] <= 30):
        return f"Background work has completed {progress['completed']} of {progress['total']} measured steps."
    return 'Background work is underway.'


class ProgressUpdates:
    """Bounded in-memory deduplication and per-task coalescing for spoken updates."""
    def __init__(self, limit=128):
        self.limit = limit
        self.stream_id = None
        self.seen = OrderedDict()
        self.pending = OrderedDict()
        self.last_delivered_at = None

    def observe(self, snapshots):
        present = set()
        for event in snapshots if isinstance(snapshots, list) else ():
            if not isinstance(event, dict):
                continue
            try:
                validate_event(event)
            except (ValidationError, TypeError, ValueError, KeyError):
                continue
            stream = event.get('stream_id')
            task_id = event.get('task_id')
            generation, revision = event.get('generation'), event.get('revision')
            state = event.get('state')
            if (not isinstance(stream, str) or not stream or not isinstance(task_id, str) or not task_id
                    or event.get('source') not in {'file_task', 'model', 'hermes', 'agent', 'team'}
                    or state not in {'queued', 'running', 'waiting_confirmation', 'cancelling', *_TERMINAL}
                    or type(generation) is not int or generation < 1
                    or type(revision) is not int or revision < 1):
                continue
            present.add(task_id)
            if stream != self.stream_id:
                self.stream_id = stream
                self.seen.clear()
                self.pending.clear()
            prior = self.seen.get(task_id)
            if prior and (generation < prior[0] or (generation == prior[0] and revision <= prior[1])):
                continue
            signature = (generation, state, tuple(sorted((event.get('progress') or {}).items()))
                         if isinstance(event.get('progress'), dict) else None)
            self.seen[task_id] = (generation, revision, signature)
            self.seen.move_to_end(task_id)
            while len(self.seen) > self.limit:
                expired, _ = self.seen.popitem(last=False)
                self.pending.pop(expired, None)
            if event.get('terminal') is True or state in _TERMINAL:
                self.pending.pop(task_id, None)
                continue
            message = _message(event)
            if not message:
                self.pending.pop(task_id, None)
                self.seen[task_id] = (generation, revision, signature)
                continue
            identity = {key: event[key] for key in (
                'task_id', 'stream_id', 'generation', 'revision', 'sequence')}
            if prior and signature == prior[2]:
                # Refresh a waiting delivery fence without repeating an already delivered update.
                if task_id in self.pending:
                    self.pending[task_id] = (message, identity)
                continue
            self.pending[task_id] = (message, identity)
            self.pending.move_to_end(task_id)
            while len(self.pending) > self.limit:
                self.pending.popitem(last=False)
        for task_id in self.pending.keys() - present:
            self.pending.pop(task_id, None)

    def peek(self):
        if not self.pending:
            return None
        return next(iter(self.pending.values()))[0]

    def peek_event(self):
        if not self.pending:
            return None
        return next(iter(self.pending.values()))[1]

    def ready(self, now=None):
        now = time.monotonic() if now is None else now
        return self.last_delivered_at is None or now - self.last_delivered_at >= 20

    def acknowledge(self, now=None):
        if self.pending:
            self.pending.popitem(last=False)
            self.last_delivered_at = time.monotonic() if now is None else now


def _idle(voice):
    return (voice.connected and not voice.muted and not voice.standby_active
            and not voice.standby.engaged and not voice.gate.active
            and not voice.player.is_playing(0.35) and not voice._waiting
            and not voice._reply_authorized and not voice._model_active
            and not voice._tools_in_flight and not voice._drop_response
            and not voice._barge_pending and not voice._background_active
            and not getattr(voice, '_wake_confirmation_pending', False)
            and not getattr(voice, '_wake_confirmation_in_flight', False)
            and not getattr(voice, '_greeting_active', False))


async def announce_progress(voice, control, updates):
    """Speak one fixed, task-fact update only during an idle connected turn."""
    desktop = getattr(control, 'desktop', None)
    presenter = getattr(desktop, '_task_presentation', None)
    if presenter is None or not hasattr(presenter, 'store'):
        return False
    snapshots = await asyncio.to_thread(presenter.store.snapshots)
    updates.observe(snapshots)
    if not _idle(voice) or not updates.ready():
        return False
    message = updates.peek()
    if not message:
        return False
    delivered = await voice.announce_background(message, task_event=updates.peek_event())
    if delivered:
        updates.acknowledge()
    return delivered
