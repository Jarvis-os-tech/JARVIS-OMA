"""Recover missing desktop session identifiers from the user's live runtime sockets."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import stat
import sys
import time
from collections.abc import Mapping


def _is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False


def recover_desktop_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return missing Wayland/Hyprland variables inferred from unique socket nodes.

    Existing values (including explicitly empty ones) are left untouched. A socket
    node is treated as live; no connection is made to the user's compositor.
    """
    env = os.environ if environ is None else environ
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        return {}

    runtime = Path(runtime_dir)
    recovered: dict[str, str] = {}

    if "WAYLAND_DISPLAY" not in env:
        try:
            wayland_sockets = sorted(
                path for path in runtime.glob("wayland-*") if _is_socket(path)
            )
        except OSError:
            wayland_sockets = []
        if len(wayland_sockets) == 1:
            recovered["WAYLAND_DISPLAY"] = wayland_sockets[0].name

    if "HYPRLAND_INSTANCE_SIGNATURE" not in env:
        hypr_root = runtime / "hypr"
        try:
            instances = sorted(
                directory.name
                for directory in hypr_root.iterdir()
                if directory.is_dir() and _is_socket(directory / ".socket.sock")
            )
        except OSError:
            instances = []
        if len(instances) == 1:
            recovered["HYPRLAND_INSTANCE_SIGNATURE"] = instances[0]

    return recovered


def wait_for_desktop_environment(
    environ: Mapping[str, str] | None = None,
    *,
    timeout: float = 0.0,
    poll_interval: float = 0.25,
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Wait briefly for compositor sockets and return recovered and missing names."""
    original = dict(os.environ if environ is None else environ)
    recovered: dict[str, str] = {}
    required = ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE")
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        recovered.update(recover_desktop_environment({**original, **recovered}))
        missing = tuple(name for name in required if name not in original and name not in recovered)
        if not missing or time.monotonic() >= deadline:
            return recovered, missing
        time.sleep(max(0.01, poll_interval))


def main(argv: list[str] | None = None) -> int:
    """Print safely quoted shell exports for variables that were recovered."""
    args = list(sys.argv[1:] if argv is None else argv)
    wait_seconds = 0.0
    if args:
        if len(args) != 2 or args[0] != "--wait-seconds":
            print("usage: python -m core.desktop_session [--wait-seconds SECONDS]", file=sys.stderr)
            return 2
        try:
            wait_seconds = max(0.0, float(args[1]))
        except ValueError:
            print("desktop session wait must be a number", file=sys.stderr)
            return 2
    recovered, missing = wait_for_desktop_environment(timeout=wait_seconds)
    for name, value in recovered.items():
        print(f"export {name}={shlex.quote(value)}")
    if missing:
        print(f"JARVIS desktop session unavailable: missing {', '.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
