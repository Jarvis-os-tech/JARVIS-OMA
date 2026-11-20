"""Certify the memory package on the current installed JARVIS layout."""
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

def prepare():
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Unmanaged runtime')
    target = Path(tempfile.mkdtemp(prefix='jarvis-organized-memory-'))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)], check=True)
    changed = {}
    def put(relative, content):
        path = target / relative
        if path.is_symlink():
            raise ValueError('Linked release file')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.chmod(path.stat().st_mode | 0o200)
        if path.suffix == '.py':
            compile(content, relative, 'exec')
        path.write_text(content)
        changed[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for folder in ('jarvis_memory', 'tests'):
        for path in (SOURCE / folder).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.json'} and '__pycache__' not in path.parts:
                put(str(path.relative_to(SOURCE)), path.read_text())
    for relative in ('skill_manifests/memory.json', 'scripts/evaluate_memory.py', 'scripts/behavior_gate.py'):
        put(relative, (SOURCE / relative).read_text())
    relative = 'skills/skills.py'
    put(relative, splice((target / relative).read_text(), (SOURCE / relative).read_text(),
        ['DesktopSkills._adapter_remember_memory', 'DesktopSkills._adapter_recall_memory', 'DesktopSkills._adapter_forget_memory']))
    python = str(RUNTIME / 'venv/bin/python')
    subprocess.run([python, '-m', 'pytest', 'tests/test_memory', '-q'], cwd=target, check=True, timeout=90)
    subprocess.run([python, str(target / 'scripts/behavior_gate.py'), '--report',
                    str(target / 'behavior-gate.json')], cwd=target, check=True, timeout=140)
    evidence = json.loads((target / 'behavior-gate.json').read_text())
    if evidence.get('passed') is not True or evidence.get('source_unchanged') is not True:
        raise RuntimeError('Candidate certification failed')
    changed['behavior-gate.json'] = hashlib.sha256((target / 'behavior-gate.json').read_bytes()).hexdigest()
    metadata = json.loads((target / 'release.json').read_text())
    metadata['organized_memory'] = dict(parent=str(parent), sha256=dict(changed),
        tested_at=datetime.now(timezone.utc).isoformat(), tests=evidence['collected_tests'])
    put('release.json', json.dumps(metadata, indent=2) + '\n')
    return target

if __name__ == '__main__':
    print(json.dumps({'prepared':str(prepare())}))
