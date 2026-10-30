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
