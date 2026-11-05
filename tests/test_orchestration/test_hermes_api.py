import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from orchestration.hermes_api import HermesAPI, workflow_prompt
from orchestration.durable_hermes import DurableHermes, GoalWorker
try:
    from tests.test_orchestration.test_durable_hermes import Bridge, Supervisor
except ImportError:
    from test_durable_hermes import Bridge, Supervisor


@pytest.fixture
def api(tmp_path):
    operations = [{'name': 'cron.' + action, 'inputSchema': {
        'type': 'object', 'properties': {'action': {'const': action}, 'name': {'type': 'string'},
        'schedule': {'type': 'string'}, 'prompt': {'type': 'string'}},
        'required': ['action'], 'additionalProperties': False}}
        for action in ('list', 'create')]
    async def request(operation, **kwargs):
        if operation == 'native_catalog':
            # The live catalog returns independent JSON objects each request.
            return {'operations': list(operations)}
        return {'ok': True, 'data': {'name': kwargs['arguments'].get('name')}}
    bridge = SimpleNamespace(_request=AsyncMock(side_effect=request), features=AsyncMock())
    return HermesAPI(SimpleNamespace(root=tmp_path, bridge=bridge))


@pytest.mark.asyncio
async def test_native_write_deduplicates_across_new_clients(api):
    args = {'name': 'Morning summary', 'prompt': 'Summarize', 'schedule': 'every day at 9am'}
    result = await api.call('cron.create', args, 'morning-one')
    assert result['ok']
    returning = HermesAPI(api.agents)
    assert await returning.call('cron.create', args, 'morning-one') == result
    calls = [c for c in api.bridge._request.call_args_list if c.args[0] == 'native_call']
    assert len(calls) == 1
    with pytest.raises(ValueError, match='different operation'):
        await returning.call('cron.create', {**args, 'schedule': 'every hour'}, 'morning-one')


@pytest.mark.asyncio
async def test_unknown_write_never_replays(api):
    original = api.bridge._request.side_effect
    async def request(op, **kwargs):
        if op == 'native_call':
            raise TimeoutError()
        return await original(op, **kwargs)
    api.bridge._request.side_effect = request
    assert (await api.call('cron.create', {'name': 'Test'}, 'unknown'))['class'] == 'unknown'
    assert (await api.call('cron.create', {'name': 'Test'}, 'unknown'))['class'] == 'unknown'
    assert len([c for c in api.bridge._request.call_args_list if c.args[0] == 'native_call']) == 1


@pytest.mark.asyncio
async def test_concurrent_identical_write_runs_once(api):
    entered, release = asyncio.Event(), asyncio.Event()
    original = api.bridge._request.side_effect
    async def request(op, **kwargs):
        if op == 'native_call':
            entered.set()
            await release.wait()
        return await original(op, **kwargs)
    api.bridge._request.side_effect = request
    first = asyncio.create_task(api.call('cron.create', {'name': 'Concurrent'}, 'same'))
    await entered.wait()
    second = await HermesAPI(api.agents).call('cron.create', {'name': 'Concurrent'}, 'same')
    assert second['class'] == 'pending'
    release.set()
    assert (await first)['ok']
    assert len([c for c in api.bridge._request.call_args_list if c.args[0] == 'native_call']) == 1


@pytest.mark.asyncio
async def test_schema_and_write_key_required_before_mutation(api):
    for operation, args, key in [('cron.create', {}, None), ('cron.create', {'surprise': True}, 'x'),
                                  ('not-real', {}, 'x')]:
        with pytest.raises(ValueError):
            await api.call(operation, args, key)
    assert not [c for c in api.bridge._request.call_args_list if c.args[0] == 'native_call']
    assert (await api.call('cron.list'))['ok']


