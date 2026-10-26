import asyncio
import json
from pathlib import Path
import stat

import pytest

from orchestration.task_agents import TaskAgents


class Bridge:
    def __init__(self, *, blocked=False, acknowledged=True, failed=False):
        self.blocked, self.acknowledged, self.failed = blocked, acknowledged, failed
        self.sessions = []
        self.calls = []
        self.entered = asyncio.Event()

    async def capabilities(self):
        return {'status': 'success', 'connected': True}

    async def create_session(self, *, workspace):
        assert (Path(workspace) / '.git').is_file()
        key = 'session-' + str(len(self.sessions))
        self.sessions.append(key)
        return key

    async def run(self, session_id, prompt, *, timeout_seconds):
        self.calls.append((session_id, prompt))
        self.entered.set()
        if self.blocked:
            await asyncio.Event().wait()
        if self.failed:
            return {'status': 'error', 'output': 'a claimed answer in an error'}
        return {'status': 'completed', 'output': 'Prepared a list. Actions are only claimed.'}

    async def cancel(self, session_id):
        return {'acknowledged': self.acknowledged}


@pytest.mark.asyncio
async def test_role_runs_in_new_session_and_followup_reuses_only_explicit_session(tmp_path):
    bridge = Bridge()
    events = asyncio.Queue(maxsize=2)
    agents = TaskAgents(tmp_path, events, bridge=bridge)
    try:
        first = agents.start('Summarize these notes', role='summarizer', context='Meeting notes')
        assert first['status'] == 'queued'
        await asyncio.wait_for(agents.workers[first['id']], 3)
        result = agents.status(first['id'])
        assert result['status'] == 'completed' and result['verified'] is False
        assert 'Meeting notes' in bridge.calls[0][1]
        assert '/workspaces/' in result['workspace']
        assert result['workspace'].endswith('/worktree')
        assert 'Do not change global skills' in bridge.calls[0][1]
        followup = agents.followup(first['id'], 'Make it shorter')
        await asyncio.wait_for(agents.workers[followup['id']], 3)
        assert len(bridge.sessions) == 1
        assert bridge.calls[1][0] == result['session_id']
        assert followup['parent'] == first['id']
        assert events.get_nowait()['kind'] == 'task_agent'
        assert stat.S_IMODE((tmp_path / (first['id'] + '.json')).stat().st_mode) == 0o600
        assert (await agents.capabilities())['maximum_active_tasks'] == 3
    finally:
        await agents.close()
    recovered = TaskAgents(tmp_path, bridge=Bridge())
    assert recovered.status(first['id'])['status'] == 'completed'
    assert recovered.status(first['id'])['verified'] is False
    await recovered.close()


@pytest.mark.asyncio
async def test_failed_provider_response_is_never_reported_as_completed(tmp_path):
    agents = TaskAgents(tmp_path, bridge=Bridge(failed=True))
    try:
        item = agents.start('Draft a list')
        await asyncio.wait_for(agents.workers[item['id']], 3)
        assert agents.status(item['id'])['status'] == 'failed'
        assert not agents.status(item['id'])['output']
        with pytest.raises(ValueError, match='completed task'):
            agents.followup(item['id'], 'Continue')
    finally:
        await agents.close()


@pytest.mark.asyncio
async def test_cancel_distinguishes_acknowledgement_from_local_wait_stop(tmp_path):
    bridge = Bridge(blocked=True, acknowledged=False)
    agents = TaskAgents(tmp_path, bridge=bridge)
    try:
        item = agents.start('Wait')
        await asyncio.wait_for(bridge.entered.wait(), 3)
        result = await agents.cancel(item['id'])
        assert result['status'] == 'cancelled'
        assert result['execution'] == 'unknown'
        assert result['cancellation_acknowledged'] is False
        with pytest.raises(ValueError, match='unknown execution'):
            agents.start('More work')
        bridge.acknowledged = True
        result = await agents.cancel(item['id'])
        assert result['execution'] == 'cancel_acknowledged'
        assert result['cancellation_acknowledged'] is True
    finally:
        await agents.close()


