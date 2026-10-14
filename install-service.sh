#!/usr/bin/env bash
# Install and manage JARVIS systemd user service.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="jarvis.service"
SRC_UNIT="${SCRIPT_DIR}/systemd/${SERVICE_NAME}"
TARGET_DIR="${HOME}/.config/systemd/user"
TARGET_UNIT="${TARGET_DIR}/${SERVICE_NAME}"

action="${1:-install}"

case "${action}" in
  install)
    mkdir -p "${TARGET_DIR}"
    if [[ -f "${TARGET_UNIT}" ]] && ! cmp -s "${SRC_UNIT}" "${TARGET_UNIT}"; then
      cp -a "${TARGET_UNIT}" "${TARGET_UNIT}.bak.$(date +%s)"
      echo "Backed up existing unit to ${TARGET_UNIT}.bak.*"
    fi
    cp "${SRC_UNIT}" "${TARGET_UNIT}"
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    echo "✓ JARVIS systemd user service installed and enabled for boot/login."
    echo "  Activate now:       systemctl --user start ${SERVICE_NAME}"
    echo "  Check status:       systemctl --user status ${SERVICE_NAME}"
    echo "  Follow live logs:   journalctl --user -u jarvis -f"
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
    systemctl --user daemon-reload
    echo "✓ JARVIS systemd user service removed."
    ;;
  *)
    echo "Usage: $0 {install|enable|disable|start|stop|restart|status|logs|uninstall}"
    exit 1
    ;;
esac
