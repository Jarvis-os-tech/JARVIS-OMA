"""Natural interruption boundaries without microphone, speaker or network access."""
import asyncio
import struct
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback
from jarvis_voice.speech import GateFrame, SpeechTurnGate


def event(**content):
    return SimpleNamespace(server_content=SimpleNamespace(**content))


def audio_event(pcm):
    return event(model_turn=SimpleNamespace(parts=[
        SimpleNamespace(inline_data=SimpleNamespace(data=pcm))]))


def interrupted_voice(*, speaking=True):
    voice = LiveVoice(Playback('default'), barge_in=True)
    voice._reply_authorized = voice._waiting = True
    voice._reply_started = voice._model_active = speaking
    voice._accept_interruption()
    return voice


@pytest.mark.asyncio
@pytest.mark.parametrize('speaking', [False, True])
async def test_interrupting_waiting_or_speaking_reply_preserves_new_turn(speaking):
    voice = interrupted_voice(speaking=speaking)
    assert voice._barge_pending
    assert voice.gate.active
    assert voice._reply_authorized

    # The protocol ends the interrupted OLD turn in this order. Neither event
    # may reset the locally accepted NEW utterance.
    await voice.handle(event(interrupted=True))
    assert voice._barge_pending
    assert voice.gate.active
    assert voice._reply_authorized
    await voice.handle(event(turn_complete=True))
    assert not voice._barge_pending
    assert voice.gate.active
    assert voice._reply_authorized


@pytest.mark.asyncio
@pytest.mark.parametrize('with_old_boundary', [False, True])
async def test_new_input_transcript_survives_old_turn_drain(with_old_boundary):
    voice = interrupted_voice()
    text = 'Stop, tell me the current time.'
    await voice.handle(event(
        input_transcription=SimpleNamespace(text=text),
        turn_complete=with_old_boundary))

    assert voice._user_text == text
    assert voice._memory_user == text
    assert voice.recognized_input_events == 1
    assert voice._reply_authorized
    assert voice.gate.active
    assert voice._barge_pending == (not with_old_boundary)


@pytest.mark.asyncio
async def test_old_audio_and_tool_calls_stay_blocked_until_boundary():
    voice = interrupted_voice()
    execute = AsyncMock(return_value='done')
    voice.skills = SimpleNamespace(
        declarations=[{'name': 'system_control'}], execute=execute)
    session = SimpleNamespace(send_tool_response=AsyncMock())
    old_pcm = b'\x01\x00' * 480
    await voice.handle(audio_event(old_pcm), session)
    tool = SimpleNamespace(function_calls=[SimpleNamespace(
        id='old-action', name='system_control', args={'action': 'volume_get'})])
    await voice.handle(SimpleNamespace(tool_call=tool), session)
    execute.assert_not_awaited()
    assert voice.player.queued_bytes == 0
    assert voice._barge_pending

    await voice.handle(event(interrupted=True), session)
    await voice.handle(event(turn_complete=True), session)
    new_pcm = b'\x02\x00' * 480
    await voice.handle(audio_event(new_pcm), session)
    assert voice.player.queued_bytes == len(new_pcm)
    generation, queued = voice.player.queue.get_nowait()
    assert generation == voice.player.generation
    assert queued == new_pcm


@pytest.mark.asyncio
async def test_utterance_can_close_before_old_interruption_acknowledgement():
    voice = interrupted_voice(speaking=False)
    voice.gate.active = False
    voice._speech_closed_at = 100.0
    voice.activity_end_sent_at = 100.1
    await voice.handle(event(interrupted=True))
    await voice.handle(event(turn_complete=True))
    assert not voice._barge_pending
    assert not voice.gate.active
    assert voice._reply_authorized
    assert voice._waiting
    assert voice._speech_closed_at == 100.0
    assert voice.activity_end_sent_at == 100.1
    new_pcm = bytes(960)
    await voice.handle(audio_event(new_pcm))
    assert voice.player.queued_bytes == len(new_pcm)


def test_local_interruption_immediately_flushes_buffered_speech():
    player = Playback('default')
    player.enqueue(b'\x01\x00' * 960)
    player.playback_until = time.monotonic() + 4
    voice = LiveVoice(player, barge_in=True)
    voice._reply_authorized = voice._reply_started = voice._model_active = True
    old_generation = player.generation
    voice._accept_interruption()
    assert player.generation == old_generation + 1
    assert player.queued_bytes == 0
    assert player.queue.empty()
    assert not player.busy
    assert voice.gate.active
    assert voice.local_interruptions == 1


