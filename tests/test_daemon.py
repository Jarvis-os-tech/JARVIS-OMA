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
    assert config['speech_config']['language_code'] == 'en-US'
    assert 'en-IN' in config['input_audio_transcription']['language_codes']
    assert 'None attached yet' in config['system_instruction']
    assert 'LANGUAGE & ACCENT ROBUSTNESS' in config['system_instruction']


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


@pytest.mark.asyncio
async def test_delayed_audio_still_plays_after_warning(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice._reply_authorized = voice._waiting = True
    voice._last_progress = 10.0
    calls = 0
    async def one_cycle(delay):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise asyncio.CancelledError
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', one_cycle)
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 26.0)
    with pytest.raises(asyncio.CancelledError):
        await voice.monitor_response()
    assert voice.response_delayed
    assert voice._reply_authorized
    await voice.handle(SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(
        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=bytes(960)))]))))
    assert voice.player.queued_bytes == 960
    assert not voice.response_delayed


@pytest.mark.asyncio
async def test_stalled_provider_reconnects_without_resuming_old_answer(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice._reply_authorized = True
    voice._last_progress = 10.0
    voice.resume_handle = 'old-session'
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', AsyncMock())
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 56.0)
    with pytest.raises(ConnectionError, match='Please repeat'):
        await voice.monitor_response()
    assert voice.resume_handle is None


@pytest.mark.asyncio
async def test_production_setup_attaches_memory_and_drains_on_exit(tmp_path, monkeypatch):
    from jarvis_voice import daemon
    from jarvis_voice.config import Config
    from jarvis_memory.bridge import MemoryBridge
    from google.genai import types
    config = Config(autostart_listening=False)
    config.memory.path = str(tmp_path / 'memory')
    bridge = MemoryBridge(config.memory)
    bridge.remember('Prefers cobalt notebooks')
    bridge.close()
    seen = {}
    class StopSetup(BaseException):
        pass
    original = daemon.live_config
    def capture_config(**kwargs):
        seen.update(kwargs)
        result = original(**kwargs)
        assert 'cobalt' in result['system_instruction']
        types.LiveConnectConfig(**result)
        raise StopSetup
    monkeypatch.setattr(daemon, 'live_config', capture_config)
    ipc = MagicMock()
    ipc.start = AsyncMock()
    ipc.close = AsyncMock()
    monkeypatch.setattr(daemon, 'ControlServer', lambda **kwargs: ipc)
    with pytest.raises(StopSetup):
        await daemon.run(SimpleNamespace(config_obj=config), 'not-sent')
    assert seen['skills']._closed
    assert seen['config'] is config
    assert seen['tools'][0]['function_declarations']
    tool_names = {t['name'] for t in seen['tools'][0]['function_declarations']}
    assert 'github_connection_status' in tool_names
    assert 'google_connection_status' in tool_names
    assert 'system_query' in tool_names
    assert len(tool_names) > 200
    ipc.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_memory_tool_roundtrip_and_unknown_tool(tmp_path):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.config import Config
    from jarvis_voice.playback import Playback
    from jarvis_memory.skills import MemorySkills
    config = Config()
    config.memory.path = str(tmp_path)
    skills = MemorySkills(config)
    try:
        await skills.start()
        voice = LiveVoice(Playback('default'), skills=skills, config=config)
        voice._reply_authorized = True
        session = SimpleNamespace(send_tool_response=AsyncMock())
        for name, args in [('remember_memory', {'text': 'Prefers copper notebooks'}), ('unsupported', {})]:
            event = SimpleNamespace(tool_call=SimpleNamespace(function_calls=[SimpleNamespace(id='call-1', name=name, args=args)]))
            await voice.handle(event, session)
            response = session.send_tool_response.call_args.kwargs['function_responses'][0]
            assert response.id == 'call-1'
            assert ('error' in response.response) == (name == 'unsupported')
            if name == 'remember_memory':
                await voice.handle(SimpleNamespace(server_content=SimpleNamespace(turn_complete=True)))
                assert voice._reply_authorized  # Intermediate tool boundary must not silence the answer.
                await voice.handle(SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(
                    parts=[SimpleNamespace(inline_data=SimpleNamespace(data=bytes(960)))]))))
                assert voice.player.queued_bytes == 960
                await voice.handle(SimpleNamespace(server_content=SimpleNamespace(turn_complete=True)))
                assert not voice._reply_authorized
        recalled = await skills.execute('recall_memory', {'query': 'copper'})
        assert 'copper' in recalled['facts'][0]['text']
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_completed_turn_clears_delay_warning():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice.response_delayed = True
    voice.last_error = 'The response is taking longer than expected.'
    await voice.handle(SimpleNamespace(server_content=SimpleNamespace(turn_complete=True)))
    assert not voice.response_delayed
    assert voice.last_error == ''


