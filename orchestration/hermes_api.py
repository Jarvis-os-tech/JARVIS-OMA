"""Private operation API over native Hermes features and durable goals.

Matches API Anything's catalog/inputSchema/ok/data contract without capturing
private gateway tokens or publishing local operations to its shared registry.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from learning.bundles import private_directory

READS = {'cron.list', 'kanban.list', 'kanban.show', 'kanban.attachments'}


def workflow_prompt(goal, tasks):
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
        raise ValueError('Provide a workflow goal of up to 2000 characters')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 24:
        raise ValueError('Provide between 1 and 24 workflow steps')
    known = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) - {'name', 'instruction', 'depends_on', 'agent'}:
            raise ValueError('Each step accepts name, instruction, depends_on and optional agent')
        name, instruction = task.get('name'), task.get('instruction')
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or name in known:
            raise ValueError('Workflow step names must be unique and at most 100 characters')
        if not isinstance(instruction, str) or not 1 <= len(instruction) <= 2000:
            raise ValueError('Each step needs an instruction of up to 2000 characters')
        if 'agent' in task and (not isinstance(task['agent'], str) or not 1 <= len(task['agent']) <= 80):
            raise ValueError('Use a readable worker name')
        dependencies = task.get('depends_on', [])
        if not isinstance(dependencies, list) or any(not isinstance(d, str) or d not in known for d in dependencies):
            raise ValueError('Dependencies must name earlier steps; cycles and missing dependencies are refused')
        known.add(name)
    prompt = (goal.strip() + '\n\nExecute this user-requested workflow with Hermes native features. '
              'Run independent steps concurrently within the available worker limit; queue excess work. '
              'Wait for dependencies, inspect each result, and do not run dependent steps after a failed prerequisite. '
              'Delegate to the named agent when supplied; report an unavailable agent rather than silently substituting. '
              'Keep a named checklist, collect artifacts and verify the final result. '
              'Do not recursively delegate the entire workflow. Steps:\n' + json.dumps(tasks, ensure_ascii=False))
    if len(prompt) > 12000:
        raise ValueError('Workflow instructions exceed the native goal size limit')
    return prompt


class HermesAPI:
    def __init__(self, agents):
        self.agents = agents
        self.bridge = agents.bridge
        self.root = private_directory(agents.root / 'api-requests')

    async def catalog(self):
        result = await self.bridge._request('native_catalog', timeout=40)
        if not isinstance(result.get('operations'), list):
            raise ValueError('Hermes is unavailable; no operation was submitted')
        # The operation name already selects the cron action.
        result = json.loads(json.dumps(result))
        for row in result['operations']:
            if row['name'].startswith('cron.'):
                schema = row['inputSchema']
                schema['properties'].pop('action', None)
                schema['required'] = [key for key in schema.get('required', []) if key != 'action']
        result['site'] = 'hermes'
        result['private'] = True
        result['operations'].extend([
            {'name': 'features.list', 'readOnly': True, 'inputSchema': {'type': 'object', 'properties': {
                'query': {'type': 'string'}, 'include_unavailable': {'type': 'boolean'}}, 'additionalProperties': False}},
            {'name': 'tasks.list', 'readOnly': True, 'inputSchema': {'type': 'object', 'additionalProperties': False}},
            {'name': 'tasks.status', 'readOnly': True, 'inputSchema': {'type': 'object', 'properties': {
                'job_id': {'type': 'string'}}, 'required': ['job_id'], 'additionalProperties': False}},
            {'name': 'tasks.start', 'readOnly': False, 'inputSchema': {'type': 'object', 'properties': {
                'goal': {'type': 'string'}, 'context': {'type': 'string'}, 'timeout_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 86400},
                'workspace_id': {'enum': ['scratch', 'jarvis-os']}}, 'required': ['goal'], 'additionalProperties': False}},
            {'name': 'workflow.start', 'readOnly': False, 'inputSchema': {'type': 'object', 'properties': {
                'goal': {'type': 'string'}, 'tasks': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'items': {'type': 'object'}},
                'timeout_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 86400},
                'workspace_id': {'enum': ['scratch', 'jarvis-os']}}, 'required': ['goal', 'tasks'], 'additionalProperties': False}},
        ])
        return {'ok': True, **result}

    async def call(self, operation, arguments=None, request_key=None):
        if not isinstance(operation, str) or not isinstance(arguments or {}, dict):
            raise ValueError('Use an operation name and an arguments object')
        args = dict(arguments or {})
        if len(json.dumps(args).encode()) > 48000:
            raise ValueError('Hermes operation arguments exceed the bounded request size')
        # Validate using the live installed schema before recording or sending a write.
        from jsonschema import Draft202012Validator
        catalog = await self.catalog()
        definition = next((row for row in catalog['operations'] if row['name'] == operation), None)
        if definition is None:
            raise ValueError('Unknown Hermes operation; inspect the operation catalog')
        if definition.get('enabled') is False:
            return {'ok': False, 'class': 'unavailable', 'data': {'error': 'Feature disabled in the active Hermes profile'}}
        errors = list(Draft202012Validator(definition['inputSchema']).iter_errors(args))
        if errors:
            raise ValueError(errors[0].message[:500])
        if operation == 'features.list':
            return {'ok': True, 'data': await self.bridge.features(**args)}
        if operation == 'tasks.list':
            return {'ok': True, 'data': self.agents.list()}
        if operation == 'tasks.status':
            await self.agents.refresh(args['job_id'])
            return {'ok': True, 'data': self.agents.status(args['job_id'])}
        if operation in {'tasks.start', 'workflow.start'}:
            self._key(request_key)
            if operation == 'workflow.start':
                args['goal'] = workflow_prompt(args['goal'], args.pop('tasks'))
            goal = args.pop('goal')
            result = await asyncio.to_thread(self.agents.start, goal, role='main orchestrator', request_key=request_key, **args)
            return {'ok': True, 'class': 'pending', 'data': result, 'completed': False}
        if operation in READS:
            return await self.bridge._request('native_call', name=operation, arguments=args, timeout=40)
        self._key(request_key)
        identity = hashlib.sha256(request_key.encode()).hexdigest()
        digest = hashlib.sha256(json.dumps([operation, args], sort_keys=True).encode()).hexdigest()
        path = self.root / (identity + '.json')
        fd = os.open(self.root / (identity + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'ok': False, 'class': 'pending', 'error': 'This request is in progress; inspect it using the same request key'}
            if path.exists():
                if path.is_symlink() or path.stat().st_size > 256000:
                    raise ValueError('Invalid native operation receipt')
                prior = json.loads(path.read_text())
                if prior['digest'] != digest:
                    raise ValueError('Request key belongs to different operation arguments')
                return prior.get('result') or {'ok': False, 'class': 'unknown',
                    'error': 'Prior write has no final receipt. Inspect native state; it will not be sent again.'}
            self._save(path, {'digest': digest, 'operation': operation, 'state': 'pending'})
            try:
                result = await self.bridge._request('native_call', name=operation, arguments=args, timeout=60)
            except (OSError, ValueError, TimeoutError):
                result = {'ok': False, 'class': 'unknown', 'error': 'Native write outcome is unknown; inspect native state before a new request'}
            self._save(path, {'digest': digest, 'operation': operation, 'state': 'recorded', 'result': result})
            return result
        finally:
            os.close(fd)

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise ValueError('Writes require a stable request_key of up to 128 characters')

    def _save(self, path, value):
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix='.request-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
