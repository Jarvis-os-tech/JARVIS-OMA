import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from jarvis_control.device_execution import SharedToolExecutor
from jarvis_control.device_bridge import DeviceBridge
from jarvis_voice.ipc import ControlServer


@pytest.mark.asyncio
async def test_same_action_is_never_executed_twice_even_after_restart(tmp_path):
    skills = type('Skills', (), {'declarations': [{'name': 'system_query'}], 'execute': AsyncMock(return_value='ok')})()
    ledger = tmp_path / 'calls.sqlite'
    router = SharedToolExecutor(skills, ledger)
    request = {'request_id': 'phone:1', 'name': 'system_query', 'args': {'topic': 'time'}}
    first, second = await asyncio.gather(router.call(request), router.call(request))
    assert first == second
    assert skills.execute.await_count == 1
    router.close()
    router = SharedToolExecutor(skills, ledger)
    assert await router.call(request) == first
    assert skills.execute.await_count == 1
    assert 'error' in await router.call({**request, 'args': {'topic': 'os'}})
    router.close()


@pytest.mark.asyncio
async def test_uncertain_call_is_not_replayed(tmp_path):
    skills = type('Skills', (), {'declarations': [{'name': 'action'}], 'execute': AsyncMock(side_effect=RuntimeError)})()
    router = SharedToolExecutor(skills, tmp_path / 'ledger')
    request = {'request_id': 'phone:2', 'name': 'action', 'args': {}}
    assert (await router.call(request))['status'] == 'unknown'
    assert (await router.call(request))['status'] == 'unknown'
    assert skills.execute.await_count == 1
    assert 'error' in await router.call({**request, 'name': 'not_enabled'})
    router.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('output,status', [
    ('ERROR: action did not run', 'failed'),
    ('{"status":"blocked","verified":false}', 'blocked'),
    ('{"status":"unverified_effect","verified":false}', 'unverified'),
    ('{"status":"queued","id":"fixture"}', 'queued'),
    ('{"task":{"status":"running","id":"fixture"}}', 'running'),
])
async def test_shared_executor_does_not_promote_incomplete_results(tmp_path, output, status):
    skills = type('Skills', (), {'declarations': [{'name': 'action'}],
                                'execute': AsyncMock(return_value=output)})()
    router = SharedToolExecutor(skills, tmp_path / 'calls.sqlite')
    try:
        request = {'request_id': 'fixture:incomplete', 'name': 'action', 'args': {}}
        result = await router.call(request)
        assert result['status'] == status
        assert result['completed'] is False
        assert await router.call(request) == result
        skills.execute.assert_awaited_once()
    finally:
        router.close()


@pytest.mark.asyncio
async def test_bridge_authentication_and_existing_executor(tmp_path):
    skills = type('Skills', (), {'declarations': [{'name': 'system_query'}], 'execute': AsyncMock(return_value='existing executor')})()
    router = SharedToolExecutor(skills, tmp_path / 'calls.sqlite')
    ipc = ControlServer(socket_path=tmp_path / 'control.sock', tools_provider=router.declarations, tool_call_cb=router.call)
    await ipc.start()
    bridge = DeviceBridge('x' * 64, ipc.socket_path)
    server = await asyncio.start_server(bridge.handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]

    async def request(path, token, payload=None):
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        body = json.dumps(payload).encode() if payload else b''
        method = 'POST' if payload else 'GET'
        writer.write(f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body)
        await writer.drain()
        data = await reader.read()
        writer.close()
        await writer.wait_closed()
        header, body = data.split(b'\r\n\r\n', 1)
        return int(header.split(b' ')[1]), json.loads(body)

    try:
        status, _ = await request('/v1/tools', 'wrong')
        assert status == 401
        status, manifest = await request('/v1/tools', 'x' * 64)
        assert status == 200 and manifest['tools'] == skills.declarations
        payload = {'request_id': 'mobile:3', 'name': 'system_query', 'args': {'topic': 'time'}}
        assert (await request('/v1/call', 'x' * 64, payload))[1]['output'] == 'existing executor'
        await request('/v1/call', 'x' * 64, payload)
        assert skills.execute.await_count == 1
        assert (await request('/v1/call', 'x' * 64, {'arbitrary': 'input'}))[0] == 400
    finally:
        server.close()
        await server.wait_closed()
        await ipc.close()
        router.close()
