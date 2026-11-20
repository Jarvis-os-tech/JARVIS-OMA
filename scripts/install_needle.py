#!/usr/bin/env python3
"""Provision pinned Needle artifacts once; inference never downloads or executes tools."""
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
    parser.add_argument('--destination', type=Path, default=Path.home() / '.local/share/jarvis-runtime/needle')
    parser.add_argument('--whistle-runtime', type=Path, default=Path.home() / '.local/share/jarvis-runtime/whistle')
    args = parser.parse_args()
    root = args.destination.expanduser().resolve()
    source = args.whistle_runtime.expanduser().resolve()
    if root.exists():
        raise SystemExit(f'Refusing to overwrite existing runtime: {root}')
    root.mkdir(parents=True, mode=0o700)
    try:
        shutil.copytree(source / 'python', root / 'python')
        shutil.copy2(source / 'libneedle.so', root / 'libneedle.so')
        subprocess.run(['uv', 'pip', 'install', '--python', sys.executable, '--target',
                        str(root / 'python'), 'espeakng-loader==0.2.4'], check=True)
        env = dict(os.environ, PYTHONPATH=str(root / 'python'), NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1',
                   NEEDLE3_LIB_PATH=str(root / 'libneedle.so'))
        code = '''import sys, needle
from needle.agent.fetch import fetch_weights, engine_version
assert needle.__version__ == '3.2.1'
assert engine_version(3) == '3.3.1'
print(fetch_weights(generation=3, dest_dir=sys.argv[1]))'''
        subprocess.run([sys.executable, '-c', code, str(root)], env=env, check=True, timeout=180)
        files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                 for name in ('needle3.cact', 'libneedle.so')}
        (root / 'manifest.json').write_text(json.dumps({
            'package': 'cactus-needle==3.2.1', 'engine': '3.3.1', 'speech': 'espeakng-loader==0.2.4',
            'files': files, 'telemetry': False, 'network_required_after_install': False}, indent=2)+'\n')
        print(json.dumps({'installed': str(root), 'files': files}))
    except BaseException:
        shutil.rmtree(root)
        raise


if __name__ == '__main__':
    main()
