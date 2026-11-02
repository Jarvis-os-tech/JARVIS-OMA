import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback
from jarvis_voice.speech import GateFrame


def voice():
    instance = LiveVoice(Playback('test'))
    instance.connected = instance._reply_authorized = True
    instance._start_reply_watch()
    instance._reply_notices = {name: bytes([index, 0]) * 480 for index, name in enumerate(
        ('filler_hmm', 'filler_ah', 'filler_sure', 'filler_on_it'), 1)}
    return instance


@pytest.mark.asyncio
@pytest.mark.parametrize('name,clip', [
    ('web_search', 'filler_on_it'), ('browser_task', 'filler_on_it'),
    ('start_hermes_goal', 'filler_sure'), ('search_files', 'filler_hmm'),
])
async def test_ack_is_queued_before_work_executes_without_timer(monkeypatch, name, clip):
    instance = voice()
    monkeypatch.setattr('jarvis_control.nlu.NLUEngine.validate_tool_intent', lambda *args: (True, ''))

    async def execute(*args):
        assert instance.player.queue.get_nowait()[1] == instance._reply_notices[clip]
        assert not instance._reply_started
        return {'ok': True}

    instance.skills = NS(declarations=[{'name': name}], execute=AsyncMock(side_effect=execute))
    session = NS(send_tool_response=AsyncMock())
    # No timer is armed: task admission alone must trigger the acknowledgement.
    assert instance._reply_wait_started_at is None
    call = NS(function_calls=[NS(id='work', name=name, args={})])
    await instance.handle_tools(call, session)
    instance.skills.execute.assert_awaited_once()
    assert instance.local_fillers_played == 1
    await instance.handle_tools(call, session)
    instance.skills.execute.assert_awaited_once()  # No repeated action or filler.
    assert instance.local_fillers_played == 1


@pytest.mark.asyncio
async def test_rejected_action_does_not_receive_an_on_it_ack(monkeypatch):
    instance = voice()
    instance.skills = NS(declarations=[{'name': 'browser_task'}], execute=AsyncMock())
    monkeypatch.setattr('jarvis_control.nlu.NLUEngine.validate_tool_intent', lambda *args: (False, 'Not requested'))
    await instance.handle_tools(NS(function_calls=[NS(id='blocked', name='browser_task', args={})]),
                                NS(send_tool_response=AsyncMock()))
    assert instance.player.queue.empty()
    instance.skills.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_started_during_user_speech_acks_at_activity_end():
    instance = voice()
    instance.gate.active = True
    instance._tools_in_flight = 1
    assert not instance._acknowledge_task_start('web_search')
    assert instance.player.queue.empty()
    instance.gate.active = False
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(bytes(640), opened=True), 0))
    queue.put_nowait((GateFrame(bytes(640), closed=True), 0))
    worker = asyncio.create_task(instance._send_frames(NS(send_realtime_input=AsyncMock()), queue))
    try:
        async with asyncio.timeout(1):
            while not instance._filler_played:
                await asyncio.sleep(0)
        assert instance.player.queue.get_nowait()[1] == instance._reply_notices['filler_on_it']
        assert instance._pending_task_ack is None
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.parametrize('blocked', ['muted', 'answered', 'standby', 'new_turn', 'finished_task'])
def test_no_immediate_ack_for_ineligible_or_stale_work(blocked):
    instance = voice()
    if blocked == 'muted':
        instance.muted = True
    elif blocked == 'answered':
        instance._reply_started = True
    elif blocked == 'standby':
        instance.standby._requested.set()
    elif blocked == 'new_turn':
        instance.gate.active = True
        instance._acknowledge_task_start('web_search')
        instance._start_reply_watch()
        assert instance._pending_task_ack is None
        return
    else:
        assert not instance._acknowledge_task_start('get_assistant_status')
        return
    assert not instance._acknowledge_task_start('web_search')
    assert instance.player.queue.empty()
