import os
import subprocess
from pathlib import Path
import pytest
from scripts import jarvis_mode

_RUNTIME_CURRENT = Path.home() / ".local" / "share" / "jarvis-runtime" / "current"
_SYSTEMD_SERVICE = Path.home() / ".config" / "systemd" / "user" / "jarvis-voice.service"

def test_voice_layer_symlink_matches_configured_mode():
    home = Path.home()
    voice_share = home / ".local" / "share" / "jarvis-voice"
    if voice_share.is_symlink():
        target = voice_share.resolve()
        expected = (jarvis_mode.TEST_ROOT if jarvis_mode.DROPIN.exists()
                    else jarvis_mode.PRODUCTION_ROOT).resolve()
        assert target == expected, f"{voice_share} points to {target}, but configured mode requires {expected}"
    elif voice_share.is_dir():
        # Directory must not be the repo directory
        assert voice_share.resolve() != Path(__file__).resolve().parents[1]

@pytest.mark.skipif(not _RUNTIME_CURRENT.exists(), reason="Requires locally installed jarvis-runtime")
def test_jarvis_runtime_current_exists_and_compiled():
    home = Path.home()
    current = home / ".local" / "share" / "jarvis-runtime" / "current"
    assert current.is_dir(), f"Expected {current} to exist as an active release directory"
    assert (current / "release.json").is_file(), f"Missing release.json in {current}"
    assert (current / "bin" / "jarvis-voice").is_file(), f"Missing jarvis-voice in {current}/bin"

    # Verify bytecode files exist
    pyc_files = list((current / "voice_layer").rglob("*.pyc")) or list((current / "jarvis_voice").rglob("*.pyc"))
    assert len(pyc_files) > 0, f"Expected compiled .pyc files in {current}/voice_layer or {current}/jarvis_voice, found none"

@pytest.mark.skipif(not _SYSTEMD_SERVICE.exists(), reason="Requires locally installed systemd service")
def test_systemd_services_point_to_standalone_runtime():
    home = Path.home()
    voice_service = home / ".config" / "systemd" / "user" / "jarvis-voice.service"
    assert voice_service.is_file(), f"Missing {voice_service}"
    content = voice_service.read_text()
    assert "jarvis-runtime/current" in content, "jarvis-voice.service does not point to jarvis-runtime/current"
    assert "TimeoutStopSec=" in content
    assert "KillMode=mixed" in content
