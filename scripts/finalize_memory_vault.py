"""Preserve old agent notes, register the verified vault, trash old vaults."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import quote

OLD_VAULTS = (Path('/home/g0pi/Projects/Jarvis-OS/memory/vault'), Path('/home/g0pi/secondary memory'))

def main():
    deployment = json.loads(Path('/tmp/jarvis-organized-memory-deployment.json').read_text())
    verified = json.loads(Path('/tmp/jarvis-organized-memory-installed-check.json').read_text())
    vault = Path(deployment['vault'])
    if vault != Path.home() / 'Documents/JARVIS Memory' or verified['broken_links'] or not verified['category_recall_verified']:
        raise RuntimeError('New vault verification is missing')
    registry = Path.home() / '.config/obsidian/obsidian.json'
    original = registry.read_bytes()
    settings = json.loads(original)
    if not isinstance(settings.get('vaults'), dict):
        raise RuntimeError('Unsupported Obsidian registry')
    backup = Path(deployment['backup'])
    (backup / 'obsidian-registry.json').write_bytes(original)
    (backup / 'obsidian-registry.json').chmod(0o600)
    archive = vault / 'Imported Agent History'
    imported = []
    for old in OLD_VAULTS:
        if old.is_symlink() or vault.is_relative_to(old) or old.is_relative_to(vault):
            raise RuntimeError('Unsafe previous vault location')
        if not old.is_dir():
            continue
        for source in old.rglob('*.md'):
            relative = source.relative_to(old)
            if any(part.startswith('.') for part in relative.parts) or source.is_symlink():
                continue
            if not source.resolve().is_relative_to(old.resolve()):
                raise RuntimeError('Linked old note')
            destination = archive / old.name / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination.exists():
                if destination.read_bytes() != source.read_bytes():
                    raise RuntimeError('Imported note conflict')
            else:
                shutil.copy2(source, destination)
                destination.chmod(0o600)
            imported.append(str(destination.relative_to(vault))[:-3])
    archive.mkdir(mode=0o700, exist_ok=True)
    (archive / 'README.md').write_text('# Previous agent conversation archive\n\n'
        'These notes were preserved from the previous vault before it was moved to Trash. '
        'They are historical agent records, not automatically confirmed facts, active instructions or executable skills. '
        'Hidden Obsidian settings and plugins were not imported.\n\n'
        + '\n'.join('- [[' + key + ']]' for key in imported) + '\n')
    home = vault / 'START HERE.md'
    with home.open('a') as stream:
        stream.write('\n[[Imported Agent History/README|Preserved previous agent history]]\n')
    old_paths = {str(p) for p in OLD_VAULTS}
    settings['vaults'] = {k:v for k,v in settings['vaults'].items() if v.get('path') not in old_paths}
    identity = sha256(str(vault).encode()).hexdigest()[:16]
    if identity in settings['vaults'] and settings['vaults'][identity].get('path') != str(vault):
        raise RuntimeError('Vault registry identity collision')
    settings['vaults'][identity] = {'path':str(vault), 'ts':int(time.time() * 1000), 'open':True}
    if registry.read_bytes() != original:
        raise RuntimeError('Obsidian registry changed concurrently')
    temporary = registry.with_name('.obsidian-jarvis-new.json')
    with temporary.open('xb') as stream:
        os.chmod(temporary, 0o600)
        stream.write((json.dumps(settings, indent=2) + '\n').encode())
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, registry)
    trashed = []
    for old in OLD_VAULTS:
        if old.exists():
            subprocess.run(['gio', 'trash', '--', str(old)], check=True, timeout=30, capture_output=True)
            if old.exists():
                raise RuntimeError('Previous vault still exists after trash operation')
            trashed.append(str(old))
    uri = 'obsidian://open?vault=' + quote(vault.name) + '&file=START%20HERE'
    subprocess.Popen(['obsidian', uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    report = {'vault':str(vault), 'imported_historical_notes':len(imported), 'trashed':trashed,
              'removed_previous_registrations':list(old_paths), 'registry_backup':str(backup / 'obsidian-registry.json')}
    Path('/tmp/jarvis-organized-vault-finalization.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
