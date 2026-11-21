#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configurable port defaulting to 8768 (8765 is occupied by agent-reach.service)
DRONE_PORT="${JARVIS_DRONE_PORT:-8768}"
DRY_RUN=false
PASS_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --port=*)
            DRONE_PORT="${1#*=}"
            shift
            ;;
        --port)
            if [ -n "${2:-}" ]; then
                DRONE_PORT="$2"
                shift 2
            else
                echo "Error: --port requires an argument" >&2
                exit 1
            fi
            ;;
        *)
            PASS_ARGS+=("$1")
            shift
            ;;
    esac
done

# 1. Apply dynamic Hyprland window rules if hyprctl is available
if command -v hyprctl &>/dev/null; then
    echo "Configuring Hyprland window rules for jarvis-drone..."
    # Legacy/standard windowrulev2 directives
    hyprctl keyword windowrulev2 "float, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "pin, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "noborder, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "bordersize 0, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "noshadow, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "nodim, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "opacity 1.0 override 1.0 override, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "noinitialfocus, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true
    hyprctl keyword windowrulev2 "size 96 96, class:^(jarvis-drone|jarvis-drone-companion|electron)$" &>/dev/null || true

    # Also apply via hyprctl eval for modern Lua/Omarchy config environments
    hyprctl eval "pcall(function() if o and o.window then o.window({ class = '^(jarvis-drone|jarvis-drone-companion|electron)$' }, { float = true, pin = true, border_size = 0, no_shadow = true, no_dim = true, no_initial_focus = true, opacity = '1.0 1.0' }) end end)" &>/dev/null || true
fi

# 2. Start WebSocket bridge if not already running on target port
BRIDGE_PID=""
if ss -tuln | grep -q ":${DRONE_PORT} "; then
    echo "Drone WebSocket Bridge is already running on port ${DRONE_PORT}."
else
    if [ "$DRY_RUN" = true ]; then
        echo "[Dry-Run] Drone WebSocket Bridge would start on port ${DRONE_PORT}."
    else
        echo "Starting Drone WebSocket Bridge on port ${DRONE_PORT}..."
        JARVIS_DRONE_PORT="${DRONE_PORT}" python3 bridge.py &
        BRIDGE_PID=$!
        trap 'kill $BRIDGE_PID 2>/dev/null || true' EXIT INT TERM
        sleep 0.5
        if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
            echo "Error: Bridge daemon died on startup" >&2
            exit 1
        fi
    fi
fi

# 3. Launch Electron Overlay
if pgrep -f "electron.*ui/jarvis_drone" &>/dev/null || pgrep -f "app-path=.*ui/jarvis_drone" &>/dev/null; then
    echo "JARVIS Drone companion overlay is already running. Preventing duplicate instance."
    exit 0
fi

if [ "$DRY_RUN" = true ]; then
    echo "[Dry-Run] Would execute: electron . --ozone-platform=x11 --port=\"${DRONE_PORT}\" ${PASS_ARGS[*]:-}"
    echo "[Dry-Run] Dry run completed successfully."
    exit 0
fi

ELECTRON_CMD="npx electron"
if command -v electron &>/dev/null; then
    ELECTRON_CMD="electron"
fi

echo "Launching JARVIS Drone Companion (port ${DRONE_PORT})..."
$ELECTRON_CMD "${SCRIPT_DIR}" --ozone-platform=x11 --port="${DRONE_PORT}" "${PASS_ARGS[@]}"
