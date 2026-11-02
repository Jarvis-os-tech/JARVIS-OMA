"""Tests for conversational filler reflexes and automatic acknowledgement triggers.

Validates:
- Bundled audio fallback for missing external voice files ('Hmm', 'Ah', 'Sure', 'On it')
- Turn budget reset across sequential turns
- Privacy and preference gating (mute, speech active, standby, disable_local_fillers)
- Automatic 650ms/1.2s local acknowledgement triggering on speech upload or request dispatch
- Suppression during active speech, wake confirmation, greetings, or incoming provider audio
"""
import asyncio
from types import SimpleNamespace as NS

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback


def voice():
    instance = LiveVoice(Playback('test'))
    instance.connected = True
    instance._reply_authorized = True
    instance._reply_notices = {
        'filler_hmm': b'\x01\x00' * 480,
        'filler_ah': b'\x02\x00' * 480,
        'filler_sure': b'\x03\x00' * 480,
        'filler_on_it': b'\x04\x00' * 480,
        'reply_waiting': b'\x05\x00' * 480,
    }
    return instance


@pytest.mark.parametrize('context,clip', [
    ('generic_deep_thought', 'filler_sure'),
    ('system_mutation', 'filler_on_it'),
    ('filesystem_grep', 'filler_hmm'),
    ('sub_agent_spawn', 'filler_sure'),
])
def test_missing_external_recordings_use_bundled_speech(context, clip):
    instance = voice()
    instance._start_reply_watch()
    assert instance._play_filler_reflex(context)
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices[clip]
    assert not instance._reply_started
    assert not instance._play_filler_reflex(context)
    assert instance.player.queue.empty()


def test_new_turn_resets_filler_budget():
    instance = voice()
    for clip in ('filler_sure', 'filler_sure'):
        instance._start_reply_watch()
        assert instance._play_filler_reflex()
        assert instance.player.queue.get_nowait()[1] == instance._reply_notices[clip]


@pytest.mark.parametrize('state', ['muted', 'speech', 'standby', 'disabled'])
def test_fillers_respect_input_privacy_and_preferences(state):
    instance = voice()
    if state == 'muted':
        instance.muted = True
    elif state == 'speech':
        instance.gate.active = True
    elif state == 'standby':
        instance.standby._requested.set()
    else:
        instance.config = NS(fillers=NS(enable_local_fillers=False))
    assert not instance._play_filler_reflex()
    assert instance.player.queue.empty()


@pytest.mark.asyncio
async def test_long_wait_gets_one_clear_status_notice(monkeypatch):
    instance = voice()
    instance._start_reply_watch()
    instance._last_progress = 10
    cycles = 0

    async def cycle(_):
        nonlocal cycles
        cycles += 1
        if cycles > 2:
            raise asyncio.CancelledError

    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 16)
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()
    assert instance.player.queue.qsize() == 1
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices['reply_waiting']
    assert instance._last_progress == 10


@pytest.mark.asyncio
async def test_closed_user_turn_gets_ack_without_waiting_for_cloud_tool(monkeypatch):
    instance = voice()
    instance._start_reply_watch()
    instance._reply_wait_started_at = 10
    instance._last_progress = 10
    cycles = 0

    async def cycle(_):
        nonlocal cycles
        cycles += 1
        if cycles > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 11.3)
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()
    assert instance.player.queue.qsize() == 1
    assert instance.player.queue.get_nowait()[1] == instance._reply_notices['filler_sure']
    assert not instance._reply_started


@pytest.mark.asyncio
@pytest.mark.parametrize('flag', [
    '_reply_started', '_greeting_active', '_background_active', '_barge_pending',
    '_wake_confirmation_pending', '_wake_confirmation_in_flight', 'muted',
])
async def test_early_ack_does_not_compete_with_answers_or_control_turns(monkeypatch, flag):
    instance = voice()
    instance._reply_wait_started_at = instance._last_progress = 10
    setattr(instance, flag, True)
    cycles = 0

    async def cycle(_):
        nonlocal cycles
        cycles += 1
        if cycles > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 11.3)
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await instance.monitor_response()
    assert instance.player.queue.empty()


@pytest.mark.asyncio
async def test_uploaded_speech_boundary_arms_local_ack():
    from jarvis_voice.speech import GateFrame
    instance = voice()
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(bytes(640), opened=True), 0))
    queue.put_nowait((GateFrame(bytes(640), closed=True), 0))
    finished = asyncio.Event()

    async def send(**kwargs):
        if 'activity_end' in kwargs:
            finished.set()

    worker = asyncio.create_task(instance._send_frames(NS(send_realtime_input=send), queue))
    try:
        await asyncio.wait_for(finished.wait(), 1)
        # The send completes before the ActivityEnd timestamp is recorded.
        async with asyncio.timeout(1):
            while instance._reply_wait_started_at is None:
                await asyncio.sleep(0)
        assert instance._reply_wait_started_at == instance.activity_end_sent_at
        assert not instance._filler_played
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
