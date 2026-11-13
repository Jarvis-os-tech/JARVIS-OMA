"""Stage and activate the scoped wake-word and shortcut repair."""
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

SOURCE = Path(__file__).resolve().parents[1]


def prepare(destination):
    runtime = Path.home() / '.local/share/jarvis-runtime'
    parent = (runtime / 'current').resolve(strict=True)
    if not parent.is_relative_to(runtime / 'releases'):
        raise ValueError('Current build is not a managed release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-wake-release-', dir=destination))
    shutil.copytree(parent, target, symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    changed = []
    for relative in ('voice_layer/standby.py', 'voice_layer/ipc.py', 'voice_layer/daemon.py',
                     'voice_layer/persona.py', 'skill_manifests/standby.json'):
        deployed = relative.replace('voice_layer/', 'voice_layer/')
        path = target / deployed
        if path.is_symlink():
            raise ValueError('Linked source file: ' + deployed)
        if path.exists():
            path.chmod(path.stat().st_mode | 0o200)
        path.write_bytes((SOURCE / relative).read_bytes())
        if path.suffix == '.py':
            compile(path.read_text(), deployed, 'exec')
        changed.append(deployed)
    model = SOURCE / 'mobile/app/src/main/assets/wake-model'
    model_target = target / 'voice_layer/assets/wake-model'
    if not (model / 'am/final.mdl').is_file():
        raise ValueError('Bundled offline model is missing')
    for source in model.rglob('*'):
        if source.is_symlink():
            raise ValueError('Linked model asset')
        if not source.is_file():
            continue
        path = model_target / source.relative_to(model)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError('Linked model destination')
        if path.exists():
            path.chmod(path.stat().st_mode | 0o200)
        shutil.copyfile(source, path)
        changed.append(str(path.relative_to(target)))
    check = """import json
from importlib.metadata import version
from voice_layer.standby import JarvisWakeDetector
from voice_layer.daemon import live_config
from google.genai import types
d=JarvisWakeDetector()
assert version('vosk')=='0.3.45'
assert set(d.phrases)=={'Hey Jarvis','Hello Jarvis'}
assert not d.process(bytes(640))
types.LiveConnectConfig.model_validate(live_config())
print('Both offline greetings and voice setup validated')
"""
    subprocess.run([str(runtime / 'venv/bin/python'), '-c', check], cwd=target,
        env=dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1'),
        timeout=30, check=True)
    metadata = json.loads((target / 'release.json').read_text())
    metadata['wake_extension'] = {'parent': str(parent), 'created_at': datetime.now(timezone.utc).isoformat(),
        'sha256': {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in changed}}
    (target / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return target


def activate(staged):
    staged = Path(staged).resolve(strict=True)
    meta = json.loads((staged / 'release.json').read_text())['wake_extension']
    runtime = Path.home() / '.local/share/jarvis-runtime'
    sys.path.insert(0, str(SOURCE))
    from orchestration.release_manager import ReleaseManager
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-wake-repair'
    target = ReleaseManager(runtime).install_prepared_release(staged, name,
        expected_current=Path(meta['parent']), expected_hashes=meta['sha256'], timeout=20)
    print(json.dumps({'activated': str(target), 'previous': meta['parent']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', type=Path)
    group.add_argument('--activate', type=Path)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps({'prepared': str(prepare(args.prepare))}))
    else:
        activate(args.activate)