def test_idle_connected_microphone_reports_listening():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice.connected = True
    assert voice.status()['listening']
    voice.muted = True
    assert not voice.status()['listening']
    assert voice.status()['connection_state'] == 'muted'


@pytest.mark.parametrize('muted,volume,state,issue', [
    (True, 42, 'microphone_muted', 'System microphone is muted.'),
    (False, 0, 'microphone_silent', 'Microphone volume is zero.'),
])
def test_system_microphone_block_cannot_report_listening(muted, volume, state, issue):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from jarvis_voice.ipc import ControlServer
    voice = LiveVoice(Playback('default'))
    voice.connected = True
    voice.microphone_state = dict(source='actual-input', muted=muted,
                                  volume_percent=volume, issue=issue)
    status = voice.status()
    assert status['state'] == state
    assert status['connection_state'] == state
    assert not status['listening']
    assert status['error'] == issue
    assert status['microphone']['source'] == 'actual-input'
    assert issue in ControlServer(status_provider=voice.status)._dispatch('status')
    # A read-only health check must preserve the user's software mute choice.
    assert voice.muted is False


@pytest.mark.asyncio
async def test_microphone_monitor_recovers_when_system_unmutes(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice.connected = True
    snapshots = [dict(source='actual-input', muted=True, volume_percent=42,
                      issue='System microphone is muted.'),
                 dict(source='actual-input', muted=False, volume_percent=42, issue='')]
    observed = []
    async def health():
        return snapshots.pop(0)
    async def cycle(_):
        observed.append(voice.status())
        if not snapshots:
            raise asyncio.CancelledError
    monkeypatch.setattr('jarvis_voice.daemon.read_microphone_state', health)
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycle)
    with pytest.raises(asyncio.CancelledError):
        await voice.monitor_microphone()
    assert not observed[0]['listening']
    assert observed[1]['listening']
    assert observed[1]['error'] == ''


def test_unknown_microphone_health_does_not_invent_mute():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice.connected = True
    voice.microphone_state = dict(source='', muted=None, volume_percent=None,
                                  issue='Unable to verify microphone state.')
    assert voice.status()['listening']
    assert voice.status()['error'] == ''


