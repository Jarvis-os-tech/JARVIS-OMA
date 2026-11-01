import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from jarvis_voice.ipc import ControlServer
from jarvis_control.device_bridge import DeviceBridge


@pytest.mark.asyncio
async def test_ipc_waits_for_durable_memory_callback():
    callback = AsyncMock(return_value={'status': 'ok', 'acknowledged': ['record-1'], 'history': []})
    control = ControlServer(sync_companion_cb=callback)
    records = [{'id': 'record-1'}]
    result = json.loads(await control._handle_json_command({'command': 'companion_memory', 'records': records}))
    callback.assert_awaited_once_with(records)
    assert result['acknowledged'] == ['record-1']


@pytest.mark.asyncio
async def test_memory_exchange_rejects_wrong_token_before_forwarding():
    bridge = DeviceBridge('a' * 64)
    bridge.forward = AsyncMock(return_value={'status': 'ok', 'acknowledged': []})
    server = await asyncio.start_server(bridge.handle, '127.0.0.1', 0)
    async def request(token):
        reader, writer = await asyncio.open_connection('127.0.0.1', server.sockets[0].getsockname()[1])
        body = b'{"records":[]}'
        writer.write((f'POST /v1/memory/exchange HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body)
        await writer.drain()
        result = await asyncio.wait_for(reader.read(), 2)
        writer.close()
        await writer.wait_closed()
        return result
    async with server:
        assert b'401' in (await request('wrong')).splitlines()[0]
        bridge.forward.assert_not_awaited()
        assert b'200' in (await request('a' * 64)).splitlines()[0]
        bridge.forward.assert_awaited_once_with({'records': [], 'command': 'companion_memory'})
