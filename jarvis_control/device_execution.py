"""Device-independent access to the running UnifiedSkills instance.

The ledger records intent before execution. A retry never replays an action,
including when the daemon was stopped before its result could be recorded.
"""
import asyncio
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .outcomes import classify_result
from .execution_policy import tool_timeout


DEVICE_RESPONSE_DEADLINE = 170


def _observe_task(task):
    if not task.cancelled():
        task.exception()


class SharedToolExecutor:
    def __init__(self, skills, ledger: Path):
        self.skills = skills
        ledger.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(ledger)
        ledger.chmod(0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, fingerprint TEXT, result TEXT)')
        self.db.commit()
        self.active = None
        self.closed = False

    def declarations(self):
        return self.skills.declarations

    @staticmethod
    def _running(identity):
        return {'status': 'running', 'device': 'pc', 'ok': True, 'completed': False,
                'pending': True, 'request_id': identity,
                'message': 'Execution is still running; retry with the same request_id to inspect it. Do not replay with a new ID.'}

    @staticmethod
    def _busy():
        return {'status': 'busy', 'device': 'pc', 'ok': False, 'completed': False,
                'not_started': True,
                'error': 'Another device tool is running; this request was not started. Retry with the same request_id.'}

    @staticmethod
    def _stored_result(raw):
        result = json.loads(raw)
        # Reinterpret old receipts with today's completion rules.
        if 'output' in result:
            outcome = classify_result(result['output'])
            if not outcome.completed:
                result.update(status=outcome.status, ok=outcome.ok, completed=False)
                if not outcome.ok:
                    result['error'] = outcome.detail or outcome.status
        return result

    async def _execute(self, identity, name, args):
        try:
            output = await self.skills.execute(name, args)
            outcome = classify_result(output)
            result = {'status': outcome.status, 'device': 'pc', 'output': output,
                      'ok': outcome.ok, 'completed': outcome.completed}
            if not outcome.ok:
                result['error'] = outcome.detail or outcome.status
        except asyncio.CancelledError:
            raise
        except Exception:
            result = {'status': 'unknown', 'device': 'pc', 'ok': False, 'completed': False,
                      'error': 'Execution did not return a result; inspect effects. Action will not be replayed.'}
        if not self.closed:
            self.db.execute('UPDATE calls SET result=? WHERE id=?', (json.dumps(result), identity))
            self.db.commit()
        return result

    async def _wait_for(self, task, deadline, identity):
        remaining = max(0, deadline - time.monotonic())
        if remaining:
            done, _ = await asyncio.wait({task}, timeout=remaining)
            if done:
                return task.result()
        elif task.done():
            return task.result()
        return self._running(identity)

    async def call(self, request):
        identity, name, args = request.get('request_id'), request.get('name'), request.get('args')
        if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
            return {'error': 'A request_id of 1-200 characters is required'}
        if not isinstance(name, str) or name not in {d['name'] for d in self.declarations()} or not isinstance(args, dict):
            return {'error': 'Unknown tool or invalid arguments'}
        if self.closed:
            return {'error': 'PC executor is shutting down', 'status': 'busy', 'completed': False,
                    'not_started': True}
        fingerprint = hashlib.sha256(json.dumps([name, args], sort_keys=True).encode()).hexdigest()
        old = self.db.execute('SELECT fingerprint,result FROM calls WHERE id=?', (identity,)).fetchone()
        if old:
            if old[0] != fingerprint:
                return {'error': 'Request identity already belongs to another action'}
            if old[1]:
                return self._stored_result(old[1])
            if self.active and self.active[0] == identity:
                return await self._wait_for(self.active[2], self.active[3], identity)
            return {'status': 'unknown', 'device': 'pc', 'completed': False,
                    'error': 'Execution may have started; inspect effects before retrying. Action was not replayed.'}
        if self.active is not None and self.active[2].done():
            self._clear_active(self.active[2])
        if self.active is not None:
            return self._busy()

        deadline = time.monotonic() + min(tool_timeout(name, args), DEVICE_RESPONSE_DEADLINE)
        self.db.execute('INSERT INTO calls VALUES(?,?,NULL)', (identity, fingerprint))
        self.db.commit()
        task = asyncio.create_task(self._execute(identity, name, args))
        self.active = (identity, fingerprint, task, deadline)
        task.add_done_callback(_observe_task)
        task.add_done_callback(lambda completed: self._clear_active(completed))
        return await self._wait_for(task, deadline, identity)

    def _clear_active(self, task):
        if self.active and self.active[2] is task:
            self.active = None

    def close(self):
        self.closed = True
        if self.active:
            task = self.active[2]
            self.active = None
            task.cancel()
        self.db.close()
