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
    assert status['automatic_barge_in'] is True


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
