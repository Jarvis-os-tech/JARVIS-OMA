"""Unit and integration tests for Gemini Decision 1 integration in JARVIS-OMA.

Validates single-pass decision routing:
1. Addressability check (is_for_jarvis)
2. Spoken acknowledgement PCM clip selection (ack_clip)
3. Subsystem routing (orchestration/model_routes.py)
4. Desktop safety policy enforcement (jarvis_control/execution_policy.py)
5. Zero-wait audio masking playback via Playback queue
"""
import asyncio
import io
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
import wave

import pytest

from jarvis_control.execution_policy import requires_confirmation
from voice_layer.acknowledgements import (
    DECISION_ACK_CRITERIA,
    get_decision_ack_phrase,
    resolve_ack_asset,
)
from voice_layer.daemon import LiveVoice
from voice_layer.decision_router import (
    DecisionResult,
    DecisionRouter,
    pcm_to_wav,
)
from voice_layer.playback import Playback


def test_decision_config_loads_and_reaches_router(tmp_path, monkeypatch):
    from voice_layer.config import load

    config_dir = tmp_path / 'jarvis-voice'
    config_dir.mkdir()
    (config_dir / 'config.toml').write_text(
        '[decision]\nenabled = false\nmodel = "custom-model"\ntimeout_seconds = 1.5\n'
    )
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    decision = load().decision
    router = DecisionRouter(config=decision)
    assert not decision.enabled
    assert (router.model, router.timeout_seconds) == ('custom-model', 1.5)


def test_pcm_to_wav_conversion():
    """Verify raw PCM conversion to valid 16kHz mono WAV format."""
    raw_pcm = b'\x00\x00' * 1600  # 100ms of 16kHz 16-bit mono
    wav_bytes = pcm_to_wav(raw_pcm, sample_rate=16000, channels=1)

    assert wav_bytes.startswith(b'RIFF')
    assert b'WAVE' in wav_bytes[:12]

    # Verify WAV header params with wave module
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 1600

    # Idempotent if already WAV
    assert pcm_to_wav(wav_bytes) == wav_bytes


def test_acknowledgement_resolution():
    """Test mapping and resolution of decision ack clips to assets and phrases."""
    assert 'ack_short_sure' in DECISION_ACK_CRITERIA
    assert 'none' in DECISION_ACK_CRITERIA
    assert get_decision_ack_phrase('ack_short_sure') == 'Sure.'
    assert get_decision_ack_phrase('ack_short_on_it') == 'On it.'
    assert get_decision_ack_phrase('none') == ''
    assert get_decision_ack_phrase('nonexistent') == ''

    # Test asset path resolution
    sure_asset = resolve_ack_asset('ack_short_sure')
    assert sure_asset is not None
    assert sure_asset.exists()
    assert sure_asset.suffix in ('.pcm', '.wav')

    assert resolve_ack_asset('none') is None
    assert resolve_ack_asset('') is None


def test_execution_policy_safety_gate():
    """Verify safety check gates destructive actions and permits safe actions."""
    # Destructive commands that require confirmation
    assert requires_confirmation('reboot') is True
    assert requires_confirmation('shutdown the computer') is True
    assert requires_confirmation('poweroff') is True
    assert requires_confirmation('rm -rf /') is True
    assert requires_confirmation('system_control', {'action': 'shutdown'}) is True
    assert requires_confirmation('uninstall_app') is True
    assert requires_confirmation('execute_system_command', {'command': 'mkfs /dev/sda1'}) is True

    # Benign commands that do not require confirmation
    assert requires_confirmation('system_control', {'action': 'volume_set', 'value': 50}) is False
    assert requires_confirmation('set_brightness', {'value': 80}) is False
    assert requires_confirmation('open chrome') is False
    assert requires_confirmation('what is the weather?') is False
    assert requires_confirmation('read_file', {'path': '/tmp/test.txt'}) is False


@pytest.mark.asyncio
async def test_decision_router_with_mock_client():
    """Test single-pass evaluation with mock Google GenAI decision client."""
    mock_response = MagicMock()
    mock_response.answers = {
        'is_for_jarvis': NS(noul=True, confidence=0.98),
        'ack_clip': NS(choice='ack_short_on_it', confidence=0.95),
        'route': NS(choice='jarvis_control', confidence=0.92),
        'requires_confirmation': NS(noul=False, confidence=0.99),
    }

    mock_client = MagicMock()
    mock_client.aio.decisions.create = AsyncMock(return_value=mock_response)

    router = DecisionRouter(client=mock_client)
    result = await router.evaluate(b'\x00\x00' * 800, text='Set brightness to 80%')

    assert isinstance(result, DecisionResult)
    assert result.is_for_jarvis is True
    assert result.ack_clip == 'ack_short_on_it'
    assert result.route == 'jarvis_control'
    assert result.requires_confirmation is False
    assert result.confidence['is_for_jarvis'] == 0.98
    assert result.confidence['ack_clip'] == 0.95

    # Verify client was called with correct model
    mock_client.aio.decisions.create.assert_called_once()
    call_kwargs = mock_client.aio.decisions.create.call_args.kwargs
    assert call_kwargs['model'] == 'gemini-decision-1'
    assert 'is_for_jarvis' in call_kwargs['questions']
    assert 'ack_clip' in call_kwargs['questions']
    assert 'route' in call_kwargs['questions']
    assert 'requires_confirmation' in call_kwargs['questions']


