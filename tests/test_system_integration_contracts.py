"""Operational failures must survive voice, adapter and durable-cache boundaries."""
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from jarvis_control.device_execution import SharedToolExecutor
from jarvis_control.outcomes import classify_result
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback
from jarvis_control.execution_policy import tool_timeout
from jarvis_control.nlu import NLUEngine
import asyncio


@pytest.mark.parametrize('receipt', [
    'started', 'queued', 'None', 'null', 'false',
    {'status': 'written', 'ground_truth_verified': False},
    {'status': 'success', 'post_action_verified': False},
    {'status': 'success', 'post_action_focus_verified': False},
    {'successful': False},
    {'success': True, 'data': {'successful': False, 'error': 'API rejected the action'}},
    {'structuredContent': {'verified': False}},
    {'status': 'stopped'},
    {'status': 'TIMED_OUT'},
    {'status': 'WAITING_APPROVAL'},
])
def test_failure_dialects_cannot_be_promoted_to_completion(receipt):
    assert not classify_result(receipt).completed
    assert not classify_result(json.dumps(receipt)).completed


@pytest.mark.asyncio
async def test_verified_workflow_continues_past_five_tool_calls():
    execute = AsyncMock(return_value={'status': 'success', 'verified': True})
    skills = NS(declarations=[{'name': 'system_query'}], execute=execute)
    voice = LiveVoice(Playback('test'), skills=skills)
    voice._reply_authorized = True
    session = NS(send_tool_response=AsyncMock())
    calls = [NS(id=f'step-{i}', name='system_query', args={'topic': str(i)}) for i in range(9)]
    await voice.handle_tools(NS(function_calls=calls), session)
    assert execute.await_count == 9
    responses = session.send_tool_response.call_args.kwargs['function_responses']
    assert all(response.response['completed'] for response in responses)
    assert all(response.response['completion_scope'] == 'tool_call' for response in responses)


@pytest.mark.asyncio
async def test_runaway_limit_reports_unfinished_work_without_executing_more(monkeypatch):
    monkeypatch.setattr('voice_layer.daemon.MAX_TOOL_CALLS_PER_TURN', 2)
    execute = AsyncMock(return_value={'status': 'success', 'verified': True})
    voice = LiveVoice(Playback('test'), skills=NS(declarations=[{'name': 'system_query'}], execute=execute))
    voice._reply_authorized = True
    session = NS(send_tool_response=AsyncMock())
    await voice.handle_tools(NS(function_calls=[NS(id=str(i), name='system_query', args={}) for i in range(3)]), session)
    assert execute.await_count == 2
    result = session.send_tool_response.call_args.kwargs['function_responses'][-1].response
    assert result['status'] == 'stopped' and result['completed'] is False
    assert 'unfinished' in result['error']


@pytest.mark.asyncio
async def test_old_success_cache_is_reclassified_without_replaying_action(tmp_path):
    skills = NS(declarations=[{'name': 'action'}], execute=AsyncMock(return_value='ok'))
    executor = SharedToolExecutor(skills, tmp_path/'ledger.sqlite')
    request = {'request_id': 'old-action', 'name': 'action', 'args': {}}
    try:
        await executor.call(request)
        old = {'status': 'completed', 'output': json.dumps({'successful': False}), 'completed': True}
        executor.db.execute('UPDATE calls SET result=? WHERE id=?', (json.dumps(old), request['request_id']))
        executor.db.commit()
        result = await executor.call(request)
        assert result['completed'] is False and result['status'] == 'failed'
        skills.execute.assert_awaited_once()
    finally:
        executor.close()


def test_domain_routed_slow_tools_have_the_same_deadline_as_direct_calls():
    for name in ('read_screen', 'gui_browser_navigate', 'execute_platform_action'):
        assert tool_timeout('execute_domain_tool', {'tool_name': name}) == tool_timeout(name) == 90


@pytest.mark.parametrize('name', ['phone_control', 'phone_call', 'phone_list_contacts'])
def test_all_phone_adapters_require_a_current_phone_target(name):
    assert not NLUEngine.validate_tool_intent(name, {}, 'Open WhatsApp on my PC')[0]
    assert NLUEngine.validate_tool_intent(name, {}, 'Open WhatsApp on my phone')[0]


@pytest.mark.asyncio
async def test_timed_out_shared_execution_returns_pending_and_keeps_admission_slot(tmp_path, monkeypatch):
    monkeypatch.setattr('jarvis_control.device_execution.tool_timeout', lambda *_: .01)
    started, release = asyncio.Event(), asyncio.Event()

    async def blocked(*_):
        started.set()
        await release.wait()
        return 'finished'

    execute = AsyncMock(side_effect=blocked)
    router = SharedToolExecutor(NS(declarations=[{'name':'action'}], execute=execute), tmp_path/'ledger')
    request = {'request_id':'hung','name':'action','args':{}}
    try:
        result = await asyncio.wait_for(router.call(request), .2)
        await started.wait()
        assert result['status'] == 'running' and result['completed'] is False
        assert (await router.call(request))['status'] == 'running'
        assert (await router.call({'request_id':'later','name':'action','args':{}}))['not_started'] is True
        release.set()
        await asyncio.wait_for(router.active[2], .2)
        assert (await router.call(request))['output'] == 'finished'
        assert (await router.call(request))['completed'] is True
        execute.assert_awaited_once()
    finally:
        release.set()
        router.close()
