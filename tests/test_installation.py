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
    env.update(JARVIS_INSTALL_HOME=str(destination),
               JARVIS_MEMORY_PATH=str(tmp_path / 'synthetic-state'),
               XDG_CONFIG_HOME=str(destination / '.config'),
               PATH=str(fake_bin) + os.pathsep + env['PATH'])
    def run(*args):
        result = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout
    run('bash', str(root / 'scripts/install.sh'))
    installed = destination / '.local/share/jarvis-voice'
    assert (installed / 'jarvis_memory/__init__.py').is_file()
    assert (installed / 'jarvis_control/omarchy_guides/SKILL.md').is_file()
    assert (installed / 'jarvis_control/web_text.py').is_file()
    assert (installed / 'jarvis_voice/background.py').is_file()
    assert (installed / 'skill_manifests/vision.json').is_file()
    interpreter = installed / '.venv/bin/python'
    run(str(interpreter), '-c',
        'import sys; sys.path.insert(0, ' + repr(str(installed)) + '); '
        'from skills.skills import DesktopSkills; from jarvis_voice.background import monitor')

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
