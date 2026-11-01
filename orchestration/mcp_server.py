"""Local stdio bridge: Hermes coordinates Jarvis workers, never another Hermes.

CLI children belong to this server and are cancelled on disconnect. A private
SQLite ledger preserves request identities and results; uncertain work is never
replayed. Jarvis's native task tools retain their independent systemd workers.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

from core.secret_env import sanitized_subprocess_env
from learning.bundles import private_directory
from learning.evidence import sanitize
from orchestration.agent_orchestrator import AgentOrchestrator, AGENTS, TERMINAL
from orchestration.tool_tiers import routed_arguments_match
from orchestration.executables import installed_executables, installed_path
from orchestration.task_names import task_name
from proactive.verification import capture_workspace, verify_workspace_changes
from jarvis_control.config import load as load_control_config
from jarvis_control.tasks import TaskManager, SCHEMAS as TASK_SCHEMAS

WORKERS = tuple(agent for agent in AGENTS if agent != 'hermes')


def schema(name, description, properties=None, required=()):
    return {'name': name, 'description': description, 'inputSchema': {
        'type': 'object', 'properties': properties or {}, 'required': list(required),
        'additionalProperties': False}}


STRING = {'type': 'string'}
TOOLS = [
    schema('jarvis_capabilities', 'Discover connected workers and orchestration ownership; does not start work.'),
    schema('jarvis_delegate', 'Delegate bounded user-authorized work to a named installed agent. '
           'Reuse request_key on retries. Default is a fresh empty Git workspace; include required inputs. '
           'A specified workspace must be within the configured project roots. '
           'Returns queued, not success. Inspect jarvis_job_status before concluding the goal. '
           'Agent instructions are guidance, not OS confinement. Never use for unrelated tasks.',
           {'agent': {'type': 'string', 'enum': list(WORKERS)}, 'prompt': STRING,
            'request_key': STRING, 'workspace': STRING,
            'timeout_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 1800}},
           ('agent', 'prompt', 'request_key')),
    schema('jarvis_job_status', 'Read an owned worker result and independent workspace checks. '
           'Exit code zero does not prove task fulfillment.', {'job_id': STRING}, ('job_id',)),
    schema('jarvis_job_wait', 'Wait up to 20 seconds for an owned worker. Returns its actual state; '
           'running means work is unfinished. Use instead of rapid polling.',
           {'job_id': STRING, 'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 20}}, ('job_id',)),
    schema('jarvis_job_list', 'List this bridge\'s worker jobs; never starts or replays work.'),
    schema('jarvis_job_cancel', 'Cancel an owned worker only on user request; does not undo changes.',
           {'job_id': STRING}, ('job_id',)),
] + [{**item, 'name': 'jarvis_' + item['name'], 'inputSchema': item['input_schema']}
     for item in TASK_SCHEMAS]
for item in TOOLS:
    item.pop('input_schema', None)
BY_NAME = {item['name']: item for item in TOOLS}


class OrchestratorMCP:
    def __init__(self, state_dir, workspace_roots=(), *, orchestrator=None, tasks=None):
        self.root = private_directory(state_dir)
        self.roots = [Path(path).expanduser().resolve(strict=True) for path in workspace_roots]
        self.orchestrator = orchestrator or AgentOrchestrator(executables=installed_executables())
        self.orchestrator.executables.pop('hermes', None)  # no coordinator recursion
        self.tasks = tasks
        self.watchers = set()
        self.lock = os.open(self.root / 'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock)
            raise ValueError('Another Jarvis orchestration bridge owns this state') from None
        db_path = self.root / 'delegations.sqlite3'
        if db_path.is_symlink():
            os.close(self.lock)
            raise ValueError('Delegation ledger must not be a symlink')
        self.db = sqlite3.connect(db_path)
        db_path.chmod(0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT, data TEXT)')
        for row in self.db.execute('SELECT id,data FROM jobs').fetchall():
            job = json.loads(row[1])
            if job['state'] not in TERMINAL | {'interrupted'}:
                job.update(state='interrupted', execution='unknown',
                           summary='Bridge restarted; inspect prior effects. Work was not replayed.')
                self._save(job)
        self.db.commit()

    def _save(self, job):
        self.db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job), job['id']))
        self.db.commit()

    def _get(self, job_id):
        row = self.db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Unknown bridge-owned job')
        return json.loads(row[0])

    def _list(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT data FROM jobs ORDER BY rowid DESC LIMIT 200')]

    async def _workspace(self, job_id, requested):
        if requested:
            root = Path(requested).expanduser().resolve(strict=True)
            owned = (root.is_relative_to(self.root / 'workspaces') and
                     any(job.get('workspace') == str(root) for job in self._list()))
            allowed_project = any(root == allowed or root.is_relative_to(allowed) for allowed in self.roots)
            if not root.is_dir() or not (owned or allowed_project):
                raise ValueError('Workspace is outside configured project roots')
            if '.git' in root.parts or (root.is_relative_to(self.root) and not owned):
                raise ValueError('Workspace cannot be bridge or Git metadata')
            return root
        root = private_directory(self.root / 'workspaces' / job_id)
        process = await asyncio.create_subprocess_exec('/usr/bin/git', '-c', 'core.hooksPath=/dev/null',
            'init', '--quiet', str(root), env=sanitized_subprocess_env(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null'),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(process.wait(), 10)
        if process.returncode:
            raise ValueError('Worker workspace could not be initialized')
        return root

    async def delegate(self, agent, prompt, request_key, workspace='', timeout_seconds=600):
        if agent not in WORKERS or not self.orchestrator.executables.get(agent):
            raise ValueError('Named agent is not installed; no substitute was started')
        if not 1 <= len(request_key) <= 128 or not 1 <= len(prompt.strip()) <= 16000:
            raise ValueError('Use a request key of 1-128 characters and prompt of 1-16000 characters')
        prompt = sanitize(prompt)['data']
        fingerprint = hashlib.sha256(json.dumps([agent, prompt, workspace, timeout_seconds]).encode()).hexdigest()
        old = self.db.execute('SELECT fingerprint,data FROM jobs WHERE request_key=?', (request_key,)).fetchone()
        if old:
            if old[0] != fingerprint:
                raise ValueError('request_key belongs to a different task')
            return json.loads(old[1])
        history = self._list()
        if any(job.get('execution') == 'unknown' for job in history):
            raise ValueError('Prior execution is unknown; inspect the ledger and worker effects before more work')
        if len(history) >= 200:
            raise ValueError('Bridge history is full; archive reviewed records before more work')
        job = {'id': uuid.uuid4().hex, 'name': task_name(prompt), 'agent': agent, 'coordinator_owner': 'hermes',
               'state': 'queued', 'execution': 'not_started', 'verified': False,
               'summary': 'Worker queued; no result yet.'}
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?)', (job['id'], request_key, fingerprint, json.dumps(job)))
        self.db.commit()  # record identity before any external launch
        try:
            root = await self._workspace(job['id'], workspace)
            baseline = await capture_workspace(root)
            if baseline['status'] != 'passed':
                raise ValueError('Workspace baseline unavailable; no worker submitted')
            brief = (prompt + '\n\nOrchestration context: Hermes is the main orchestrator for Jarvis OS. '
                     'Complete only this assignment; report evidence and limitations. '
                     'Do not invoke Hermes or recursively delegate this assignment. '
                     'Do not change global agent settings or permissions. '
                     'Use a clear name describing this assignment in progress reports; '
                     'keep session IDs and task IDs internal unless requested.')
            job.update(execution='submitting', workspace=str(root))
            self._save(job)
            result = self.orchestrator.delegate(agent, brief, str(root), timeout_seconds)
            worker_id = result['job']['id']
            job.update(worker_id=worker_id, state='running', execution='running')
            self._save(job)
            watcher = asyncio.create_task(self._watch(job['id'], worker_id, baseline))
            self.watchers.add(watcher)
            watcher.add_done_callback(self.watchers.discard)
        except Exception as error:
            job.update(state='failed', summary=str(error)[:300])
            self._save(job)
        return job

    async def _watch(self, identity, worker_id, baseline):
        try:
            worker = self.orchestrator.workers.get(worker_id)
            if worker:
                await asyncio.shield(worker)
            result = self.orchestrator.status(worker_id)['job']
            evidence = await verify_workspace_changes(result['workspace'], baseline)
            job = self._get(identity)
            job.update(state=result['state'], execution='response_received',
                       exit_code=result['exit_code'], output=sanitize(result['output'])['data'],
                       output_truncated=result['output_truncated'], verification=evidence,
                       summary='Worker returned; inspect output and verification scope. Functional success is not established.')
            self._save(job)
        except Exception as error:
            job = self._get(identity)
            job.update(state='interrupted', execution='unknown', summary='Result could not be recorded: ' + type(error).__name__)
            self._save(job)

    async def call(self, name, args):
        spec = BY_NAME.get(name)
        if not spec or not routed_arguments_match(args, spec['inputSchema']):
            raise ValueError('Unknown tool or invalid arguments')
        if name == 'jarvis_capabilities':
            return {'main_orchestrator': 'hermes', 'primary_orchestrators': ['hermes', 'jarvis'],
                    'availability_scope': 'Installed executable presence; provider login and execution must be checked separately.',
                    'workers': [{'name': agent, 'available': bool(self.orchestrator.executables.get(agent))} for agent in WORKERS],
                    'cli_worker_lifetime': 'owned by this MCP server; disconnect cancels active CLI jobs',
                    'recovery': 'ledger retained; uncertain jobs never replayed',
                    'native_tasks': self.tasks.providers() if self.tasks else {}}
        if name == 'jarvis_delegate':
            return await self.delegate(**args)
        if name == 'jarvis_job_list':
            return {'jobs': [{k: v for k, v in job.items() if k not in {'output', 'verification'}} for job in self._list()]}
        if name == 'jarvis_job_status':
            return self._get(args['job_id'])
        if name == 'jarvis_job_wait':
            job = self._get(args['job_id'])
            deadline = asyncio.get_running_loop().time() + args.get('timeout_seconds', 20)
            while job['state'] not in TERMINAL | {'interrupted'} and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.2)
                job = self._get(job['id'])
            return job
        if name == 'jarvis_job_cancel':
            job = self._get(args['job_id'])
            if job.get('worker_id') in self.orchestrator.jobs:
                await self.orchestrator.cancel(job['worker_id'])
                # Yield for this job's result watcher, never wait for unrelated jobs.
                for _ in range(100):
                    if self._get(job['id'])['state'] in TERMINAL | {'interrupted'}:
                        break
                    await asyncio.sleep(0.05)
            return self._get(job['id'])
        if name.startswith('jarvis_task_') and self.tasks:
            method = name.removeprefix('jarvis_task_')
            if method not in {'submit', 'list', 'status', 'read', 'cancel', 'resume'}:
                raise ValueError('Unknown native task operation')
            return await asyncio.to_thread(getattr(self.tasks, method), **args)
        raise ValueError('Native Jarvis task service is unavailable')

    async def handle(self, request):
        identity = request.get('id')
        method = request.get('method')
        if identity is None:
            return None
        try:
            if method == 'initialize':
                result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'jarvis-orchestrator', 'version': '1.0.0'}}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': TOOLS}
            elif method == 'tools/call':
                params = request.get('params') or {}
                try:
                    value = await self.call(params.get('name'), params.get('arguments', {}))
                    result = {'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': False}
                except (ValueError, OSError, RuntimeError) as error:
                    result = {'content': [{'type': 'text', 'text': sanitize(str(error))['data'][:1000]}], 'isError': True}
            else:
                return {'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32601, 'message': 'Method not found'}}
            return {'jsonrpc': '2.0', 'id': identity, 'result': result}
        except Exception:
            return {'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32603, 'message': 'Bridge operation failed'}}

    async def close(self):
        await self.orchestrator.close()
        if self.watchers:
            await asyncio.gather(*list(self.watchers), return_exceptions=True)
        self.db.close()
        os.close(self.lock)


async def serve(args):
    # Services do not inherit the interactive shell's mise PATH. Use installed
    # binaries directly; wrappers which run `mise use -g` can change global state.
    os.environ['PATH'] = installed_path()
    config = load_control_config()
    if args.task_root:
        config.tasks_root = args.task_root
    bridge = OrchestratorMCP(args.state_dir, args.workspace_root, tasks=TaskManager(config))
    try:
        while True:
            raw = await asyncio.to_thread(sys.stdin.buffer.readline, 65537)
            if not raw:
                break
            if len(raw) > 65536:
                break
            try:
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError('Request must be an object')
                response = await bridge.handle(request)
            except (ValueError, UnicodeError):
                response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON request'}}
            if response is not None:
                print(json.dumps(response), flush=True)
    finally:
        await bridge.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--workspace-root', action='append', default=[])
    parser.add_argument('--task-root', default='')
    args = parser.parse_args()
    asyncio.run(serve(args))


if __name__ == '__main__':
    main()
