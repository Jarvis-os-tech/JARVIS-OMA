import asyncio
from types import SimpleNamespace as NS

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback


async def cycle(instance, monkeypatch, now):
    count = 0

    async def sleep(_):
        nonlocal count
        count += 1
        if count > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', sleep)
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: now)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()


def voice():
    instance = LiveVoice(Playback('test'))
    instance.connected = instance._reply_authorized = True
    instance._reply_notices = {'reply_waiting': bytes(960)}
    instance._last_progress = instance._last_reply_sound_at = 10
    return instance


@pytest.mark.asyncio
@pytest.mark.parametrize('tools', [0, 1])
async def test_answer_started_never_gets_a_still_processing_clip(monkeypatch, tools):
    instance = voice()
    instance._reply_started = True
    instance._tools_in_flight = tools
    await cycle(instance, monkeypatch, 16)
    assert instance.player.queue.empty()
    assert not instance._waiting_notice_played


@pytest.mark.asyncio
async def test_finished_generation_cannot_trigger_stale_wait_or_timeout(monkeypatch):
    instance = voice()
    instance._reply_started = instance._model_active = True
    await instance.handle(NS(server_content=NS(generation_complete=True)))
    assert instance._reply_generation_done
    assert instance.player.reply_complete
    assert not instance._model_active
    await cycle(instance, monkeypatch, 60)
    assert instance.player.queue.empty()
    assert not instance.response_delayed


@pytest.mark.asyncio
@pytest.mark.parametrize('pending', ['tools', 'result', 'no_audio'])
async def test_incomplete_work_is_not_mistaken_for_a_finished_answer(pending):
    instance = voice()
    instance._reply_started = pending != 'no_audio'
    instance._tools_in_flight = int(pending == 'tools')
    instance._tool_answer_pending = pending == 'result'
    await instance.handle(NS(server_content=NS(generation_complete=True)))
    assert not instance._reply_generation_done


@pytest.mark.asyncio
async def test_actual_wait_before_answer_still_gets_feedback(monkeypatch):
    instance = voice()
    await cycle(instance, monkeypatch, 16)
    assert instance._waiting_notice_played
    assert instance.player.queued_bytes == 960


@pytest.mark.asyncio
async def test_completed_explanation_does_not_get_offline_failure_notice():
    instance = voice()
    instance._reply_started = instance._reply_generation_done = True
    await instance.announce_reply_failure()
    assert instance.player.queue.empty()
