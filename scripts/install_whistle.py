#!/usr/bin/env python3
"""Install Whistle separately from JARVIS's conversation dependencies.

Run with the runtime Python. Downloads only the pinned package, speech model
and CPU engine. Activation/configuration is a separate release operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path.home() / '.local/share/jarvis-runtime/whistle')
    parser.add_argument('--package-source', type=Path, help='Reuse an already verified package directory')
    args = parser.parse_args()
    root = args.destination.expanduser().resolve()
    if root.exists():
        raise SystemExit(f'Refusing to overwrite an existing Whistle runtime: {root}')
    root.mkdir(parents=True, mode=0o700)
    try:
        if args.package_source:
            shutil.copytree(args.package_source, root / 'python')
        else:
            subprocess.run(['uv', 'pip', 'install', '--python', sys.executable,
                            '--target', str(root / 'python'), 'cactus-needle==3.2.1'], check=True)
        env = dict(os.environ, PYTHONPATH=str(root / 'python'), NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1')
        # Fetch/cache once during installation, never on the microphone path.
        setup = '''import json, needle
from needle.agent.fetch import engine_version
assert needle.__version__ == '3.2.1'
assert engine_version(3) == '3.3.1'
model = needle.Whistle()
print(json.dumps({'weights':model.weights, 'library':needle._library_path(3)}))
'''
        result = subprocess.run([sys.executable, '-c', setup], env=env,
                                capture_output=True, text=True, check=True, timeout=120)
        paths = json.loads(result.stdout.strip().splitlines()[-1])
        hashes = {}
        for key, name in (('weights', 'whistle.cact'), ('library', 'libneedle.so')):
            shutil.copy2(paths[key], root / name)
            hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        (root / 'manifest.json').write_text(json.dumps({
            'package': 'cactus-needle==3.2.1', 'engine': '3.3.1', 'files': hashes,
            'telemetry': False, 'network_required_after_install': False}, indent=2) + '\n')
        print(json.dumps({'installed': str(root), 'files': hashes}))
    except BaseException:
        shutil.rmtree(root)
        raise


if __name__ == '__main__':
    main()
