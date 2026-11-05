"""Six memory layers over the existing authoritative stores and agent policy."""
from collections import OrderedDict
import threading
import time

class MemoryManager:
    def __init__(self, bridge):
        self.bridge = bridge
        self._working = OrderedDict()
        self._lock = threading.RLock()

    def set_working(self, key, text, ttl=1800):
        if not isinstance(key, str) or not 1 <= len(key) <= 100 or not isinstance(text, str) or len(text) > 8000:
            raise ValueError('Invalid working-memory item')
        if type(ttl) is not int or not 1 <= ttl <= 86400:
            raise ValueError('Working-memory TTL must be 1–86400 seconds')
        if not self.bridge.scanner.scan(text).is_clean:
            return {'status': 'rejected'}
        with self._lock:
            self._working.pop(key, None)
            self._working[key] = {'key': key, 'text': text, 'expires': time.monotonic() + ttl}
            while len(self._working) > 32:
                self._working.popitem(last=False)
        return {'status': 'temporary', 'persistent': False}

    def working(self):
        with self._lock:
            now = time.monotonic()
            for key in list(self._working):
                if self._working[key]['expires'] <= now:
                    del self._working[key]
            return [{'key': r['key'], 'text': r['text']} for r in self._working.values()]

    def clear_working(self):
        with self._lock:
            self._working.clear()

    def remember(self, text, category='auto', scope='user'):
        return self.bridge.remember(text, category=category, scope=scope)

    def recall(self, query='', category='all', scope='user', **kwargs):
        return self.bridge.recall(query, category=category, scope=scope, **kwargs)

    def record_episode(self, event, outcome, *, occurred_at=None, scope='user'):
        from .categories import validate_selection
        validate_selection('episodes', scope)
        if any(not isinstance(value, str) or not 1 <= len(value) <= 1000 for value in (event, outcome)):
            raise ValueError('Event and reported outcome must be 1–1000 characters')
        if not self.bridge.scanner.scan(event + ' ' + outcome).is_clean:
            raise ValueError('Episode contains unsafe content')
        return self.bridge.knowledge.upsert(event, kind='event', scope=scope, source='user-reported-event',
            observed_at=time.time() if occurred_at is None else occurred_at,
            evidence={'reported_outcome': outcome, 'verified': False}, authority='user')

    def store_procedure(self, title, steps, *, scope='user'):
        from .categories import validate_selection
        validate_selection('procedures', scope)
        if not isinstance(title, str) or not 1 <= len(title) <= 200:
            raise ValueError('Procedure title must be 1–200 characters')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 30 or any(not isinstance(s, str) or not 1 <= len(s) <= 500 for s in steps):
            raise ValueError('Procedure needs 1–30 bounded text steps')
        if not self.bridge.scanner.scan(title + ' '.join(steps)).is_clean:
            raise ValueError('Procedure contains unsafe content')
        return self.bridge.knowledge.upsert(title, kind='procedure', scope=scope, source='user-described-procedure',
            evidence={'steps': steps, 'verified': False, 'execution': 'never automatic'}, authority='user')

    def shared(self, policy):
        from .mcp_server import UniversalMemoryMCP, AuditLog, ClientPolicy
        from .service_facade import UniversalMemoryService
        if not isinstance(policy, ClientPolicy) or '*' in policy.read_scopes or '*' in policy.write_scopes:
            raise ValueError('Shared memory requires an explicit scoped client policy')
        if any(not scope.startswith(('shared:', 'project:')) for scope in policy.read_scopes | policy.write_scopes):
            raise ValueError('Shared clients cannot implicitly access personal user memory')
        return UniversalMemoryMCP(UniversalMemoryService(self.bridge.knowledge), policy,
                                  AuditLog(self.bridge.root / 'shared-audit.jsonl'))

    def status(self):
        rows = [r for r in self.bridge.knowledge.list() if r.get('expires_at') is None or r['expires_at'] > time.time()]
        return {
            'short_term': {'storage':'process memory', 'persistent':False, 'items':len(self.working())},
            'long_term': {'storage':'SQLite knowledge ledger', 'persistent':True, 'items':len(rows)},
            'episodic': {'storage':'dated conversation history and event records', 'events':sum(r['kind'] == 'event' for r in rows)},
            'semantic': {'storage':'facts, concepts and indexed documents', 'facts':sum(r['kind'] in ('fact','entity') for r in rows), 'vector_search_enabled':self.bridge.semantic_enabled},
            'procedural': {'storage':'procedure records', 'items':sum(r['kind'] == 'procedure' for r in rows), 'automatic_execution':False},
            'shared': {'storage':'scoped ledger via policy-checked MCP', 'items':sum(r['scope'].startswith('shared:') for r in rows), 'agent_writes':'proposal then permitted commit'},
        }
