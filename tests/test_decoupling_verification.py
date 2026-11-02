import os
import subprocess
from pathlib import Path
import pytest

_RUNTIME_CURRENT = Path.home() / ".local" / "share" / "jarvis-runtime" / "current"
_SYSTEMD_SERVICE = Path.home() / ".config" / "systemd" / "user" / "jarvis-voice.service"

def test_jarvis_voice_symlink_not_pointing_to_repo():
    home = Path.home()
    voice_share = home / ".local" / "share" / "jarvis-voice"
    repo_dir = Path(__file__).resolve().parents[1].resolve()

    if voice_share.is_symlink():
        target = voice_share.resolve()
        assert target != repo_dir, f"CRITICAL: {voice_share} is still directly pointing to dev repo {repo_dir}!"
    elif voice_share.is_dir():
        # Directory must not be the repo directory
        assert voice_share.resolve() != repo_dir

@pytest.mark.skipif(not _RUNTIME_CURRENT.exists(), reason="Requires locally installed jarvis-runtime")
def test_jarvis_runtime_current_exists_and_compiled():
    home = Path.home()
    current = home / ".local" / "share" / "jarvis-runtime" / "current"
    assert current.is_dir(), f"Expected {current} to exist as an active release directory"
    assert (current / "release.json").is_file(), f"Missing release.json in {current}"
    assert (current / "bin" / "jarvis-voice").is_file(), f"Missing jarvis-voice in {current}/bin"

    # Verify bytecode files exist
    pyc_files = list((current / "jarvis_voice").rglob("*.pyc"))
    assert len(pyc_files) > 0, f"Expected compiled .pyc files in {current}/jarvis_voice, found none"

@pytest.mark.skipif(not _SYSTEMD_SERVICE.exists(), reason="Requires locally installed systemd service")
def test_systemd_services_point_to_standalone_runtime():
    home = Path.home()
    voice_service = home / ".config" / "systemd" / "user" / "jarvis-voice.service"
    assert voice_service.is_file(), f"Missing {voice_service}"
    content = voice_service.read_text()
    assert "jarvis-runtime/current" in content, "jarvis-voice.service does not point to jarvis-runtime/current"
    assert "TimeoutStopSec=" in content
    assert "KillMode=mixed" in content
