"""Stage reviewed connector/service changes while preserving the current release."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import subprocess
import tempfile

from prepare_system_integration_release import SOURCE, RUNTIME, splice, activate


def prepare():
    parent = (RUNTIME / 'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / 'releases'):
        raise ValueError('Unmanaged current release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-connector-services-', dir='/tmp'))
    subprocess.run(['cp', '--archive', '--reflink=auto', str(parent) + '/.', str(target)], check=True)
    hashes = {}
    def put(relative, content):
        dest = target / relative
        if dest.is_symlink():
            raise ValueError('Linked target ' + relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.chmod(dest.stat().st_mode | 0o200)
        if relative.endswith('.py'):
            compile(content, relative, 'exec')
        dest.write_text(content)
        hashes[relative] = hashlib.sha256(dest.read_bytes()).hexdigest()
    for relative in ('connectors/api_anything.py', 'connectors/api_service.py',
                     'connectors/integration_status.py', 'skills/domains/api_anything.py',
                     'orchestration/tool_tiers.py', 'jarvis_control/execution_policy.py',
                     'skill_manifests/api-anything.json'):
        put(relative, (SOURCE / relative).read_text())
    for deployed, source, names in (
        ('skills/skills.py', 'skills/skills.py', ['DesktopSkills._resolve_command',
            'DesktopSkills._run', 'DesktopSkills._adapter_cli_hub_launch']),
        ('jarvis_voice/persona.py', 'voice_layer/persona.py', ['system_persona']),
        ('jarvis_voice/daemon.py', 'voice_layer/daemon.py', ['build_instruction']),
    ):
        put(deployed, splice((target / deployed).read_text(), (SOURCE / source).read_text(), names))
    metadata = json.loads((target / 'release.json').read_text())
    extension = {'parent': str(parent), 'created_at': datetime.now(timezone.utc).isoformat(), 'sha256': hashes}
    metadata['connector_services_extension'] = extension
    # Reuse the existing activation/rollback path with its privacy restoration.
    metadata['system_integration_extension'] = extension
    put('release.json', json.dumps(metadata, indent=2) + '\n')
    check = '''
import asyncio
from skills.skills import DesktopSkills
from orchestration.tool_tiers import domain_for_tool
async def main():
 s=DesktopSkills()
 try:
  for domain in ('api_anything','cli_anything','composio','integrations'):
   r=await s.execute('discover_domain_tools',{'domain':domain})
   assert r['tools'] and r['total_matches'] > 0,domain
  assert s._command('cli-hub')
  assert all(callable(getattr(s,s.ADAPTERS[x['adapter']],None)) for x in s._skills.values())
  print('Packaged connector/service smoke checks passed')
 finally: await s.close_agent_jobs()
asyncio.run(main())
'''
    subprocess.run([str(RUNTIME / 'venv/bin/python'), '-c', check], cwd=target,
                   env=dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1'),
                   check=True, timeout=30)
    print(json.dumps({'prepared': str(target), 'parent': str(parent)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', type=Path)
    args = parser.parse_args()
    if args.activate:
        activate(args.activate)
    else:
        prepare()
