import asyncio
import json

import pytest

from core.ipc import JarvisIPCServer
from voice_layer import ipc


@pytest.mark.asyncio
async def test_core_second_server_preserves_running_socket(tmp_path):
    path = tmp_path / 'core.sock'
    first = JarvisIPCServer(path, status_provider=lambda: {'connected': True})
    second = JarvisIPCServer(path)
    await first.start()
    try:
        with pytest.raises(RuntimeError, match='already running'):
            await second.start()
        await second.close()
        reader, writer = await asyncio.open_unix_connection(str(path))
        writer.write(b'{"command":"status"}\n')
        await writer.drain()
        assert json.loads(await reader.readline())['connected']
        writer.close()
        await writer.wait_closed()
    finally:
        await first.close()


@pytest.mark.asyncio
async def test_core_preserves_regular_control_path(tmp_path):
    path = tmp_path / 'core.sock'
    path.write_text('keep')
    server = JarvisIPCServer(path)
    with pytest.raises(PermissionError):
        await server.start()
    await server.close()
    assert path.read_text() == 'keep'


@pytest.mark.asyncio
async def test_voice_non_owner_preserves_speak_socket(tmp_path, monkeypatch):
    speak = tmp_path / 'speak.sock'
    monkeypatch.setattr(ipc, 'SPEAK_SOCKET_PATH', speak)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    first = ipc.ControlServer(tmp_path / 'first.sock', status_provider=lambda: {'owner': 'first'})
    second = ipc.ControlServer(tmp_path / 'second.sock')
    await first.start()
    try:
        await second.start()
        await second.close()
        reader, writer = await asyncio.open_unix_connection(str(speak))
        writer.write(b'status --json\n')
        await writer.drain()
        assert json.loads(await reader.readline())['owner'] == 'first'
        writer.close()
        await writer.wait_closed()
    finally:
        await first.close()


@pytest.mark.asyncio
async def test_voice_preserves_existing_legacy_path(tmp_path, monkeypatch):
    primary = tmp_path / 'voice.sock'
    legacy = tmp_path / 'jarvis.sock'
    legacy.write_text('keep')
    monkeypatch.setattr(ipc, 'SOCKET_PATH', primary)
    monkeypatch.setattr(ipc, 'SPEAK_SOCKET_PATH', tmp_path / 'speak.sock')
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    server = ipc.ControlServer(primary)
    await server.start()
    await server.close()
    assert legacy.read_text() == 'keep'


@pytest.mark.asyncio
async def test_concurrent_core_start_keeps_one_owner(tmp_path):
    path = tmp_path / 'core.sock'
    servers = [JarvisIPCServer(path), JarvisIPCServer(path)]
    try:
        results = await asyncio.gather(*(server.start() for server in servers), return_exceptions=True)
        assert sum(result is None for result in results) == 1
        loser = servers[next(i for i, result in enumerate(results) if isinstance(result, Exception))]
        await loser.close()
        reader, writer = await asyncio.open_unix_connection(str(path))
        writer.write(b'{"command":"status"}\n')
        await writer.drain()
        assert json.loads(await reader.readline())['status'] == 'ok'
        writer.close()
        await writer.wait_closed()
    finally:
        for server in servers:
            await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['core', 'voice', 'speak'])
async def test_shutdown_preserves_replaced_socket_path(tmp_path, monkeypatch, kind):
    primary = tmp_path / 'control.sock'
    speak = tmp_path / 'speak.sock'
    monkeypatch.setattr(ipc, 'SPEAK_SOCKET_PATH', speak)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    server = JarvisIPCServer(primary) if kind == 'core' else ipc.ControlServer(primary)
    path = speak if kind == 'speak' else primary
    await server.start()
    path.unlink()
    path.write_text('replacement')
    await server.close()
    assert path.read_text() == 'replacement'
