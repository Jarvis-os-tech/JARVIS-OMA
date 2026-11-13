from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['web_search', 'browser_task', 'start_hermes_goal', 'search_files'])
async def test_work_is_acknowledged_before_execution(monkeypatch, name):
    instance = LiveVoice(Playback('test'))
    instance.connected = instance._reply_authorized = True
    instance._start_reply_watch()
    instance._reply_notices = {key: bytes(960) for key in ('filler_sure', 'filler_on_it', 'filler_hmm')}
    monkeypatch.setattr('jarvis_control.nlu.NLUEngine.validate_tool_intent', lambda *args: (True, ''))
    async def execute(*args):
        assert not instance.player.queue.empty()
        return {'ok': True}
    instance.skills = NS(declarations=[{'name': name}], execute=AsyncMock(side_effect=execute))
    session = NS(send_tool_response=AsyncMock())
    call = NS(function_calls=[NS(id='work', name=name, args={})])
    await instance.handle_tools(call, session)
    instance.skills.execute.assert_awaited_once()
    assert instance.local_fillers_played == 1
    await instance.handle_tools(call, session)
    instance.skills.execute.assert_awaited_once()


def test_task_started_during_speech_defers_its_acknowledgement():
    instance = LiveVoice(Playback('test'))
    instance.gate.active = True
    assert not instance._acknowledge_task_start('web_search')
    assert instance._pending_task_ack == (instance._reply_serial, 'web_search', {})
    assert instance.player.queue.empty()
