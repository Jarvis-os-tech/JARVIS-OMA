#!/usr/bin/env python3
"""Overlay the tested Hermes integration onto the current managed release.

Preserves the active voice/device build, snapshots state, and uses the existing
release manager's health check and rollback. Never restarts Hermes or replays goals.
"""
from __future__ import annotations
import argparse
import compileall
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from orchestration.release_manager import ReleaseManager
from orchestration.integration_paths import locations
from orchestration.durable_hermes import DurableHermes

FILES = [
    'orchestration/' + name + '.py' for name in (
        '_hermes_gateway_worker', 'hermes_bridge', 'durable_hermes', 'hermes_api',
        'hermes_notices', 'goal_workspaces', 'integration_paths', 'task_agents',
        'task_names', 'routing', 'tool_tiers', 'hermes_setup', 'mcp_server')
] + ['skills/domains/orchestration.py', 'skills/domains/api_anything.py', 'jarvis_control/skills.py',
     'skill_manifests/personal-agents.json', 'skills/manifests/personal-agents.json',
     'scripts/hermes-jarvis-memory.py', 'scripts/hermes-jarvis-mcp.py']


def import_receipts(parent):
    destination = locations()['goals_root']
    manager = DurableHermes(destination)
    root = parent / '.jarvis-learning/task-agents'
    imported = 0
    for path in root.glob('task-*.json'):
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_size > 256000:
            raise ValueError('Invalid prior-release receipt')
        job = json.loads(path.read_text())
        if not job.get('native_authority'):
            continue
        if path.stem != job.get('id'):
            raise ValueError('Prior receipt identity mismatch')
        with manager.transaction():
            if job['id'] in manager.jobs:
                continue
            workspace = Path(job.get('workspace') or '/')
            if workspace.exists() and workspace.name == 'worktree':
                legacy_root = workspace.parents[2]
                original = legacy_root / path.name
                if original.is_file():
                    job['_legacy_storage_root'] = str(legacy_root)
            manager._save(job)
            if job.get('session_id'):
                manager.bridge.owned_sessions.add(job['session_id'])
            imported += 1
    if imported:
        manager.bridge._persist_owned()
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    runtime = Path.home() / '.local/share/jarvis-runtime'
    parent = (runtime / 'current').resolve(strict=True)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-hermes-direct-api'
    target = runtime / 'releases' / name
    shutil.copytree(parent, target, symlinks=True)
    hashes = {}
    for relative in FILES:
        source, output = SOURCE / relative, target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.chmod(0o600)
        shutil.copyfile(source, output)
        output.chmod(0o444 if output.suffix == '.py' else 0o600)
        hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    for relative in FILES:
        if relative.endswith('.py') and not compileall.compile_file(str(target / relative), force=True, quiet=1, optimize=1):
            raise RuntimeError('Compilation failed: ' + relative)
    # Run the actual installed interpreter against the prepared release.
    env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([str(runtime / 'venv/bin/python'), '-c',
        "from skills.skills import DesktopSkills; from jarvis_control.skills import UnifiedSkills; "
        "s=DesktopSkills(); u=UnifiedSkills(desktop_skills=s); "
        "assert any(t['name']=='call_hermes_api' for t in u.live_declarations); print('Prepared release: Hermes API visible')"],
        cwd=target, env=env, check=True, timeout=30)
    metadata = json.loads((parent / 'release.json').read_text())
    metadata['hermes_direct_api'] = {'parent_release': str(parent), 'files': hashes, 'created_at': datetime.now(timezone.utc).isoformat()}
    manifest = target / 'release.json'
    manifest.chmod(0o600)
    manifest.write_text(json.dumps(metadata, indent=2) + '\n')
    print('Prepared:', target)
    if args.activate:
        if (runtime / 'current').resolve() != parent:
            raise RuntimeError('Active release changed while preparing; inspect before activation')
        print('Preserved receipts:', import_receipts(parent))
        manager = ReleaseManager(root_dir=runtime)
        manager.snapshot_state()
        manager._switch_release(target, timeout=15)
        print('Activated with previous release retained for rollback.')


if __name__ == '__main__':
    main()
