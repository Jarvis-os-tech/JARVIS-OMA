"""Service, process and discovery contracts without external account mutations."""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

from connectors import api_anything as api, api_service as service
from jarvis_control.execution_policy import tool_timeout
from jarvis_control.outcomes import classify_result
from orchestration.tool_tiers import domain_for_tool, intent_domains, DOMAINS


@pytest.mark.parametrize('name,domain', [
    ('api_anything_call', 'api_anything'), ('api_anything_propose', 'api_anything'),
    ('cli_hub_launch', 'cli_anything'), ('composio_execute_tool', 'composio'),
    ('integration_service_status', 'integrations'),
])
def test_integrations_are_discoverable(name, domain):
    assert domain in DOMAINS and domain_for_tool(name) == domain


def test_intent_hints_and_deadlines_cover_real_service_limits():
    assert 'api_anything' in intent_domains('ask the API agent')
    assert 'composio' in intent_domains('check Composio connectors')
    for name, minimum in [('api_anything_propose', 125), ('api_anything_learn', 185),
                          ('cli_hub_install', 120), ('cli_hub_matrix_install', 300)]:
        assert tool_timeout(name) > minimum
        assert tool_timeout('execute_domain_tool', {'tool_name': name}) == tool_timeout(name)


@pytest.mark.asyncio
@pytest.mark.parametrize('code,expected', [
    ('print(\'{"ok":true}\'); raise SystemExit(2)', False),
    ('print("not JSON")', False),
    ('print(\'{"ok":false,"error":"denied"}\')', False),
    ('print(\'{"ok":true,"data":42}\')', True),
    ('print(\'[{"name":"example"}]\')', True),
])
async def test_process_status_and_machine_output_are_both_required(monkeypatch, tmp_path, code, expected):
    monkeypatch.setattr(api, '_resolve_bun', lambda: sys.executable)
    monkeypatch.setattr(api, '_child_env', lambda: {'PATH': os.environ['PATH']})
    result = await api._exec_bun_cmd('-c', code, cwd=tmp_path)
    assert result['ok'] is expected


@pytest.mark.asyncio
async def test_accepted_write_is_not_completed(monkeypatch, tmp_path):
    monkeypatch.setattr(api, '_resolve_bun', lambda: sys.executable)
    monkeypatch.setattr(api, '_child_env', lambda: {})
    result = await api._exec_bun_cmd('-c', 'print(\'{"ok":true,"write":"accepted"}\')', cwd=tmp_path)
    assert result['completed'] is False
    assert not classify_result(result).completed


@pytest.mark.asyncio
async def test_typed_arguments_and_stable_write_key_are_preserved(monkeypatch):
    execute = AsyncMock(return_value={'ok': True, 'write': 'applied'})
    monkeypatch.setattr(api, '_exec_bun_cmd', execute)
    args = {'enabled': True, 'items': [1, 2], 'note': 'spaces and = signs'}
    result = await service.dispatch_local('call', {'site': 'demo', 'op': 'update', 'args': args,
                                  'allow_writes': True, 'request_key': 'stable-1'})
    command = execute.call_args.args
    assert json.loads(command[command.index('--json') + 1]) == args
    assert command[-3:] == ('--allow-writes', '--idempotency-key', 'stable-1')
    assert result['write'] == 'applied'


@pytest.mark.asyncio
@pytest.mark.parametrize('operation,args', [
    ('call', {'site': 'demo', 'op': 'update', 'allow_writes': True}),
    ('call', {'site': '--help', 'op': 'read'}),
    ('call', {'site': 'demo', 'op': 'read', 'args': []}),
    ('learn', {'blueprint': []}), ('shell', {}),
])
async def test_invalid_requests_never_start_processes(monkeypatch, operation, args):
    execute = AsyncMock()
    monkeypatch.setattr(api, '_exec_bun_cmd', execute)
    result = await service.dispatch_local(operation, args)
    assert result['ok'] is False
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_reaps_owned_process_group(monkeypatch, tmp_path):
    monkeypatch.setattr(api, '_resolve_bun', lambda: sys.executable)
    monkeypatch.setattr(api, '_child_env', lambda: {})
    pidfile = tmp_path / 'pid'
    code = f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(30)'
    task = asyncio.create_task(api._exec_bun_cmd('-c', code, cwd=tmp_path))
    for _ in range(100):
        if pidfile.exists():
            break
        await asyncio.sleep(.01)
    assert pidfile.exists()
    pid = int(pidfile.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_real_service_socket_routes_health_and_rejects_unknown(monkeypatch, tmp_path):
    path = tmp_path / 'control.sock'
    monkeypatch.setattr(service, 'socket_path', lambda: path)
    server = await asyncio.start_unix_server(service.ApiService().handle, str(path))
    async with server:
        assert (await service.request('health', {}))['scope'] == 'transport_only'
        assert (await service.request('shell', {}))['ok'] is False


@pytest.mark.asyncio
async def test_missing_service_allows_local_execution(monkeypatch):
    monkeypatch.setattr(service, 'request', AsyncMock(return_value=None))
    execute = AsyncMock(return_value={'ok': True})
    monkeypatch.setattr(service, 'dispatch_local', execute)
    await api.search('example')
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_uncertain_service_result_never_replays_locally(monkeypatch):
    monkeypatch.setattr(service, 'request', AsyncMock(return_value={'ok': False, 'status': 'unknown'}))
    execute = AsyncMock()
    monkeypatch.setattr(service, 'dispatch_local', execute)
    result = await api.call_operation('demo', 'update', {}, True, 'same-key')
    assert result['status'] == 'unknown'
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_saturation_is_rejected_before_dispatch(monkeypatch):
    broker = service.ApiService()
    broker.active = 2
    reader = asyncio.StreamReader()
    reader.feed_data(b'{"operation":"call","arguments":{}}\n')
    class Writer:
        data = b''
        def write(self, data): self.data += data
        async def drain(self): pass
        def close(self): pass
    writer = Writer()
    execute = AsyncMock()
    monkeypatch.setattr(service, 'dispatch_local', execute)
    await broker.handle(reader, writer)
    assert json.loads(writer.data)['status'] == 'unavailable'
    execute.assert_not_awaited()
