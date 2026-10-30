"""Integration verification for the complete voice foundation."""
import pytest
from pathlib import Path


def test_all_modules_import():
    """Every jarvis_voice submodule imports without error."""
    import jarvis_voice
    from jarvis_voice import config, ipc, recovery, speech, playback, daemon
    assert jarvis_voice.__version__ == '0.1.0'


def test_voice_lock_files_untouched():
    """Verify zero modifications to locked voice core files in JARVIS-OMA."""
    lock_file = Path('/home/g0pi/Projects/JARVIS-OMA/audio/.voice_lock.json')
    if lock_file.exists():
        import json
        manifest = json.loads(lock_file.read_text())
        for entry in manifest.get('files', []):
            path = Path('/home/g0pi/Projects/JARVIS-OMA') / entry['path']
            if path.exists():
                import hashlib
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                assert actual == entry['sha256'], f'{entry["path"]} was modified!'


def test_config_to_daemon_integration():
    """Config loads and feeds into daemon correctly."""
    from jarvis_voice.config import Config
    from jarvis_voice.daemon import live_config
    c = Config(voice='Puck', model='gemini-2.0-flash-live')
    result = live_config(voice=c.voice)
    assert 'Puck' in str(result['speech_config'])


def test_recovery_in_daemon_context():
    """Recovery module integrates with daemon error handling."""
    from jarvis_voice.recovery import ConnectionRecovery
    r = ConnectionRecovery(retry_budget=3)
    d = r.decide(ConnectionError('closed'), session_opened=True, session_seconds=120)
    assert not d.fatal
    assert d.delay <= 2.0
