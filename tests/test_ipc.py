# tests/test_ipc.py
import asyncio
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

@pytest.fixture
def socket_path(tmp_path):
    return tmp_path / 'test.sock'

@pytest.mark.asyncio
async def test_status_json(socket_path):
    from jarvis_voice.ipc import ControlServer
    status = {'listening': True, 'connected': True, 'model': 'test'}
    server = ControlServer(socket_path=socket_path, status_provider=lambda: status)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'status --json\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        result = json.loads(data.decode())
        assert result['listening'] is True
        assert result['model'] == 'test'
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_listen_toggle(socket_path):
    from jarvis_voice.ipc import ControlServer
    state = {'muted': False}
    def toggle():
        state['muted'] = not state['muted']
        return state['muted']
    server = ControlServer(
        socket_path=socket_path,
        status_provider=lambda: {'listening': not state['muted']},
        toggle_mute_cb=toggle,
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'listen toggle\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert state['muted'] is True
        assert b'muted' in data.lower() or b'true' in data.lower()
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_unknown_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    server = ControlServer(socket_path=socket_path, status_provider=lambda: {})
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'foobar\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert b'unknown' in data.lower() or b'error' in data.lower()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_second_daemon_does_not_unlink_live_socket(socket_path):
    from jarvis_voice.ipc import ControlServer
    first = ControlServer(socket_path=socket_path, status_provider=lambda: {'connected': True})
    second = ControlServer(socket_path=socket_path)
    await first.start()
    try:
        with pytest.raises(RuntimeError, match='already running'):
            await second.start()
        await second.close()
        assert socket_path.exists()
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'status --json\n')
        await writer.drain()
        assert json.loads(await reader.readline())['connected']
        writer.close()
        await writer.wait_closed()
    finally:
        await first.close()


@pytest.mark.asyncio
async def test_control_path_never_replaces_regular_file(socket_path):
    from jarvis_voice.ipc import ControlServer
    socket_path.write_text('keep this file')
    server = ControlServer(socket_path=socket_path)
    with pytest.raises(PermissionError):
        await server.start()
    await server.close()
    assert socket_path.read_text() == 'keep this file'


@pytest.mark.asyncio
async def test_standby_ipc_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    called = []
    server = ControlServer(
        socket_path=socket_path,
        standby_cb=lambda: called.append(True),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'standby\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('standby') is True
        assert res.get('status') == 'standby_requested'
        assert len(called) == 1
    finally:
        await server.close()



@pytest.mark.asyncio
async def test_local_confirm_and_cancel_await_control_callbacks():
    from unittest.mock import AsyncMock, Mock
    from jarvis_voice.ipc import ControlServer
    confirm, cancel, interrupt = AsyncMock(return_value='confirmed'), AsyncMock(return_value='cancelled'), Mock()
    server = ControlServer(confirm_cb=confirm, cancel_cb=cancel, interrupt_cb=interrupt)
    assert json.loads(await server._dispatch('listen confirm')) == {'result': 'confirmed'}
    assert json.loads(await server._dispatch('listen cancel')) == {'result': 'cancelled'}
    confirm.assert_awaited_once()
    cancel.assert_awaited_once()
    interrupt.assert_called_once()


@pytest.mark.asyncio
async def test_socket_confirmation_returns_after_async_callback(tmp_path):
    from unittest.mock import AsyncMock
    from jarvis_voice.ipc import ControlServer
    callback = AsyncMock(return_value='synthetic confirmed')
    server = ControlServer(socket_path=tmp_path / 'confirmation.sock', confirm_cb=callback)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(server.socket_path))
        writer.write(b'listen confirm\n')
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 2))
        assert response == {'result': 'synthetic confirmed'}
        callback.assert_awaited_once()
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_send_text_ipc_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    sent = []
    server = ControlServer(
        socket_path=socket_path,
        send_text_cb=lambda text: sent.append(text),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'send what is the weather\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('status') == 'sent'
        assert res.get('text') == 'what is the weather'
        assert sent == ['what is the weather']
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_wake_ipc_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    woken = []
    server = ControlServer(
        socket_path=socket_path,
        wake_cb=lambda: woken.append(True),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'wake\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('status') == 'awake'
        assert res.get('standby') is False
        assert woken == [True]
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_vision_mode_json_ipc_commands(socket_path):
    from jarvis_voice.ipc import ControlServer
    current_mode = {'mode': 'off'}

    def set_mode(m):
        current_mode['mode'] = m
        return {'vision_mode': m}

    server = ControlServer(
        socket_path=socket_path,
        get_vision_mode_cb=lambda: current_mode['mode'],
        set_vision_mode_cb=set_mode,
    )
    await server.start()
    try:
        # 1. get_vision_mode when off
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'get_vision_mode'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'off'

        # 2. set_vision_mode to camera
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'set_vision_mode', 'mode': 'camera'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'camera'
        assert current_mode['mode'] == 'camera'

        # 3. get_vision_mode when camera
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'get_vision_mode'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'camera'

        # 4. text command: vision screen
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'vision screen\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'screen'
        assert current_mode['mode'] == 'screen'
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_sync_memory_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    recorded = []
    def record_cb(user, assistant):
        recorded.append((user, assistant))
        return True

    server = ControlServer(
        socket_path=socket_path,
        record_memory_cb=record_cb
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        cmd = {
            'command': 'sync_memory',
            'records': [
                {'role': 'user', 'content': 'Hello from phone'},
                {'role': 'model', 'content': 'Hello back on mobile'}
            ]
        }
        writer.write(json.dumps(cmd).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['saved'] is True
        assert len(recorded) == 1
        assert recorded[0] == ('Hello from phone', 'Hello back on mobile')
    finally:
        await server.close()