@pytest.mark.parametrize('tasks', [
    [{'name': 'One', 'instruction': 'Read', 'depends_on': ['Missing']}],
    [{'name': 'One', 'instruction': 'Read'}, {'name': 'One', 'instruction': 'Write'}],
    [{'name': 'One', 'instruction': 'Read', 'depends_on': ['One']}],
    [{'name': 'One', 'instruction': 'Read', 'agent': 5}],
])
def test_workflow_rejects_missing_dependencies_cycles_duplicates_and_bad_workers(tasks):
    with pytest.raises(ValueError):
        workflow_prompt('Report', tasks)


@pytest.mark.asyncio
async def test_workflow_is_one_durable_idempotent_assignment(api):
    api.agents.start = lambda goal, **kwargs: {'name': 'Research workflow', 'state': 'queued', 'goal': goal, **kwargs}
    result = await api.call('workflow.start', {'goal': 'Build report', 'tasks': [
        {'name': 'Research', 'instruction': 'Find evidence', 'agent': 'codex'},
        {'name': 'Review', 'instruction': 'Check evidence', 'depends_on': ['Research']}]}, 'workflow')
    assert result['class'] == 'pending' and result['completed'] is False
    assert 'Wait for dependencies' in result['data']['goal']
    assert result['data']['request_key'] == 'workflow'


@pytest.mark.asyncio
async def test_third_goal_waits_then_gets_released_slot(tmp_path):
    bridge = Bridge()
    client = DurableHermes(tmp_path, bridge=bridge, supervisor=Supervisor())
    first, second, third = [client.start(name) for name in ['First', 'Second', 'Third']]
    workers = [GoalWorker(tmp_path, item['id'], bridge=bridge) for item in [first, second, third]]
    await workers[0].step()
    await workers[1].step()
    assert len(bridge.submits) == 2
    await workers[2].step()
    assert len(bridge.submits) == 2 and not workers[2].load().get('session_id')
    bridge.value = {'status': 'terminal', 'outcome': 'completed', 'result': {'final_response': 'First finished'}}
    await workers[0].step()
    bridge.value = {'status': 'started'}
    await workers[2].step()
    assert len(bridge.submits) == 3


@pytest.mark.asyncio
async def test_fifo_claim_prevents_newer_goal_bypassing_older_waiter(tmp_path):
    bridge = Bridge()
    client = DurableHermes(tmp_path, bridge=bridge, supervisor=Supervisor())
    older, newer = client.start('Older'), client.start('Newer')
    new_worker = GoalWorker(tmp_path, newer['id'], bridge=bridge)
    assert not await new_worker.step()
    assert not bridge.submits
    await GoalWorker(tmp_path, older['id'], bridge=bridge).step()
    await new_worker.step()
    assert len(bridge.submits) == 2


@pytest.mark.asyncio
async def test_recover_unknown_receipt_reads_without_resubmitting(tmp_path):
    bridge = Bridge()
    client = DurableHermes(tmp_path, bridge=bridge, supervisor=Supervisor())
    item = client.start('Recover existing result')
    worker = GoalWorker(tmp_path, item['id'], bridge=bridge)
    await worker.step()
    worker.update(state='interrupted', execution='unknown')
    bridge.value = {'status': 'terminal', 'outcome': 'completed', 'result': {'final_response': 'Recovered output'}}
    await client.refresh(item['id'])
    result = client.status(item['id'])
    assert result['state'] == 'completed' and result['output'] == 'Recovered output'
    assert result['verified'] is False and len(bridge.submits) == 1


@pytest.mark.asyncio
async def test_api_anything_hermes_dispatch_stays_private(api):
    from skills.domains.api_anything import ApiAnythingDomain
    domain = ApiAnythingDomain()
    domain._adapter_hermes_api = AsyncMock(return_value={'ok': True})
    assert await domain._adapter_api_anything_call('hermes', 'cron.create', {'name': 'Brief', 'request_key': 'stable'}) == {'ok': True}
    domain._adapter_hermes_api.assert_awaited_once_with('cron.create', {'name': 'Brief'}, 'stable')


