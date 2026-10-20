"""Recover missing desktop session identifiers from the user's live runtime sockets."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import stat
import sys
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


def main() -> int:
    """Print safely quoted shell exports for variables that were recovered."""
    for name, value in recover_desktop_environment().items():
        print(f"export {name}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
