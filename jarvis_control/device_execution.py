"""Device-independent access to the running UnifiedSkills instance.

The ledger records intent before execution. A retry never replays an action,
including when the daemon was stopped before its result could be recorded.
"""
import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from .outcomes import classify_result


class SharedToolExecutor:
    def __init__(self, skills, ledger: Path):
        self.skills = skills
        ledger.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(ledger)
        ledger.chmod(0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, fingerprint TEXT, result TEXT)')
        self.db.commit()
        self.lock = asyncio.Lock()

    def declarations(self):
        return self.skills.declarations

    async def call(self, request):
        identity, name, args = request.get('request_id'), request.get('name'), request.get('args')
        if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
            return {'error': 'A request_id of 1-200 characters is required'}
        if not isinstance(name, str) or name not in {d['name'] for d in self.declarations()} or not isinstance(args, dict):
            return {'error': 'Unknown tool or invalid arguments'}
        fingerprint = hashlib.sha256(json.dumps([name, args], sort_keys=True).encode()).hexdigest()
        async with self.lock:
            old = self.db.execute('SELECT fingerprint,result FROM calls WHERE id=?', (identity,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    return {'error': 'Request identity already belongs to another action'}
                return json.loads(old[1]) if old[1] else {'status': 'unknown', 'error': 'Execution may have started; inspect effects before retrying. Action was not replayed.'}
            self.db.execute('INSERT INTO calls VALUES(?,?,NULL)', (identity, fingerprint))
            self.db.commit()
            try:
                output = await self.skills.execute(name, args)
                outcome = classify_result(output)
                result = {'status': outcome.status, 'device': 'pc', 'output': output,
                          'ok': outcome.ok, 'completed': outcome.completed}
                if not outcome.ok:
                    result['error'] = outcome.detail or outcome.status
            except Exception:
                result = {'status': 'unknown', 'error': 'Execution did not return a result; inspect effects. Action will not be replayed.'}
            self.db.execute('UPDATE calls SET result=? WHERE id=?', (json.dumps(result), identity))
            self.db.commit()
            return result

    def close(self):
        self.db.close()
