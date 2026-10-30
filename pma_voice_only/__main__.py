import argparse
import asyncio
import json
import shutil
import sys
from .config import load, load_env
from .session import send_control
from .voice import VoiceSession, probe, safe_error

def main():
    parser = argparse.ArgumentParser(description='PMA voice conversation only')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('run')
    sub.add_parser('probe')
    sub.add_parser('status').add_argument('--json',action='store_true')
    listen = sub.add_parser('listen')
    listen.add_argument('action',choices=['start','stop','toggle','cancel','interrupt','say','status','quit'])
    listen.add_argument('words',nargs='*')
    args = parser.parse_args()
    try:
        if args.command in ('status','listen'):
            command = 'status' if args.command == 'status' else args.action
            if args.command == 'listen' and args.words:
                command += ' '+' '.join(args.words)
            print(send_control(command,timeout=15))
            return 0
        load_env()
        config = load()
        if args.command == 'probe':
            print(json.dumps(asyncio.run(probe(config))))
        else:
            for executable in ('pw-record','pw-cat'):
                if not shutil.which(executable):
                    raise RuntimeError(executable+' is missing')
            asyncio.run(VoiceSession(config).run())
        return 0
    except Exception as exc:
        print(safe_error(exc),file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
