"""Certify task presentation over the current installed package layout."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from scripts.prepare_system_integration_release import splice

RUNTIME = Path.home() / '.local/share/jarvis-runtime'
PYTHON = RUNTIME / 'venv/bin/python'

def prepare():
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Unmanaged release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-task-events-'))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)], check=True)
    changed = {}
    def put(relative, content):
        path = target / relative
        if path.is_symlink():
            raise ValueError('Linked candidate file: ' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.chmod(path.stat().st_mode | 0o200)
        if path.suffix == '.py':
            compile(content, relative, 'exec')
        path.write_text(content)
        changed[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ('orchestration/task_events.py', 'orchestration/task_presentation.py',
                     'contracts/task-event-v1.json', 'scripts/behavior_gate.py',
                     'scripts/generate_task_event_contract.py', 'requirements.txt'):
        put(relative, (SOURCE / relative).read_text())
    for path in (SOURCE / 'ui/jarvis_widgets').iterdir():
        if path.is_file() and path.suffix in {'.py', '.qml', '.js', '.json'}:
            put(str(path.relative_to(SOURCE)), path.read_text())
    patches = {
        'skills/skills.py': ['DesktopSkills._task_presenter', 'DesktopSkills.refresh_task_presentation',
                            'DesktopSkills._task_event_response', 'DesktopSkills._adapter_start_task',
                            'DesktopSkills._adapter_task_status', 'DesktopSkills._adapter_cancel_task',
                            'DesktopSkills.close_agent_jobs'],
        'jarvis_control/skills.py': ['UnifiedSkills.background_events', 'UnifiedSkills.acknowledge_event'],
    }
    for relative, names in patches.items():
        content = splice((target / relative).read_text(), (SOURCE / relative).read_text(), names)
        if relative == 'skills/skills.py' and 'import copy\n' not in content:
            content = 'import copy\n' + content
        put(relative, content)
    for path in (SOURCE / 'tests').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.json'} and '__pycache__' not in path.parts:
            put(str(path.relative_to(SOURCE)), path.read_text())
    subprocess.run([str(PYTHON), str(target / 'scripts/behavior_gate.py'), '--report',
                    str(target / 'behavior-gate.json')], cwd=target, check=True, timeout=140)
    evidence = json.loads((target / 'behavior-gate.json').read_text())
    if not evidence.get('passed') or not evidence.get('source_unchanged'):
        raise RuntimeError('Certification failed')
    changed['behavior-gate.json'] = hashlib.sha256((target / 'behavior-gate.json').read_bytes()).hexdigest()
    metadata = json.loads((target / 'release.json').read_text())
    metadata['task_events'] = dict(parent=str(parent), sha256=changed, tests=evidence['collected_tests'])
    put('release.json', json.dumps(metadata, indent=2) + '\n')
    return target

if __name__ == '__main__':
    print(json.dumps({'prepared': str(prepare())}))