@pytest.mark.asyncio
async def test_response_watchdog_does_not_reconnect_during_tool(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    voice._reply_authorized = True
    voice._tools_in_flight = 1
    voice._last_progress = 1.0
    count = 0
    async def cycles(_):
        nonlocal count
        count += 1
        if count > 1:
            raise asyncio.CancelledError
    monkeypatch.setattr('jarvis_voice.daemon.asyncio.sleep', cycles)
    monkeypatch.setattr('jarvis_voice.daemon.time.monotonic', lambda: 100.0)
    with pytest.raises(asyncio.CancelledError):
        await voice.monitor_response()
    assert voice._reply_authorized


@pytest.mark.asyncio
async def test_tool_call_id_deduplicates_control_effect():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    skills = SimpleNamespace(declarations=[{'name': 'test_action'}], execute=AsyncMock(return_value='done'))
    voice = LiveVoice(Playback('default'), skills=skills)
    voice._reply_authorized = True
    session = SimpleNamespace(send_tool_response=AsyncMock())
    event = SimpleNamespace(function_calls=[SimpleNamespace(id='one-effect', name='test_action', args={})])
    await voice.handle_tools(event, session)
    await voice.handle_tools(event, session)
    skills.execute.assert_awaited_once()
    assert session.send_tool_response.await_count == 2


@pytest.mark.asyncio
async def test_spoken_confirmation_needs_real_new_turn():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    skills = SimpleNamespace(declarations=[{'name': 'confirm_last'}], execute=AsyncMock(return_value='done'))
    voice = LiveVoice(Playback('default'), skills=skills)
    voice._reply_authorized = True
    session = SimpleNamespace(send_tool_response=AsyncMock())
    voice._user_text = 'confirm'
    voice._confirmation_gate_turn = voice.gate.accepted_turns
    await voice.handle_tools(SimpleNamespace(function_calls=[SimpleNamespace(id='blocked', name='confirm_last', args={'heard_phrase': 'confirm'})]), session)
    skills.execute.assert_not_awaited()
    voice.gate.accepted_turns += 1
    await voice.handle_tools(SimpleNamespace(function_calls=[SimpleNamespace(id='new-turn', name='confirm_last', args={'heard_phrase': 'confirm'})]), session)
    skills.execute.assert_awaited_once()


def test_omarchy_routing_only_when_attached():
    from jarvis_voice.daemon import build_instruction, live_config
    assert 'OMARCHY DESKTOP SKILL' in build_instruction([{'function_declarations': [{'name': 'omarchy_help'}]}])
    assert 'OMARCHY DESKTOP SKILL' not in build_instruction()
    assert live_config()['session_resumption'] == {}


def test_standby_status_and_confirm_wake():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    assert voice.status()['standby'] is False
    assert voice.status()['state'] != 'standby'

    voice.standby_active = True
    assert voice.status()['standby'] is True
    assert voice.status()['state'] == 'standby'
    assert voice.status()['connection_state'] == 'standby'

    assert voice._wake_confirmation_pending is False
    voice.confirm_wake()
    assert voice._wake_confirmation_pending is True


@pytest.mark.asyncio
async def test_monitor_standby_raises_enter_standby():
    from jarvis_voice.daemon import LiveVoice, EnterStandby
    from jarvis_voice.playback import Playback
    voice = LiveVoice(Playback('default'))
    await voice.standby.request()
    with pytest.raises(EnterStandby):
        await voice.monitor_standby()


def test_long_command_turn_silence_threshold():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from jarvis_voice.config import Config
    import struct

    cfg = Config(turn_silence_frames=35)
    voice = LiveVoice(Playback('default'), config=cfg)
    assert voice.gate.silence_frames == 35

    voice.gate.active = True
    voice.gate._needs_reset = False
    voice.gate.detector = lambda pcm: 0.0
    quiet = struct.pack('<320h', *([1] * 320))
    # 30 frames of quiet pause (600ms) must not close the turn
    for i in range(34):
        assert not voice.gate.process(quiet, now=i * .02).closed
    # At frame 35 (700ms), speech turn closes cleanly
    assert voice.gate.process(quiet, now=.68).closed


@pytest.mark.asyncio
async def test_send_greeting_skipped_if_already_greeted_or_user_speaking(tmp_path, monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from jarvis_voice.config import Config

    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    cfg = Config(greet_on_start=True)
    voice = LiveVoice(Playback('default'), config=cfg)

    # 1. User is already speaking -> greeting skipped
    voice.gate.active = True
    fake_session = AsyncMock()
    await voice.send_greeting(fake_session)
    fake_session.send_client_content.assert_not_awaited()
    assert voice._greeted is True

    # 2. Reset and test flag existence -> greeting skipped
    voice2 = LiveVoice(Playback('default'), config=cfg)
    flag_dir = tmp_path / 'jarvis'
    flag_dir.mkdir(parents=True, exist_ok=True)
    (flag_dir / 'greeted.flag').touch()
    await voice2.send_greeting(fake_session)
    fake_session.send_client_content.assert_not_awaited()
    assert voice2._greeted is True


@pytest.mark.asyncio
async def test_interrupted_while_gate_active_preserves_authorization():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    voice.connected = True
    voice.gate.active = True
    voice._reply_authorized = True
    voice._waiting = True

    event = SimpleNamespace(
        server_content=SimpleNamespace(interrupted=True),
        tool_call=None, session_resumption_update=None, go_away=None, tool_call_cancellation=None,
    )
    await voice.handle(event)

    # Gate must remain active and turn authorized when interrupted arrives during new speech
    assert voice.gate.active is True
    assert voice._reply_authorized is True


@pytest.mark.asyncio
async def test_tool_turn_complete_without_audio_does_not_hang():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    voice.connected = True
    voice._reply_authorized = True
    voice._tool_response_pending = True
    voice._tool_intermediate_received = False
    voice._waiting = True

    event = SimpleNamespace(
        server_content=SimpleNamespace(turn_complete=True),
        tool_call=None, session_resumption_update=None, go_away=None, tool_call_cancellation=None,
    )
    # First turn_complete is intermediate tool boundary -> waits for response
    await voice.handle(event)
    assert voice._tool_intermediate_received is True
    assert voice._reply_authorized is True

    # Second turn_complete with no audio -> cleanly completes turn without hanging
    await voice.handle(event)
    assert voice._tool_response_pending is False
    assert voice._waiting is False
    assert voice._reply_authorized is False


@pytest.mark.asyncio
async def test_send_inputs_forwards_user_text_and_test_bar():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from skills.input_bar import TestBar

    class FakeSkills:
        def __init__(self):
            self.test_bar = TestBar()

    skills = FakeSkills()
    voice = LiveVoice(Playback('default'), skills=skills)
    sent_turns = []

    class FakeSession:
        async def send_client_content(self, turns, turn_complete):
            sent_turns.append((turns, turn_complete))

    session = FakeSession()

    # Enqueue into skills test_bar (input bar HUD)
    skills.test_bar.items.put_nowait({'text': 'query from hud', 'data': b'', 'mime': '', 'name': ''})

    # Also enqueue via voice.send_text (IPC/CLI)
    voice.send_text('query from ipc')

    worker = asyncio.create_task(voice.send_inputs(session))
    await asyncio.sleep(0.2)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker

    assert len(sent_turns) == 2
    # Verify first turn from test_bar: sent_turns is list of (turns_list, turn_complete)
    content1 = sent_turns[0][0][0]
    assert any(getattr(p, 'text', '') == 'query from hud' for p in content1.parts)
    assert sent_turns[0][1] is True  # turn_complete

    # Verify second turn from IPC
    content2 = sent_turns[1][0][0]
    assert any(getattr(p, 'text', '') == 'query from ipc' for p in content2.parts)
    assert sent_turns[1][1] is True  # turn_complete

    # State flags updated
    assert voice._reply_authorized is True
    assert voice._waiting is True
    assert voice._model_active is True


@pytest.mark.asyncio
async def test_interruption_does_not_drop_subsequent_model_response():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    voice = LiveVoice(Playback('default'))
    voice._model_active = True
    voice._accept_interruption()
    assert voice._barge_pending is True
    assert voice._barge_turn is True
    assert voice._reply_authorized is True

    # Interruption event arrives for old generation
    event_interrupted = SimpleNamespace(
        server_content=SimpleNamespace(interrupted=True),
        tool_call=None, session_resumption_update=None, go_away=None, tool_call_cancellation=None,
    )
    await voice.handle(event_interrupted)
    assert voice._barge_pending is True
    assert voice.provider_interruptions == 1

    event_complete = SimpleNamespace(
        server_content=SimpleNamespace(turn_complete=True),
        tool_call=None, session_resumption_update=None, go_away=None, tool_call_cancellation=None,
    )
    await voice.handle(event_complete)
    assert voice._barge_pending is False
    assert voice._reply_authorized is True

    # New model response arrives with audio
    enqueued = []
    voice.player.enqueue = lambda data: enqueued.append(data)
    event_audio = SimpleNamespace(
        server_content=SimpleNamespace(
            interrupted=False,
            model_turn=SimpleNamespace(
                parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b'\x01\x00' * 160))]
            ),
        ),
        tool_call=None, session_resumption_update=None, go_away=None, tool_call_cancellation=None,
    )
    await voice.handle(event_audio)
    assert len(enqueued) == 1
    assert voice.provider_audio_bytes == 320


