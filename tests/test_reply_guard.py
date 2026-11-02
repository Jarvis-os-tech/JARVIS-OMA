"""Bounded feedback and speech-only recovery for missing provider audio."""
import asyncio
from pathlib import Path
import struct
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from jarvis_voice.daemon import LiveVoice, connect_session
from jarvis_voice.playback import Playback


def voice():
    instance = LiveVoice(Playback('test'))
    instance.connected = True
    instance._reply_authorized = instance._waiting = True
    instance._reply_notices = {'reply_waiting': bytes(960), 'reply_unavailable': bytes(1920)}
    return instance


def completed():
    return NS(server_content=NS(turn_complete=True))


def test_bundled_feedback_contains_bounded_non_silent_pcm():
    assets = Path(__file__).resolve().parents[1] / 'jarvis_voice/assets'
    for name in ('reply_waiting.pcm', 'reply_unavailable.pcm', 'filler_hmm.pcm',
                 'filler_ah.pcm', 'filler_sure.pcm', 'filler_on_it.pcm'):
        pcm = (assets / name).read_bytes()
        assert 12000 <= len(pcm) <= 480000
        assert len(pcm) % 2 == 0
        assert max(abs(sample[0]) for sample in struct.iter_unpack('<h', pcm)) > 1000


@pytest.mark.asyncio
async def test_empty_answer_requests_speech_once_then_gives_local_failure():
    instance = voice()
    session = NS(send_client_content=AsyncMock())
    await instance.handle(completed(), session)
    assert instance._reply_authorized
    assert instance._reply_recovery_active
    session.send_client_content.assert_awaited_once()
    await instance.handle(completed(), session)
    session.send_client_content.assert_awaited_once()
    assert not instance._reply_authorized
    assert instance.player.queued_bytes == 1920
    assert instance.last_error == 'No spoken answer was received.'


@pytest.mark.asyncio
async def test_recovered_audio_plays_and_recovery_cannot_repeat_an_action():
    instance = voice()
    execute = AsyncMock()
    instance.skills = NS(declarations=[{'name': 'system_control'}], execute=execute)
    session = NS(send_client_content=AsyncMock(), send_tool_response=AsyncMock())
    await instance.handle(completed(), session)
    await instance.handle_tools(NS(function_calls=[
        NS(id='recovery-action', name='system_control', args={})]), session)
    execute.assert_not_awaited()
    assert not session.send_tool_response.call_args.kwargs['function_responses'][0].response['ok']
    await instance.handle(NS(server_content=NS(model_turn=NS(parts=[
        NS(inline_data=NS(data=bytes(960)))]))), session)
    await instance.handle(completed(), session)
    assert instance.player.queued_bytes == 960
    assert not instance._reply_authorized
    assert instance.last_error == ''


@pytest.mark.asyncio
async def test_recovery_send_failure_still_produces_local_reply():
    instance = voice()
    await instance.handle(completed(), NS(send_client_content=AsyncMock(side_effect=OSError)))
    assert instance.player.queued_bytes == 1920
    assert not instance._reply_authorized


@pytest.mark.asyncio
async def test_spoken_preamble_does_not_hide_missing_task_result():
    instance = voice()
    instance._reply_started = True  # e.g. "I'll check that."
    instance.skills = NS(declarations=[{'name': 'test_action'}],
                         execute=AsyncMock(return_value={'ok': True}))
    session = NS(send_tool_response=AsyncMock(), send_client_content=AsyncMock())
    await instance.handle_tools(NS(function_calls=[
        NS(id='task', name='test_action', args={})]), session)
    await instance.handle(completed(), session)  # Intermediate tool boundary
    await instance.handle(completed(), session)  # No spoken result followed
    session.send_client_content.assert_awaited_once()
    instance.skills.execute.assert_awaited_once()
    assert instance._reply_authorized


@pytest.mark.asyncio
async def test_new_speech_wins_over_an_old_recovery_waiting_for_send_lock():
    instance = voice()
    session = NS(send_client_content=AsyncMock())
    await instance.send_lock.acquire()
    worker = asyncio.create_task(instance.handle(completed(), session))
    await asyncio.sleep(0)
    instance._start_reply_watch()
    instance.gate.active = True
    instance.send_lock.release()
    await worker
    session.send_client_content.assert_not_awaited()
    assert instance._reply_authorized
    assert not instance._reply_recovery_active
    assert instance.player.queued_bytes == 0


@pytest.mark.asyncio
async def test_wait_feedback_is_once_per_turn_and_does_not_reset_watchdog(monkeypatch):
    instance = voice()
    instance._last_progress = 10
    cycles = 0

    async def cycle(_):
        nonlocal cycles
        cycles += 1
        if cycles > 3:
            raise asyncio.CancelledError

    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 26)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()
    assert instance.player.queued_bytes == 960
    assert instance._last_progress == 10
    assert instance.response_delayed
    assert not instance._reply_started


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', ['muted', 'speech', 'standby'])
async def test_feedback_and_recovery_respect_private_or_active_input(blocked):
    instance = voice()
    if blocked == 'muted':
        instance.muted = True
    elif blocked == 'speech':
        instance.gate.active = True
    else:
        instance.standby._requested.set()
    session = NS(send_client_content=AsyncMock())
    assert not instance._play_reply_notice('reply_waiting')
    assert not await instance._recover_empty_reply(session)
    await instance.announce_reply_failure()
    session.send_client_content.assert_not_awaited()
    assert instance.player.queued_bytes == 0


@pytest.mark.asyncio
async def test_offline_failure_uses_local_player_without_cloud():
    instance = voice()
    instance.connected = False

    async def playback():
        while True:
            _, data = await instance.player.queue.get()
            instance.player.queued_bytes -= len(data)

    instance.player.run = playback
    await asyncio.wait_for(instance.announce_reply_failure(), 1)
    assert instance.player.queued_bytes == 0
    assert instance.player.queue.empty()


@pytest.mark.asyncio
async def test_connection_timeout_only_bounds_setup(monkeypatch):
    monkeypatch.setattr('jarvis_voice.daemon.CONNECT_TIMEOUT_SECONDS', .01)

    class Connection:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            pass

    client = NS(live=NS(connect=lambda **_: Connection()))
    async with connect_session(client):
        await asyncio.sleep(.02)

    class Stalled(Connection):
        async def __aenter__(self):
            await asyncio.Event().wait()

    client.live.connect = lambda **_: Stalled()
    with pytest.raises(TimeoutError):
        async with connect_session(client):
            pytest.fail('Stalled setup must not connect')