@pytest.mark.asyncio
async def test_capture_keeps_interruption_preroll_and_closing_boundary():
    pcm = struct.pack('<320h', *([2000] * 320))
    preroll = struct.pack('<320h', *([1000] * 320))
    gate = SpeechTurnGate(detector=lambda _: 0.0, silence_frames=2)
    player = Playback('default')
    player.enqueue(b'\x01\x00' * 480)
    voice = LiveVoice(player, speech_gate=gate, barge_in=True)
    voice._reply_authorized = voice._reply_started = voice._model_active = True
    voice.barge_gate = SimpleNamespace(
        process=lambda chunk, now: GateFrame(preroll + chunk, opened=True, barge_in=True),
        reset=lambda: None)
    reader = asyncio.StreamReader()
    reader.feed_data(pcm + bytes(640 * 2))
    reader.feed_eof()
    queue = asyncio.Queue()

    with pytest.raises(EOFError, match='Microphone stream ended'):
        await voice._capture_audio(reader, queue)

    frames = [queue.get_nowait() for _ in range(queue.qsize())]
    assert len(frames) == 3
    assert frames[0][0].opened
    assert frames[0][0].pcm == preroll + pcm
    assert frames[-1][0].closed
    assert all(generation == player.generation for _, generation in frames)
    assert player.queue.empty()
    assert voice.gate.accepted_turns == 1
    assert voice._reply_authorized


@pytest.mark.asyncio
async def test_playback_only_interruption_accepts_next_reply_without_old_boundary():
    # Model generation has already completed, but buffered speech remains.
    player = Playback('default')
    player.enqueue(b'\x01\x00' * 480)
    voice = LiveVoice(player, barge_in=True)
    voice._accept_interruption()
    assert not voice._barge_pending
    assert player.queue.empty()
    assert voice._reply_authorized
    new_pcm = b'\x02\x00' * 480
    await voice.handle(audio_event(new_pcm))
    assert player.queued_bytes == len(new_pcm)


@pytest.mark.asyncio
async def test_interruption_while_sender_waits_lock_cannot_upload_old_pcm():
    voice = LiveVoice(Playback('default'), barge_in=True)
    dequeued, finished = asyncio.Event(), asyncio.Event()

    class ObservedQueue(asyncio.Queue):
        async def get(self):
            value = await super().get()
            dequeued.set()
            return value

    queue = ObservedQueue()
    old_pcm, new_pcm = b'\x01\x00' * 320, b'\x02\x00' * 320
    queue.put_nowait((GateFrame(old_pcm, opened=True), voice.player.generation))
    sent = []

    async def send(**payload):
        sent.append(payload)
        if 'activity_end' in payload:
            finished.set()

    await voice.send_lock.acquire()
    sender = asyncio.create_task(voice._send_frames(
        SimpleNamespace(send_realtime_input=send), queue))
    try:
        await asyncio.wait_for(dequeued.wait(), 1)
        # Cancellation happens while an already-dequeued old frame waits for
        # the shared transport lock. Its earlier generation check is obsolete.
        voice._accept_interruption()
        queue.put_nowait((GateFrame(new_pcm, opened=True), voice.player.generation))
        queue.put_nowait((GateFrame(bytes(640), closed=True), voice.player.generation))
        voice.send_lock.release()
        await asyncio.wait_for(finished.wait(), 1)
        audio = [payload['audio'].data for payload in sent if 'audio' in payload]
        assert old_pcm not in audio
        assert new_pcm in audio
        assert sum('activity_start' in payload for payload in sent) == 1
    finally:
        if voice.send_lock.locked():
            voice.send_lock.release()
        sender.cancel()
        with pytest.raises(asyncio.CancelledError):
            await sender


