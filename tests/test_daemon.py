"""Tests for jarvis_voice.daemon module."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def test_daemon_imports():
    from jarvis_voice.daemon import LiveVoice, live_config
    assert LiveVoice is not None
    assert callable(live_config)


def test_live_config_produces_valid_dict():
    from jarvis_voice.daemon import live_config
    config = live_config(voice='Aoede')
    assert config['response_modalities'] == ['AUDIO']
    assert 'system_instruction' in config
    assert 'realtime_input_config' in config
    assert config['realtime_input_config']['automatic_activity_detection']['disabled'] is True
    assert config['speech_config']['voice_config']['prebuilt_voice_config']['voice_name'] == 'Aoede'
    assert 'None attached yet' in config['system_instruction']


def test_live_config_dynamic_capabilities_with_tools():
    from jarvis_voice.daemon import live_config
    tools = [{'function_declarations': [{'name': 'set_volume'}, {'name': 'tile_window'}]}]
    config = live_config(voice='Puck', tools=tools)
    assert config['tools'] == tools
    assert 'set_volume, tile_window' in config['system_instruction']
    assert 'CURRENT ATTACHED OS TOOLS (2 available)' in config['system_instruction']


def test_live_voice_status():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    voice = LiveVoice(player)
    status = voice.status()
    assert 'state' in status
    assert status['state'] in ('connecting', 'speaking', 'listening', 'thinking', 'idle')
    assert 'muted' in status
    assert 'model' in status
    assert status['automatic_barge_in'] is False


def test_live_voice_mute_and_interrupt():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    voice = LiveVoice(player)
    assert not voice.muted

    voice.set_muted(True)
    assert voice.muted
    assert voice.status()['muted'] is True

    voice.set_muted(False)
    assert not voice.muted
    assert voice.status()['muted'] is False


@pytest.mark.asyncio
async def test_live_voice_handle_audio_and_turn():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    voice = LiveVoice(player)
    voice.connected = True
    voice._reply_authorized = True

    # Simulate server event with model turn audio
    event = SimpleNamespace(
        session_resumption_update=None,
        server_content=SimpleNamespace(
            interrupted=False,
            turn_complete=False,
            input_transcription=None,
            output_transcription=None,
            model_turn=SimpleNamespace(
                parts=[SimpleNamespace(
                    inline_data=SimpleNamespace(
                        data=b'\x00\x00' * 480,
                        mime_type='audio/pcm;rate=24000',
                    )
                )]
            ),
        ),
        go_away=None,
        tool_call_cancellation=None,
        tool_call=None,
    )

    await voice.handle(event)
    assert voice.provider_audio_bytes == 960
    assert player.queued_bytes == 960

    # Turn complete
    complete_event = SimpleNamespace(
        session_resumption_update=None,
        server_content=SimpleNamespace(
            interrupted=False,
            turn_complete=True,
            input_transcription=None,
            output_transcription=None,
            model_turn=None,
        ),
        go_away=None,
        tool_call_cancellation=None,
        tool_call=None,
    )
    await voice.handle(complete_event)
    assert not voice._reply_authorized


@pytest.mark.asyncio
async def test_live_voice_send_greeting():
    """send_greeting triggers an initial user turn prompt on session start."""
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    voice = LiveVoice(player, greet_on_start=True)
    assert not voice._greeted

    sent_turns = []
    fake_session = AsyncMock()
    fake_session.send_client_content = AsyncMock(side_effect=lambda turns, turn_complete: sent_turns.extend(turns))

    await voice.send_greeting(fake_session)
    assert voice._greeted is True
    assert voice._reply_authorized is True
    fake_session.send_client_content.assert_awaited_once()
    assert len(sent_turns) == 1
    assert 'booting up on JARVIS OS' in sent_turns[0].parts[0].text

    # Subsequent calls must not trigger duplicate greeting
    await voice.send_greeting(fake_session)
    assert fake_session.send_client_content.await_count == 1


@pytest.mark.asyncio
async def test_supervise_cleans_workers_after_failure():
    from jarvis_voice.daemon import supervise

    started, stopped = asyncio.Event(), asyncio.Event()

    async def microphone():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def transport():
        await started.wait()
        raise ConnectionError('transport lost')

    with pytest.raises(ConnectionError, match='transport lost'):
        await supervise(microphone(), transport())
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_supervise_cancellation_awaits_workers():
    from jarvis_voice.daemon import supervise

    started, stopped = asyncio.Event(), asyncio.Event()

    async def worker():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    task = asyncio.create_task(supervise(worker()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_microphone_eof_reaches_session_without_hanging():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    reader = asyncio.StreamReader()
    reader.feed_eof()
    with pytest.raises(EOFError, match='Microphone stream ended'):
        await asyncio.wait_for(voice.send_audio(AsyncMock(), reader), .5)
    assert voice._capture_queue is None


@pytest.mark.asyncio
async def test_capture_overflow_does_not_drop_turn_boundary():
    from jarvis_voice.daemon import LiveVoice, INPUT_BYTES
    from jarvis_voice.playback import Playback, MicrophoneBacklogError
    from jarvis_voice.speech import GateFrame

    gate = MagicMock(active=True, tail_seconds=.45)
    gate.process.return_value = GateFrame(bytes(INPUT_BYTES), opened=True)
    voice = LiveVoice(Playback('default'), speech_gate=gate)
    reader = asyncio.StreamReader()
    reader.feed_data(bytes(INPUT_BYTES * 2))
    queue = asyncio.Queue(maxsize=1)
    with pytest.raises(MicrophoneBacklogError):
        await asyncio.wait_for(voice._capture_audio(reader, queue), .5)
    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_turn_audio_sent_in_order_with_explicit_boundaries():
    from jarvis_voice.daemon import LiveVoice, INPUT_BYTES, supervise
    from jarvis_voice.playback import Playback
    from jarvis_voice.speech import GateFrame

    voice = LiveVoice(Playback('default'))
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(b'\x01\x00' * 320, opened=True), 0))
    queue.put_nowait((GateFrame(bytes(INPUT_BYTES), closed=True), 0))
    sent = []
    finished = asyncio.Event()

    async def send(**kwargs):
        sent.append(kwargs)
        if 'activity_end' in kwargs:
            finished.set()

    await asyncio.wait_for(supervise(
        voice._send_frames(SimpleNamespace(send_realtime_input=send), queue),
        finished.wait()), .5)
    assert [next(iter(item)) for item in sent] == ['activity_start', 'audio', 'audio', 'activity_end']
    assert sent[1]['audio'].data == b'\x01\x00' * 320


@pytest.mark.asyncio
async def test_first_audio_latency_stays_fixed_across_response_chunks(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    voice._reply_authorized = True
    voice._speech_closed_at = 10.0
    event = SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(
        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=bytes(960)))])))
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 10.25)
    await voice.handle(event)
    assert voice.status()['latency']['speech_end_to_first_audio_ms'] == 250
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 10.5)
    await voice.handle(event)
    assert voice.status()['latency']['speech_end_to_first_audio_ms'] == 250


def test_default_turn_wait_is_300ms_without_cutting_short_pauses():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    import struct

    voice = LiveVoice(Playback('default'))
    voice.gate.active = True
    voice.gate._needs_reset = False
    # A sub-threshold frame remains quiet regardless of detector probability.
    voice.gate.detector = lambda pcm: 0.0
    quiet = struct.pack('<320h', *([1] * 320))
    for i in range(14):
        assert not voice.gate.process(quiet, now=i * .02).closed
    assert voice.gate.process(quiet, now=.28).closed


@pytest.mark.asyncio
async def test_provider_latency_measured_from_actual_activity_end(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    voice._reply_authorized = True
    voice._speech_closed_at = 10.0
    voice.activity_end_sent_at = 10.2
    event = SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(
        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=bytes(960)))])))
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 10.5)
    await voice.handle(event)
    assert voice.status()['latency']['activity_end_to_first_audio_ms'] == 300
    assert voice.status()['latency']['speech_end_to_first_audio_ms'] == 500


def test_live_voice_uses_verified_low_latency_thinking_setting():
    from jarvis_voice.daemon import live_config
    assert live_config()['thinking_config'] == {'thinking_budget': 0}
