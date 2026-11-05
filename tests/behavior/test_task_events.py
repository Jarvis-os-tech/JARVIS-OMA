"""Provider/consumer contracts, actual task integration, replay and ordering."""
import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from jsonschema import ValidationError

from orchestration.task_events import CONTRACT, TaskEventStore, validate_event
from orchestration.task_presentation import TaskPresentation, project
from scripts.generate_task_event_contract import ROOT, generated


def candidate(state='running', generation=1, source='file_task', identity='one'):
    return dict(task_id=source + ':' + identity, source=source, generation=generation,
                state=state, terminal=state in CONTRACT['x-terminal-states'],
                title='Example task', message='Observed state',
                evidence={'verified': state == 'completed', 'scope': 'file_step_checks' if state == 'completed' else 'none'},
                progress=None)


def test_journal_rejects_stale_revisions_and_terminal_regression(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    running = store.publish(candidate(), source_revision=2)
    assert running['revision'] == 1
    assert store.publish(candidate(), source_revision=2) is None
    assert store.publish(candidate('queued'), source_revision=1) is None
    completed = store.publish(candidate('completed'), source_revision=3)
    assert completed['sequence'] > running['sequence']
    assert store.publish(candidate(), source_revision=4) is None
    new_attempt = store.publish(candidate(generation=2), source_revision=1)
    assert new_attempt['revision'] == 3 and new_attempt['generation'] == 2
    assert store.publish(candidate('completed'), source_revision=99) is None
    assert store.lookup('file_task:one') == new_attempt


def test_progress_cannot_regress_or_exceed_measured_total(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    event = candidate()
    event['progress'] = {'completed': 2, 'total': 3}
    store.publish(event)
    event['progress']['completed'] = 1
    assert store.publish(event) is None
    event['progress']['completed'] = 4
    with pytest.raises(ValueError):
        store.publish(event)


def test_unchanged_snapshot_still_advances_producer_fence(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    store.publish(candidate(), source_revision=2)
    assert store.publish(candidate(), source_revision=5) is None
    stale = candidate()
    stale['message'] = 'Delayed update'
    assert store.publish(stale, source_revision=4) is None


def test_capacity_never_discards_unacknowledged_terminal_outcomes(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    for index in range(128):
        store.publish(candidate('completed', identity=str(index)))
    with pytest.raises(ValueError, match='capacity'):
        store.publish(candidate(identity='new'))
    first = store.snapshots()[0]
    store.acknowledge(first['sequence'])
    assert store.publish(candidate(identity='new'))['state'] == 'running'
    assert len(store.snapshots()) == 128


def test_restart_replay_and_stale_acknowledgement(tmp_path):
    path = tmp_path / 'events.sqlite'
    first = TaskEventStore(path)
    old = first.publish(candidate('completed'))
    second = TaskEventStore(path)
    assert second.stream_id == first.stream_id
    assert second.replay()['events'] == [old]
    second.publish(candidate(generation=2))
    latest = second.publish(candidate('completed', generation=2))
    second.acknowledge(old['sequence'])
    assert second.notices({'file_task'}) == [latest]
    second.acknowledge(latest['sequence'])
    assert second.notices({'file_task'}) == []
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_bounded_history_resyncs_from_snapshot(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    for n in range(270):
        payload = candidate()
        payload['message'] = str(n)
        store.publish(payload)
    replay = store.replay(0)
    assert replay['resync'] and len(replay['events']) == 1
    assert replay['events'][0]['message'] == '269'
    assert len(store.replay(14)['events']) == 256


def test_sources_with_same_local_id_have_distinct_cards(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    a = store.publish(candidate(source='file_task'))
    b = store.publish(candidate(source='model'))
    assert a['widget_id'] != b['widget_id'] and a['task_id'] != b['task_id']


@pytest.mark.parametrize('source,job,state,verified,scope', [
    ('model', {'status':'completed', 'result':'Everything is done.'}, 'response_received', False, 'response_only'),
    ('agent', {'state':'completed', 'exit_code':0}, 'response_received', False, 'response_only'),
    ('hermes', {'state':'completed', 'verified':False}, 'response_received', False, 'response_only'),
    ('hermes', {'state':'completed', 'verified':True}, 'completed', True, 'workspace_checks'),
    ('hermes', {'state':'cancelled', 'execution':'unknown'}, 'interrupted', False, 'execution_unknown'),
    ('file_task', {'status':'running', 'cancel_requested':True}, 'cancelling', False, 'none'),
    ('file_task', {'status':'completed', 'completed_steps':1, 'total_steps':1, 'steps':[{'status':'completed'}]}, 'completed', True, 'file_step_checks'),
])
def test_projection_never_confuses_returned_text_or_cancellation_with_verified_effects(source, job, state, verified, scope):
    event = project(source, {'id':'one', **job})
    assert event['state'] == state
    assert event['evidence'] == {'verified':verified, 'scope':scope}
    if source != 'file_task':
        assert event['progress'] is None


@pytest.mark.asyncio
async def test_delivery_failure_preserves_notice_and_retries(tmp_path):
    desktop = NS(_model_jobs=NS(jobs={'one':{'id':'one','status':'completed','result':'Example result'}}))
    deliveries = []
    def send(method, payload):
        deliveries.append(copy.deepcopy(payload))
        if len(deliveries) == 1:
            raise subprocess.TimeoutExpired('synthetic shell', 4)
        return {'ok':True}
    presenter = TaskPresentation(desktop, tmp_path / 'events.sqlite', send)
    await presenter.refresh()
    assert presenter.last_delivery_error == 'TimeoutExpired'
    notice = presenter.notices()[0]
    assert 'Example result' in notice['text']
    await presenter.refresh()
    assert deliveries[0] == deliveries[1] and not presenter.last_delivery_error
    presenter.acknowledge(notice['id'])
    assert presenter.notices() == []


@pytest.mark.asyncio
async def test_lost_in_memory_job_becomes_needs_review_after_restart(tmp_path):
    path = tmp_path / 'events.sqlite'
    first = TaskPresentation(NS(_model_jobs=NS(jobs={'one':{'id':'one','status':'running'}})), path, lambda *a: None)
    await first.refresh()
    first.close()
    second = TaskPresentation(NS(), path, lambda *a: None)
    await second.refresh()
    event = second.store.snapshots()[0]
    assert event['state'] == 'interrupted' and event['evidence']['scope'] == 'execution_unknown'
    second.close()


def test_only_one_presenter_can_reconcile_a_profile(tmp_path):
    path = tmp_path / 'events.sqlite'
    first = TaskPresentation(NS(), path, lambda *a: None)
    try:
        with pytest.raises(ValueError, match='Another task presenter'):
            TaskPresentation(NS(), path, lambda *a: None)
    finally:
        first.close()
    second = TaskPresentation(NS(), path, lambda *a: None)
    second.close()


@pytest.mark.asyncio
async def test_real_file_task_status_card_and_notice_share_the_same_event(tmp_path, monkeypatch):
    from skills.skills import DesktopSkills
    from jarvis_control.skills import UnifiedSkills
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    desktop = DesktopSkills()
    deliveries = []
    presenter = TaskPresentation(desktop, tmp_path / 'events.sqlite', lambda method, payload: deliveries.append(payload))
    desktop._task_presentation = presenter
    desktop._task_agents = NS(jobs={}, close=AsyncMock())
    unified = UnifiedSkills(desktop_skills=desktop)
    try:
        path = tmp_path / 'example.txt'
        result = await desktop.execute('start_task', {'description':'Save example notes', 'plan_json':json.dumps([
            {'tool':'write_file', 'args':{'path':str(path), 'content':'Example notes'}}])})
        identity = result['id']
        assert result['task_event']['task_id'] == 'file_task:' + identity
        worker = desktop._task_runner._workers.get(identity)
        if worker:
            await worker
        status = await desktop.execute('task_status', {'task_id':identity})
        notices = await unified.background_events()
        assert path.read_text() == 'Example notes'
        event = notices[0]['task_event']
        assert status['task_event'] == event == deliveries[-1]['events'][0]
        assert event['state'] == 'completed' and event['evidence']['scope'] == 'file_step_checks'
        assert desktop.task_events.qsize() == 1  # Existing terminal queue was not consumed.
        await unified.acknowledge_event(notices[0]['id'])
        assert await unified.background_events() == []
    finally:
        await desktop.close_agent_jobs()


@pytest.mark.asyncio
async def test_cancellation_card_waits_for_operation_and_retains_partial_effects(tmp_path):
    from filesystem.task_runner import TaskRunner
    entered, release = asyncio.Event(), asyncio.Event()
    async def execute(tool, args):
        entered.set()
        await release.wait()
        Path(args['path']).write_text('A completed step')
        return {'status':'written', 'verified':True}
    runner = TaskRunner(execute, lambda *a: True)
    presenter = TaskPresentation(NS(_task_runner=runner), tmp_path / 'events.sqlite', lambda *a: None)
    try:
        job = runner.start('Two steps', json.dumps([
            {'tool':'write_file','args':{'path':str(tmp_path / 'first.txt'),'content':'one'}},
            {'tool':'write_file','args':{'path':str(tmp_path / 'second.txt'),'content':'two'}}]))
        worker = runner._workers[job['id']]
        await entered.wait()
        requested = runner.cancel(job['id'])
        event = presenter.observe('file_task', requested)
        assert event['state'] == 'cancelling' and not event['terminal']
        release.set()
        await worker
        await presenter.refresh()
        event = presenter.store.lookup('file_task:' + job['id'])
        assert event['state'] == 'cancelled' and event['terminal']
        assert event['progress'] == {'completed':1, 'total':2}
        assert (tmp_path / 'first.txt').exists() and not (tmp_path / 'second.txt').exists()
    finally:
        release.set()
        await runner.close()
        presenter.close()


@pytest.mark.asyncio
async def test_presentation_failure_cannot_turn_admission_into_a_retryable_failure():
    from skills.skills import DesktopSkills
    registry = DesktopSkills.__new__(DesktopSkills)
    def unavailable():
        raise ValueError('Synthetic presentation capacity limit')
    registry._task_presenter = unavailable
    result = await registry._task_event_response('file_task', {'id':'one','status':'queued'})
    assert result['status'] == 'queued' and result['presentation_status'] == 'unavailable'


def test_generated_consumer_schema_is_current():
    assert (ROOT / 'ui/jarvis_widgets/TaskEventContract.js').read_text() == generated()


def test_generic_widgets_cannot_forge_task_cards():
    from ui.jarvis_widgets.backend import make_widget
    with pytest.raises(ValueError, match='reserved'):
        make_widget('text', 'Fake completion', {'text':'Done'}, widget_id='jtask_' + 'a' * 24)


def test_javascript_consumer_rejects_stale_events_and_unverified_success(tmp_path):
    store = TaskEventStore(tmp_path / 'events.sqlite')
    active = store.publish(candidate())
    active['title'] = '🙂' * 160
    validate_event(active)
    final = store.publish(candidate('completed'))
    invalid = copy.deepcopy(final)
    invalid['evidence']['verified'] = False
    with pytest.raises(ValueError):
        validate_event(invalid)
    missing = copy.deepcopy(final)
    missing.pop('revision')
    with pytest.raises(ValidationError):
        validate_event(missing)
    script = r'''
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {Contract:{contract:input.schema}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(input.reducer,'utf8').split('\n').filter(s=>!s.startsWith('.')).join('\n'),context);
function check(value, message) { if (!value) throw Error(message); }
function batch(event) { return {schema_version:1,stream_id:event.stream_id,cursor:event.sequence,events:[event]}; }
let result=context.apply([],context.initial(),batch(input.active),0);
result=context.apply(result.items,result.state,batch(input.final),100);
const snapshot=JSON.stringify(result);
const stale=context.apply(result.items,result.state,batch(input.active),200);
check(JSON.stringify(stale.items)===JSON.stringify(result.items),'stale event replaced completion');
check(context.apply(result.items,result.state,batch(input.final),300).accepted===0,'duplicate replay changed card');
let state=context.hide(result.state,input.final.widget_id);
check(context.apply([],state,batch(input.final),400).items.length===0,'dismissed card resurrected');
for (const bad of [input.invalid,input.missing]) {
 let rejected=false; try { context.validate(bad); } catch(e) { rejected=true; }
 check(rejected,'invalid event accepted by consumer');
}
check(result.items[0].data.label==='Completed','wrong task label');
check(result.items[0].expiresAt===120100,'terminal lifetime was not fixed');
process.stdout.write('passed');
'''
    payload = dict(schema=CONTRACT, active=active, final=final, invalid=invalid, missing=missing,
                   reducer=str(ROOT / 'ui/jarvis_widgets/TaskEvents.js'))
    result = subprocess.run(['node','-e',script], input=json.dumps(payload), text=True,
                            capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'passed'