@pytest.mark.asyncio
async def test_send_inputs_prefetches_urls_and_attaches_web_content(monkeypatch):
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from skills.input_bar import TestBar

    monkeypatch.setattr(
        'jarvis_control.web_text.bounded_page_text',
        lambda url, timeout=12: f"Mock page text for {url}",
    )

    class FakeSkills:
        def __init__(self):
            self.test_bar = TestBar()

    skills = FakeSkills()
    voice = LiveVoice(Playback('default'), skills=skills)
    sent_turns = []

    class FakeSession:
        async def send_client_content(self, turns, turn_complete):
            sent_turns.append((turns, turn_complete))

    session = FakeSession()
    voice.send_text('please check https://example.com/article')

    worker = asyncio.create_task(voice.send_inputs(session))
    await asyncio.sleep(0.15)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker

    assert len(sent_turns) == 1
    content = sent_turns[0][0][0]
    full_text = content.parts[0].text
    assert 'please check https://example.com/article' in full_text
    assert '[Live Web Page Content for https://example.com/article]' in full_text
    assert 'Mock page text for https://example.com/article' in full_text


@pytest.mark.asyncio
async def test_send_inputs_formats_code_and_image_attachments():
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback
    from skills.input_bar import TestBar

    class FakeSkills:
        def __init__(self):
            self.test_bar = TestBar()

    skills = FakeSkills()
    voice = LiveVoice(Playback('default'), skills=skills)
    sent_turns = []

    class FakeSession:
        async def send_client_content(self, turns, turn_complete):
            sent_turns.append((turns, turn_complete))

    session = FakeSession()

    # Code attachment
    skills.test_bar.items.put_nowait({
        'text': 'analyze this script',
        'data': b'def add(a, b):\n    return a + b\n',
        'mime': 'text/x-python',
        'name': 'math_utils.py',
    })

    # Image attachment
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
    skills.test_bar.items.put_nowait({
        'text': '',
        'data': png_bytes,
        'mime': 'image/png',
        'name': 'screenshot.png',
    })

    worker = asyncio.create_task(voice.send_inputs(session))
    await asyncio.sleep(0.2)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker

    assert len(sent_turns) == 2

    # Verify code attachment turn
    turn1_content = sent_turns[0][0][0]
    parts1_text = [p.text for p in turn1_content.parts if getattr(p, 'text', None)]
    assert any('analyze this script' in t for t in parts1_text)
    assert any('Attached file: math_utils.py' in t for t in parts1_text)
    assert any('def add(a, b):' in t for t in parts1_text)

    # Verify image attachment turn
    turn2_content = sent_turns[1][0][0]
    assert any('screenshot.png' in getattr(p, 'text', '') for p in turn2_content.parts)
    assert any(getattr(getattr(p, 'inline_data', None), 'mime_type', '') == 'image/png' for p in turn2_content.parts)




