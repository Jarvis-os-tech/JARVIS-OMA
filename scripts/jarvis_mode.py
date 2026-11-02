#!/usr/bin/env python3
"""Switch JARVIS between its standalone runtime and development workspace."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import uuid


def get_production_root() -> Path:
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'jarvis-runtime/current'


def get_test_root() -> Path:
    # A copied release also contains jarvis_voice; it is never the test workspace.
    return Path(os.environ.get('JARVIS_TEST_ROOT', Path.home() / 'JARVIS OS')).resolve()


PRODUCTION_ROOT = get_production_root()
TEST_ROOT = get_test_root()
CONFIG_ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
DROPIN_DIR = CONFIG_ROOT / 'systemd/user/jarvis-voice.service.d'
DROPIN = DROPIN_DIR / 'mode.conf'
BRIDGE_DROPIN_DIR = CONFIG_ROOT / 'systemd/user/jarvis-device-bridge.service.d'
BRIDGE_DROPIN = BRIDGE_DROPIN_DIR / 'mode.conf'
SHARE_VOICE = PRODUCTION_ROOT.parent.parent / 'jarvis-voice'
BIN_DIR = Path.home() / '.local/bin'
LOCK_FILE = PRODUCTION_ROOT.parent / 'mode.lock'
SERVICES = ('jarvis-voice.service', 'jarvis-device-bridge.service')
MODES = {'production': ('JARVIS-OS', PRODUCTION_ROOT), 'test': ('workspace', TEST_ROOT)}


def _normalize(mode: str) -> str:
    aliases = {'test': 'test', 'dev': 'test', 'prod': 'production', 'production': 'production'}
    try:
        return aliases[mode.lower().strip()]
    except KeyError:
        raise ValueError("Choose 'test' or 'production'.") from None


def _atomic_link(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_symlink():
        raise RuntimeError(f'Refusing to replace regular file or directory: {path}')
    temporary = path.with_name(path.name + '.mode-tmp')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    temporary.replace(path)


def _update_symlinks(target_root: Path) -> None:
    _atomic_link(SHARE_VOICE, target_root)
    for cli in ('jarvis', 'jarvis-voice', 'jarvis-control', 'jarvis-memory'):
        target = target_root / 'bin' / cli
        if target.is_file():
            _atomic_link(BIN_DIR / cli, target)


def restart_services() -> bool:
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, capture_output=True, timeout=10)
    # Explicit user-requested switches must work after earlier failed starts.
    subprocess.run(['systemctl', '--user', 'reset-failed', *SERVICES],
                   check=True, capture_output=True, timeout=10)
    subprocess.run(['systemctl', '--user', 'restart', *SERVICES],
                   check=True, capture_output=True, timeout=30)
    return True


def _service_state(service: str) -> dict[str, str]:
    result = subprocess.run(['systemctl', '--user', 'show', service, '-p', 'ActiveState',
                             '-p', 'MainPID', '-p', 'WorkingDirectory'],
                            check=True, capture_output=True, text=True, timeout=3)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def _running_at(state: dict[str, str], root: Path) -> bool:
    try:
        pid = int(state.get('MainPID', '0'))
        return (state.get('ActiveState') == 'active' and pid > 0
                and Path(state.get('WorkingDirectory', '')).resolve() == root.resolve()
                and Path(f'/proc/{pid}/cwd').resolve(strict=True) == root.resolve())
    except (OSError, ValueError):
        return False


def verify_mode(root: Path, timeout: float = 8) -> bool:
    deadline = time.monotonic() + timeout
    healthy_since = None
    while time.monotonic() < deadline:
        try:
            healthy = all(_running_at(_service_state(service), root) for service in SERVICES)
        except (OSError, subprocess.SubprocessError):
            healthy = False
        now = time.monotonic()
        if healthy:
            healthy_since = now if healthy_since is None else healthy_since
            if now - healthy_since >= 1:
                return True
        else:
            healthy_since = None
        time.sleep(0.25)
    return False


def current_mode() -> dict[str, Any]:
    configured = 'test' if DROPIN.exists() else 'production'
    mode = configured
    root = TEST_ROOT if mode == 'test' else PRODUCTION_ROOT
    active = False
    pid = None
    try:
        state = _service_state(SERVICES[0])
        active = state.get('ActiveState') == 'active'
        pid = int(state.get('MainPID', '0')) or None
        if active:
            if _running_at(state, TEST_ROOT):
                mode, root = 'test', TEST_ROOT
            elif _running_at(state, PRODUCTION_ROOT):
                mode, root = 'production', PRODUCTION_ROOT
            else:
                mode, root = 'unknown', Path(state.get('WorkingDirectory', '/'))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return {'status': 'active' if active else 'inactive', 'mode': mode,
            'configured_mode': configured, 'branch': MODES.get(mode, ('unknown', root))[0],
            'root': str(root), 'service_active': active, 'pid': pid}


def _dropin(root: Path, executable: Path, arguments: str) -> str:
    # WorkingDirectory takes the whole value literally; ExecStart and Environment
    # use systemd's word parser and need quoting around the complete argument.
    raw = str(root).replace('%', '%%')
    command = str(executable).replace('%', '%%')
    return ('[Service]\n' + f'WorkingDirectory={raw}\nExecStart=\n'
            + f'ExecStart={json.dumps(command)} {arguments}\n'
            + f'Environment={json.dumps("PYTHONPATH=" + raw)}\n')


@contextmanager
def _mode_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another mode switch is already running.') from None
        yield


def switch_mode(mode: str, *, restart: bool = True, sync: bool = False) -> dict[str, Any]:
    if mode == 'status':
        return current_mode()
    mode = _normalize(mode)
    root = TEST_ROOT if mode == 'test' else PRODUCTION_ROOT
    python = TEST_ROOT / '.venv/bin/python' if mode == 'test' else PRODUCTION_ROOT.parent / 'venv/bin/python'
    for required in (root / 'bin/jarvis-voice', root / 'jarvis_voice', python):
        if not required.exists():
            raise RuntimeError(f'Mode target is incomplete: {required}')
    with _mode_lock():
        paths = (DROPIN, BRIDGE_DROPIN)
        files = {p: p.read_bytes() if p.exists() else None for p in paths}
        links = {p: os.readlink(p) if p.is_symlink() else None for p in
                 (SHARE_VOICE, *(BIN_DIR / n for n in ('jarvis', 'jarvis-voice', 'jarvis-control', 'jarvis-memory')))}
        for path, target in links.items():
            if target is None and path.exists():
                raise RuntimeError(f'Refusing to replace regular path: {path}')
        try:
            if mode == 'test':
                DROPIN.parent.mkdir(parents=True, exist_ok=True)
                BRIDGE_DROPIN.parent.mkdir(parents=True, exist_ok=True)
                DROPIN.write_text(_dropin(root, root / 'bin/jarvis-voice', 'run'))
                BRIDGE_DROPIN.write_text(_dropin(root, python, '-m jarvis_control.device_bridge'))
            else:
                for path in paths:
                    path.unlink(missing_ok=True)
            _update_symlinks(root)
            if restart:
                restart_services()
                if not verify_mode(root):
                    raise RuntimeError('Both services must be healthy and running from the requested root')
        except Exception as error:
            for path, data in files.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            for path, target in links.items():
                if target is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_link(path, Path(target))
            if restart:
                try:
                    restart_services()
                except Exception as recovery_error:
                    raise RuntimeError(f'Mode switch failed: {error}; recovery restart failed: {recovery_error}') from error
            raise RuntimeError(f'Mode switch failed; original configuration restored: {error}') from error
    return {'status': 'success' if restart else 'configured', 'mode': mode,
            'branch': MODES[mode][0], 'root': str(root), 'restarted': restart,
            'message': f'JARVIS {mode} mode {"activated and verified" if restart else "configured"} at {root}.'}


def schedule_mode_switch(mode: str, delay: float = 2) -> dict[str, Any]:
    """Run outside the voice service so restarting it cannot kill the switch."""
    mode = _normalize(mode)
    unit = 'jarvis-mode-' + uuid.uuid4().hex[:12]
    subprocess.run(['systemd-run', '--user', '--collect', '--unit', unit,
                    sys.executable, str(Path(__file__).resolve()), mode, '--delay', str(delay)],
                   check=True, capture_output=True, text=True, timeout=10)
    return {'status': 'switching', 'target_mode': mode, 'unit': unit,
            'root': str(TEST_ROOT if mode == 'test' else PRODUCTION_ROOT),
            'message': f'Switching to {mode} mode. Restarting JARVIS service in two seconds.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=('production', 'prod', 'test', 'dev', 'status'), default='status')
    parser.add_argument('--no-restart', action='store_true')
    parser.add_argument('--delay', type=float, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.delay:
            time.sleep(max(0, args.delay))
        result = switch_mode(args.mode, restart=not args.no_restart)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    if args.mode == 'status':
        print(f"JARVIS Mode: {result['mode'].upper()}\n  Root: {result['root']}\n  Service: {result['status']} (PID {result['pid']})")
    else:
        print(result['message'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
