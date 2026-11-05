"""Project task facts into one journal for UI, status receipts and notices."""
from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path
import re
import subprocess
import fcntl

from orchestration.task_events import CONTRACT, TERMINAL, TaskEventStore
from jsonschema import ValidationError
import sqlite3


def _text(value, fallback='', limit=800):
    return re.sub(r'[\x00-\x1f]', ' ', str(value or fallback)).strip()[:limit]


def project(source, job):
    """Observe trusted coordinator metadata, never infer success from result prose."""
    identity = str(job['id'])
    state = job.get('status') or job.get('state') or 'interrupted'
    if state not in CONTRACT['properties']['state']['enum']:
        state = 'interrupted'
    title = job.get('name') or job.get('description') or job.get('task_summary') or job.get('agent') or 'Background task'
    scope, verified, progress = 'none', False, None
    message = job.get('summary') or ''
    if state not in TERMINAL:
        if job.get('cancel_requested'):
            state = 'cancelling'
        elif job.get('pending_approvals'):
            state = 'waiting_confirmation'
    if source == 'file_task':
        complete, total = job.get('completed_steps'), job.get('total_steps')
        if type(complete) is int and type(total) is int and 0 <= complete <= total <= 30 and total > 0:
            progress = {'completed': complete, 'total': total}
        if state == 'completed':
            verified = bool(progress and progress['completed'] == progress['total']
                            and len(job.get('steps', [])) == total
                            and all(s.get('status') == 'completed' for s in job.get('steps', [])))
            state = 'completed' if verified else 'interrupted'
            scope = 'file_step_checks' if verified else 'execution_unknown'
        message = f"{complete} of {total} file steps finished." if progress else 'File-task progress is unavailable.'
        if state == 'failed':
            failure = next((s for s in job.get('steps', []) if s.get('status') == 'failed'), {})
            message = _text(failure.get('error'), 'A file step failed.')
    elif source == 'model':
        title = 'Analysis' if job.get('route') == 'reasoning' else 'Text processing'
        if state == 'completed':
            state, scope = 'response_received', 'response_only'
            message = 'A response is available. No computer actions were verified.'
        elif state == 'failed':
            message = _text(job.get('error'), 'Text processing failed.')
    elif state == 'completed':
        if source == 'hermes' and job.get('verified') is True:
            verified, scope = True, 'workspace_checks'
        else:
            state, scope = 'response_received', 'response_only'
            message = message or 'A worker response is available; claimed effects are unverified.'
    if state in {'cancelled', 'timed_out', 'interrupted'} and job.get('execution') == 'unknown':
        state, scope = 'interrupted', 'execution_unknown'
        message = 'Local waiting stopped; remote execution is unknown. Inspect before retrying.'
    if state == 'cancelling':
        message = 'Cancellation requested; waiting for the current operation to stop.'
    if state == 'waiting_confirmation':
        message = 'Work is waiting for your response.'
    return dict(task_id=source + ':' + identity, source=source,
                generation=job.get('owner_generation', 1), state=state, terminal=state in TERMINAL,
                title=_text(title, 'Background task', 160), message=_text(message),
                evidence={'verified': verified, 'scope': scope}, progress=progress)


