import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest

from orchestration.hermes_bridge import HermesBridge, HermesBridgeError
from orchestration._hermes_gateway_worker import operate


@pytest.mark.asyncio
async def test_foreign_sessions_cannot_run_or_cancel():
    bridge = HermesBridge(python=sys.executable)
    bridge._request = AsyncMock()
    with pytest.raises(HermesBridgeError, match='Only sessions'):
        await bridge.run('someone-elses-chat', 'task')
    with pytest.raises(HermesBridgeError, match='Only sessions'):
        await bridge.cancel('someone-elses-chat')
    bridge._request.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_requires_checkout_and_retains_ownership(tmp_path):
    bridge = HermesBridge(python=sys.executable)
    bridge._request = AsyncMock(return_value={'session_id': 'owned-one'})
    with pytest.raises(HermesBridgeError, match='isolated task Git'):
        await bridge.create_session(workspace=tmp_path)
    (tmp_path / '.git').mkdir()
    assert await bridge.create_session(workspace=tmp_path) == 'owned-one'
    assert 'owned-one' in bridge.owned_sessions
    bridge._request.assert_awaited_once_with('create', workspace=str(tmp_path))


@pytest.mark.asyncio
async def test_unavailable_runtime_does_not_install_or_submit(tmp_path):
    bridge = HermesBridge(home=tmp_path)
    result = await bridge.capabilities()
    assert result['available'] is False
    assert not (tmp_path / 'installs').exists()


@pytest.mark.parametrize('budget', [True, 0, 1801, 1.5])
@pytest.mark.asyncio
async def test_invalid_budgets_never_dispatch(budget):
    bridge = HermesBridge(python=sys.executable)
    bridge.owned_sessions.add('mine')
    bridge._request = AsyncMock()
    with pytest.raises(HermesBridgeError, match='timeout'):
        await bridge.run('mine', 'task', timeout_seconds=budget)
    bridge._request.assert_not_awaited()


def fake_gateway(monkeypatch, client):
    runtime, gateway = ModuleType('hermes_cli.gateway_runtime'), ModuleType('hermes_cli.gateway_client')
    endpoint = object()
    runtime.discover_gateway_endpoint = lambda home: SimpleNamespace(endpoint=endpoint)
    runtime.attachable = lambda result: True

    @asynccontextmanager
    async def connect_gateway(*, endpoint):
        yield client

    gateway.connect_gateway = connect_gateway
    monkeypatch.setitem(sys.modules, 'hermes_cli.gateway_runtime', runtime)
    monkeypatch.setitem(sys.modules, 'hermes_cli.gateway_client', gateway)
    monkeypatch.setenv('HERMES_HOME', '/tmp/test-hermes')


@pytest.mark.asyncio
async def test_worker_filters_other_sessions_and_admissions(monkeypatch):
    events = asyncio.Queue()
    for session, admission, kind, payload in [
        ('other', 'a', 'message.complete', {'text': 'private-other-chat'}),
        ('mine', 'old', 'message.complete', {'text': 'old-turn'}),
        ('mine', None, 'message.complete', {'text': 'uncorrelated-old-turn'}),
        ('mine', 'a', 'message.delta', {'text': 'my answer'}),
        ('mine', 'a', 'message.complete', {'status': 'completed'}),
    ]:
        events.put_nowait({'params': {'session_id': session, 'admission_id': admission,
                                     'type': kind, 'payload': payload}})

    async def rpc(method, **params):
        if method == 'session.resume':
            return {'session_id': 'mine'}
        assert method == 'prompt.submit'
        return {'admission_id': 'a'}

    client = SimpleNamespace(events=events, rpc=rpc)
    fake_gateway(monkeypatch, client)
    result = await operate({'operation': 'run', 'session_id': 'mine', 'prompt': 'task', 'timeout_seconds': 10})
    assert result['status'] == 'completed'
    assert result['output'] == 'my answer'
    assert result['verified'] is False


@pytest.mark.asyncio
async def test_worker_detects_identity_change_before_submission(monkeypatch):
    client = SimpleNamespace(rpc=AsyncMock(return_value={'session_id': 'foreign'}))
    fake_gateway(monkeypatch, client)
    with pytest.raises(ValueError, match='identity changed'):
        await operate({'operation': 'run', 'session_id': 'mine', 'prompt': 'task', 'timeout_seconds': 10})
    assert client.rpc.await_count == 1


@pytest.mark.parametrize('admission', ['a', None])
@pytest.mark.asyncio
async def test_worker_rejects_replay_gap_even_without_admission(monkeypatch, admission):
    events = asyncio.Queue()
    events.put_nowait({'params': {'session_id': 'mine', 'admission_id': admission, 'type': 'session.replay_gap'}})
    async def rpc(method, **kwargs):
        return {'session_id': 'mine'} if method == 'session.resume' else {'admission_id': 'a'}
    fake_gateway(monkeypatch, SimpleNamespace(events=events, rpc=rpc))
    with pytest.raises(ValueError, match='outcome unknown'):
        await operate({'operation': 'run', 'session_id': 'mine', 'prompt': 'task', 'timeout_seconds': 10})


@pytest.mark.asyncio
async def test_cancel_during_spawn_reaps_late_owned_helper(tmp_path, monkeypatch):
    bridge = HermesBridge(source=tmp_path, python=sys.executable)
    entered, release = asyncio.Event(), asyncio.Event()
    process = object()

    async def spawn(*args, **kwargs):
        entered.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    bridge._stop = AsyncMock()
    request = asyncio.create_task(bridge._request('capabilities'))
    await asyncio.wait_for(entered.wait(), 1)
    request.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(request, 1)
    bridge._stop.assert_awaited_once_with(process)
    assert not bridge._processes


@pytest.mark.asyncio
async def test_transport_does_not_inherit_credentials_or_remote_gateway(tmp_path, monkeypatch):
    bridge = HermesBridge(source=tmp_path, python=sys.executable)
    for key in ('GEMINI_API_KEY', 'AWS_ACCESS_KEY', 'PRIVATE_KEY', 'AUTHORIZATION',
                'HERMES_TUI_GATEWAY_URL'):
        monkeypatch.setenv(key, 'private-transport-test')

    class Process:
        returncode = 0
        stdin = SimpleNamespace(write=lambda data: None, drain=AsyncMock(), close=lambda: None)
        stdout = SimpleNamespace(read=AsyncMock(side_effect=[b'{"status":"success"}', b'']))
        wait = AsyncMock(return_value=0)

    async def spawn(*args, **kwargs):
        for key in ('GEMINI_API_KEY', 'AWS_ACCESS_KEY', 'PRIVATE_KEY', 'AUTHORIZATION',
                    'HERMES_TUI_GATEWAY_URL'):
            assert key not in kwargs['env']
        assert kwargs['start_new_session'] is True
        return Process()

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    assert (await bridge._request('capabilities'))['status'] == 'success'


@pytest.mark.asyncio
async def test_close_interrupts_only_active_owned_work():
    bridge = HermesBridge(python=sys.executable)
    bridge.owned_sessions.update({'completed', 'running'})
    bridge._active.add('running')
    bridge.cancel = AsyncMock(return_value={'acknowledged': True})
    await bridge.close()
    bridge.cancel.assert_awaited_once_with('running')
    assert bridge._closed
