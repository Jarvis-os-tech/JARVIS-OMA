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


def test_input_and_output_devices_are_independent(tmp_path, monkeypatch):
    from jarvis_voice.config import load

    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text('device = "microphone"\noutput_device = "speakers"\n')
    config = load()
    assert config.device == 'microphone'
    assert config.output_device == 'speakers'


def test_distributed_example_loads_with_memory(tmp_path, monkeypatch):
    from jarvis_voice.config import load
    folder = tmp_path / 'jarvis-voice'
    folder.mkdir()
    (folder / 'config.toml').write_text((Path(__file__).parents[1] / 'configs/config.toml.example').read_text())
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    config = load()
    assert config.memory.enabled
    config.memory.validate()


def test_invalid_voice_boolean_is_rejected(tmp_path, monkeypatch):
    import pytest
    from jarvis_voice.config import load
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text('barge_in = "false"\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with pytest.raises(ValueError, match='barge_in must be a boolean'):
        load()


def test_configured_credential_name_is_loaded(tmp_path, monkeypatch):
    from jarvis_voice.config import load_env
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'env').write_text('CUSTOM_VOICE_KEY=synthetic-test-value\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.delenv('CUSTOM_VOICE_KEY', raising=False)
    load_env('CUSTOM_VOICE_KEY')
    assert os.environ['CUSTOM_VOICE_KEY'] == 'synthetic-test-value'
    monkeypatch.delenv('CUSTOM_VOICE_KEY')


def test_control_sections_share_voice_switches_and_preserve_policy(tmp_path, monkeypatch):
    from jarvis_voice.config import load, control_config
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text('''tasks_enabled = false
vision_enabled = false
[control]
allow_shell = true
confirm_patterns = ["custom-danger"]
[control.tasks]
max_active = 2
root = "/tmp/jarvis-synthetic-tasks"
[control.vision]
model = "synthetic-vision"
''')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    control = control_config(load())
    assert control.tasks_max_active == 2
    assert control.tasks_root == '/tmp/jarvis-synthetic-tasks'
    assert control.vision_model == 'synthetic-vision'
    assert not control.allow_shell
    assert not control.tasks_enabled
    assert not control.vision_enabled
    assert 'custom-danger' in control.confirm_patterns
    assert len(control.confirm_patterns) > 1


def test_invalid_control_settings_fail_before_startup():
    import pytest
    from jarvis_voice.config import Config
    with pytest.raises(ValueError, match='Unsupported control setting'):
        Config(control={'tasks': {'typo': 2}}).validate()
    with pytest.raises(ValueError, match='tasks.max_active'):
        Config(control={'tasks': {'max_active': 0}}).validate()


def test_barge_in_calibration_config(tmp_path, monkeypatch):
    from jarvis_voice.config import load
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text(
        'barge_in = true\n'
        'barge_in_min_rms = 0.005\n'
        'barge_in_echo_threshold = 0.70\n'
        'barge_in_vad_threshold = 0.55\n'
    )
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    config = load()
    assert config.barge_in is True
    assert config.barge_in_min_rms == 0.005
    assert config.barge_in_echo_threshold == 0.70
    assert config.barge_in_vad_threshold == 0.55


def test_invalid_barge_in_calibration_rejected(tmp_path, monkeypatch):
    import pytest
    from jarvis_voice.config import load
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text('barge_in_min_rms = "invalid"\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with pytest.raises(ValueError, match='barge_in_min_rms must be a positive number'):
        load()


def test_language_config_loaded_and_validated(tmp_path, monkeypatch):
    import pytest
    from jarvis_voice.config import load, Config
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text(
        'language = "en-IN"\n'
        'language_codes = ["en-IN", "en-US"]\n'
    )
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    config = load()
    assert config.language == 'en-IN'
    assert config.language_codes == ['en-IN', 'en-US']

    with pytest.raises(ValueError, match='language_codes must be a list'):
        Config(language_codes="invalid").validate()


def test_standby_config_loaded_and_validated(tmp_path, monkeypatch):
    import pytest
    from jarvis_voice.config import load, Config, StandbyConfig
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text(
        '[standby]\n'
        'enabled = true\n'
        'threshold = 0.08\n'
        'vad_threshold = 0.1\n'
    )
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    config = load()
    assert config.standby.enabled is True
    assert config.standby.threshold == 0.08
    assert config.standby.vad_threshold == 0.1

    with pytest.raises(ValueError, match='standby.threshold must be between'):
        Config(standby=StandbyConfig(threshold=1.5)).validate()


