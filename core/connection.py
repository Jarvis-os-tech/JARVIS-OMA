"""Bound connection setup without imposing a deadline on the conversation."""
from contextlib import AsyncExitStack, asynccontextmanager
import asyncio
import hashlib
import json


class ToolCallConflict(ValueError):
    pass


class ToolCallCache:
    """Bounded in-process action identities; reconnect never repeats an action.

    Payload eviction leaves an identity tombstone. Exhaustion rejects new calls
    until a fresh conversation, rather than forgetting old side effects.
    """
    def __init__(self, capacity=256, max_result_bytes=8 * 1024 * 1024):
        self.capacity = capacity
        self.max_result_bytes = max_result_bytes
        self.records = {}
        self.responses = {}
        self._bytes = 0

    def claim(self, identifier, name, arguments):
        if (not isinstance(identifier, str) or not 0 < len(identifier) <= 1024 or
                not isinstance(name, str) or not 0 < len(name) <= 256):
            raise ToolCallConflict('Invalid tool call identity')
        encoded = json.dumps([name, arguments], sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(encoded) > 6 * 1024 * 1024:
            raise ToolCallConflict('Tool arguments exceed the resumption cache limit')
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        previous = self.records.get(identifier)
        if previous is not None:
            if previous['fingerprint'] != digest:
                raise ToolCallConflict('Provider reused a tool call ID with different arguments')
            return previous['state']
        if len(self.records) >= self.capacity:
            raise ToolCallConflict('Tool identity cache is full; start a fresh conversation before more actions')
        self.records[identifier] = {'fingerprint': digest, 'state': 'executing', 'bytes': 0}
        return 'new'

    def store(self, identifier, response):
        record = self.records.get(identifier)
        if record is None:
            return
        try:
            encoded = response.model_dump_json() if hasattr(response, 'model_dump_json') else json.dumps(response)
            size = len(encoded.encode())
        except (TypeError, ValueError):
            size = self.max_result_bytes + 1
        self._bytes -= record['bytes']
        self.responses.pop(identifier, None)
        record.update(state='result_unavailable', bytes=0)
        if self._bytes + size <= self.max_result_bytes:
            self.responses[identifier] = response
            record.update(state='result_ready', bytes=size)
            self._bytes += size

    def delivered(self, identifier):
        record = self.records.get(identifier)
        if record is not None and record['state'] == 'result_ready':
            record['state'] = 'delivered'

    def interrupted(self, identifier):
        record = self.records.get(identifier)
        if record is not None and record['state'] == 'executing':
            record['state'] = 'outcome_unknown'

    def disconnect(self):
        for identifier in self.records:
            self.interrupted(identifier)

    def clear(self):
        self.records.clear()
        self.responses.clear()
        self._bytes = 0


class LiveSessionState:
    """Session-scoped tool identity and atomic, content-free UI state snapshots."""
    def __init__(self):
        self.tools = ToolCallCache()
        self.connected = False
        self.has_connected = False
        self.epoch = 0
        self.revision = 0
        self.state = 'offline'

    def opened(self, *, resumed):
        if not resumed:
            self.tools.clear()
            self.epoch += 1
        self.connected = self.has_connected = True

    def disconnect(self):
        self.connected = False
        self.tools.disconnect()

    def transition(self, state):
        self.state = state
        self.revision += 1
        return self.snapshot()

    def snapshot(self):
        transport = self.state
        if transport in ('idle', 'thinking', 'processing'):
            transport = 'listening' if self.connected else 'reconnecting' if self.has_connected else 'connecting'
        return {'connection_state': transport, 'connection_revision': self.revision,
                'session_epoch': self.epoch,
                'pending_tool_calls': sum(record['state'] == 'executing' for record in self.tools.records.values())}


@asynccontextmanager
async def connect_live(client, *, model, config, timeout=10):
    async with AsyncExitStack() as stack:
        async with asyncio.timeout(timeout):
            session = await stack.enter_async_context(
                client.live.connect(model=model, config=config))
        yield session


class ResumeRecovery:
    """Try preserving provider context twice before abandoning a failed handle.

    This never resubmits user requests or tool calls. Persistent local memory
    remains available when the next connection starts a fresh provider session.
    """
    def __init__(self):
        self.failures = 0

    def opened(self):
        self.failures = 0

    def failed(self, handle, *, opened, code, transient):
        if opened or not handle:
            self.failures = 0
            return False
        if code in (400, 1008):
            self.failures = 0
            return True
        if transient and code != 429:
            self.failures += 1
            if self.failures >= 2:
                self.failures = 0
                return True
        return False
