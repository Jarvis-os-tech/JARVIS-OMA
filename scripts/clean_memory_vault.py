"""Install a certified exporter and organize only JARVIS-owned vault content."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orchestration.release_manager import ReleaseManager
from scripts.deploy_organized_memory import atomic

def states():
    names = ('jarvis-voice.service', 'jarvis-device-bridge.service')
    return {name:subprocess.run(['systemctl','--user','is-active',name], capture_output=True,text=True).stdout.strip() for name in names}

class PreserveStoppedVoice(ReleaseManager):
    """For an intentionally stopped voice service, certify files and keep it off."""
    def __init__(self, root, expected):
        super().__init__(root)
        self.expected_states = expected
    def _restart_services(self):
        if states() != self.expected_states:
            raise RuntimeError('Service state changed during stopped-service activation')
    def verify_health(self, timeout=5):
        return states() == self.expected_states and (self.current_link / 'jarvis_memory/vault_layout.py').is_file()

def main(staged):
    initial = states()
    if initial['jarvis-voice.service'] != 'inactive':
        raise RuntimeError('This cleanup activation preserves an already stopped voice service')
    runtime = Path.home() / '.local/share/jarvis-runtime'
    meta = json.loads((staged / 'release.json').read_text())['organized_memory']
    parent = Path(meta['parent'])
    if (runtime / 'current').resolve() != parent:
        raise RuntimeError('Active runtime changed')
    vault = Path.home() / 'Documents/JARVIS Memory'
    old = vault / 'JARVIS-OMA Memory'
    config = Path.home() / '.config/jarvis-voice/config.toml'
    original = config.read_bytes()
    if b'obsidian_layout' in original:
        raise RuntimeError('A vault layout is already configured')
    updated = original.rstrip() + b'\nobsidian_layout = "organized"\n'
    import tomllib
    if tomllib.loads(updated.decode()).get('memory',{}).get('obsidian_layout') != 'organized':
        raise RuntimeError('Vault layout setting is not in the memory table')
    backup = Path.home() / '.local/state/jarvis/backups' / ('clean-vault-' + str(time.time_ns()))
    backup.mkdir(mode=0o700, parents=True)
    (backup / 'config.toml').write_bytes(original)
    (backup / 'config.toml').chmod(0o600)
    atomic(config, updated)
    manager = PreserveStoppedVoice(runtime, initial)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-clean-memory-vault'
    try:
        installed = manager.install_prepared_release(staged, name, expected_current=parent,
                            expected_hashes=meta['sha256'], timeout=10)
    except Exception:
        if config.read_bytes() == updated:
            atomic(config, original)
        raise
    code = '''
import json
from pathlib import Path
from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import load_config
b=MemoryBridge(load_config(Path.home()/'.config/jarvis-voice/config.toml').memory)
try: print(json.dumps(b.sync_obsidian()))
finally:b.close()
'''
    result = subprocess.run([str(runtime/'venv/bin/python'),'-c',code], cwd=installed,
             env=dict(os.environ,PYTHONPATH=str(installed)), capture_output=True,text=True,check=True,timeout=60)
    receipt = json.loads(result.stdout)
    if receipt['conflicts']:
        raise RuntimeError('Clean export has conflicts; previous notes retained')
    import re
    for note in vault.rglob('*.md'):
        if old in note.parents or (vault/'Imported Agent History') in note.parents:
            continue
        if note.name in ('START HERE.md','VOICE TEST COMMANDS.md'):
            continue
        for target in re.findall(r'(?<!\\)\[\[([^\]]+)\]\]', note.read_text()):
            if not (vault/(target+'.md')).is_file():
                raise RuntimeError('Broken clean-vault link')
    # Preserve edited or unowned Markdown before removing the generated legacy tree.
    previous = json.loads((old/'.jarvis-sync.json').read_text())
    preserved = 0
    for note in old.rglob('*.md'):
        relative = str(note.relative_to(old))
        if note.is_symlink():
            raise RuntimeError('Linked legacy note; cleanup deferred')
        if previous.get(relative) != sha256(note.read_bytes()).hexdigest():
            dest = vault/'03 Episodic Memory/Preserved Notes'/relative
            dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copy2(note,dest); preserved += 1
    archive = vault/'Imported Agent History'
    if archive.exists():
        target = vault/'03 Episodic Memory/Agent History'
        if target.exists():
            raise RuntimeError('Agent-history destination already exists')
        archive.rename(target)
        index = target/'README.md'
        index.write_text(index.read_text().replace('Imported Agent History/', '03 Episodic Memory/Agent History/'))
    voice = vault/'VOICE TEST COMMANDS.md'
    if voice.exists():
        target = vault/'02 Long-Term Memory/Instructions/Voice Test Commands.md'
        text = voice.read_text().replace('[[START HERE|Return to memory home]]','[[00 HOME|Return to memory home]]')
        target.write_text(text)
    for path in (old,vault/'START HERE.md',voice):
        if path.exists():
            subprocess.run(['gio','trash','--',str(path)],check=True,capture_output=True,timeout=30)
    report = dict(installed=str(installed), previous=str(parent), backup=str(backup),
        vault=str(vault), generated_nodes=receipt['nodes'], preserved_edited_notes=preserved,
        sections=[p.name for p in sorted(vault.iterdir()) if p.is_dir() and not p.name.startswith('.')],
        service_states=states(), old_generated_folder_trashed=True)
    Path('/tmp/jarvis-clean-memory-vault.json').write_text(json.dumps(report,indent=2)+'\n')
    subprocess.Popen(['obsidian','obsidian://open?vault='+quote(vault.name)+'&file=00%20HOME'],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    print(json.dumps(report))

if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve(strict=True))
