import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize('initialized,explicit,disabled,expected', [
    (False, None, '0', '<unset>'),
    (True, None, '0', 'auto'),
    (True, '/chosen/private/state', '0', '/chosen/private/state'),
    (True, '', '0', ''),
    (True, '/chosen/private/state', '1', '<unset>'),
])
def test_normal_startup_selects_only_initialized_or_explicit_learning_state(
        tmp_path, initialized, explicit, disabled, expected):
    source = Path(__file__).resolve().parents[2] / 'run.sh'
    script = tmp_path / 'run.sh'
    script.write_text(source.read_text())
    python = tmp_path / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/usr/bin/env bash\nif [[ "${1-}" == "-m" ]]; then exit 0; fi\n'
                      'printf "%s" "${JARVIS_LEARNING_DIR-<unset>}"\n')
    python.chmod(0o700)
    if initialized:
        directory = tmp_path / '.jarvis-learning'
        directory.mkdir()
        (directory / 'active.json').write_text('{}')
    env = dict(os.environ)
    env.pop('JARVIS_LEARNING_DIR', None)
    env['JARVIS_LEARNING_DISABLED'] = disabled
    if explicit is not None:
        env['JARVIS_LEARNING_DIR'] = explicit
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (str(tmp_path / '.jarvis-learning') if expected == 'auto' else expected)
