import os
from pathlib import Path
import subprocess
import wave
import pytest

from core.system_monitor import AlertAudioEngine, DesktopNotifier, SUPPORTED_ALERTS


def test_supported_alerts_list():
    expected = {
        "network_down",
        "server_down",
        "cpu_overload",
        "memory_critical",
        "disk_exhaustion",
        "service_failure",
        "thermal_critical",
        "recovery",
    }
    assert expected.issubset(set(SUPPORTED_ALERTS.keys()))


def test_synthesize_all_alert_types(tmp_path):
    engine = AlertAudioEngine(cache_dir=tmp_path / "alerts")
    for alert_name in SUPPORTED_ALERTS:
        wav_path = engine.synthesize_alert_wav(alert_name)
        assert wav_path.exists(), f"Failed to synthesize {alert_name}"
        assert wav_path.stat().st_size > 500, f"File too small for {alert_name}"

        # Verify it is a valid 16-bit PCM WAV
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            n_frames = wf.getnframes()
            assert n_frames > 2000  # at least ~0.05s of audio


def test_synthesis_caching(tmp_path):
    engine = AlertAudioEngine(cache_dir=tmp_path / "alerts")
    wav_path1 = engine.synthesize_alert_wav("recovery")
    mtime1 = wav_path1.stat().st_mtime_ns

    wav_path2 = engine.synthesize_alert_wav("recovery")
    mtime2 = wav_path2.stat().st_mtime_ns

    assert wav_path1 == wav_path2
    assert mtime1 == mtime2


def test_audio_player_detection():
    engine = AlertAudioEngine()
    player_cmd = engine.detect_player()
    # On Omarchy/Linux, at least one of pw-play, paplay, aplay, mpv is available
    assert player_cmd is not None
    assert player_cmd[0] in ("pw-play", "paplay", "aplay", "mpv", "ffplay", "canberra-gtk-play")


def test_desktop_notifier_mock(monkeypatch):
    called = []

    class FakePopen:
        def __init__(self, cmd, *args, **kwargs):
            called.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    notifier = DesktopNotifier()
    notifier.notify("Test Alert", "Testing message", urgency="critical")

    assert len(called) == 1
    assert "notify-send" in called[0][0]
    assert "Test Alert" in called[0]
    assert "Testing message" in called[0]
