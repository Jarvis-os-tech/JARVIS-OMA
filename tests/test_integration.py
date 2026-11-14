"""Integration verification for the complete voice foundation."""
import pytest
from pathlib import Path


def test_all_modules_import():
    """Every voice_layer submodule imports without error."""
    import voice_layer
    from voice_layer import config, ipc, recovery, speech, playback, daemon
    assert voice_layer.__version__ == '0.1.0'


def test_config_to_daemon_integration():
    """Config loads and feeds into daemon correctly."""
    from voice_layer.config import Config
    from voice_layer.daemon import live_config
    c = Config(voice='Puck', model='gemini-2.0-flash-live')
    result = live_config(voice=c.voice)
    assert 'Puck' in str(result['speech_config'])


def test_recovery_in_daemon_context():
    """Recovery module integrates with daemon error handling."""
    from voice_layer.recovery import ConnectionRecovery
    r = ConnectionRecovery(retry_budget=3)
    d = r.decide(ConnectionError('closed'), session_opened=True, session_seconds=120)
    assert not d.fatal
    assert d.delay <= 2.0
