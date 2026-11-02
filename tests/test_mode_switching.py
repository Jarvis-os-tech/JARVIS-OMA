import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest
import scripts.jarvis_mode as jm


@pytest.fixture
def mode_paths(tmp_path, monkeypatch):
    for name, path in {
        'TEST_ROOT': tmp_path / 'JARVIS OS',
        'PRODUCTION_ROOT': tmp_path / 'runtime/current',
        'DROPIN': tmp_path / 'voice.d/mode.conf',
        'BRIDGE_DROPIN': tmp_path / 'bridge.d/mode.conf',
        'SHARE_VOICE': tmp_path / 'share/jarvis-voice',
        'BIN_DIR': tmp_path / 'bin',
        'LOCK_FILE': tmp_path / 'mode.lock',
    }.items():
        monkeypatch.setattr(jm, name, path)
    for root in (jm.TEST_ROOT, jm.PRODUCTION_ROOT):
        (root / 'bin').mkdir(parents=True)
        (root / 'bin/jarvis-voice').touch()
        (root / 'bin/jarvis').touch()
        (root / 'jarvis_voice').mkdir()
    for python in (jm.TEST_ROOT / '.venv/bin/python', jm.PRODUCTION_ROOT.parent / 'venv/bin/python'):
        python.parent.mkdir(parents=True)
        python.touch()
    return tmp_path


def test_installed_release_uses_real_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.delenv('JARVIS_TEST_ROOT', raising=False)
    assert jm.get_test_root() == tmp_path / 'JARVIS OS'


def test_switch_roundtrip(mode_paths):
    with patch.object(jm, 'restart_services'), patch.object(jm, 'verify_mode', return_value=True) as verify:
        assert jm.switch_mode('test')['status'] == 'success'
        assert f'WorkingDirectory={jm.TEST_ROOT}\n' in jm.DROPIN.read_text()
        assert f'Environment="PYTHONPATH={jm.TEST_ROOT}"' in jm.DROPIN.read_text()
        assert jm.SHARE_VOICE.resolve() == jm.TEST_ROOT
        verify.assert_called_with(jm.TEST_ROOT)
        assert jm.switch_mode('prod')['status'] == 'success'
        assert not jm.DROPIN.exists()
        assert not jm.BRIDGE_DROPIN.exists()
        assert jm.SHARE_VOICE.resolve() == jm.PRODUCTION_ROOT
        verify.assert_called_with(jm.PRODUCTION_ROOT)


def test_failed_switch_restores_files_and_links(mode_paths):
    jm.BRIDGE_DROPIN.parent.mkdir()
    jm.BRIDGE_DROPIN.write_text('old bridge')
    jm._update_symlinks(jm.PRODUCTION_ROOT)
    with patch.object(jm, 'restart_services'), patch.object(jm, 'verify_mode', return_value=False):
        with pytest.raises(RuntimeError, match='original configuration restored'):
            jm.switch_mode('test')
    assert not jm.DROPIN.exists()
    assert jm.BRIDGE_DROPIN.read_text() == 'old bridge'
    assert jm.SHARE_VOICE.resolve() == jm.PRODUCTION_ROOT


def test_restart_timeout_is_not_success(mode_paths):
    with patch.object(jm, 'restart_services', side_effect=[subprocess.TimeoutExpired('restart', 30), True]):
        with pytest.raises(RuntimeError, match='original configuration restored'):
            jm.switch_mode('test')
    assert not jm.DROPIN.exists()
    assert not jm.SHARE_VOICE.is_symlink()


def test_live_status_overrides_requested_configuration(mode_paths):
    jm.DROPIN.parent.mkdir()
    jm.DROPIN.write_text('test configured')
    with patch.object(jm, '_service_state', return_value={'ActiveState': 'active', 'MainPID': str(os.getpid())}), \
         patch.object(jm, '_running_at', side_effect=[False, True]):
        assert jm.current_mode()['mode'] == 'production'


def test_running_at_rejects_wrong_process_cwd(mode_paths):
    state = {'ActiveState': 'active', 'MainPID': str(os.getpid()), 'WorkingDirectory': str(jm.TEST_ROOT)}
    assert not jm._running_at(state, jm.TEST_ROOT)


def test_schedule_runs_outside_voice_service(mode_paths):
    with patch.object(jm.subprocess, 'run') as run:
        assert jm.schedule_mode_switch('dev')['target_mode'] == 'test'
    command = run.call_args.args[0]
    assert command[:3] == ['systemd-run', '--user', '--collect']
    assert '--delay' in command


def test_incomplete_target_fails_before_writing(mode_paths):
    (jm.TEST_ROOT / '.venv/bin/python').unlink()
    with pytest.raises(RuntimeError, match='incomplete'):
        jm.switch_mode('test')
    assert not jm.DROPIN.exists()


def test_regular_file_is_preserved(mode_paths):
    jm.BIN_DIR.mkdir()
    (jm.BIN_DIR / 'jarvis').write_text('do not delete')
    with pytest.raises(RuntimeError, match='regular path'):
        jm.switch_mode('test')
    assert (jm.BIN_DIR / 'jarvis').read_text() == 'do not delete'


def test_voice_control_tool_schedules_switch(mode_paths):
    from jarvis_control.config import Config
    from jarvis_control.tools import Executor
    with patch.object(jm, 'schedule_mode_switch', return_value={'message': 'Switch scheduled'}) as schedule:
        result = Executor(Config()).call('switch_jarvis_mode', {'mode': 'test'})
    assert result.ok
    schedule.assert_called_once_with('test')


def test_explicit_restart_clears_start_limit():
    with patch.object(jm.subprocess, 'run') as run:
        jm.restart_services()
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[1] == ['systemctl', '--user', 'reset-failed', *jm.SERVICES]
    assert commands[2] == ['systemctl', '--user', 'restart', *jm.SERVICES]
