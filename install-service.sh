#!/usr/bin/env bash
# Install and manage JARVIS systemd user service.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="jarvis-oma.service"
TARGET_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
TARGET_UNIT="${TARGET_DIR}/${SERVICE_NAME}"

action="${1:-install}"

case "${action}" in
  install)
    python_bin="${SCRIPT_DIR}/.venv/bin/python"
    [[ -x "${python_bin}" ]] || python_bin=python3
    exec "${python_bin}" "${SCRIPT_DIR}/scripts/desktop_integration.py"
    ;;
  enable)
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    echo "✓ JARVIS service enabled to start on boot/session start."
    ;;
  disable)
    systemctl --user disable "${SERVICE_NAME}"
    echo "✓ JARVIS service disabled from starting on boot/session start."
    ;;
  start)
    systemctl --user start "${SERVICE_NAME}"
    systemctl --user status "${SERVICE_NAME}" --no-pager
    ;;
  stop)
    systemctl --user stop "${SERVICE_NAME}"
    echo "✓ JARVIS service stopped."
    ;;
  restart)
    systemctl --user restart "${SERVICE_NAME}"
    systemctl --user status "${SERVICE_NAME}" --no-pager
    ;;
  status)
    systemctl --user status "${SERVICE_NAME}" --no-pager
    ;;
  logs)
    exec journalctl --user -u jarvis -n 50 -f
    ;;
  uninstall)
    systemctl --user stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}" 2>/dev/null || true
    rm -f "${TARGET_UNIT}"
    if [[ -L "${TARGET_DIR}/jarvis.service" && "$(readlink "${TARGET_DIR}/jarvis.service")" == "jarvis-oma.service" ]]; then
      rm "${TARGET_DIR}/jarvis.service"
    fi
    rm -f "${XDG_CONFIG_HOME:-${HOME}/.config}/omarchy/hooks/post-boot.d/jarvis-desktop"
    rm -f "${XDG_DATA_HOME:-${HOME}/.local/share}/applications/jarvis.desktop"
    systemctl --user daemon-reload
    echo "✓ JARVIS systemd user service removed."
    ;;
  *)
    echo "Usage: $0 {install|enable|disable|start|stop|restart|status|logs|uninstall}"
    exit 1
    ;;
esac
