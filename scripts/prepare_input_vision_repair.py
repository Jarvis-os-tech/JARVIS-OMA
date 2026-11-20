"""Stage the input-bar/vision repair over the installed release, then activate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from scripts.prepare_system_integration_release import splice, status, ipc

RUNTIME = Path.home() / '.local/share/jarvis-runtime'


def prepare(destination):
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Active runtime is not a managed release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-input-vision-', dir=destination))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)],
                   check=True)
    patches = {
        'skills/skills.py': ('skills/skills.py', [
            'DesktopSkills._adapter_open_input_bar',
            'DesktopSkills._adapter_close_input_bar',
            'DesktopSkills._adapter_control_vision_mode',
        ]),
        'voice_layer/daemon.py': ('voice_layer/daemon.py', ['LiveVoice.set_vision_mode']),
        'voice_layer/ipc.py': ('voice_layer/ipc.py', ['ControlServer._handle_json_command']),
        'orchestration/tool_tiers.py': ('orchestration/tool_tiers.py', ['CORE_TOOLS']),
    }
    hashes = {}
    for deployed, (source, definitions) in patches.items():
        path = target / deployed
        if path.is_symlink():
            raise ValueError('Cannot patch a linked runtime module: ' + deployed)
        content = splice(path.read_text(), (SOURCE / source).read_text(), definitions)
        if deployed == 'voice_layer/daemon.py':
            for name in ('shutil', 'subprocess'):
                if '\nimport ' + name + '\n' not in content:
                    content = content.replace('\nimport os\n', '\nimport os\nimport ' + name + '\n', 1)
        compile(content, deployed, 'exec')
        path.chmod(path.stat().st_mode | 0o200)
        path.write_text(content)
        hashes[deployed] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = json.loads((target / 'release.json').read_text())
    metadata['input_vision_repair'] = {
        'parent': str(parent), 'created_at': datetime.now(timezone.utc).isoformat(),
        'sha256': hashes,
    }
    path = target / 'release.json'
    path.chmod(path.stat().st_mode | 0o200)
    path.write_text(json.dumps(metadata, indent=2) + '\n')
    check = """
import inspect
from voice_layer import daemon
from skills.skills import DesktopSkills
from orchestration.tool_tiers import CORE_TOOLS
assert daemon.shutil.which and daemon.subprocess.Popen
source = inspect.getsource(DesktopSkills._adapter_open_input_bar)
assert 'self.test_bar.start()' in source and "shell_call, 'input'" not in source
assert 'control_vision_mode' in CORE_TOOLS
print('Staged input-bar and vision definitions validated')
"""
    subprocess.run([str(RUNTIME / 'venv/bin/python'), '-c', check], cwd=target,
                   env=dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1'),
                   check=True, timeout=20)
    return target


def activate(staged):
    staged = Path(staged).resolve(strict=True)
    repair = json.loads((staged / 'release.json').read_text())['input_vision_repair']
    parent = Path(repair['parent'])
    before = status()
    if before.get('tools_in_flight') or before.get('vision_mode', 'off') != 'off':
        raise RuntimeError('Wait for active tools/vision to stop before restarting the runtime')
    from orchestration.release_manager import ReleaseManager
    manager = ReleaseManager(RUNTIME)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-input-vision-repair'
    installed = manager.install_prepared_release(
        staged, name, expected_current=parent, expected_hashes=repair['sha256'], timeout=25)
    try:
        deadline = time.monotonic() + 20
        after = {}
        while time.monotonic() < deadline:
            try:
                after = status()
            except (ValueError, OSError):
                pass
            if after.get('control_enabled'):
                break
            time.sleep(.25)
        if not after.get('control_enabled'):
            raise RuntimeError('Repaired service did not load desktop controls')
        if before.get('muted'):
            ipc({'command': 'set_mute', 'muted': True})
        if before.get('standby'):
            ipc({'command': 'standby'})
        if before.get('microphone', {}).get('muted') is True:
            source = after.get('microphone', {}).get('source', '')
            if source.startswith('jarvis_aec_'):
                subprocess.run(['pactl', 'set-source-mute', source, '1'], check=True, timeout=5)
    except Exception:
        manager._switch_release(parent, 25, expected_current=installed)
        raise
    return {'installed': str(installed), 'previous': str(parent),
            'control_enabled': after.get('control_enabled'),
            'voice_tool_count': after.get('voice_tool_count'),
            'sha256': repair['sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', type=Path)
    group.add_argument('--activate', type=Path)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps({'prepared': str(prepare(args.prepare))}))
    else:
        print(json.dumps(activate(args.activate)))
