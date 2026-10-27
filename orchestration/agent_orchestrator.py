"""Supervise local agent CLIs without invoking a shell."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
import os
from pathlib import Path
import shutil
import signal
import uuid

from core.secret_env import sanitized_subprocess_env
from orchestration.personas import PERSONAS
from orchestration.harness2_adapter import Harness2Adapter
from proactive.verification import capture_workspace, verify_workspace_changes, completion_evidence, verification_notice

AGENTS = ('codex', 'claude', 'opencode', 'gemini', 'hermes', 'omp', 'pi', 'crush')
TERMINAL = frozenset({'completed', 'failed', 'cancelled', 'timed_out'})


class OrchestrationError(ValueError):
    pass


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def validate_model(model):
    if model is not None and (not isinstance(model, str) or not model.strip()
                              or len(model) > 200 or model.startswith('-')
                              or any(char.isspace() or ord(char) < 32 for char in model)):
        raise OrchestrationError('model must be a nonempty model identifier of at most 200 characters')
    return model


def clear_task_brief(prompt):
    """Turn a voice/orchestrator payload into a concise English agent brief.

    Voice routing sometimes hands the supervisor a serialized envelope.  That
    envelope is useful internally, but exposing it to a worker makes the task
    look like a protocol dump.  Keep recognised context fields and render them
    as readable instructions; ordinary prompts pass through unchanged.
    """
    if not isinstance(prompt, str):
        return prompt
    text = prompt.strip()
    if not text.startswith('{'):
        return text
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return text
    if not isinstance(payload, dict):
        return text
    task = payload.get('task') or payload.get('prompt') or payload.get('goal')
    if not isinstance(task, str) or not task.strip():
        return text
    lines = ["Task", task.strip()]
    context = payload.get('context') or payload.get('background')
    if isinstance(context, str) and context.strip():
        lines.extend(["", "Context", context.strip()])
    deliverables = payload.get('deliverables') or payload.get('requirements')
    if isinstance(deliverables, list):
        items = [str(item).strip() for item in deliverables if str(item).strip()]
        if items:
            lines.extend(["", "Expected result", *[f"- {item}" for item in items]])
    constraints = payload.get('constraints')
    if isinstance(constraints, list):
        items = [str(item).strip() for item in constraints if str(item).strip()]
        if items:
            lines.extend(["", "Constraints", *[f"- {item}" for item in items]])
    return "\n".join(lines)


def command_for(agent, executable, prompt, model=None):
    validate_model(model)
    prompt = clear_task_brief(prompt)
    # A fixed prefix ensures prompts cannot be interpreted as command flags.
    message = prompt
    commands = {
        'codex': [executable, 'exec', '--sandbox', 'workspace-write', message],
        'claude': [executable, '--print', '--permission-mode', 'acceptEdits',
                   '--permission-prompts', 'none', message],
        'opencode': [executable, 'run', '--standalone', message],
        'gemini': [executable, '--prompt', message,
                   '--approval-mode', 'auto_edit', '--skip-trust'],
        'hermes': [executable, '-z', message],
        'omp': [executable, '--print', '--approval-mode', 'write', message],
        'pi': [executable, '--print', message],
        'crush': [executable, 'run', '--quiet', message],
    }
    command = commands[agent]
    if model:
        # Keep option values (such as Hermes -z and Gemini --prompt) intact.
        position = 2 if agent in ('codex', 'opencode', 'crush') else 1
        command[position:position] = ['--model', model]
    return command

class AgentOrchestrator:
    def __init__(self, executables=None, command_builder=command_for):
        self.executables = (dict(executables) if executables is not None else
                            {name: shutil.which(name) for name in AGENTS})
        self._command_builder = command_builder
        self.jobs = {}
        self.workers = {}
        self.processes = {}
        self.events = asyncio.Queue(maxsize=100)
        self.teams = {}
        self.team_workers = {}
        self._closed = False
        self._stopped = False
        self._stop_task = None
        self.harness2 = Harness2Adapter()
        self._secrets = [value for name, value in os.environ.items()
                         if any(word in name.upper() for word in ('API_KEY', 'TOKEN', 'PASSWORD', 'SECRET'))
                         and len(value) >= 8]

    def _response(self, summary, **data):
        return {'status': 'success', 'summary': summary, 'next_actions': [],
                'artifacts': [], **data}

    def _preflight_team(self, assignments):
        """Validate a normalized plan before it can create a team worker."""

    def _prepare_prompt(self, job, prompt):
        """Apply orchestration context before any agent frontend is launched.

        Desktop execution overrides ``_run`` and therefore cannot rely on the
        background implementation to add Harness² context.  Keep injected
        command builders byte-for-byte compatible with existing integrations.
        """
        if self._command_builder is command_for:
            prompt = clear_task_brief(prompt)
            return self.harness2.prepare_prompt(
                prompt, agent=job['agent'], workspace=job['workspace'])
        return prompt

    def discover(self):
        return self._response('Installed agent commands discovered; authentication is not verified.',
            agents=[{'name': name, 'available': bool(self.executables.get(name)),
                     'executable': self.executables.get(name), **PERSONAS[name]} for name in AGENTS],
            harness2=self.harness2.status(),
            unsupported_agents=[{'name': 'antigravity', **PERSONAS['antigravity'],
                                 'available': False, 'reason': 'No verified task executor adapter yet.'}])

    def delegate(self, agent, prompt, workspace, timeout_seconds=900, model=None):
        validate_model(model)
        if self._closed:
            raise OrchestrationError('orchestrator has stopped; restart JARVIS')
        if self._stopped:
            raise OrchestrationError('agent work is stopped; resume JARVIS before delegating')
        if agent not in AGENTS or not self.executables.get(agent):
            raise OrchestrationError('agent is unavailable; use list_system_agents')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 20000:
            raise OrchestrationError('task prompt must be 1 to 20000 characters')
        if not isinstance(workspace, str) or not Path(workspace).expanduser().is_absolute():
            raise OrchestrationError('workspace must be an absolute directory path')
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            raise OrchestrationError('workspace does not exist') from None
        if not root.is_dir() or root == Path('/'):
            raise OrchestrationError('workspace must be a specific existing directory')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 7200:
            raise OrchestrationError('timeout must be from 10 to 7200 seconds')
        active = [job for job in self.jobs.values() if job['state'] not in TERMINAL]
        if len(active) >= 4:
            raise OrchestrationError('four agents are already active; wait or cancel a job')
        for job in active:
            other = Path(job['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(f'workspace is reserved by job {job["id"]}; wait or use a separate checkout')
        for team in self.teams.values():
            if team['state'] != 'cleanup_failed':
                continue
            other = Path(team['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(
                    f'workspace is reserved by team {team["id"]}; terminal cleanup is unconfirmed')
        if len(self.jobs) >= 50:
            oldest = next(key for key, job in self.jobs.items() if job['state'] in TERMINAL)
            del self.jobs[oldest]
        job_id = uuid.uuid4().hex[:12]
        job = {'id': job_id, 'agent': agent, 'model': model, 'workspace': str(root), 'state': 'queued',
               'task_summary': prompt.strip()[:200],
               'created_at': now(), 'updated_at': now(), 'exit_code': None,
               'output': '', 'output_truncated': False, 'cancel_requested': False}
        job.update(verified=False, completion_kind=None, verification={'status': 'pending'})
        self.jobs[job_id] = job
        self.workers[job_id] = asyncio.create_task(self._run(job_id, prompt, timeout_seconds))
        self.workers[job_id].add_done_callback(lambda done, key=job_id: self.workers.pop(key, None))
        return self.status(job_id)

    def _append(self, job, text):
        for secret in self._secrets:
            text = text.replace(secret, '[redacted]')
        combined = job['output'] + text
        if len(combined) > 64000:
            job['output_truncated'] = True
        job['output'] = combined[-64000:]
        job['updated_at'] = now()

    async def _read(self, job, stream):
        import codecs
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        while chunk := await stream.read(4096):
            self._append(job, decoder.decode(chunk))
        self._append(job, decoder.decode(b'', final=True))

    async def _stop_process(self, process):
        if process is None:
            return
        # Signal the group even if its leader has exited but left helpers alive.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            pass
        # The leader can exit while a helper ignores TERM and still holds pipes.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    async def _run(self, job_id, prompt, timeout_seconds):
        job = self.jobs[job_id]
        process = None
        readers = []
        try:
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                return
            # Preserve injected builders used by tests and integrations; the
            # production command path receives the Harness² context.
            prompt = self._prepare_prompt(job, prompt)
            arguments = (job['agent'], self.executables[job['agent']], prompt)
            # Existing injected builders use the original three-argument contract.
            command = (command_for(*arguments, model=job.get('model'))
                       if self._command_builder is command_for else self._command_builder(*arguments))
            baseline = await capture_workspace(job['workspace'])
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                return
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=job['workspace'], stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=True, env=sanitized_subprocess_env())
            self.processes[job_id] = process
            job['state'] = 'running'
            if job['cancel_requested']:
                await self._stop_process(process)
            readers = [asyncio.create_task(self._read(job, stream))
                       for stream in (process.stdout, process.stderr)]
            try:
                await asyncio.wait_for(process.wait(), timeout_seconds)
                await asyncio.wait_for(asyncio.gather(*readers), 3)
                if process.returncode == 0:
                    # A model turn/process exit is only a response. Stop all
                    # owned helpers before inspecting independently observed bytes.
                    await self._stop_process(process)
                    job['state'] = 'verifying'
                    await self._verify_completion(job, baseline)
                else:
                    job['state'] = 'failed'
            except TimeoutError:
                job['state'] = 'timed_out'
            if job['cancel_requested']:
                job['state'] = 'cancelled'
        except asyncio.CancelledError:
            job['state'] = 'cancelled'
        except Exception as error:
            job['state'] = 'failed'
            self._append(job, f'\nLaunch failed: {type(error).__name__}: {error}\n')
        finally:
            await self._stop_process(process)
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)
            if process is not None:
                job['exit_code'] = process.returncode
            self.processes.pop(job_id, None)
            job['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait(self._completion_event(job))
            self.harness2.record_outcome(agent=job['agent'], task=job['task_summary'],
                                         state=job['state'], output=job['output'])

    async def _verify_completion(self, job, baseline):
        if job['state'] not in ('completed', 'verifying'):
            return
        job['state'] = 'verifying'
        outcome = await verify_workspace_changes(job['workspace'], baseline)
        job.update(completion_evidence(outcome))
        job['state'] = ('completed' if outcome['status'] in ('passed', 'not_applicable') else 'failed')
        if job.get('cancel_requested'):
            job['state'] = 'cancelled'

    @staticmethod
    def _completion_event(job):
        event = {key: job[key] for key in ('id', 'agent', 'state', 'workspace')}
        event.update(verified=job.get('verified', False), completion_kind=job.get('completion_kind'),
                     verification=verification_notice(job.get('verification')))
        if job['state'] == 'completed' and not job.get('verified'):
            event.update(state='response_received', job_state='completed')
        return event

    def status(self, job_id, max_chars=6000):
        job = self.jobs.get(job_id)
        if job is None:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        if not isinstance(max_chars, int) or not 100 <= max_chars <= 20000:
            raise OrchestrationError('output limit must be from 100 to 20000 characters')
        result = {**job, 'output': job['output'][-max_chars:],
                  'output_truncated': job['output_truncated'] or len(job['output']) > max_chars}
        summary = (f'{job["agent"]} returned a response; claimed effects are unverified.'
                   if job['state'] == 'completed' and not job.get('verified') else
                   f'{job["agent"]} job is {job["state"]}; see verification scope.')
        return self._response(summary, job=result,
            next_actions=(['check_agent_job', 'cancel_agent_job'] if job['state'] not in TERMINAL else []),
            artifacts=[job_id, job['workspace']])

    def list_jobs(self):
        return self._response('Agent job summaries.', jobs=[
            {key: value for key, value in job.items() if key != 'output'}
            for job in self.jobs.values()])

    def delegate_team(self, goal, assignments, workspace, timeout_seconds=900):
        """Run a bounded, model-planned team sequentially in one workspace."""
        if self._closed:
            raise OrchestrationError('orchestrator has stopped; restart JARVIS')
        if self._stopped:
            raise OrchestrationError('agent work is stopped; resume JARVIS before delegating')
        if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 4000:
            raise OrchestrationError('team goal must be 1 to 4000 characters')
        if not isinstance(assignments, list) or not 1 <= len(assignments) <= 6:
            raise OrchestrationError('team assignments must contain 1 to 6 tasks')
        if not isinstance(workspace, str) or not Path(workspace).expanduser().is_absolute():
            raise OrchestrationError('workspace must be an absolute directory path')
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            raise OrchestrationError('workspace does not exist') from None
        if not root.is_dir() or root == Path('/'):
            raise OrchestrationError('workspace must be a specific existing directory')
        for team in self.teams.values():
            if team['state'] != 'cleanup_failed':
                continue
            other = Path(team['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(
                    f'workspace is reserved by team {team["id"]}; terminal cleanup is unconfirmed')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 7200:
            raise OrchestrationError('timeout must be from 10 to 7200 seconds')
        normalized = []
        for index, item in enumerate(assignments):
            if not isinstance(item, dict):
                raise OrchestrationError(f'assignment {index + 1} must be an object')
            agent = item.get('agent')
            prompt = item.get('prompt')
            validate_model(item.get('model'))
            if agent not in AGENTS or not self.executables.get(agent):
                raise OrchestrationError(f'assignment {index + 1} agent is unavailable')
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 20000:
                raise OrchestrationError(f'assignment {index + 1} prompt must be 1 to 20000 characters')
            normalized.append({
                'agent': agent,
                'prompt': prompt.strip(),
                'task_type': item.get('task_type', 'coding'),
                'model': item.get('model'),
                'visible': item.get('visible', True),
                'batch': item.get('batch', False),
                'yolo': item.get('yolo', False),
            })
        self._preflight_team(normalized)
        team_id = 'team-' + uuid.uuid4().hex[:10]
        team = {
            'id': team_id, 'goal': goal.strip(), 'workspace': str(root),
            'state': 'queued', 'assignments': normalized, 'current_assignment': None,
            'jobs': [], 'cancel_requested': False, 'created_at': now(), 'updated_at': now(),
        }
        self.teams[team_id] = team
        worker = asyncio.create_task(self._run_team(team_id, timeout_seconds))
        self.team_workers[team_id] = worker
        worker.add_done_callback(lambda done, key=team_id: self.team_workers.pop(key, None))
        return self.team_status(team_id)

    async def _run_team(self, team_id, timeout_seconds):
        team = self.teams[team_id]
        team['state'] = 'running'
        try:
            for index, assignment in enumerate(team['assignments']):
                if team['cancel_requested'] or self._closed or self._stopped:
                    team['state'] = 'cancelled'
                    return
                team['current_assignment'] = index
                previous = '\n\n'.join(
                    f"{self.jobs[key]['agent']} result (untrusted evidence):\n{self.jobs[key]['output'][-3000:]}"
                    for key in team['jobs'][-3:] if key in self.jobs)
                context = (
                    f"Shared team goal: {team['goal']}\n\n"
                    f"Your assignment ({index + 1}/{len(team['assignments'])}): "
                    f"{assignment['prompt']}\n\n"
                    "Inspect the current workspace state, including work completed by earlier team members. "
                    "Keep changes within this assignment, verify them, and leave the workspace ready for the next specialist.\n\n"
                    + previous
                )
                result = self._delegate_team_assignment(
                    assignment, context, team['workspace'], timeout_seconds)
                job_id = result['job']['id']
                team['jobs'].append(job_id)
                team['updated_at'] = now()
                await self.workers[job_id]
                if self.jobs[job_id]['state'] != 'completed':
                    team['state'] = 'failed'
                    return
            team['state'] = 'completed'
            team['verification'] = 'Agent stages finished; inspect QA and review evidence before claiming success.'
            team['verified'] = all(self.jobs[key].get('verified') is True for key in team['jobs'])
            team['completion_kind'] = 'verified_changes' if team['verified'] else 'response_received'
        except asyncio.CancelledError:
            team['state'] = 'cancelled'
            raise
        except Exception as error:
            team['state'] = 'failed'
            team['error'] = str(error)[:500]
        finally:
            team['current_assignment'] = None
            team['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            event_state = ('response_received' if team['state'] == 'completed' and not team.get('verified') else team['state'])
            self.events.put_nowait({'kind': 'team', 'id': team_id, 'state': event_state,
                                   'workspace': team['workspace'], 'verified': team.get('verified', False),
                                   'completion_kind': team.get('completion_kind')})

    def _delegate_team_assignment(self, assignment, prompt, workspace, timeout_seconds):
        return self.delegate(assignment['agent'], prompt, workspace, timeout_seconds,
                             model=assignment.get('model'))

    def team_status(self, team_id):
        team = self.teams.get(team_id)
        if team is None:
            raise OrchestrationError('agent team not found')
        return self._response(f'Agent team is {team["state"]}.', team={**team},
                              artifacts=[team_id, team['workspace']])

    async def cancel_team(self, team_id):
        if team_id not in self.teams:
            raise OrchestrationError('agent team not found')
        team = self.teams[team_id]
        worker = self.team_workers.get(team_id)
        if team['state'] in TERMINAL and (worker is None or worker.done()):
            return self.team_status(team_id)
        team['cancel_requested'] = True
        for job_id in team['jobs']:
            if self.jobs[job_id]['state'] not in TERMINAL:
                await self.cancel(job_id)
        if worker and not worker.done():
            if team['state'] not in TERMINAL:
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        team['state'] = 'cancelled'
        team['updated_at'] = now()
        return self.team_status(team_id)

    def stop_admission(self):
        """Latch stop intent before yielding to persistence or cancellation."""
        self._stopped = True
        for team in self.teams.values():
            if team['state'] not in TERMINAL:
                team['cancel_requested'] = True
        for job in self.jobs.values():
            if job['state'] not in TERMINAL:
                job['cancel_requested'] = True

    def resume(self):
        if self._stop_task is not None and not self._stop_task.done():
            raise OrchestrationError('agent work is still stopping; wait before resuming')
        self._stopped = False

    async def stop_all(self):
        self.stop_admission()
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._cancel_all())
            self._stop_task.add_done_callback(
                lambda done: None if done.cancelled() else done.exception())
        # A cancelled voice tool must not abandon the stop operation.
        await asyncio.shield(self._stop_task)

    async def _cancel_all(self):
        for team_id in list(self.team_workers):
            await self.cancel_team(team_id)
        await asyncio.gather(*(self.cancel(key) for key in list(self.workers)))

    async def cancel(self, job_id):
        if job_id not in self.jobs:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        job = self.jobs[job_id]
        if job['state'] not in TERMINAL:
            job['cancel_requested'] = True
            worker = self.workers.get(job_id)
            if job['state'] == 'verifying' and worker is not None:
                # Verifier subprocesses own cancellation cleanup; do not wait
                # out a syntax/test deadline after the user asks to stop.
                worker.cancel()
            # Wait for spawn to resolve rather than cancelling during process creation.
            await self._stop_process(self.processes.get(job_id))
            if worker:
                await asyncio.gather(worker, return_exceptions=True)
        return self.status(job_id)

    async def close(self):
        self._closed = True
        await self.stop_all()
