#!/usr/bin/env bash
# Refresh desktop identifiers at login, including after compositor restarts.
set -euo pipefail
session_names=()
for name in WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS; do
    if [[ -n "${!name:-}" ]]; then
        session_names+=("${name}")
    fi
done
if (( ${#session_names[@]} )); then
    systemctl --user import-environment "${session_names[@]}"
fi
if systemctl --user is-enabled --quiet jarvis-oma.service; then
    systemctl --user start --no-block jarvis-oma.service
fi