class TaskPresentation:
    def __init__(self, desktop, path=None, send=None):
        self.desktop = desktop
        path = path or Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'jarvis/task-ui/events.sqlite'
        self.store = TaskEventStore(path)
        descriptor = os.open(self.store.path.parent / 'presenter.lock',
                             os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        self._lease = os.fdopen(descriptor, 'w')
        try:
            fcntl.flock(self._lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lease.close()
            raise ValueError('Another task presenter owns this profile') from None
        self._lock = asyncio.Lock()
        self._send = send
        self.last_delivery_error = ''

    def close(self):
        self._lease.close()

    def observe(self, source, job):
        event = self.store.publish(project(source, job), source_revision=job.get('event_sequence', 0))
        if event and job.get('notice_acknowledged'):
            self.store.acknowledge(event['sequence'])
        return event or self.store.lookup(source + ':' + str(job['id']))

    def _jobs(self):
        d = self.desktop
        for source, owner, attribute in (
            ('file_task', getattr(d, '_task_runner', None), '_jobs'),
            ('model', getattr(d, '_model_jobs', None), 'jobs'),
            ('hermes', getattr(d, '_task_agents', None), 'jobs'),
            ('agent', getattr(d, '_agent_orchestrator', None), 'jobs'),
            ('team', getattr(d, '_agent_orchestrator', None), 'teams'),
        ):
            for job in list(getattr(owner, attribute, {}).values()):
                yield source, copy.deepcopy(job)

    async def refresh(self):
        async with self._lock:
            # Snapshot on the owning event-loop thread, before crossing a worker
            # boundary. No queue is consumed and no task is dispatched here.
            all_jobs = list(self._jobs())
            active_jobs = [(s, j) for s, j in all_jobs if (j.get('status') or j.get('state')) not in TERMINAL]
            finished_jobs = [(s, j) for s, j in all_jobs if (j.get('status') or j.get('state')) in TERMINAL]
            jobs = active_jobs[:128] + (finished_jobs[-(128-len(active_jobs)):] if len(active_jobs) < 128 else [])
            def reconcile():
                observed = {s + ':' + str(j['id']) for s, j in all_jobs}
                errors = []
                for source, job in jobs:
                    try:
                        self.observe(source, job)
                    except (ValueError, ValidationError, sqlite3.Error, KeyError, TypeError) as error:
                        errors.append(type(error).__name__)
                for old in self.store.snapshots():
                    if old['task_id'] not in observed and not old['terminal'] and old['source'] != 'hermes':
                        job = {'id': old['task_id'].split(':', 1)[1], 'name': old['title'],
                               'state': 'interrupted', 'execution': 'unknown', 'owner_generation': old['generation']}
                        candidate = project(old['source'], job)
                        candidate['message'] = 'Previous process ended; this in-memory task cannot be confirmed running. Inspect before retrying.'
                        self.store.publish(candidate)
                return self.store.snapshots(), errors
            events, errors = await asyncio.to_thread(reconcile)
            active = [e for e in events if not e['terminal']]
            finished = [e for e in events if e['terminal']]
            selected = (active[-24:] + finished[-max(0, 24 - len(active)):]) if len(active) < 24 else active[-24:]
            selected = sorted(selected, key=lambda e: e['sequence'])
            cursor = max((e['sequence'] for e in events), default=0)
            payload = {'schema_version': 1, 'stream_id': self.store.stream_id, 'cursor': cursor,
                       'events': selected, 'omitted': max(0, len(events) - len(selected)),
                       'projection_errors': errors[:5]}
            if events:
                try:
                    if self._send is None:
                        from ui.jarvis_widgets.backend import shell_call
                        send = shell_call
                    else:
                        send = self._send
                    await asyncio.to_thread(send, 'taskEvents', payload)
                    self.last_delivery_error = ''
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                    self.last_delivery_error = type(error).__name__
                    # Journal and pending notices remain intact for retry.
            return payload

    def notices(self):
        notices = []
        for event in self.store.notices({'file_task', 'model', 'hermes', 'agent', 'team'}):
            label = CONTRACT['x-state-labels'][event['state']]
            scope = CONTRACT['x-evidence-labels'][event['evidence']['scope']]
            text = f"{event['title']}: {label}. {event['message']} {scope}"
            if event['source'] == 'model':
                key = event['task_id'].removeprefix('model:')
                jobs = getattr(self.desktop, '_model_jobs', None)
                job = getattr(jobs, 'jobs', {}).get(key, {})
                if event['state'] == 'response_received':
                    text += ' ' + _text(job.get('result'), limit=2100)
            notices.append({'id': f"task-event:{self.store.stream_id}:{event['sequence']}",
                            'text': text, 'task_event': event})
        return notices

    def acknowledge(self, identity):
        prefix = 'task-event:' + self.store.stream_id + ':'
        if not identity.startswith(prefix):
            return
        self.store.acknowledge(int(identity[len(prefix):]))
