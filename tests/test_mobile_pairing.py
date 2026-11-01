import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from jarvis_control.mobile_pairing import open_pairing_qr
from jarvis_control.tools import tools_for
from jarvis_control.config import Config
from scripts import pairing_window_state as state


def test_pairing_tool_uses_own_widget_without_returning_private_output(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    def generate(command, **kwargs):
        Path(command[command.index('--output') + 1]).write_bytes(b'private-qr')
        return subprocess.CompletedProcess([], 0, stdout='private-key-never-returned', stderr='')
    with patch('jarvis_control.mobile_pairing.subprocess.run', side_effect=generate) as run, patch(
        'jarvis_control.mobile_pairing.subprocess.Popen'
    ) as window:
        response = open_pairing_qr()
    assert 'private-key-never-returned' not in response
    assert '--no-ascii' in run.call_args.args[0]
    assert '--show-payload' not in run.call_args.args[0]
    assert '--view' not in run.call_args.args[0]
    assert '--pairing-session' in run.call_args.args[0]
    assert 'mobile_pairing_widget.py' in window.call_args.args[0][1]
    from jarvis_control import to_gemini_tools
    schemas = to_gemini_tools(tools_for(Config()))[0]['function_declarations']
    assert any(tool['name'] == 'phone_pair' for tool in schemas)


def test_confirmation_is_bound_to_exact_unexpired_session(tmp_path):
    session = state.create(tmp_path, now=100)
    assert not state.confirm('f' * 64, tmp_path, now=101)
    assert not state.confirm(session, tmp_path, now=401)
    assert not json.loads(state.path_for(session, tmp_path).read_text())['confirmed']
    assert state.confirm(session, tmp_path, now=200)
    assert json.loads(state.path_for(session, tmp_path).read_text())['confirmed']


def test_session_paths_reject_traversal(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        state.confirm('../../pairing_credentials', tmp_path)


async def request(port, token, session):
    import asyncio
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    body = json.dumps({'session': session}).encode()
    writer.write((f'POST /v1/pairing/confirm HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body)
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return int(data.split(b' ')[1])


def test_bridge_acknowledgement_requires_pairing_token_and_live_session(tmp_path, monkeypatch):
    import asyncio
    from jarvis_control.device_bridge import DeviceBridge
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    async def check():
        session = state.create()
        bridge = DeviceBridge('x' * 64)
        server = await asyncio.start_server(bridge.handle, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        try:
            assert await request(port, 'wrong', session) == 401
            assert state.status(session) == 'pending'
            assert await request(port, 'x' * 64, 'f' * 64) == 410
            assert state.status(session) == 'pending'
            assert await request(port, 'x' * 64, session) == 200
            assert state.status(session) == 'confirmed'
        finally:
            server.close()
            await server.wait_closed()
    asyncio.run(check())
