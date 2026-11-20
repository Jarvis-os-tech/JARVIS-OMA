"""Install the reviewed user service after activating its matching runtime."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1]


def install(install_cli=False):
    runtime = Path.home() / '.local/share/jarvis-runtime'
    if not (runtime / 'current/connectors/api_service.py').is_file():
        raise RuntimeError('Activate the connector-services release before installing its service')
    if install_cli:
        env = Path.home() / '.local/share/jarvis-integrations/venv'
        if not (env / 'bin/python').is_file():
            subprocess.run(['uv', 'venv', str(env)], check=True, timeout=30)
        subprocess.run(['uv', 'pip', 'install', '--python', str(env / 'bin/python'),
                        '-r', str(SOURCE / 'configs/integration-requirements.txt')], check=True, timeout=90)
    destination = Path.home() / '.config/systemd/user/jarvis-api-agent.service'
    destination.parent.mkdir(parents=True, exist_ok=True)
    unit = (SOURCE / 'systemd/jarvis-api-agent.service').read_bytes()
    if destination.is_symlink():
        raise RuntimeError('Refusing a linked service destination')
    if destination.exists() and destination.read_bytes() != unit:
        suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        shutil.copy2(destination, destination.with_name(destination.name + '.backup-' + suffix))
    destination.write_bytes(unit)
    destination.chmod(0o644)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, timeout=10)
    subprocess.run(['systemctl', '--user', 'enable', 'jarvis-api-agent.service'], check=True, timeout=15)
    subprocess.run(['systemctl', '--user', 'restart', 'jarvis-api-agent.service'], check=True, timeout=15)
    check = '''
import asyncio,json
from connectors.api_service import request
async def main():
 for _ in range(30):
  result=await request('health',{})
  if result and result.get('ok'):
   print(json.dumps(result));return
  await asyncio.sleep(.1)
 raise SystemExit('API service health check failed')
asyncio.run(main())
'''
    subprocess.run([str(runtime / 'venv/bin/python'), '-B', '-c', check],
                   cwd=runtime / 'current', check=True, timeout=12)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-cli', action='store_true')
    install(parser.parse_args().install_cli)