@pytest.mark.asyncio
async def test_native_command_directive_is_executed_as_durable_goal():
    from skills.domains.orchestration import OrchestrationDomain
    domain = OrchestrationDomain()
    domain._personal_agents = lambda: SimpleNamespace(bridge=SimpleNamespace(command=AsyncMock(return_value={'requires_agent': True})))
    domain._adapter_start_hermes_goal = AsyncMock(return_value={'state': 'queued'})
    result = await domain._adapter_hermes_command('skills', 'search documentation')
    assert result['state'] == 'queued'
    assert '/skills search documentation' in domain._adapter_start_hermes_goal.call_args.args[0]


@pytest.mark.asyncio
async def test_quarantined_old_goal_does_not_block_unrelated_new_work(tmp_path):
    bridge = Bridge()
    client = DurableHermes(tmp_path, bridge=bridge, supervisor=Supervisor())
    for name in ['Uncertain old task one', 'Uncertain old task two']:
        item = client.start(name)
        worker = GoalWorker(tmp_path, item['id'], bridge=bridge)
        worker.update(state='interrupted', execution='unknown', session_id='old-session', slot_reserved=True)
    item = client.start('Independent new work')
    await GoalWorker(tmp_path, item['id'], bridge=bridge).step()
    assert len(bridge.submits) == 1
    assert all(j['state']=='interrupted' for j in client.jobs.values() if j['id']!=item['id'])


def test_imported_workspace_requires_original_matching_receipt(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'user'))
    client = DurableHermes(tmp_path / 'stable', bridge=Bridge(), supervisor=Supervisor())
    item = client.start('Imported task')
    legacy = tmp_path / 'user/.local/share/jarvis-runtime/releases/old/.jarvis-learning/task-agents'
    workspace = legacy / 'workspaces' / item['id'] / 'worktree'
    workspace.mkdir(parents=True)
    (workspace / 'result.txt').write_text('Preserved result')
    import json
    original = {'workspace': str(workspace), 'session_id': 'owned-legacy'}
    (legacy / (item['id'] + '.json')).write_text(json.dumps(original))
    with client.transaction():
        job = client._get(item['id'])
        job.update(workspace=str(workspace), session_id='owned-legacy', _legacy_storage_root=str(legacy))
        client._save(job)
    assert 'Preserved result' in str(client.artifact_read(item['id'], 'result.txt'))
    original['session_id'] = 'someone-else'
    (legacy / (item['id'] + '.json')).write_text(json.dumps(original))
    with pytest.raises(ValueError, match='outside owned'):
        client.artifact_read(item['id'], 'result.txt')


@pytest.mark.asyncio
async def test_failed_delegate_cannot_be_reported_as_successful_parent(tmp_path, monkeypatch):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    item=client.start('Run both required workers');worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    await worker.step()
    worker.update(consumed_children=['failed-worker'])
    monkeypatch.setattr(worker,'children',lambda job:[{'id':'failed-worker','state':'failed','execution':'response_received'}])
    bridge.value={'status':'terminal','outcome':'completed','result':{'final_response':'One worker failed.'}}
    assert await worker.step()
    assert worker.load()['state']=='failed'


@pytest.mark.asyncio
async def test_inspected_failed_assignment_can_be_resolved_by_successful_replacement(tmp_path, monkeypatch):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    item=client.start('Run required assignment');worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    await worker.step()
    worker.update(consumed_children=['failed','replacement'])
    monkeypatch.setattr(worker,'children',lambda job:[
        {'id':'failed','state':'failed','execution':'response_received','assignment_hash':'same-assignment'},
        {'id':'replacement','state':'completed','execution':'response_received','assignment_hash':'same-assignment'}])
    bridge.value={'status':'terminal','outcome':'completed','result':{'final_response':'Replacement succeeded.'}}
    assert await worker.step()
    assert worker.load()['state']=='completed'
