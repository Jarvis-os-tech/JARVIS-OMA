"""Stage only audited memory repairs on the current managed runtime."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from prepare_system_integration_release import SOURCE, RUNTIME, splice, activate


def prepare():
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Unmanaged current release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-memory-audit-', dir='/tmp'))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)], check=True)
    hashes = {}
    def put(relative, content):
        dest = target / relative
        if dest.is_symlink():
            raise ValueError('Linked module ' + relative)
        if dest.exists():
            dest.chmod(dest.stat().st_mode | 0o200)
        if relative.endswith('.py'):
            compile(content, relative, 'exec')
        dest.write_text(content)
        hashes[relative] = hashlib.sha256(dest.read_bytes()).hexdigest()
    for relative in ('jarvis_memory/bridge.py', 'jarvis_memory/skills.py', 'skill_manifests/memory.json'):
        put(relative, (SOURCE / relative).read_text())
    put('skills/skills.py', splice((target / 'skills/skills.py').read_text(),
        (SOURCE / 'skills/skills.py').read_text(), ['DesktopSkills._adapter_recall_memory']))
    metadata = json.loads((target / 'release.json').read_text())
    extension = {'parent': str(parent), 'created_at': datetime.now(timezone.utc).isoformat(), 'sha256': dict(hashes)}
    metadata['memory_audit_extension'] = extension
    metadata['system_integration_extension'] = extension
    dest = target / 'release.json'
    dest.chmod(dest.stat().st_mode | 0o200)
    dest.write_text(json.dumps(metadata, indent=2) + '\n')
    check = '''
import asyncio,tempfile
from pathlib import Path
from jarvis_memory.config import Config,MemoryConfig
from jarvis_memory.skills import MemorySkills
from skills.skills import DesktopSkills
async def main():
 with tempfile.TemporaryDirectory(prefix='jarvis-memory-smoke-') as root:
  s=MemorySkills(Config(memory=MemoryConfig(path=root,obsidian_auto_sync=False)))
  try:
   await s.start()
   await s._memory_operation('record_exchange',user_text='Synthetic PC notebook',assistant_text='Synthetic reply',device='pc')
   await s._memory_operation('record_exchange',user_text='Synthetic phone notebook',assistant_text='',device='mobile')
   r=await s.execute('recall_memory',{'query':'notebook','device':'mobile'})
   assert r['conversation'] and all(x['device']=='mobile' for x in r['conversation'])
   assert not (await s.execute('recall_memory',{'query':'xylophonium-no-match'}))['conversation']
   assert (await s.execute('memory_status'))['capture_worker']['failed_exchanges']==0
  finally:await s.close_agent_jobs()
 d=DesktopSkills.__new__(DesktopSkills)
 d.manifest_dirs=[Path('skill_manifests')]
 specs=d._load_manifests()
 assert all(callable(getattr(d,d.ADAPTERS[x['adapter']],None)) for x in specs.values())
 print('Packaged memory checks passed using isolated synthetic data')
asyncio.run(main())
'''
    subprocess.run([str(RUNTIME / 'venv/bin/python'), '-B', '-c', check], cwd=target,
        env=dict(os.environ, PYTHONPATH=str(target)), check=True, timeout=25)
    print(json.dumps({'prepared': str(target), 'parent': str(parent)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', type=Path)
    args = parser.parse_args()
    if args.activate:
        activate(args.activate)
    else:
        prepare()
