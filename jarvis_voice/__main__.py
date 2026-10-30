"""CLI entry point: python -m jarvis_voice"""
import argparse
import os
import shutil
import sys


def _ipc_command(args):
    """Send a command to the running daemon via its control socket."""
    import socket
    from jarvis_voice.config import SOCKET_PATH

    if not SOCKET_PATH.exists():
        print('jarvis-voice is not running', file=sys.stderr)
        return 1

    if args.command == 'status':
        cmd = 'status --json' if args.json else 'status'
    elif args.command == 'listen':
        action = args.action or 'toggle'
        cmd = f'listen {action}'
    else:
        cmd = args.command

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(str(SOCKET_PATH))
        sock.sendall((cmd + '\n').encode())
        data = sock.recv(4096)
        sock.close()
        print(data.decode().strip())
        return 0
    except Exception as e:
        print(f'IPC error: {e}', file=sys.stderr)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='jarvis-voice',
        description='JARVIS Voice Core — sovereign voice foundation')
    parser.add_argument('command', nargs='?', default='run',
        choices=['run', 'status', 'listen'],
        help='Command to execute (default: run)')
    parser.add_argument('action', nargs='?', help='Action for listen command')
    parser.add_argument('--model', default=os.getenv('GEMINI_LIVE_MODEL', 'gemini-3.8-live'))
    parser.add_argument('--voice', default=None, help='Gemini voice name')
    parser.add_argument('--check', action='store_true',
        help='Check dependencies without opening audio or network')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--transcripts', action='store_true')
    parser.add_argument('--retries', type=int, default=5)

    args = parser.parse_args(argv)

    if args.check:
        missing = [n for n in ('pw-record', 'pw-play', 'pactl', 'pw-cli')
                   if shutil.which(n) is None]
        if missing:
            print(f'Missing: {", ".join(missing)}', file=sys.stderr)
            return 1
        try:
            from jarvis_voice.config import load
            config = load()
            print(f'PASS: audio commands present, config valid (model={config.model})')
            return 0
        except Exception as e:
            print(f'Config error: {e}', file=sys.stderr)
            return 1

    if args.command in ('status', 'listen'):
        return _ipc_command(args)

    if args.command == 'run':
        try:
            from jarvis_voice.daemon import main as daemon_main
            return daemon_main(args)
        except ImportError:
            print('jarvis-voice: daemon start requires full implementation (Task 7)')
            return 0

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