@pytest.mark.asyncio
async def test_bounds_duplicate_and_competing_manager(tmp_path):
    bridge = Bridge(blocked=True)
    agents = TaskAgents(tmp_path, bridge=bridge)
    competing = TaskAgents(tmp_path, bridge=Bridge())
    try:
        first = agents.start('Task one')
        with pytest.raises(ValueError, match='already running'):
            agents.start('Task one')
        with pytest.raises(ValueError, match='Another JARVIS'):
            competing.start('Competing')
        agents.start('Task two')
        agents.start('Task three')
        with pytest.raises(ValueError, match='Three task'):
            agents.start('Task four')
        with pytest.raises(ValueError, match='timeout_seconds'):
            agents.start('Invalid', timeout_seconds=True)
        await agents.cancel(first['id'])
    finally:
        await agents.close()
        await competing.close()


@pytest.mark.asyncio
async def test_restart_unknown_execution_does_not_replay_and_requires_inspection(tmp_path):
    bridge = Bridge()
    agents = TaskAgents(tmp_path, bridge=bridge)
    item = agents.start('Draft an outline')
    await asyncio.wait_for(agents.workers[item['id']], 3)
    await agents.close()
    path = tmp_path / (item['id'] + '.json')
    journal = json.loads(path.read_text())
    journal.update(state='running', execution='running')
    path.write_text(json.dumps(journal))
    recovered = TaskAgents(tmp_path, bridge=bridge)
    try:
        assert recovered.status(item['id'])['status'] == 'interrupted'
        assert len(bridge.calls) == 1
        with pytest.raises(ValueError, match='unknown execution'):
            recovered.start('Do not replay')
        assert (await recovered.cancel(item['id']))['cancellation_acknowledged'] is True
    finally:
        await recovered.close()


@pytest.mark.asyncio
async def test_notification_pressure_keeps_result_and_marks_drop(tmp_path):
    events = asyncio.Queue(maxsize=1)
    events.put_nowait({'other': 'event'})
    agents = TaskAgents(tmp_path, events, bridge=Bridge())
    try:
        item = agents.start('Draft a checklist')
        await asyncio.wait_for(agents.workers[item['id']], 3)
        assert agents.status(item['id'])['notification_dropped'] is True
        assert agents.status(item['id'])['status'] == 'completed'
    finally:
        await agents.close()


@pytest.mark.asyncio
async def test_preparation_failure_never_submits_and_does_not_invent_remote_execution(tmp_path, monkeypatch):
    bridge = Bridge()
    agents = TaskAgents(tmp_path, bridge=bridge)
    def unavailable(job):
        raise OSError('scratch setup unavailable')
    monkeypatch.setattr(agents, '_workspace', unavailable)
    try:
        item = agents.start('Draft a list')
        await asyncio.wait_for(agents.workers[item['id']], 3)
        assert agents.status(item['id'])['execution'] == 'not_started'
        assert not bridge.sessions and not bridge.calls
        assert agents.start('A separate request')['status'] == 'queued'
    finally:
        await agents.close()


@pytest.mark.asyncio
async def test_recognized_credentials_are_redacted_before_journal_and_delegation(tmp_path, monkeypatch):
    secret = 'private-example-credential'
    monkeypatch.setenv('TASK_TEST_API_KEY', secret)
    class SecretBridge(Bridge):
        async def run(self, session_id, prompt, *, timeout_seconds):
            self.calls.append((session_id, prompt))
            return {'status': 'completed', 'output': secret}
    bridge = SecretBridge()
    agents = TaskAgents(tmp_path, bridge=bridge)
    try:
        item = agents.start('Describe ' + secret)
        await asyncio.wait_for(agents.workers[item['id']], 3)
        result = agents.status(item['id'])
        assert result['input_redacted'] and result['output_redacted']
        assert secret not in bridge.calls[0][1]
        assert secret not in (tmp_path / (item['id'] + '.json')).read_text()
    finally:
        await agents.close()


@pytest.mark.asyncio
async def test_repeated_cancel_does_not_interrupt_remote_acknowledgement(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    class SlowCancelBridge(Bridge):
        async def cancel(self, session_id):
            entered.set()
            await release.wait()
            return {'acknowledged': True}
    bridge = SlowCancelBridge(blocked=True)
    agents = TaskAgents(tmp_path, bridge=bridge)
    try:
        item = agents.start('Wait for cancellation')
        await asyncio.wait_for(bridge.entered.wait(), 3)
        first = asyncio.create_task(agents.cancel(item['id']))
        await asyncio.wait_for(entered.wait(), 3)
        second = asyncio.create_task(agents.cancel(item['id']))
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, second), 3)
        assert all(result['cancellation_acknowledged'] for result in results)
        assert agents.status(item['id'])['state'] == 'cancelled'
    finally:
        release.set()
        await agents.close()
