"""Keep offline tests independent of the developer's connected accounts."""
import os
import sys
from pathlib import Path

import pytest

from connectors import credentials
from core.secret_env import is_secret_name


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(runtime))
    # User PATH entries can include disconnected mounts. Discovery must not
    # stall the offline suite while probing those directories for each adapter.
    monkeypatch.setenv('PATH', os.pathsep.join((str(Path(sys.executable).parent),
                                              '/usr/local/bin', '/usr/bin', '/bin')))
    for name in tuple(os.environ):
        if is_secret_name(name):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(credentials, 'SECRET_DIR', tmp_path / 'connector-secrets')
