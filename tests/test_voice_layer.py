"""Tests for the consolidated voice_layer package."""
import pytest


def test_voice_layer_exports():
    import voice_layer
    from voice_layer import (
        LiveVoice,
        EchoCancellation,
        SpeechTurnGate,
        Playback,
        ControlServer,
        ConnectionRecovery,
        OpenWakeWordDetector,
    )

    assert LiveVoice is not None
    assert EchoCancellation is not None
    assert SpeechTurnGate is not None
    assert Playback is not None
    assert ControlServer is not None
    assert ConnectionRecovery is not None
    assert OpenWakeWordDetector is not None


def test_voice_layer_recovery():
    from voice_layer.recovery import ConnectionRecovery, RecoveryDecision

    recovery = ConnectionRecovery(retry_budget=3)
    decision = recovery.decide(Exception("test"), None)
    assert isinstance(decision, RecoveryDecision)


def test_voice_layer_echo():
    from voice_layer.echo import EchoCancellation, monitor_properties

    echo = EchoCancellation()
    assert echo is not None
    props = monitor_properties("mic", "speaker", "test_aec")
    assert props["monitor.mode"] is True
