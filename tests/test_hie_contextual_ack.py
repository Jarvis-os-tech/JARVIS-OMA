from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from voice_layer.acknowledgements import PHRASES
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


def voice():
    instance = LiveVoice(Playback('test'))
    instance._reply_authorized = True
    return instance


def test_deferred_ack_keeps_arguments_for_getter_and_setter():
    instance = voice()
    instance.gate.active = True
    setter = {'action': 'volume_set', 'value': 20}
    assert not instance._acknowledge_task_start('system_control', setter)
    setter['action'] = 'volume_get'
    assert instance._pending_task_ack == (instance._reply_serial, 'system_control',
                                           {'action': 'volume_set', 'value': 20})

    instance.gate.active = False
    instance._filler_played = False
    instance._reply_notices = {'ack_volume': b'\x01\x00' * 480,
                               'ack_general_2': b'\x02\x00' * 480}
    assert instance._play_filler_reflex('system_control', instance._pending_task_ack[2], admitted=True)
    assert instance.last_acknowledgement == PHRASES['ack_volume']
    instance._filler_played = False
    assert instance._play_filler_reflex('system_control', {'action': 'volume_get'}, admitted=True)
    assert instance.last_acknowledgement == PHRASES['ack_general_2']


def test_missing_contextual_clip_uses_safe_cached_fallback():
    instance = voice()
    fallback = b'\x03\x00' * 480
    instance._reply_notices = {'filler_sure': fallback}
    assert instance._acknowledge_task_start('web_search')
    assert instance.player.queue.get_nowait()[1] == fallback


@pytest.mark.asyncio
async def test_rejected_tool_does_not_play_acknowledgement():
    instance = voice()
    instance._user_text = 'Open the browser'
    session = NS(send_tool_response=AsyncMock())
    call = NS(function_calls=[NS(id='reject', name='phone_control', args={'action': 'status'})])
    await instance.handle_tools(call, session)
    response = session.send_tool_response.call_args.kwargs['function_responses'][0].response
    assert response['status'] == 'conversational_intent_required'
    assert instance.player.queue.empty()


def test_deferred_ack_does_not_keep_arguments_after_reset():
    instance = voice()
    instance.gate.active = True
    instance._acknowledge_task_start('system_control', {'action': 'volume_set', 'value': 20})
    instance._start_reply_watch()
    assert instance._pending_task_ack is None


@pytest.mark.parametrize('action', ['volume_set_typo', 'volume_get_typo', 'workspace_set', 'brightness_unknown'])
def test_invalid_control_action_does_not_claim_a_change(action):
    instance = voice()
    assert instance._acknowledge_task_start('system_control', {'action': action})
    assert instance.last_acknowledgement == PHRASES['ack_general_2']
