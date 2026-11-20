"""Activate certified memory code, preserve state, and create its new vault."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import tomllib

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from scripts.prepare_system_integration_release import status
from scripts.prepare_parsing_release import restore_settings
from orchestration.release_manager import ReleaseManager

def atomic(path, data):
    temporary = path.with_name('.' + path.name + '.jarvis-new')
    with temporary.open('xb') as output:
        os.chmod(temporary, 0o600)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)

def deploy(staged):
    runtime = Path.home() / '.local/share/jarvis-runtime'
    meta = json.loads((staged / 'release.json').read_text())['organized_memory']
    parent = Path(meta['parent'])
    if (runtime / 'current').resolve() != parent:
        raise RuntimeError('Active release changed')
    for relative, digest in meta['sha256'].items():
        if hashlib.sha256((staged / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Candidate changed: ' + relative)
    before = status()
    if not before or before.get('tools_in_flight') or before.get('vision_mode', 'off') != 'off':
        raise RuntimeError('Tools or vision active, or voice status unknown')
    prior = json.loads(Path('/tmp/jarvis-organized-memory-before.json').read_text())
    state = Path(prior['path'])
    vault = Path.home() / 'Documents/JARVIS Memory'
    if vault.exists():
        raise RuntimeError('New vault destination already exists')
    config = Path.home() / '.config/jarvis-voice/config.toml'
    original = config.read_bytes()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = Path.home() / '.local/state/jarvis/backups' / ('organized-memory-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    for path in state.rglob('*'):
        if path.is_symlink() or not path.is_file() or path.name.endswith(('-wal', '-shm')):
            continue
        dest = backup / 'memory' / path.relative_to(state)
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.suffix == '.db':
            dest.touch(mode=0o600)
            source_db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
            target_db = sqlite3.connect(dest)
            try:
                source_db.backup(target_db)
            finally:
                target_db.close(); source_db.close()
        else:
            shutil.copy2(path, dest)
            dest.chmod(0o600)
    (backup / 'config.toml').write_bytes(original)
    (backup / 'config.toml').chmod(0o600)
    vault.mkdir(parents=True, mode=0o700)
    (vault / '.obsidian').mkdir(mode=0o700)
    (vault / '.obsidian/app.json').write_text(json.dumps({'showInlineTitle': True, 'newLinkFormat':'absolute'}))
    (vault / 'START HERE.md').write_text('# JARVIS Memory\n\n[[JARVIS-OMA Memory/Start Here|Open your organized memory library]]\n\nSix layers: short-term, long-term, episodic, semantic, procedural and shared.\n\nSQLite stores current authoritative memory; this vault is its linked Markdown view. Short-term context stays temporary and is not exported.\n')
    # Export using the certified package, reading existing state without opening
    # a new session or running extraction. No user contents are printed.
    export_code = '''
import json,sys
from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import MemoryConfig
b=MemoryBridge(MemoryConfig(path=sys.argv[1],obsidian_vault=sys.argv[2],obsidian_auto_sync=False))
try:
 r=b.sync_obsidian()
 print(json.dumps(r))
finally:b.close()
'''
    env = dict(os.environ, PYTHONPATH=str(staged))
    export = subprocess.run([str(runtime / 'venv/bin/python'), '-c', export_code, str(state), str(vault)],
        cwd=staged, env=env, check=True, capture_output=True, text=True, timeout=60)
    exported = json.loads(export.stdout)
    if exported['conflicts'] or not Path(exported['start_here']).is_file():
        raise RuntimeError('Vault export did not verify')
    text = original.decode()
    section = re.search(r'^\[memory\]\s*\n(?P<body>.*?)(?=^\[|\Z)', text, re.M | re.S)
    values = 'obsidian_vault = ' + json.dumps(str(vault)) + '\nobsidian_auto_sync = true\n'
    if section:
        body = re.sub(r'^\s*obsidian_(?:vault|auto_sync)\s*=.*\n?', '', section['body'], flags=re.M)
        text = text[:section.start('body')] + body.rstrip() + '\n' + values + '\n' + text[section.end('body'):]
    else:
        text += '\n[memory]\n' + values
    parsed = tomllib.loads(text)
    old_parsed = tomllib.loads(original.decode())
    for obj in (parsed, old_parsed):
        obj.setdefault('memory', {}).pop('obsidian_vault', None)
        obj['memory'].pop('obsidian_auto_sync', None)
    if parsed != old_parsed or config.read_bytes() != original:
        raise RuntimeError('Concurrent or unrelated configuration change')
    updated = text.encode()
    atomic(config, updated)
    manager = ReleaseManager(runtime)
    installed = None
    try:
        installed = manager.install_prepared_release(staged, stamp + '-organized-memory',
            expected_current=parent, expected_hashes=meta['sha256'], timeout=30)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            after = status()
            audio_ready = not before.get('microphone', {}).get('muted') or after.get('microphone', {}).get('source', '').startswith('jarvis_aec_')
            connection_ready = before.get('standby') or before.get('muted') or after.get('connected')
            if audio_ready and connection_ready and after.get('control_enabled'):
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Voice service did not become ready')
        restore_settings(before)
        after = status()
    except Exception:
        if config.read_bytes() == updated:
            atomic(config, original)
        if installed:
            manager._switch_release(parent, 30, expected_current=installed)
            restore_settings(before)
        raise
    report = dict(installed=str(installed), previous=str(parent), backup=str(backup), vault=str(vault),
        export=exported, tests=meta['tests'], status={k:after.get(k) for k in ('state','connected','standby','muted','vision_mode')})
    Path('/tmp/jarvis-organized-memory-deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    deploy(Path(sys.argv[1]).resolve(strict=True))
