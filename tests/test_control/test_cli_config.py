"""Control CLI uses JARVIS settings and rejects invalid calls before dispatch."""
from unittest.mock import Mock

import pytest

from jarvis_control import __main__ as cli
from jarvis_control.tools import Result


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    directory = tmp_path / 'jarvis-voice'
    directory.mkdir()
    path = directory / 'config.toml'
    path.write_text('tasks_enabled = false\nvision_enabled = false\n')
    return path


def test_disabled_camera_and_tasks_are_not_dispatched(config_file, monkeypatch, capsys):
    executor = Mock()
    monkeypatch.setattr(cli, 'Executor', executor)
    for tool in ('camera_view', 'task_submit'):
        assert cli.main(['call', tool, '{}']) == 1
    executor.assert_not_called()
    assert 'Tool is not enabled' in capsys.readouterr().err


def test_non_object_arguments_are_rejected(config_file, monkeypatch, capsys):
    executor = Mock()
    monkeypatch.setattr(cli, 'Executor', executor)
    assert cli.main(['call', 'system_query', '[]']) == 1
    executor.assert_not_called()
    assert 'JSON object' in capsys.readouterr().err


def test_control_settings_and_dry_run_reach_executor(config_file, monkeypatch):
    config_file.write_text('''tasks_enabled = false
vision_enabled = false
[control.tasks]
max_active = 2
''')
    executor = Mock()
    executor.return_value.call.return_value = Result(True, 'synthetic result')
    monkeypatch.setattr(cli, 'Executor', executor)
    assert cli.main(['call', 'launch_app', '{"app":"firefox"}', '--dry-run']) == 0
    config = executor.call_args.args[0]
    assert config.dry_run
    assert config.tasks_max_active == 2
    assert not config.tasks_enabled
    executor.return_value.call.assert_called_once_with('launch_app', {'app': 'firefox'})


def test_vision_command_uses_shared_settings(config_file, monkeypatch, capsys):
    import json
    config_file.write_text('''vision_enabled = true
[control.vision]
model = "synthetic-camera-model"
''')
    client = Mock()
    client.return_value.call.return_value = {'ok': True, 'active': False}
    monkeypatch.setattr('jarvis_control.vision.VisionClient', client)
    assert cli.main(['vision', 'inspect', 'this', 'connector', '--region', '0', '0', '500', '500']) == 0
    assert client.call_args.args[0].vision_model == 'synthetic-camera-model'
    client.return_value.call.assert_called_once_with('inspect', 'this connector', [0, 0, 500, 500])
    assert json.loads(capsys.readouterr().out)['ok']


def test_task_submit_is_blocked_when_disabled(config_file, monkeypatch, tmp_path):
    submit = Mock()
    monkeypatch.setattr('jarvis_control.cli.cmd_task', submit)
    assert cli.main(['task', 'submit', str(tmp_path / 'spec.json')]) == 1
    submit.assert_not_called()


def test_task_resume_and_typed_request_use_shared_config(config_file, monkeypatch):
    config_file.write_text('''tasks_enabled = true
[control.tasks]
model = "synthetic-worker-model"
''')
    task = Mock(return_value=0)
    say = Mock(return_value=0)
    monkeypatch.setattr('jarvis_control.cli.cmd_task', task)
    monkeypatch.setattr('jarvis_control.cli.cmd_say', say)
    assert cli.main(['task', '--dry-run', 'resume', 'synthetic', '--guidance', 'continue checks']) == 0
    args, config = task.call_args.args
    assert args.guidance == 'continue checks' and config.dry_run
    assert config.tasks_model == 'synthetic-worker-model'
    assert cli.main(['say', '--dry-run', 'open', 'a', 'terminal']) == 0
    args, config = say.call_args.args
    assert args.text == ['open', 'a', 'terminal'] and config.dry_run


def test_doctor_checks_jarvis_settings_without_disclosing_credentials(config_file, monkeypatch, capsys):
    import json
    from jarvis_control import diagnostics
    config_file.write_text('''api_key_env = "SYNTHETIC_VOICE_KEY"
tasks_enabled = false
vision_enabled = false
''')
    monkeypatch.setenv('SYNTHETIC_VOICE_KEY', 'synthetic-secret-not-for-output')
    monkeypatch.setattr(diagnostics.shutil, 'which', lambda command: '/synthetic/' + command)
    monkeypatch.setattr(diagnostics.importlib.util, 'find_spec', lambda name: object())
    assert cli.main(['doctor', '--json']) == 0
    output = capsys.readouterr().out
    assert 'synthetic-secret-not-for-output' not in output
    report = json.loads(output)
    assert report['checks']['voice credential']['detail'] == 'SYNTHETIC_VOICE_KEY'
    assert not report['tasks_enabled'] and not report['vision_enabled']
