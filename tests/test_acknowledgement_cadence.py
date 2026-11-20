import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from voice_layer.daemon import LiveVoice, build_instruction
from voice_layer.playback import Playback


def voice():
    instance = LiveVoice(Playback('test'))
    instance.connected = instance._reply_authorized = True
    instance._reply_notices = {name: bytes([index, 0]) * 480 for index, name in enumerate(
        ('filler_hmm', 'filler_ah', 'filler_sure', 'filler_on_it', 'reply_waiting'), 1)}
    return instance


async def tick(instance, monkeypatch, now):
    cycles = 0
    async def cycle(_):
        nonlocal cycles
        cycles += 1
        if cycles > 1:
            raise asyncio.CancelledError
    monkeypatch.setattr('voice_layer.daemon.time.monotonic', lambda: now)
    monkeypatch.setattr('voice_layer.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()


@pytest.mark.asyncio
@pytest.mark.parametrize('delay', [.1, .2, .34, .36, .8, 3])
async def test_wait_acknowledgement_has_no_speculative_speech(monkeypatch, delay):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    await tick(instance, monkeypatch, 10+delay)
    assert instance.player.queue.empty()


@pytest.mark.parametrize('context', ['generic_deep_thought', 'filesystem_grep', 'system_mutation', 'sub_agent_spawn'])
def test_acknowledgement_plays_only_once(context):
    instance = voice()
    assert instance._play_filler_reflex(context)
    assert not instance._play_filler_reflex(context)
    assert instance.player.queue.qsize() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('tool', ['web_search', 'browser_task', 'start_task_agent', 'search_files'])
async def test_running_tool_does_not_inject_speculative_speech(monkeypatch, tool):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    instance._tools_in_flight = 1
    instance._active_tool = tool
    await tick(instance, monkeypatch, 10.8)
    assert instance.player.queue.empty()


@pytest.mark.asyncio
async def test_long_silence_never_injects_another_conversation_turn(monkeypatch):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    instance._request_contextual_update = AsyncMock(return_value=True)
    await tick(instance, monkeypatch, 16)
    await tick(instance, monkeypatch, 17)
    instance._request_contextual_update.assert_not_awaited()
    assert instance.player.queue.empty()


@pytest.mark.asyncio
async def test_legacy_progress_hook_does_not_send_synthetic_user_messages():
    instance = voice()
    instance._user_text = 'Compare the two local projects'
    instance._session = NS(send_client_content=AsyncMock())
    assert not await instance._request_contextual_update()
    instance._session.send_client_content.assert_not_awaited()
    assert instance.player.queue.empty()


@pytest.mark.asyncio
@pytest.mark.parametrize('condition', ['muted', 'speaking', 'standby', 'already_answered', 'offline'])
async def test_contextual_update_respects_privacy_and_turn_state(condition):
    instance = voice()
    instance._session = NS(send_client_content=AsyncMock())
    if condition == 'muted': instance.muted = True
    elif condition == 'speaking': instance.gate.active = True
    elif condition == 'standby': instance.standby._requested.set()
    elif condition == 'already_answered': instance._reply_started = True
    elif condition == 'offline': instance.connected = False
    assert not await instance._request_contextual_update()
    instance._session.send_client_content.assert_not_awaited()


def test_instruction_requires_natural_updates_without_phrase_list():
    instruction = build_instruction([{'function_declarations': [{'name': 'play_local_filler'}]}])
    assert 'Fast answers should go straight to the answer' in instruction
    assert 'Do not call play_local_filler' in instruction
    assert 'not a fixed phrase list' in instruction or 'not use canned examples as a phrase list' in instruction
    assert "context_type='generic_deep_thought' ('Sure')" not in instruction


@pytest.mark.asyncio
async def test_progress_update_does_not_interrupt_an_outstanding_tool_call():
    instance = voice()
    instance._session = NS(send_client_content=AsyncMock())
    instance._tools_in_flight = 1
    assert not await instance._request_contextual_update()
    instance._session.send_client_content.assert_not_awaited()
