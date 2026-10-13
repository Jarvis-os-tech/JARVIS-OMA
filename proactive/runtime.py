"""Integration runtime joining events, policy, planning, controls and agents."""
from __future__ import annotations
import asyncio
from dataclasses import asdict
from pathlib import Path
import time
import hashlib

from .control import AutonomyControl
from .events import EventBus, EventStatus
from .ledger import ActivityLedger, ActivityStatus
from .planner import AutonomousPlanner
from .policy import Action, ActionEffect, ProactivePolicy
from .monitor import ProactiveMonitor


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
        self._job_activity = {}

    def enqueue(self, prompt, workspace, agent=None, *, authorized=True):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('proactive task prompt is required')
        payload = {'prompt': prompt.strip(), 'workspace': workspace,
                   'authorized': bool(authorized)}
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
                       'authorized': priority in ('critical', 'high')}
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

    async def tick(self):
        self._reconcile_jobs()
        state = self.control.get_state()
        if state.stop_all:
            for job in list(self.orchestrator.workers):
                await self.orchestrator.cancel(job)
            return {'status': 'stopped', 'cancelled': True}
        if state.paused:
            return {'status': 'paused'}
        results = []
        for event in self.bus.claim(limit=4):
            activity = self.ledger.append('plan', 'Planning ' + event.type,
                                          event_id=event.id, details=event.payload,
                                          status=ActivityStatus.PLANNED)
            try:
                plan = self.planner.plan({'event_id': event.id, 'event_type': event.type,
                                          'data': event.payload})
                if plan.status != 'ready':
                    self.bus.transition(event.id, EventStatus.COMPLETED)
                    self.ledger.transition(activity.id, ActivityStatus.CANCELLED)
                    results.append({'event_id': event.id, 'status': plan.status})
                    continue
                effect = ActionEffect.LOCAL_REVERSIBLE if event.payload.get('authorized') else ActionEffect.UNKNOWN
                decision = self.policy.evaluate(event.id, Action('delegate_agent', effect), time.monotonic())
                if not decision.allowed:
                    self.bus.transition(event.id, EventStatus.COMPLETED)
                    self.ledger.transition(activity.id, ActivityStatus.CANCELLED)
                    results.append({'event_id': event.id, 'status': decision.status.value})
                    continue
                self.ledger.transition(activity.id, ActivityStatus.RUNNING)
                jobs = []
                for task in plan.tasks:
                    response = self.orchestrator.delegate(
                        task.agent, task.prompt, event.payload.get('workspace', ''), 900)
                    jobs.append(response['job']['id'])
                    job_id = response['job']['id']
                    self.monitor.track(job_id, timeout_seconds=900, now=time.monotonic(),
                                       metadata={'agent': task.agent, 'event_id': event.id})
                    self._job_activity[job_id] = activity.id
                self.bus.transition(event.id, EventStatus.COMPLETED)
                results.append({'event_id': event.id, 'status': 'delegated', 'jobs': jobs})
            except Exception as error:
                self.bus.transition(event.id, EventStatus.FAILED, error=type(error).__name__)
                self.ledger.transition(activity.id, ActivityStatus.FAILED)
                results.append({'event_id': event.id, 'status': 'failed', 'error': str(error)[:300]})
        return {'status': 'active', 'results': results}

    def _reconcile_jobs(self):
        terminal = {'completed', 'failed', 'timed_out', 'cancelled'}
        for job_id, activity_id in list(self._job_activity.items()):
            job = self.orchestrator.jobs.get(job_id)
            if not job or job.get('state') not in terminal:
                continue
            status = job['state']
            try:
                self.monitor.update(job_id, status, now=time.monotonic())
                target = (ActivityStatus.SUCCEEDED if status == 'completed' else
                          ActivityStatus.CANCELLED if status == 'cancelled' else ActivityStatus.FAILED)
                self.ledger.transition(activity_id, target)
            finally:
                del self._job_activity[job_id]

    async def stop_all(self):
        state = self.control.stop_all()
        for job in list(self.orchestrator.workers):
            await self.orchestrator.cancel(job)
        return {'status': 'stopped', 'state': asdict(state)}

    def pause(self): return {'status': 'paused', 'state': asdict(self.control.pause())}
    def resume(self): return {'status': 'active', 'state': asdict(self.control.resume())}
    def status(self):
        return {'status': 'active' if self.control.get_state().can_run else 'paused',
                'state': asdict(self.control.get_state()),
                'pending_events': len(self.bus.pending(limit=100)),
                'recent_activity': [asdict(item) for item in self.ledger.list(limit=20)]}
