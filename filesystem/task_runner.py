"""In-process, bounded multi-step jobs for approved desktop skills."""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import uuid


TASK_TOOLS = frozenset({
    'make_directory', 'write_file', 'append_file', 'edit_file',
    'copy_path', 'move_path', 'trash_path',
})
MAX_STEPS = 30
MAX_JOBS = 20
MAX_EVENTS = 32
MAX_VERIFICATION_BYTES = 5 * 1024 * 1024


class TaskPlanError(ValueError):
    """A task request is invalid or cannot be completed."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


class TaskRunner:
    def __init__(self, execute, validate):
        self._execute = execute
        self._validate = validate
        self._jobs: dict[str, dict] = {}
        self._workers: dict[str, asyncio.Task] = {}
        self._cancel_requested: set[str] = set()
        self.events: asyncio.Queue[dict] = asyncio.Queue(maxsize=MAX_EVENTS)

    def start(self, description: str, plan_json: str) -> dict:
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 200:
            raise TaskPlanError('task description must be 1 to 200 characters')
        if not isinstance(plan_json, str) or len(plan_json) > 30000:
            raise TaskPlanError('task plan is too large')
        try:
            plan = json.loads(plan_json)
        except json.JSONDecodeError:
            raise TaskPlanError('task plan must be a JSON array') from None
        if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_STEPS:
            raise TaskPlanError(f'task plan must have 1 to {MAX_STEPS} steps')
        steps = []
        for index, step in enumerate(plan, start=1):
            if not isinstance(step, dict) or set(step) != {'tool', 'args'}:
                raise TaskPlanError(f'step {index} must contain tool and args')
            tool, args = step['tool'], step['args']
            if tool not in TASK_TOOLS or not isinstance(args, dict) or not self._validate(tool, args):
                raise TaskPlanError(f'step {index} uses an unavailable tool or invalid arguments')
            steps.append({'tool': tool, 'args': args, 'status': 'pending'})
        if len(self._jobs) >= MAX_JOBS:
            finished = next((key for key, job in self._jobs.items()
                             if job['status'] in ('completed', 'failed', 'cancelled')), None)
            if finished is None:
                raise TaskPlanError('too many active or retained tasks')
            del self._jobs[finished]
        task_id = uuid.uuid4().hex[:12]
        job = {'id': task_id, 'description': description.strip(), 'status': 'queued',
               'created_at': _now(), 'updated_at': _now(), 'completed_steps': 0,
               'total_steps': len(steps), 'steps': steps}
        self._jobs[task_id] = job
        worker = asyncio.create_task(self._run(task_id))
        self._workers[task_id] = worker
        worker.add_done_callback(lambda done, key=task_id: self._workers.pop(key, None))
        return self.status(task_id)

    async def _run(self, task_id: str) -> None:
        job = self._jobs[task_id]
        job['status'] = 'running'
        job['updated_at'] = _now()
        try:
            for step in job['steps']:
                if task_id in self._cancel_requested:
                    job['status'] = 'cancelled'
                    break
                step['status'] = 'running'
                job['updated_at'] = _now()
                try:
                    before_state = await self._capture_step_state(step['tool'], step['args'])
                    result = await self._execute(step['tool'], step['args'])
                    self._reject_error_result(result)
                    if task_id in self._cancel_requested:
                        step['status'] = 'completed'
                        step['result'] = result
                        job['completed_steps'] += 1
                        job['status'] = 'cancelled'
                        break
                    await self._verify_step_ground_truth(step['tool'], step['args'], before_state)
                except Exception as error:
                    if task_id in self._cancel_requested:
                        step['status'] = 'cancelled'
                        job['status'] = 'cancelled'
                        break
                    step['status'] = 'failed'
                    step['error'] = str(error)[:300]
                    job['status'] = 'failed'
                    break
                step['status'] = 'completed'
                step['result'] = result
                job['completed_steps'] += 1
                job['updated_at'] = _now()
            else:
                job['status'] = 'completed'
        except asyncio.CancelledError:
            job['status'] = 'cancelled'
            raise
        finally:
            job['updated_at'] = _now()
            self._cancel_requested.discard(task_id)
            event = {
                'kind': 'task',
                'id': job['id'],
                'description': job['description'],
                'status': job['status'],
                'completed_steps': job['completed_steps'],
                'total_steps': job['total_steps'],
                'updated_at': job['updated_at'],
            }
            if job['status'] == 'failed':
                failed_step = next((s for s in job['steps'] if s.get('status') == 'failed'), None)
                if failed_step and failed_step.get('error'):
                    event['error'] = failed_step['error']
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait(event)

    @staticmethod
    def _reject_error_result(result) -> None:
        """Treat the executor's explicit error result as a failed step."""
        if not isinstance(result, dict):
            return
        if result.get('success') is False:
            detail = result.get('error') or result.get('message') or 'success was false'
            raise TaskPlanError(f'Executor reported failure: {str(detail)[:250]}')
        status = result.get('status')
        if isinstance(status, str) and status.strip().casefold() in {'error', 'failed'}:
            detail = result.get('error') or result.get('message') or status
            raise TaskPlanError(f'Executor reported failure: {str(detail)[:250]}')
        if result.get('error'):
            raise TaskPlanError(f'Executor reported failure: {str(result["error"])[:250]}')

    async def _capture_step_state(self, tool: str, args: dict):
        """Capture bounded file state needed to prove a content operation."""
        if tool not in ('write_file', 'append_file', 'edit_file'):
            return None

        def _capture():
            from pathlib import Path

            raw_path = args.get('path', '')
            if not raw_path:
                return None
            path = Path(raw_path).expanduser().resolve()
            if tool == 'write_file':
                content = args.get('content')
                if not isinstance(content, str):
                    raise TaskPlanError('Cannot verify write: content must be text')
                expected = content.encode('utf-8')
                if len(expected) > MAX_VERIFICATION_BYTES:
                    raise TaskPlanError('Cannot verify write: content exceeds 5 MiB')
                return expected
            try:
                if not path.exists():
                    if tool == 'append_file':
                        previous = b''
                    else:
                        raise TaskPlanError(f'Cannot verify edit: file {raw_path} does not exist')
                elif not path.is_file():
                    raise TaskPlanError(f'Cannot verify content operation: {raw_path} is not a file')
                else:
                    if path.stat().st_size > MAX_VERIFICATION_BYTES:
                        raise TaskPlanError('Cannot verify content operation: file exceeds 5 MiB')
                    with path.open('rb') as stream:
                        previous = stream.read(MAX_VERIFICATION_BYTES + 1)
                    if len(previous) > MAX_VERIFICATION_BYTES:
                        raise TaskPlanError('Cannot verify content operation: file exceeds 5 MiB')
                if tool == 'append_file':
                    content = args.get('content')
                    if not isinstance(content, str):
                        raise TaskPlanError('Cannot verify append: content must be text')
                    expected = previous + content.encode('utf-8')
                else:
                    old, new = args.get('old'), args.get('new')
                    if not isinstance(old, str) or not old or not isinstance(new, str):
                        raise TaskPlanError('Cannot verify edit: old and new must be text')
                    # Path.read_text() in the adapter uses universal newline
                    # translation before replacement, then writes normalized text.
                    previous_text = previous.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
                    if previous_text.count(old) != 1:
                        raise TaskPlanError('Cannot verify edit: expected exactly one matching passage')
                    expected = previous_text.replace(old, new, 1).encode('utf-8')
                if len(expected) > MAX_VERIFICATION_BYTES:
                    raise TaskPlanError('Cannot verify content operation: expected file exceeds 5 MiB')
                return expected
            except OSError as error:
                raise TaskPlanError(f'Cannot capture file before execution: {error}') from None

        return await asyncio.to_thread(_capture)

    async def _verify_step_ground_truth(self, tool: str, args: dict, expected_content=None) -> None:
        """Deterministically verify physical ground truth on disk after step execution."""
        def _verify_disk():
            from pathlib import Path
            if tool in ('write_file', 'append_file', 'edit_file'):
                raw_path = args.get('path', '')
                if raw_path:
                    path = Path(raw_path).expanduser().resolve()
                    if not path.is_file():
                        raise TaskPlanError(f'Ground-truth verification failed: file {raw_path} not found')
                    try:
                        if path.stat().st_size > MAX_VERIFICATION_BYTES:
                            raise TaskPlanError('Ground-truth verification failed: file exceeds 5 MiB')
                        with path.open('rb') as stream:
                            actual = stream.read(MAX_VERIFICATION_BYTES + 1)
                    except OSError as error:
                        raise TaskPlanError(f'Ground-truth verification failed: cannot read {raw_path}: {error}') from None
                    if len(actual) > MAX_VERIFICATION_BYTES:
                        raise TaskPlanError('Ground-truth verification failed: file exceeds 5 MiB')
                    if not isinstance(expected_content, bytes):
                        raise TaskPlanError('Ground-truth verification failed: could not determine expected content')
                    if actual != expected_content:
                        raise TaskPlanError(f'Ground-truth verification failed: file {raw_path} does not contain the expected content')
            elif tool == 'make_directory':
                raw_path = args.get('path', '')
                if raw_path:
                    path = Path(raw_path).expanduser().resolve()
                    if not path.is_dir():
                        raise TaskPlanError(f'Ground-truth verification failed: directory {raw_path} does not exist')
            elif tool == 'copy_path':
                raw_dst = args.get('destination', '')
                if raw_dst:
                    dst = Path(raw_dst).expanduser().resolve()
                    if not dst.exists():
                        raise TaskPlanError(f'Ground-truth verification failed: copy destination {raw_dst} does not exist')
            elif tool == 'move_path':
                raw_dst = args.get('destination', '')
                if raw_dst:
                    dst = Path(raw_dst).expanduser().resolve()
                    if not dst.exists():
                        raise TaskPlanError(f'Ground-truth verification failed: move destination {raw_dst} does not exist')
            elif tool == 'trash_path':
                raw_path = args.get('path', '')
                if raw_path:
                    path = Path(raw_path).expanduser().resolve()
                    if path.exists():
                        raise TaskPlanError(f'Ground-truth verification failed: path {raw_path} still exists after trash')

        await asyncio.to_thread(_verify_disk)

    async def close(self) -> None:
        """Cancel all active task workers and wait for them to finish."""
        workers = list(self._workers.values())
        for worker in workers:
            if not worker.done():
                worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()

    def status(self, task_id: str) -> dict:
        job = self._jobs.get(task_id)
        if job is None:
            raise TaskPlanError('task not found')
        return {'id': job['id'], 'description': job['description'], 'status': job['status'],
                'created_at': job['created_at'], 'updated_at': job['updated_at'],
                'completed_steps': job['completed_steps'], 'total_steps': job['total_steps'],
                'steps': [{**{key: value for key, value in step.items() if key != 'args'},
                           'target': {key: value for key, value in step['args'].items()
                                      if key in ('path', 'source', 'destination', 'overwrite')}}
                          for step in job['steps']]}

    def list_tasks(self) -> dict:
        return {'tasks': [self.status(task_id) for task_id in self._jobs]}

    def cancel(self, task_id: str) -> dict:
        job = self._jobs.get(task_id)
        if job is None:
            raise TaskPlanError('task not found')
        if job['status'] in ('queued', 'running'):
            self._cancel_requested.add(task_id)
            job['cancel_requested'] = True
        result = self.status(task_id)
        result['cancel_requested'] = task_id in self._cancel_requested
        return result
