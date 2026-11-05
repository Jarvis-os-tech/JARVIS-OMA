"""Stage tested parsing definitions over the installed release, certify, activate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from scripts.prepare_system_integration_release import node_for, splice, status, ipc

RUNTIME = Path.home() / '.local/share/jarvis-runtime'
PYTHON = RUNTIME / 'venv/bin/python'


def prepare(destination):
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Active runtime is not a managed release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-parsing-', dir=destination))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)], check=True)
    changed = {}

    def put(relative, content):
        path = target / relative
        if path.is_symlink():
            raise ValueError('Linked candidate module: ' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.chmod(path.stat().st_mode | 0o200)
        if path.suffix == '.py':
            compile(content, relative, 'exec')
        path.write_text(content)
        changed[relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    for relative in ('jarvis_control/command_values.py', 'jarvis_control/parsing_service.py',
                     'jarvis_control/parsing_worker.py', 'jarvis_control/nlu.py',
                     'skill_manifests/parsing.json', 'connectors/calendar_time.py',
                     'configs/parsing-requirements.txt', 'scripts/behavior_gate.py',
                     'scripts/install_widget_plugin.py',
                     'requirements.txt', 'requirements-dev.txt', 'pytest.ini'):
        put(relative, (SOURCE / relative).read_text())
    patches = {
        'jarvis_voice/local_speech.py': ('voice_layer/local_speech.py', ['command_for']),
        'jarvis_voice/daemon.py': ('voice_layer/daemon.py', ['LiveVoice.handle', 'LiveVoice.send_inputs']),
        'jarvis_control/evidence.py': ('jarvis_control/evidence.py', ['META_TOOLS']),
        'orchestration/tool_tiers.py': ('orchestration/tool_tiers.py', ['CORE_TOOLS', 'META_TOOLS']),
        'orchestration/release_manager.py': ('orchestration/release_manager.py', [
            'ReleaseManager.verify_behavior', 'ReleaseManager.build_release']),
        'skills/skills.py': ('skills/skills.py', ['DesktopSkills._adapter_parse_command_values']),
    }
    for deployed, (source, names) in patches.items():
        content = splice((target / deployed).read_text(), (SOURCE / source).read_text(), names)
        if deployed == 'skills/skills.py':
            marker = "'parsing.values': '_adapter_parse_command_values'"
            if marker not in content:
                node = node_for(content, 'DesktopSkills.ADAPTERS')
                if node is None:
                    raise ValueError('Missing adapter registry')
                lines = content.splitlines(keepends=True)
                lines.insert(node.lineno, '        ' + marker + ',\n')
                content = ''.join(lines)
        put(deployed, content)

    # Keep executable certification inputs with this release. Only the test
    # conftest aliases the source package name to the installed package name;
    # there is no production package rename or duplicate voice implementation.
    for path in (SOURCE / 'tests').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.json'} and '__pycache__' not in path.parts:
            put(str(path.relative_to(SOURCE)), path.read_text())
    conftest = (target / 'tests/conftest.py').read_text()
    conftest += '''
# Installed runtime keeps jarvis_voice; source-checkout tests use voice_layer.
import jarvis_voice
sys.modules['voice_layer'] = jarvis_voice
for _name, _module in list(sys.modules.items()):
    if _name.startswith('jarvis_voice.'):
        sys.modules['voice_layer' + _name[len('jarvis_voice'):]] = _module
'''
    put('tests/conftest.py', conftest)
    subprocess.run([str(PYTHON), str(target / 'scripts/behavior_gate.py'),
                    '--report', str(target / 'behavior-gate.json')], cwd=target,
                   check=True, timeout=140)
    evidence = json.loads((target / 'behavior-gate.json').read_text())
    if evidence.get('passed') is not True or evidence.get('source_unchanged') is not True:
        raise RuntimeError('Candidate did not pass its behavior gate')
    changed['behavior-gate.json'] = hashlib.sha256((target / 'behavior-gate.json').read_bytes()).hexdigest()
    metadata = json.loads((target / 'release.json').read_text())
    metadata['command_parsing'] = dict(parent=str(parent), created_at=datetime.now(timezone.utc).isoformat(),
                                       sha256=changed, tested_python=str(PYTHON),
                                       tests=evidence['collected_tests'])
    path = target / 'release.json'
    path.chmod(path.stat().st_mode | 0o200)
    path.write_text(json.dumps(metadata, indent=2) + '\n')
    return target


def restore_settings(before):
    if before.get('muted'):
        ipc({'command': 'set_mute', 'muted': True})
    if before.get('standby'):
        ipc({'command': 'standby'})
    if before.get('microphone', {}).get('muted') is True:
        source = status().get('microphone', {}).get('source', '')
        if source.startswith('jarvis_aec_'):
            subprocess.run(['pactl', 'set-source-mute', source, '1'], check=True, timeout=5)


def activate(staged):
    staged = Path(staged).resolve(strict=True)
    metadata = json.loads((staged / 'release.json').read_text())['command_parsing']
    parent = Path(metadata['parent'])
    before = status()
    if not before or before.get('tools_in_flight') or before.get('vision_mode', 'off') != 'off':
        raise RuntimeError('Cannot restart while state is unknown or tools/vision are active')
    from orchestration.release_manager import ReleaseManager
    manager = ReleaseManager(RUNTIME)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-command-parsing'
    installed = manager.install_prepared_release(
        staged, name, expected_current=parent, expected_hashes=metadata['sha256'], timeout=25)
    try:
        deadline = time.monotonic() + 20
        after = {}
        while time.monotonic() < deadline:
            try:
                after = status()
            except (ValueError, OSError):
                pass
            if after.get('control_enabled') and after.get('voice_tool_count', 0) > before.get('voice_tool_count', 0):
                break
            time.sleep(.25)
        if not after.get('control_enabled') or after.get('voice_tool_count', 0) <= before.get('voice_tool_count', 0):
            raise RuntimeError('Service did not attach the new parsing tool')
        restore_settings(before)
        if not before.get('standby') and not before.get('muted'):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                after = status()
                if after.get('connected'):
                    break
                time.sleep(.25)
            if not after.get('connected'):
                raise RuntimeError('Voice provider did not reconnect')
        final = status()
        if before.get('standby') and not final.get('standby'):
            raise RuntimeError('Previous standby setting was not restored')
        if before.get('muted') and not final.get('muted'):
            raise RuntimeError('Previous mute setting was not restored')
    except Exception:
        manager._switch_release(parent, 25, expected_current=installed)
        restore_settings(before)
        raise
    report = dict(installed=str(installed), previous=str(parent), tests=metadata['tests'],
                  status=final, privacy_before={k: before.get(k) for k in ('muted', 'standby', 'vision_mode')},
                  module_hashes=metadata['sha256'])
    Path('/tmp/jarvis-parsing-deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    return {k: report[k] for k in ('installed', 'previous', 'tests')} | {
        'standby': final.get('standby'), 'muted': final.get('muted'),
        'voice_tool_count': final.get('voice_tool_count'), 'error': final.get('error')}


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
