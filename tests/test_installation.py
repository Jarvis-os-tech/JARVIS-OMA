"""Exercise the real installer and its exposed commands outside the source cwd."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def test_installed_commands_and_distributed_config(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / 'installation'
    fake_bin = tmp_path / 'fake-bin'
    fake_bin.mkdir()
    systemctl = fake_bin / 'systemctl'
    systemctl.write_text('#!/bin/sh\nexit 0\n')
    systemctl.chmod(0o755)
    # Stub desktop audio utilities in fake-bin if missing in headless CI environments
    for tool in ('pw-record', 'pw-play', 'pw-cli', 'pactl'):
        if shutil.which(tool) is None:
            t = fake_bin / tool
            t.write_text('#!/bin/sh\nexit 0\n')
            t.chmod(0o755)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.update(JARVIS_INSTALL_HOME='installation',
               JARVIS_MEMORY_PATH=str(tmp_path / 'synthetic-state'),
               XDG_CONFIG_HOME=str(destination / '.config'),
               PATH=str(fake_bin) + os.pathsep + env['PATH'])
    def run(*args):
        result = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout
    run('bash', str(root / 'scripts/install.sh'))
    runtime = destination / '.local/share/jarvis-runtime'
    installed = runtime / 'current'
    assert installed.is_symlink()
    assert Path(os.readlink(installed)).is_absolute()
    assert installed.resolve().is_relative_to(runtime / 'releases')
    assert (installed / 'jarvis_memory/__init__.py').is_file()
    assert (installed / 'jarvis_control/omarchy_guides/SKILL.md').is_file()
    assert (installed / 'jarvis_control/web_text.py').is_file()
    assert (installed / 'voice_layer/background.py').is_file()
    assert (installed / 'skill_manifests/vision.json').is_file()
    interpreter = installed / '.venv/bin/python'
    run(str(interpreter), '-c',
        'import sys; sys.path.insert(0, ' + repr(str(installed)) + '); '
        'from skills.skills import DesktopSkills; from voice_layer.background import monitor; '
        'from orchestration.task_events import CONTRACT; import learning')

    service = (destination / '.config/systemd/user/jarvis-voice.service').read_text()
    assert '%h/.local/share/jarvis-runtime/current/bin/jarvis-voice run' in service
    assert '%h/.local/share/jarvis-runtime/current' in service

    exposed = destination / '.local/bin'
    assert 'usage:' in run(str(exposed / 'jarvis-voice'), '--help')
    assert 'PASS:' in run(str(exposed / 'jarvis-voice'), '--check')
    assert 'System Control' in run(str(exposed / 'jarvis'), '--help')
    assert 'usage:' in run(str(exposed / 'jarvis-control'), '--help')
    for command in ('task', 'vision', 'say', 'doctor'):
        assert 'usage:' in run(str(exposed / 'jarvis'), command, '--help')
    memory = str(exposed / 'jarvis-memory')
    assert 'remembered' in run(memory, '--json', 'store', 'Synthetic fixture prefers bronze notebooks')
    recalled = json.loads(run(memory, '--json', 'search', 'bronze'))
    assert any('bronze' in fact['text'] for fact in recalled['facts'])


def test_installer_preserves_existing_runtime_pointer_and_release(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / 'installation'
    runtime = destination / '.local/share/jarvis-runtime'
    current = runtime / 'current'
    release = runtime / 'releases/existing'
    release.mkdir(parents=True)
    for package in ('voice_layer', 'orchestration', 'contracts', 'learning', 'configs', 'core'):
        shutil.copytree(root / package, release / package)
    shutil.copy2(root / 'requirements.txt', release / 'requirements.txt')
    (release / 'bin').mkdir()
    for command in ('jarvis-voice', 'jarvis', 'jarvis-memory', 'jarvis-control'):
        entry = release / 'bin' / command
        entry.write_text('#!/bin/sh\nexit 0\n')
        entry.chmod(0o755)
    target_venv = (root / '.venv').resolve() if (root / '.venv').is_dir() else Path(sys.prefix).resolve()
    (release / '.venv').symlink_to(target_venv, target_is_directory=True)
    (release / 'release.json').write_text('{"commit":"existing","schema_version":1}')
    (release / 'user-state').write_text('keep')
    current.symlink_to(release)
    fake_bin = tmp_path / 'fake-bin'
    fake_bin.mkdir()
    systemctl = fake_bin / 'systemctl'
    systemctl.write_text('#!/bin/sh\nexit 0\n')
    systemctl.chmod(0o755)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.update(JARVIS_INSTALL_HOME=str(destination), PATH=str(fake_bin) + os.pathsep + env['PATH'])
    result = subprocess.run(['bash', str(root / 'scripts/install.sh')], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout
    assert current.resolve() == release
    assert (release / 'user-state').read_text() == 'keep'


def test_installer_rejects_incomplete_existing_runtime_without_repointing(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / 'installation'
    runtime = destination / '.local/share/jarvis-runtime'
    release = runtime / 'releases/incomplete'
    (release / '.venv/bin').mkdir(parents=True)
    (release / '.venv/bin/python').symlink_to(shutil.which('python3'))
    (release / 'release.json').write_text('{"commit":"incomplete","schema_version":1}')
    current = runtime / 'current'
    current.symlink_to(release)
    env = dict(os.environ, JARVIS_INSTALL_HOME=str(destination))
    result = subprocess.run(['bash', str(root / 'scripts/install.sh')], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert current.resolve() == release
    assert not (destination / '.local/bin/jarvis-voice').exists()


def test_missing_runtime_dependency_cannot_publish_current(tmp_path):
    root = Path(__file__).resolve().parents[1]
    shadow = tmp_path / 'shadow'
    shadow.mkdir()
    (shadow / 'google.py').write_text('# Simulate a Python environment without google.genai.\n')
    destination = tmp_path / 'installation'
    env = dict(os.environ, JARVIS_INSTALL_HOME=str(destination), PYTHONPATH=str(shadow))
    result = subprocess.run(['bash', str(root / 'scripts/install.sh')], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert 'Missing runtime dependencies: google.genai' in result.stderr
    assert not (destination / '.local/share/jarvis-runtime/current').is_symlink()
    assert not (destination / '.local/bin/jarvis-voice').exists()