@pytest.mark.asyncio
async def test_decision_router_safety_override():
    """Local safety policy acts as guardrail if model fails to flag destructive action."""
    mock_response = MagicMock()
    # Model hallucinated that rm -rf is not destructive
    mock_response.answers = {
        'is_for_jarvis': NS(noul=True, confidence=0.99),
        'ack_clip': NS(choice='ack_terminal', confidence=0.95),
        'route': NS(choice='jarvis_control', confidence=0.90),
        'requires_confirmation': NS(noul=False, confidence=0.90),
    }

    mock_client = MagicMock()
    mock_client.aio.decisions.create = AsyncMock(return_value=mock_response)

    router = DecisionRouter(client=mock_client)
    result = await router.evaluate(b'', text='rm -rf /home/user/data')

    # Local safety policy caught it and forced requires_confirmation=True
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_daemon_decision_gate_routes_without_speculative_acknowledgement():
    """Only the provider reply or an admitted action should produce speech."""
    player = Playback('test')
    voice = LiveVoice(player)
    voice._reply_authorized = True

    # Preload mock ack audio
    fake_pcm = b'\x05\x00' * 480
    voice._reply_notices['ack_short_sure'] = fake_pcm

    # Mock decision router returning positive for jarvis and ack_short_sure
    mock_decision = DecisionResult(
        is_for_jarvis=True,
        ack_clip='ack_short_sure',
        route='jarvis_memory',
        requires_confirmation=False,
    )
    voice.decision_router.evaluate = AsyncMock(return_value=mock_decision)

    token = (voice.gate.accepted_turns, voice.player.generation)
    buffered = [(NS(pcm=b'\x01\x00' * 320, opened=False, closed=False), voice.player.generation)]
    forwarded = asyncio.Queue()
    mock_session = MagicMock()

    handled = await voice._handle_decision_gate(
        b'\x01\x00' * 320, token, buffered, forwarded, mock_session
    )

    assert handled is True
    assert player.queue.empty()
    assert voice.last_acknowledgement == ''

    # The audio frames must have been forwarded to gemini_live session
    assert not forwarded.empty()
    forwarded_frame, forwarded_gen = forwarded.get_nowait()
    assert forwarded_frame.pcm == buffered[0][0].pcm
    assert forwarded_frame.barge_in is True
    assert forwarded_gen == buffered[0][1]


@pytest.mark.asyncio
async def test_daemon_decision_gate_addressability_rejection():
    """Room noise / background speech (is_for_jarvis=False) is dropped without playing audio."""
    player = Playback('test')
    voice = LiveVoice(player)

    fake_pcm = b'\x05\x00' * 480
    voice._reply_notices['ack_short_sure'] = fake_pcm

    # Utterance judged not for Jarvis
    mock_decision = DecisionResult(
        is_for_jarvis=False,
        ack_clip='none',
        route='gemini_live',
        requires_confirmation=False,
    )
    voice.decision_router.evaluate = AsyncMock(return_value=mock_decision)

    token = (voice.gate.accepted_turns, voice.player.generation)
    buffered = [(NS(pcm=b'\x01\x00' * 320, opened=False, closed=False), voice.player.generation)]
    forwarded = asyncio.Queue()
    mock_session = MagicMock()

    handled = await voice._handle_decision_gate(
        b'\x01\x00' * 320, token, buffered, forwarded, mock_session
    )

    assert handled is True
    # No audio queued
    assert player.queue.empty()
    # No frames forwarded
    assert forwarded.empty()


@pytest.mark.asyncio
async def test_daemon_decision_gate_safety_confirmation():
    """Destructive action is gated and held for confirmation."""
    player = Playback('test')
    voice = LiveVoice(player)

    mock_decision = DecisionResult(
        is_for_jarvis=True,
        ack_clip='ack_short_sure',
        route='jarvis_control',
        requires_confirmation=True,
    )
    voice.decision_router.evaluate = AsyncMock(return_value=mock_decision)
    voice._last_turn_text = 'reboot the computer'

    token = (voice.gate.accepted_turns, voice.player.generation)
    buffered = [(NS(pcm=b'\x01\x00' * 320, opened=True, closed=True), token[1])]
    forwarded = asyncio.Queue()

    handled = await voice._handle_decision_gate(
        b'\x01\x00' * 320, token, buffered, forwarded, MagicMock()
    )

    assert handled is True
    assert voice._decision_confirmation_turn == token[0]
    assert voice._decision_confirmation_text == 'reboot the computer'
    assert forwarded.get_nowait()[0].pcm == buffered[0][0].pcm


@pytest.mark.asyncio
async def test_offline_decision_gate_never_calls_provider():
    voice = LiveVoice(Playback('test'))
    voice.decision_router.evaluate = AsyncMock()
    token = (voice.gate.accepted_turns, voice.player.generation)
    assert not await voice._handle_decision_gate(b'local', token, [], asyncio.Queue(), None)
    voice.decision_router.evaluate.assert_not_awaited()
