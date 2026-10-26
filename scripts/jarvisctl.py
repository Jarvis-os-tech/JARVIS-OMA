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


def configure_hypr_autostart(enable: bool, autostart_path: Optional[Path] = None) -> bool:
    """Enable or disable JARVIS service autostart in ~/.config/hypr/autostart.lua."""
    if autostart_path is None:
        autostart_path = Path.home() / ".config" / "hypr" / "autostart.lua"
    if not autostart_path.exists():
        if enable:
            try:
                autostart_path.parent.mkdir(parents=True, exist_ok=True)
                autostart_path.write_text('o.launch_on_start("systemctl --user start jarvis-oma.service")\n', encoding="utf-8")
                return True
            except OSError:
                return False
        return True

    try:
        content = autostart_path.read_text(encoding="utf-8")
        line_active = 'o.launch_on_start("systemctl --user start jarvis-oma.service")'
        line_commented = '-- o.launch_on_start("systemctl --user start jarvis-oma.service")'

        if enable:
            if line_commented in content:
                content = content.replace(line_commented, line_active)
            elif line_active not in content:
                content += f"\n{line_active}\n"
        else:
            if line_active in content:
                content = content.replace(line_active, line_commented)

        autostart_path.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


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
    subparsers.add_parser("mute", help="Mute JARVIS")
    subparsers.add_parser("unmute", help="Unmute JARVIS")

    # interrupt
    subparsers.add_parser("interrupt", help="Interrupt active AI speech")

    # start / stop / restart / enable / disable systemd service
    subparsers.add_parser("start", help="Start jarvis-oma systemd service")
    subparsers.add_parser("stop", help="Stop jarvis-oma systemd service")
    subparsers.add_parser("restart", help="Restart jarvis-oma systemd service")
    subparsers.add_parser("enable", help="Enable and start jarvis-oma systemd service and autostart")
    subparsers.add_parser("disable", help="Disable and stop jarvis-oma systemd service and autostart")

    # mode
    p_mode = subparsers.add_parser("mode", help="Query or switch JARVIS operating mode (production/test)")
    p_mode.add_argument("mode", nargs="?", choices=["production", "test", "status", "promote", "sync"], default="status",
                        help="Target mode: production (main), test (dev), status, promote, or sync")
    p_mode.add_argument("--no-restart", action="store_true", help="Do not restart systemd service")
    p_mode.add_argument("--no-sync", action="store_true", help="Do not sync git branch")

    # subscribe
    p_sub = subparsers.add_parser("subscribe", help="Stream real-time daemon state events")
    p_sub.add_argument("--max-events", type=int, default=None, help="Stop after N events")

    # systemctl
    p_systemctl = subparsers.add_parser("systemctl", help="Inspect or control JARVIS OS systemd services")
    p_systemctl.add_argument("service_or_action", help="Service name (jarvis, healer, hyprland) or systemctl action (status, start, stop, restart)")
    p_systemctl.add_argument("extra_args", nargs=argparse.REMAINDER, help="Additional systemctl arguments (e.g. action or service name)")

    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "systemctl":
        services_map = {
            "jarvis": "jarvis-oma.service",
            "jarvis-oma": "jarvis-oma.service",
            "healer": "omarchy-healer.service",
            "omarchy-healer": "omarchy-healer.service",
            "hyprland": "hyprland.service",
            "voice": "omarchy-voice.service",
        }
        known_actions = {"start", "stop", "restart", "status", "enable", "disable", "reload", "is-active", "is-enabled"}

        first = args.service_or_action
        rest = list(args.extra_args or [])

        # Case 1: jarvisctl systemctl jarvis [action]
        if first in services_map:
            service_unit = services_map[first]
            action = rest[0] if rest and rest[0] in known_actions else (rest[0] if rest else "status")
            extra = rest[1:] if rest and rest[0] == action else rest
            cmd = ["systemctl", "--user", action, service_unit] + extra
        # Case 2: jarvisctl systemctl status jarvis
        elif first in known_actions:
            action = first
            target = rest[0] if rest else "jarvis"
            service_unit = services_map.get(target, target if target.endswith(".service") else f"{target}.service")
            extra = rest[1:]
            cmd = ["systemctl", "--user", action, service_unit] + extra
        else:
            cmd = ["systemctl", "--user", first] + rest

        proc = subprocess.run(cmd)
        return proc.returncode

    if args.subcommand in ("start", "stop", "restart", "enable", "disable"):
        action = args.subcommand
        if action == "enable":
            subprocess.run(["systemctl", "--user", "enable", "jarvis-oma.service"], capture_output=True)
            proc = subprocess.run(
                ["systemctl", "--user", "start", "jarvis-oma.service"],
                capture_output=True,
                text=True,
            )
            configure_hypr_autostart(enable=True)
            if proc.returncode != 0:
                sys.stderr.write(f"Failed to start jarvis-oma.service: {proc.stderr}\n")
                return proc.returncode
            print("JARVIS service enabled and started (autostart configured).")
            return 0
        elif action == "disable":
            proc = subprocess.run(
                ["systemctl", "--user", "stop", "jarvis-oma.service"],
                capture_output=True,
                text=True,
            )
            subprocess.run(["systemctl", "--user", "disable", "jarvis-oma.service"], capture_output=True)
            configure_hypr_autostart(enable=False)
            print("JARVIS service disabled and stopped (autostart removed).")
            return 0
        else:
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
        "mute": {"command": "set_mute", "muted": True},
        "unmute": {"command": "set_mute", "muted": False},
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
