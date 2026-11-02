import asyncio

import pytest

from jarvis_voice.daemon import LiveVoice, build_instruction
from jarvis_voice.playback import Playback


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

    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: now)
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()


@pytest.mark.asyncio
async def test_fast_conversation_does_not_need_filler(monkeypatch):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    await tick(instance, monkeypatch, 10.1)
    assert instance.player.queue.empty()


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,clip', [
    ('web_search', 'filler_on_it'), ('browser_task', 'filler_on_it'),
    ('start_task_agent', 'filler_sure'), ('search_files', 'filler_hmm'),
    ('start_hermes_goal', 'filler_sure'),
])
async def test_running_task_gets_early_contextual_ack(monkeypatch, tool, clip):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    instance._tools_in_flight = 1
    instance._active_tool = tool
    await tick(instance, monkeypatch, 10.8)
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices[clip]


@pytest.mark.asyncio
async def test_tool_progress_cannot_postpone_spoken_update_forever(monkeypatch):
    instance = voice()
    instance._reply_wait_started_at = 10
    instance._last_reply_sound_at = 11
    instance._filler_played = True
    instance._last_progress = 16.5  # A task just reported progress, silently.
    instance._tools_in_flight = 1
    await tick(instance, monkeypatch, 17)
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices['reply_waiting']
    assert instance._last_progress == 16.5


@pytest.mark.asyncio
async def test_recent_speech_keeps_update_from_playing_too_soon(monkeypatch):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    instance._last_reply_sound_at = 15
    instance._filler_played = True
    instance._reply_started = True
    await tick(instance, monkeypatch, 16)
    assert instance.player.queue.empty()


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [True, False])
async def test_missing_or_disabled_filler_cannot_starve_wait_notice(monkeypatch, disabled):
    from types import SimpleNamespace
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    if disabled:
        instance.config = SimpleNamespace(fillers=SimpleNamespace(enable_local_fillers=False))
    else:
        instance._reply_notices = {'reply_waiting': bytes(960)}
    await tick(instance, monkeypatch, 16)
    assert instance._waiting_notice_played
    assert not instance._filler_played
    assert instance.player.queue.qsize() == 1


def test_model_is_not_forced_to_call_filler_before_work():
    instruction = build_instruction([{'function_declarations': [{'name': 'play_local_filler'}]}])
    assert 'very first token output must' not in instruction
    assert 'Fast answers should go straight to the answer' in instruction


def test_spoken_answer_or_preamble_is_already_an_acknowledgement():
    instance = voice()
    instance._reply_started = True
    assert not instance._play_filler_reflex('system_mutation')
    assert instance.player.queue.empty()


# Ensure conversational acknowledgements use affirmative words like 'Sure' rather than vocal hesitations like 'Ah'
@pytest.mark.parametrize('serial', [1, 2])
def test_generic_acknowledgement_never_uses_ah(serial):
    instance = voice()
    instance._reply_serial = serial
    assert instance._play_filler_reflex('generic_deep_thought')
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices['filler_sure']
