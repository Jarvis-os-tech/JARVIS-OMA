"""Install JARVIS in the user's desktop session without root privileges."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time


def _write(path: Path, content: str, *, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not path.is_symlink() and path.read_text() == content:
        if executable:
            path.chmod(0o755)
        return
    _backup(path)
    path.write_text(content)
    path.chmod(0o755 if executable else 0o644)


def _backup(path: Path):
    if path.exists() or path.is_symlink():
        path.rename(path.with_name(f'{path.name}.bak.{time.time_ns()}'))


def _link(path: Path, target: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() and path.readlink() == target:
        return
    _backup(path)
    path.symlink_to(target)


def _unit_path(path: Path, *, command=False, quoted=True):
    if not quoted:
        value = str(path).replace('%', '%%')
        if any(char in value for char in '\n\r\0'):
            raise ValueError('Desktop installation paths must not contain line breaks or NUL')
        return value
    value = str(path).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"')
    if any(char in value for char in '\n\r\0'):
        raise ValueError('Desktop installation paths must not contain line breaks or NUL')
    if command:
        value = value.replace('$', '$$')
    return f'"{value}"'


def _desktop_command(path: Path):
    # Desktop Entry quoting has an additional string-escape layer.
    value = str(path)
    for char in ('\\', '"', '$', '`'):
        value = value.replace(char, '\\' + char)
    value = value.replace('\\', '\\\\').replace('%', '%%')
    if any(char in value for char in '\n\r\0'):
        raise ValueError('Desktop launcher paths must not contain line breaks or NUL')
    return f'"{value}"'


def install(repo: Path, *, config_home: Path, data_home: Path, bin_home: Path):
    repo = repo.resolve()
    # Validate paths before changing the installation.
    # WorkingDirectory consumes a single literal path, unlike ExecStart's argv.
    working = _unit_path(repo, quoted=False)
    launcher = _unit_path(repo / 'run.sh', command=True)
    environment = _unit_path(repo / '.env', quoted=False)
    desktop_command = _desktop_command(bin_home / 'jarvisctl')
    unit = (repo / 'systemd/jarvis-oma.service').read_text()
    unit = unit.replace('WorkingDirectory=%h/Projects/JARVIS-OMA', f'WorkingDirectory={working}')
    unit = unit.replace('ExecStart=%h/Projects/JARVIS-OMA/run.sh', f'ExecStart={launcher}')
    unit = unit.replace('EnvironmentFile=-%h/Projects/JARVIS-OMA/.env', f'EnvironmentFile=-{environment}')
    # Reject invalid units before replacing the currently working installation.
    with tempfile.TemporaryDirectory(prefix='jarvis-service-') as directory:
        candidate = Path(directory) / 'jarvis-oma.service'
        candidate.write_text(unit)
        subprocess.run(['systemd-analyze', '--user', 'verify', str(candidate)], check=True)
    units = config_home / 'systemd/user'
    legacy = units / 'jarvis.service'
    # Retire an independently installed legacy unit before making it an alias.
    if legacy.exists() and not legacy.is_symlink():
        subprocess.run(['systemctl', '--user', 'stop', 'jarvis.service'], check=True)
        subprocess.run(['systemctl', '--user', 'disable', 'jarvis.service'], check=True)
    _write(units / 'jarvis-oma.service', unit)
    _link(legacy, Path('jarvis-oma.service'))
    for name in ('jarvis', 'jarvisctl'):
        _link(bin_home / name, repo / 'scripts' / name)

    # Omarchy invokes this with the current compositor environment at each login.
    # Import named variables only; credentials never enter the manager this way.
    hook = config_home / 'omarchy/hooks/post-boot.d/jarvis-desktop'
    _write(hook, '#!/usr/bin/env bash\nset -euo pipefail\n'
           f'exec {shlex.quote(str(repo / "scripts/desktop-session.sh"))}\n', executable=True)
    _write(data_home / 'applications/jarvis.desktop',
           '[Desktop Entry]\nType=Application\nName=JARVIS Voice\n'
           'Comment=Toggle JARVIS listening\nIcon=audio-input-microphone\n'
           f'Exec={desktop_command} toggle\n'
           'Terminal=false\nCategories=Utility;Accessibility;\n')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', 'jarvis-oma.service'], check=True)
    return hook


def main():
    repo = Path(__file__).resolve().parents[1]
    install(repo,
            config_home=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config'),
            data_home=Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share'),
            bin_home=Path.home() / '.local/bin')
    subprocess.run([str(repo / 'scripts/desktop-session.sh')], check=True)
    print('JARVIS installed: login startup, desktop launcher, jarvis and jarvisctl commands.')


if __name__ == '__main__':
    main()
