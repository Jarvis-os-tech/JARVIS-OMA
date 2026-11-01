#!/usr/bin/env bash
# Jarvis-OS Quickshell Launcher
# Standard config location: ~/.config/quickshell

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUICKSHELL_CONFIG_DIR="${QUICKSHELL_CONFIG_DIR:-$SCRIPT_DIR}"

# Force Wayland platform (we're on Hyprland)
export QT_QPA_PLATFORM=wayland

# Export the QML import path so 'import qs' works
export QML_IMPORT_PATH="$QUICKSHELL_CONFIG_DIR:${QML_IMPORT_PATH:-}"

# Export theme directory for the theme system
export JARVIS_OS_THEME_DIR="$QUICKSHELL_CONFIG_DIR/themes"

# Launch Quickshell with the shell.qml entry point
# Use --path for direct file path (not --config which expects a config name)
exec quickshell --path "$QUICKSHELL_CONFIG_DIR/shell.qml" "$@"