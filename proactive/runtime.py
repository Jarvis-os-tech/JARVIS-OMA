"""Integration runtime joining events, policy, planning, controls and agents."""
from __future__ import annotations
import asyncio
from dataclasses import asdict
from pathlib import Path
import time
import hashlib

from core.workers import BoundedWorker

from .control import AutonomyControl
from .events import EventBus, EventStatus
from .ledger import ActivityLedger, ActivityStatus
from .planner import AutonomousPlanner
from .policy import Action, ActionEffect, ProactivePolicy
from .monitor import ProactiveMonitor
from .verification import validate_checks, verify_files


class ProactiveRuntime:
    def __init__(self, root, orchestrator):
        root = Path(root)
        self.bus = EventBus(root / 'events.db')
        self.ledger = ActivityLedger(root / 'activity.db')
        self.control = AutonomyControl(root / 'control.db')
        self.policy = ProactivePolicy()
        self.planner = AutonomousPlanner()
        self.orchestrator = orchestrator
        self.monitor = ProactiveMonitor()
        self._tick_lock = asyncio.Lock()
        self._worker = BoundedWorker('proactive', capacity=16)
        self._tick_task = None
        self._close_task = None
        self._closing = False

    def enqueue(self, prompt, workspace, agent=None, *, authorized=False, verification=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('proactive task prompt is required')
        if type(authorized) is not bool:
            raise ValueError('authorized must be an explicit boolean')
        workspace = str(Path(workspace).expanduser().resolve(strict=True))
        if not Path(workspace).is_dir():
            raise ValueError('workspace must be a directory')
        payload = {'prompt': prompt.strip(), 'workspace': workspace,
                   'authorized': authorized, 'verification': validate_checks(verification)}
        if agent:
            payload['agent'] = agent
        event = self.bus.publish('task_requested', payload)
        self.ledger.append('task_requested', prompt[:500], event_id=event.id,
                           details={'workspace': workspace, 'authorized': bool(authorized)})
        return {'status': 'queued', 'event_id': event.id}

    def observe_todos(self, tasks, workspace):
        """Turn new ongoing Omarchy todos into durable proactive events."""
        observed = []
        for item in tasks:
            if not isinstance(item, dict) or item.get('completed') or item.get('status') == 'complete':
                continue
            identifier = str(item.get('id') or hashlib.sha256(
                str(item.get('title', '')).encode()).hexdigest()[:16])
            event_id = 'todo:' + identifier[:120]
            if self.bus.get(event_id):
                continue
            title = str(item.get('title', '')).strip()
            description = str(item.get('description', '')).strip()
            if not title:
                continue
            priority = item.get('priority', 'medium')
            payload = {'prompt': title + (': ' + description if description else ''),
                       'workspace': workspace, 'source': 'omarchy-todo',
                       'authorized': False}
            self.bus.publish('todo_due', payload, event_id=event_id)
            self.ledger.append('todo_observed', title, event_id=event_id,
                               details={'priority': priority, 'workspace': workspace})
            observed.append(event_id)
        return observed

    def observe_reminders(self, reminders, workspace):
        observed = []
        for item in reminders:
            if not isinstance(item, dict):
                continue
            identity = str(item.get('timer') or item.get('id') or item.get('message', ''))
            message = str(item.get('message') or item.get('text') or 'Reminder').strip()
            if not identity or not message:
                continue
            event_id = 'reminder:' + hashlib.sha256(identity.encode()).hexdigest()[:24]
            if self.bus.get(event_id):
                continue
            self.bus.publish('reminder_due', {'prompt': message, 'workspace': workspace,
                             'source': 'omarchy-reminder', 'authorized': False}, event_id=event_id)
            self.ledger.append('reminder_observed', message, event_id=event_id)
            observed.append(event_id)
        return observed

    async def call(self, method, *args, **kwargs):
        """Run a synchronous runtime operation on its bounded persistence worker."""
        if self._closing and asyncio.current_task() is not self._tick_task:
            raise RuntimeError('proactive runtime is closing')
        if isinstance(method, str):
            method = getattr(self, method)
        return await self._worker.run(method, *args, **kwargs)

    async def close(self, timeout=5):
        """Stop admission and drain owned work, preserving an in-flight dispatch."""
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._finish_close())
        # A slow database does not block shutdown callers indefinitely; the
        # owned drain continues so its tick cannot use an already closed worker.
        await asyncio.wait_for(asyncio.shield(self._close_task), timeout)

    async def _finish_close(self):
        if self._tick_task is not None:
            await asyncio.gather(self._tick_task, return_exceptions=True)
        await self._worker.close()

    async def tick(self):
        if self._closing:
            raise RuntimeError('proactive runtime is closing')
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._run_tick())
            # Retrieve failures even when a reconnect cancels the only waiter.
            self._tick_task.add_done_callback(
                lambda done: None if done.cancelled() else done.exception())
        # A reconnect can cancel its observer while a database claim is running.
        # Keep that claim and its dispatch under this runtime's ownership.
        return await asyncio.shield(self._tick_task)

    async def _run_tick(self):
        async with self._tick_lock:
            return await self._tick()

    async def _tick(self):
        await self._reconcile_jobs()
        state = await self.call(self.control.get_state)
        if state.stop_all:
            for job in list(self.orchestrator.workers):
                await self.orchestrator.cancel(job)
            return {'status': 'stopped', 'cancelled': True}
        if state.paused:
            return {'status': 'paused'}
        results = []
        for event in await self.call(self.bus.claim, limit=4):
            activity = await self.call(self.ledger.append, 'plan', 'Planning ' + event.type,
                                          event_id=event.id, details=event.payload,
                                          status=ActivityStatus.PLANNED)
            record = None
            try:
                plan = await self.call(self.planner.plan, {'event_id': event.id, 'event_type': event.type,
                                          'data': event.payload})
                if plan.status != 'ready':
                    await self.call(self.bus.transition, event.id, EventStatus.COMPLETED)
                    await self.call(self.ledger.transition, activity.id, ActivityStatus.CANCELLED)
                    results.append({'event_id': event.id, 'status': plan.status})
                    continue
                # Authorization to delegate is not an assertion about downstream
                # effects. Workers retain their native action permission controls.
                decision = self.policy.evaluate(
                    event.id, Action('delegate_agent', ActionEffect.UNKNOWN), time.monotonic(),
                    approved=event.payload.get('authorized') is True)
                if not decision.allowed:
                    await self.call(self.bus.transition, event.id, EventStatus.COMPLETED)
                    await self.call(self.ledger.transition, activity.id, ActivityStatus.CANCELLED)
                    results.append({'event_id': event.id, 'status': decision.status.value})
                    continue
                checks = validate_checks(event.payload.get('verification'))
                record = {'workspace': event.payload.get('workspace', ''), 'verification': checks,
                          'expected_jobs': len(plan.tasks), 'jobs': {}, 'dispatched': False,
                          'control_revision': state.revision, 'outcome': None}
                await self.call(self.ledger.save_execution, activity.id, record)
                await self.call(self.ledger.transition, activity.id, ActivityStatus.RUNNING)
                for task in plan.tasks:
                    current = await self.call(self.control.get_state)
                    if not current.can_run or current.revision != state.revision:
                        raise RuntimeError('autonomy controls changed before dispatch')
                    response = self.orchestrator.delegate(
                        task.agent, task.prompt, record['workspace'], 900)
                    job_id = response['job']['id']
                    record['jobs'][job_id] = 'running'
                    await self.call(self.ledger.save_execution, activity.id, record)
                    self.monitor.track(job_id, timeout_seconds=900, now=time.monotonic(),
                                       metadata={'agent': task.agent, 'event_id': event.id})
                record['dispatched'] = True
                await self.call(self.ledger.save_execution, activity.id, record)
                # Event completion means dispatch handled, never verified task success.
                await self.call(self.bus.transition, event.id, EventStatus.COMPLETED)
                results.append({'event_id': event.id, 'activity_id': activity.id,
                                'status': 'delegated', 'jobs': list(record['jobs'])})
            except Exception as error:
                if record is not None:
                    record['dispatch_error'] = type(error).__name__
                    await self.call(self.ledger.save_execution, activity.id, record)
                    # Partial launches must not be orphaned on a later failure.
                    for job_id in record['jobs']:
                        try:
                            await self.orchestrator.cancel(job_id)
                        except Exception:
                            record.setdefault('cancellation_errors', []).append(job_id)
                    await self.call(self.ledger.save_execution, activity.id, record)
                await self.call(self.bus.transition, event.id, EventStatus.FAILED, error=type(error).__name__)
                await self.call(self.ledger.transition, activity.id, ActivityStatus.FAILED)
                results.append({'event_id': event.id, 'status': 'failed', 'error': str(error)[:300]})
        return {'status': 'active', 'results': results}

    async def _reconcile_jobs(self):
        terminal = {'completed', 'failed', 'timed_out', 'cancelled', 'interrupted'}
        tracked = {job['id'] for job in self.monitor.list_jobs() if job['status'] == 'running'}
        executions = await self.call(self.ledger.executions, pending_only=True)
        for activity_id, record in executions.items():
            for job_id, previous in record['jobs'].items():
                if previous in terminal:
                    continue
                job = self.orchestrator.jobs.get(job_id)
                # Lost workers cannot be silently retried or inferred successful.
                record['jobs'][job_id] = job.get('state', 'running') if job else 'interrupted'
                if job_id in tracked and record['jobs'][job_id] in terminal:
                    self.monitor.update(job_id, 'failed' if record['jobs'][job_id] == 'interrupted' else record['jobs'][job_id],
                                        now=time.monotonic())
            await self.call(self.ledger.save_execution, activity_id, record)
            states = list(record['jobs'].values())
            if any(value not in terminal for value in states):
                continue
            if not record['dispatched'] or len(states) != record['expected_jobs'] or 'interrupted' in states:
                target = ActivityStatus.INTERRUPTED
            elif any(value in ('failed', 'timed_out') for value in states):
                target = ActivityStatus.FAILED
            elif 'cancelled' in states:
                target = ActivityStatus.CANCELLED
            else:
                outcome = await self.call(verify_files, record['workspace'], record['verification'])
                record['outcome'] = outcome
                target = {'passed': ActivityStatus.SUCCEEDED, 'failed': ActivityStatus.FAILED,
                          'unverified': ActivityStatus.UNVERIFIED}[outcome['status']]
            record['result'] = target.value
            await self.call(self.ledger.save_execution, activity_id, record)
            await self.call(self.ledger.transition, activity_id, target)

    async def stop_all(self):
        state = await self.call(self.control.stop_all)
        for job in list(self.orchestrator.workers):
            await self.orchestrator.cancel(job)
        return {'status': 'stopped', 'state': asdict(state)}

    def pause(self): return {'status': 'paused', 'state': asdict(self.control.pause())}
    def resume(self): return {'status': 'active', 'state': asdict(self.control.resume())}
    def status(self):
        state = self.control.get_state()
        recent = [{**asdict(item), 'execution': self.ledger.execution(item.id)}
                  for item in self.ledger.list(limit=20)]
        return {'status': 'stopped' if state.stop_all else 'active' if state.can_run else 'paused',
                'state': asdict(state),
                'pending_events': len(self.bus.pending(limit=100)),
                'recent_activity': recent}