@pytest.mark.asyncio
async def test_pending_ack_watchdog_waits_for_tool_then_keeps_five_second_bound(monkeypatch):
    clock = [99.0]
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: clock[0])
    voice = LiveVoice(Playback('default'), barge_in=True)
    voice._reply_authorized = voice._waiting = True
    voice.resume_handle = 'retain-this-session'
    tool_started, tool_release = asyncio.Event(), asyncio.Event()

    async def execute(name, arguments):
        tool_started.set()
        await tool_release.wait()
        return 'Completed existing action'

    voice.skills = SimpleNamespace(
        declarations=[{'name': 'browser_task'}], execute=execute)
    session = SimpleNamespace(send_tool_response=AsyncMock())
    batch = SimpleNamespace(function_calls=[SimpleNamespace(
        id='running-action', name='browser_task', args={})])
    running = asyncio.create_task(voice.handle_tools(batch, session))

    async def one_monitor_cycle():
        calls = 0
        async def sleep_once(_):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise asyncio.CancelledError
        with monkeypatch.context() as scoped:
            scoped.setattr('jarvis_voice.daemon.asyncio.sleep', sleep_once)
            with pytest.raises(asyncio.CancelledError):
                await voice.monitor_response()

    try:
        await tool_started.wait()
        assert voice._tools_in_flight == 1
        clock[0] = 100.0
        voice._accept_interruption()
        assert voice._barge_pending
        voice.gate.active = False  # The user's short interruption has finished.
        # receive() is occupied by this existing tool; it cannot yet consume
        # the provider's interruption boundary. Do not reconnect prematurely.
        clock[0] = 166.0
        await one_monitor_cycle()
        assert voice.resume_handle == 'retain-this-session'
        clock[0] = 167.0
        tool_release.set()
        await running
        assert voice._tools_in_flight == 0
        assert voice._barge_started_at == 167.0
        assert voice._last_progress == 167.0
        clock[0] = 171.9
        await one_monitor_cycle()
        assert voice._barge_pending
        # A genuinely missing provider boundary still has a finite deadline.
        clock[0] = 172.1
        with monkeypatch.context() as scoped:
            scoped.setattr('jarvis_voice.daemon.asyncio.sleep', AsyncMock())
            with pytest.raises(ConnectionError, match='Barge-in acknowledgement timeout'):
                await voice.monitor_response()
        assert voice.resume_handle is None
    finally:
        tool_release.set()
        if not running.done():
            running.cancel()
        try:
            await running
        except asyncio.CancelledError:
            pass


def test_live_voice_initializes_calibrated_barge_gate_from_config():
    from jarvis_voice.config import Config
    player = Playback('default')
    config = Config(
        barge_in=True,
        barge_in_min_rms=0.004,
        barge_in_echo_threshold=0.72,
        barge_in_vad_threshold=0.58,
    )
    voice = LiveVoice(player, barge_in=True, config=config)
    assert voice.barge_gate is not None
    assert voice.barge_gate.min_rms == 0.004
    assert voice.barge_gate.echo_threshold == 0.72
    assert voice.barge_gate.vad_threshold == 0.58
    assert voice.barge_gate.min_voiced == 4
    assert voice.barge_gate.min_positives == 2


@pytest.mark.asyncio
async def test_capture_holds_off_barge_in_during_playback_startup():
    pcm = struct.pack('<320h', *([2000] * 320))
    gate = SpeechTurnGate(detector=lambda _: 0.0, silence_frames=2)
    player = Playback('default')
    player.enqueue(b'\x01\x00' * 480)
    player.first_write_at = time.monotonic()  # 0ms elapsed, within 250ms startup window
    voice = LiveVoice(player, speech_gate=gate, barge_in=True)
    voice._reply_authorized = voice._reply_started = voice._model_active = True
    barge_calls = []
    voice.barge_gate = SimpleNamespace(
        process=lambda chunk, t: barge_calls.append(t) or GateFrame(chunk, opened=True, barge_in=True),
        reset=lambda: None)
    reader = asyncio.StreamReader()
    reader.feed_data(pcm)
    reader.feed_eof()
    queue = asyncio.Queue()

    with pytest.raises(EOFError, match='Microphone stream ended'):
        await voice._capture_audio(reader, queue)

    assert len(barge_calls) == 0
    assert voice.local_interruptions == 0


@pytest.mark.asyncio
async def test_capture_holds_microphone_when_model_active_half_duplex():
    """Half-duplex holds microphone while model is actively replying, even during playback pauses."""
    pcm = struct.pack('<320h', *([2000] * 320))
    gate = SpeechTurnGate(detector=lambda _: 0.95, silence_frames=2)
    player = Playback('default')
    # player is NOT playing (empty queue, playback_until in the past)
    player.playback_until = 0.0
    voice = LiveVoice(player, speech_gate=gate, barge_in=False)
    voice._model_active = True
    voice._reply_started = True

    reader = asyncio.StreamReader()
    reader.feed_data(pcm * 3)
    reader.feed_eof()
    queue = asyncio.Queue()

    with pytest.raises(EOFError, match='Microphone stream ended'):
        await voice._capture_audio(reader, queue)

    assert queue.empty()
    assert voice.gate.accepted_turns == 0


def test_spoken_interruption_clears_frames_and_resets_on_echo():
    from jarvis_voice.speech import SpokenInterruption, PlaybackReference
    ref = PlaybackReference()
    ref.correlation = lambda mic, now: 0.25
    detector = lambda _: 0.95
    interruption = SpokenInterruption(ref, detector=detector, echo_threshold=0.20)
    interruption._positives = 3
    interruption._voiced_frames = 3
    interruption._frames.append(bytes(640))

    pcm = struct.pack('<320h', *([3000] * 320))
    res = interruption.process(pcm, time.monotonic())
    assert res is None
    assert interruption._positives == 0
    assert interruption._voiced_frames == 0
    assert len(interruption._frames) == 0
    assert interruption.rejected_echo_frames == 1



