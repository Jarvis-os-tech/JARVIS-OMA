#!/usr/bin/env python3
"""jarvisctl / voicectl CLI control plane for JARVIS-OMA daemon."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def default_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime_dir) / "jarvis.sock"


async def send_command(socket_path: Path, cmd_payload: dict) -> dict:
    if not socket_path.exists():
        raise FileNotFoundError(f"Daemon not running (socket {socket_path} does not exist)")
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
    except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
        raise ConnectionError(f"Daemon not running: {exc}") from exc

    try:
        msg = json.dumps(cmd_payload) + "\n"
        writer.write(msg.encode("utf-8"))
        await writer.drain()
        line = await reader.readline()
        if not line:
            raise ConnectionError("Daemon closed connection without response")
        return json.loads(line.decode("utf-8").strip())
    finally:
        writer.close()
        await writer.wait_closed()


async def subscribe_stream(socket_path: Path, max_events: Optional[int] = None) -> int:
    if not socket_path.exists():
        sys.stderr.write(f"Error: JARVIS daemon not running (socket {socket_path} does not exist)\n")
        return 1
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
    except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"Error: JARVIS daemon not running: {exc}\n")
        return 1

    count = 0
    try:
        writer.write((json.dumps({"command": "subscribe"}) + "\n").encode("utf-8"))
        await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            print(line.decode("utf-8").strip(), flush=True)
            count += 1
            if max_events is not None and count >= max_events:
                break
        return 0
    except (asyncio.CancelledError, KeyboardInterrupt):
        return 0
    finally:
        writer.close()
        await writer.wait_closed()


async def run_async(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvisctl",
        description="Control and inspect the JARVIS-OMA continuous voice daemon",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        default=default_socket_path(),
        help="Path to JARVIS UNIX domain socket",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Command to run")

    # status
    p_status = subparsers.add_parser("status", help="Query daemon status")
    p_status.add_argument("--json", action="store_true", help="Output raw JSON")

    # toggle / mute
    subparsers.add_parser("toggle", help="Toggle mute state")
    subparsers.add_parser("mute", help="Toggle mute state (alias)")
    subparsers.add_parser("unmute", help="Toggle mute state (alias)")

    # interrupt
    subparsers.add_parser("interrupt", help="Interrupt active AI speech")

    # start / stop / restart systemd service
    subparsers.add_parser("start", help="Start jarvis-oma systemd service")
    subparsers.add_parser("stop", help="Stop jarvis-oma systemd service")
    subparsers.add_parser("restart", help="Restart jarvis-oma systemd service")

    # mode
    p_mode = subparsers.add_parser("mode", help="Query or switch JARVIS operating mode (production/test)")
    p_mode.add_argument("mode", nargs="?", choices=["production", "test", "status", "promote", "sync"], default="status",
                        help="Target mode: production (main), test (dev), status, promote, or sync")
    p_mode.add_argument("--no-restart", action="store_true", help="Do not restart systemd service")
    p_mode.add_argument("--no-sync", action="store_true", help="Do not sync git branch")

    # subscribe
    p_sub = subparsers.add_parser("subscribe", help="Stream real-time daemon state events")
    p_sub.add_argument("--max-events", type=int, default=None, help="Stop after N events")

    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand in ("start", "stop", "restart"):
        action = args.subcommand
        proc = subprocess.run(
            ["systemctl", "--user", action, "jarvis-oma.service"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stderr.write(f"Failed to {action} jarvis-oma.service: {proc.stderr}\n")
            return proc.returncode
        past = "stopped" if action == "stop" else f"{action}ed"
        print(f"Service jarvis-oma.service {past}.")
        return 0

    if args.subcommand == "mode":
        try:
            from scripts.jarvis_mode import switch_mode, promote_to_main, sync_branch, current_mode
        except ImportError:
            try:
                from jarvis_mode import switch_mode, promote_to_main, sync_branch, current_mode
            except ImportError:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from jarvis_mode import switch_mode, promote_to_main, sync_branch, current_mode

        try:
            if args.mode == "promote":
                result = promote_to_main()
                print(f"JARVIS promoted to production: branch {result['branch']}, root {result['root']}")
                return 0
            elif args.mode == "sync":
                cur = current_mode()
                root = Path(cur["root"])
                res = sync_branch(root, cur["branch"])
                print(f"JARVIS sync ({cur['mode']}): {res.get('status')} - {res.get('message', res.get('output', ''))}")
                return 0
            else:
                result = switch_mode(args.mode, sync=not getattr(args, 'no_sync', False),
                                     restart=not args.no_restart)
        except (RuntimeError, ValueError) as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return 1

        if args.mode == "status":
            active_str = "running (PID {})".format(result['pid']) if result.get('service_active') and result.get('pid') else (
                "active" if result.get('service_active') else "inactive"
            )
            print(f"JARVIS mode: {result['mode']} (branch {result['branch']})\n  Root:    {result['root']}\n  Service: {active_str}")
        else:
            print(
                f"JARVIS mode: {result['mode']} "
                f"(branch {result['branch']}, {result['root']})"
            )
        return 0

    if args.subcommand == "subscribe":
        return await subscribe_stream(args.socket, max_events=args.max_events)

    cmd_map = {
        "status": {"command": "status"},
        "toggle": {"command": "toggle_mute"},
        "mute": {"command": "toggle_mute"},
        "unmute": {"command": "toggle_mute"},
        "interrupt": {"command": "interrupt"},
    }

    try:
        resp = await send_command(args.socket, cmd_map[args.subcommand])
    except (FileNotFoundError, ConnectionError) as exc:
        sys.stderr.write(f"Error: JARVIS daemon not running ({exc})\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Error communicating with daemon: {exc}\n")
        return 1

    if args.subcommand == "status":
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2))
        else:
            print("JARVIS-OMA Daemon Status:")
            print(f"  Status:      {resp.get('status', 'unknown')}")
            print(f"  State:       {resp.get('state', 'unknown')}")
            print(f"  Muted:       {resp.get('muted', False)}")
            print(f"  Model:       {resp.get('model', 'unknown')}")
            print(f"  Active Jobs: {resp.get('active_jobs', 0)}")
    elif args.subcommand in ("toggle", "mute", "unmute"):
        muted = resp.get("muted")
        print(f"Muted: {muted}")
    elif args.subcommand == "interrupt":
        print("Interrupted active generation.")

    return 0


def main():
    sys.exit(asyncio.run(run_async(sys.argv[1:])))


if __name__ == "__main__":
    main()
