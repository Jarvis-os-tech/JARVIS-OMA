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

AGENTS = ('codex', 'claude', 'opencode', 'gemini', 'hermes', 'omp')
TERMINAL = frozenset({'completed', 'failed', 'cancelled', 'timed_out'})


class OrchestrationError(ValueError):
    pass


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def command_for(agent, executable, prompt):
    # A fixed prefix ensures prompts cannot be interpreted as command flags.
    message = ('Task delegated by JARVIS. Work in the supplied working directory. '
               'Report your result and changed files.\n\n' + prompt)
    commands = {
        'codex': [executable, 'exec', '--json', '--sandbox', 'workspace-write', message],
        'claude': [executable, '--print', '--verbose', '--output-format', 'stream-json',
                   '--permission-mode', 'acceptEdits', '--permission-prompts', 'none', message],
        'opencode': [executable, 'run', '--standalone', '--format', 'json', message],
        'gemini': [executable, '--prompt', message, '--output-format', 'stream-json',
                   '--approval-mode', 'auto_edit', '--skip-trust'],
        'hermes': [executable, '-z', message],
        'omp': [executable, '--print', '--mode', 'json', '--approval-mode', 'write', message],
    }
    return commands[agent]

class AgentOrchestrator:
    def __init__(self, executables=None, command_builder=command_for):
        self.executables = (dict(executables) if executables is not None else
                            {name: shutil.which(name) for name in AGENTS})
        self._command_builder = command_builder
        self.jobs = {}
        self.workers = {}
        self.processes = {}
        self.events = asyncio.Queue(maxsize=100)
        self._closed = False
        self._secrets = [value for name, value in os.environ.items()
                         if any(word in name.upper() for word in ('API_KEY', 'TOKEN', 'PASSWORD', 'SECRET'))
                         and len(value) >= 8]

    def _response(self, summary, **data):
        return {'status': 'success', 'summary': summary, 'next_actions': [],
                'artifacts': [], **data}

    def discover(self):
        return self._response('Installed agent commands discovered; authentication is not verified.',
            agents=[{'name': name, 'available': bool(self.executables.get(name)),
                     'executable': self.executables.get(name)} for name in AGENTS])

    def delegate(self, agent, prompt, workspace, timeout_seconds=900):
        if self._closed:
            raise OrchestrationError('orchestrator has stopped; restart JARVIS')
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
        if len(self.jobs) >= 50:
            oldest = next(key for key, job in self.jobs.items() if job['state'] in TERMINAL)
            del self.jobs[oldest]
        job_id = uuid.uuid4().hex[:12]
        job = {'id': job_id, 'agent': agent, 'workspace': str(root), 'state': 'queued',
               'task_summary': prompt.strip()[:200],
               'created_at': now(), 'updated_at': now(), 'exit_code': None,
               'output': '', 'output_truncated': False, 'cancel_requested': False}
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
            process = await asyncio.create_subprocess_exec(
                *self._command_builder(job['agent'], self.executables[job['agent']], prompt),
                cwd=job['workspace'], stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=True)
            self.processes[job_id] = process
            job['state'] = 'running'
            if job['cancel_requested']:
                await self._stop_process(process)
            readers = [asyncio.create_task(self._read(job, stream))
                       for stream in (process.stdout, process.stderr)]
            try:
                await asyncio.wait_for(process.wait(), timeout_seconds)
                await asyncio.wait_for(asyncio.gather(*readers), 3)
                job['state'] = 'completed' if process.returncode == 0 else 'failed'
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
            self.events.put_nowait({key: job[key] for key in ('id', 'agent', 'state', 'workspace')})

    def status(self, job_id, max_chars=6000):
        job = self.jobs.get(job_id)
        if job is None:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        if not isinstance(max_chars, int) or not 100 <= max_chars <= 20000:
            raise OrchestrationError('output limit must be from 100 to 20000 characters')
        result = {**job, 'output': job['output'][-max_chars:],
                  'output_truncated': job['output_truncated'] or len(job['output']) > max_chars}
        return self._response(f'{job["agent"]} job is {job["state"]}.', job=result,
            next_actions=(['check_agent_job', 'cancel_agent_job'] if job['state'] not in TERMINAL else []),
            artifacts=[job_id, job['workspace']])

    def list_jobs(self):
        return self._response('Agent job summaries.', jobs=[
            {key: value for key, value in job.items() if key != 'output'}
            for job in self.jobs.values()])

    async def cancel(self, job_id):
        if job_id not in self.jobs:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        job = self.jobs[job_id]
        if job['state'] not in TERMINAL:
            job['cancel_requested'] = True
            # Wait for spawn to resolve rather than cancelling during process creation.
            await self._stop_process(self.processes.get(job_id))
            worker = self.workers.get(job_id)
            if worker:
                await worker
        return self.status(job_id)

    async def close(self):
        self._closed = True
        workers = list(self.workers.values())
        await asyncio.gather(*(self.cancel(key) for key in list(self.workers)))
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
