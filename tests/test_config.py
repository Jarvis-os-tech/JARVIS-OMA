# tests/test_config.py
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_default_config():
    from jarvis_voice.config import Config
    c = Config()
    assert c.model == 'gemini-3.8-live'
    assert c.voice == 'Aoede'
    assert c.barge_in is False
    assert c.autostart_listening is True
    assert c.api_key_env == 'GEMINI_API_KEY'

def test_load_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / 'config.toml'
    toml.write_text('model = "gemini-2.0-flash-live"\nvoice = "Puck"\nbarge_in = false\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    (tmp_path / 'jarvis-voice').mkdir()
    (tmp_path / 'jarvis-voice' / 'config.toml').write_text(toml.read_text())
    from jarvis_voice.config import load
    c = load()
    assert c.model == 'gemini-2.0-flash-live'
    assert c.voice == 'Puck'
    assert c.barge_in is False

def test_unknown_setting_rejected(tmp_path, monkeypatch):
    (tmp_path / 'jarvis-voice').mkdir()
    (tmp_path / 'jarvis-voice' / 'config.toml').write_text('unknown_key = true\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    import pytest
    from jarvis_voice.config import load
    with pytest.raises(ValueError, match='Unsupported'):
        load()

def test_load_env_sets_key(tmp_path, monkeypatch):
    (tmp_path / 'jarvis-voice').mkdir()
    env_file = tmp_path / 'jarvis-voice' / 'env'
    env_file.write_text('GEMINI_API_KEY=test-key-12345\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    from jarvis_voice.config import load_env
    load_env()
    assert os.environ.get('GEMINI_API_KEY') == 'test-key-12345'

def test_runtime_paths():
    from jarvis_voice.config import RUNTIME_DIR, SOCKET_PATH, STATE_FILE
    assert RUNTIME_DIR.name == 'jarvis'
    assert SOCKET_PATH.name == 'control.sock'
    assert STATE_FILE.name == 'state.json'
