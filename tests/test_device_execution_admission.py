import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

from jarvis_control.device_execution import SharedToolExecutor
from jarvis_control.outcomes import classify_result


@pytest.mark.asyncio
async def test_unrelated_request_is_rejected_without_queueing_or_ledger_entry(tmp_path, monkeypatch):
    monkeypatch.setattr('jarvis_control.device_execution.tool_timeout', lambda *_: 1)
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(name, args):
        started.set()
        await release.wait()
        return name

    skills = SimpleNamespace(declarations=[{'name': 'action'}], execute=execute)
    path = tmp_path / 'calls.sqlite'
    router = SharedToolExecutor(skills, path)
    try:
        first = asyncio.create_task(router.call({'request_id': 'one', 'name': 'action', 'args': {}}))
        await started.wait()
        rejected = await router.call({'request_id': 'two', 'name': 'action', 'args': {}})
        assert rejected['status'] == 'busy'
        assert rejected['not_started'] is True and rejected['completed'] is False
        assert router.db.execute('SELECT id FROM calls ORDER BY id').fetchall() == [('one',)]

        release.set()
        assert (await first)['output'] == 'action'
        assert (await router.call({'request_id': 'two', 'name': 'action', 'args': {}}))['output'] == 'action'
    finally:
        release.set()
        router.close()


@pytest.mark.asyncio
async def test_response_deadline_returns_pending_and_keeps_slot_until_real_completion(tmp_path, monkeypatch):
    monkeypatch.setattr('jarvis_control.device_execution.tool_timeout', lambda *_: .01)
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(name, args):
        started.set()
        await release.wait()
        return 'finished'

    skills = SimpleNamespace(declarations=[{'name': 'action'}], execute=execute)
    path = tmp_path / 'calls.sqlite'
    router = SharedToolExecutor(skills, path)
    request = {'request_id': 'same', 'name': 'action', 'args': {}}
    try:
        pending = await asyncio.wait_for(router.call(request), .2)
        await started.wait()
        assert pending['status'] == 'running' and pending['pending'] is True
        assert pending['completed'] is False
        assert pending['request_id'] == request['request_id']
        assert classify_result(pending).status == 'running'
        assert (await router.call(request))['status'] == 'running'
        assert (await router.call({'request_id': 'next', 'name': 'action', 'args': {}}))['status'] == 'busy'

        release.set()
        await asyncio.wait_for(router.active[2], .2)
        result = await router.call(request)
        assert result['output'] == 'finished' and result['completed'] is True
        assert await router.call(request) == result
        assert router.db.execute('SELECT result FROM calls WHERE id=?', ('same',)).fetchone()[0]
    finally:
        release.set()
        router.close()


@pytest.mark.asyncio
async def test_cancelled_request_waiter_does_not_cancel_admitted_action(tmp_path):
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(name, args):
        started.set()
        await release.wait()
        return 'finished'

    skills = SimpleNamespace(declarations=[{'name': 'action'}], execute=execute)
    router = SharedToolExecutor(skills, tmp_path / 'calls.sqlite')
    request = {'request_id': 'cancelled-waiter', 'name': 'action', 'args': {}}
    try:
        waiter = asyncio.create_task(router.call(request))
        await started.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert router.active is not None
        assert (await router.call({'request_id': 'unrelated', 'name': 'action', 'args': {}}))['not_started'] is True
        release.set()
        await asyncio.wait_for(router.active[2], .2)
        assert (await router.call(request))['output'] == 'finished'
    finally:
        release.set()
        router.close()


def test_shutdown_preserves_durable_null_receipt(tmp_path):
    ledger = tmp_path / 'calls.sqlite'
    router = SharedToolExecutor(type('Skills', (), {'declarations': [], 'execute': None})(), ledger)
    router.db.execute('INSERT INTO calls VALUES(?,?,NULL)', ('unfinished', 'fingerprint'))
    router.db.commit()
    router.close()
    with sqlite3.connect(ledger) as db:
        assert db.execute('SELECT result FROM calls WHERE id=?', ('unfinished',)).fetchone() == (None,)


@pytest.mark.asyncio
async def test_shutdown_cancels_active_wrapper_without_replaying_after_restart(tmp_path):
    started = asyncio.Event()
    calls = []

    async def execute(name, args):
        calls.append(name)
        started.set()
        await asyncio.Event().wait()

    skills = SimpleNamespace(declarations=[{'name': 'action'}], execute=execute)
    ledger = tmp_path / 'calls.sqlite'
    router = SharedToolExecutor(skills, ledger)
    request = {'request_id': 'shutdown-active', 'name': 'action', 'args': {}}
    waiter = asyncio.create_task(router.call(request))
    await asyncio.wait_for(started.wait(), 1)
    router.close()
    await asyncio.gather(waiter, return_exceptions=True)
    replacement = SharedToolExecutor(skills, ledger)
    try:
        assert (await replacement.call(request))['status'] == 'unknown'
        assert calls == ['action']
    finally:
        replacement.close()
