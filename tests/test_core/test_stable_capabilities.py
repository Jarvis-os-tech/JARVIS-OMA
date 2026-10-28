"""Capability restoration must preserve turn protection and fail independently."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from core.config import Config
from core.stable_capabilities import CapabilityServices
from core.stable_voice import LiveVoice, Playback, live_config
from skills import DesktopSkills, SkillError


@pytest.mark.asyncio
async def test_registry_status_tool_reaches_the_actual_live_voice():
    config = Config()
    skills = DesktopSkills(config=config)
    voice = LiveVoice(Playback('test'), skills=skills)
    voice.connected = True
    try:
        result = await skills.execute('get_assistant_status', {})
        assert result['available'] and result['skills_enabled']
        assert result['registered_tools'] > 100
        cfg = types.LiveConnectConfig.model_validate(
            live_config('Aoede', skills=skills, settings=config, memory_context='Saved project: JARVIS'))
        prompt = str(cfg.system_instruction)
        assert 'Jarvis' in prompt and 'Saved project: JARVIS' in prompt
        assert cfg.realtime_input_config.activity_handling.value == 'NO_INTERRUPTION'
        names = {d.name for d in cfg.tools[0].function_declarations}
        assert {'discover_domain_tools', 'execute_domain_tool', 'list_capabilities'} <= names
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_memory_failure_does_not_prevent_voice_configuration():
    skills = NS(memory_call=AsyncMock(side_effect=OSError('offline storage')))
    services = CapabilityServices(skills, Config())
    assert await services.context() == ''
    assert not services.memory_ready


@pytest.mark.asyncio
async def test_unsolicited_model_cannot_operate_desktop():
    skills = NS(execute=AsyncMock())
    voice = LiveVoice(Playback('test'), skills=skills)
    event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
        types.FunctionCall(id='unsolicited', name='open_application', args={'application': 'terminal'})]))
    await voice.handle(event, NS())
    skills.execute.assert_not_called()
    assert not voice.tool_tasks


@pytest.mark.asyncio
async def test_tool_completion_refreshes_response_watchdog():
    skills = NS(execute=AsyncMock(return_value={'status': 'ok'}))
    voice = LiveVoice(Playback('test'), skills=skills)
    voice._reply_authorized = True
    voice._last_progress = 0
    session = NS(send_tool_response=AsyncMock())
    await voice._execute_tool(session, NS(id='call', name='get_assistant_status', args={}))
    assert voice._last_progress > 0
    assert voice._reply_authorized
    assert session.send_tool_response.await_args.kwargs['function_responses'].id == 'call'


def test_unimplemented_streaming_never_claims_active():
    skills = NS(vision_mode='camera')
    services = CapabilityServices(skills, Config())
    with pytest.raises(SkillError):
        services.reject_streaming('camera')
    assert skills.vision_mode == 'off'


@pytest.mark.asyncio
async def test_memory_exchange_is_recorded_only_after_authorized_response():
    from unittest.mock import Mock
    skills = NS(queue_memory_exchange=Mock())
    voice = LiveVoice(Playback('test'), skills=skills)
    voice.memory_enabled = voice._reply_authorized = voice._reply_started = True
    event = types.LiveServerMessage(server_content=types.LiveServerContent(
        input_transcription=types.Transcription(text='Remember my project'),
        output_transcription=types.Transcription(text='Your project is JARVIS.'), turn_complete=True))
    await voice.handle(event)
    skills.queue_memory_exchange.assert_called_once_with('Remember my project', 'Your project is JARVIS.')
    assert not voice._reply_authorized


@pytest.mark.asyncio
async def test_typed_request_grants_exactly_one_response_budget():
    from unittest.mock import Mock
    skills = NS(test_bar=NS(pop=Mock(side_effect=[{'text': 'Check my system', 'data': None}, None])))
    voice = LiveVoice(Playback('test'), skills=skills)
    sent = asyncio.Event()
    async def send(**kwargs):
        assert kwargs['turn_complete']
        sent.set()
    worker = asyncio.create_task(voice.send_input_bar(NS(send_client_content=send)))
    try:
        await asyncio.wait_for(sent.wait(), 1)
        assert voice._reply_authorized and voice._waiting
        assert voice._user_text == 'Check my system'
        skills.test_bar.pop.assert_called_once()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_reconnect_replay_never_repeats_a_desktop_action():
    skills = NS(execute=AsyncMock(return_value={'status': 'ok'}))
    voice = LiveVoice(Playback('test'), skills=skills)
    voice._reply_authorized = True
    session = NS(send_tool_response=AsyncMock())
    event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
        types.FunctionCall(id='same-action', name='open_application', args={'name': 'terminal'})]))
    await voice.handle(event, session)
    await asyncio.gather(*list(voice.tool_tasks.values()))
    await voice.cancel_tools()
    await voice.handle(event, session)
    await asyncio.gather(*list(voice.tool_tasks.values()))
    skills.execute.assert_awaited_once()
    assert session.send_tool_response.await_count == 2


def test_hud_status_never_rescans_registry_after_initialization():
    class Skills:
        scans = 0
        @property
        def declarations(self):
            self.scans += 1
            return [{'name': 'get_assistant_status'}]
    skills = Skills()
    voice = LiveVoice(Playback('test'), skills=skills)
    for _ in range(20):
        assert voice.status()['registered_tools'] == 1
    assert skills.scans == 1


@pytest.mark.asyncio
async def test_first_audio_timing_is_measured_once_not_overwritten_by_later_chunks():
    from unittest.mock import patch
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    voice._speech_closed_at = 10.0
    event = types.LiveServerMessage(server_content=types.LiveServerContent(model_turn=types.Content(
        parts=[types.Part(inline_data=types.Blob(data=b'\x01\x00' * 480, mime_type='audio/pcm;rate=24000'))])))
    with patch('core.stable_voice.time.monotonic', return_value=10.25):
        await voice.handle(event)
    assert voice.status()['last_reply_after_local_end_ms'] == 250
    with patch('core.stable_voice.time.monotonic', return_value=10.5):
        await voice.handle(event)
    assert voice.status()['last_reply_after_local_end_ms'] == 250


@pytest.mark.asyncio
async def test_sender_brackets_speech_with_one_explicit_activity():
    from core.speech_turn import SpeechTurnGate
    voice = LiveVoice(Playback('test'), speech_gate=SpeechTurnGate(detector=lambda data: .9,
                                                                silence_frames=20))
    reader = asyncio.StreamReader()
    reader.feed_data(b'\x00\x10' * 640 + bytes(640) * 25)
    reader.feed_eof()
    session = NS(send_realtime_input=AsyncMock())
    with pytest.raises(EOFError):
        await voice.send_audio(session, reader)
    sent = [call.kwargs for call in session.send_realtime_input.await_args_list]
    starts = [i for i, message in enumerate(sent) if 'activity_start' in message]
    ends = [i for i, message in enumerate(sent) if 'activity_end' in message]
    assert len(starts) == len(ends) == 1
    assert starts[0] < ends[0]
    assert any('audio' in message and any(message['audio'].data)
               for message in sent[starts[0]:ends[0]])
