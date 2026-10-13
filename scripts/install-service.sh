#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
mkdir -p "${UNIT_DIR}"
install -m 0644 "${ROOT}/systemd/jarvis-oma.service" "${UNIT_DIR}/jarvis-oma.service"
systemctl --user daemon-reload
systemctl --user enable --now jarvis-oma.service
echo "JARVIS installed and started as a user service."
echo "Status: systemctl --user status jarvis-oma.service"
echo "Logs:   journalctl --user -u jarvis-oma.service -f"
echo "Mute:   systemctl --user kill --signal=SIGUSR1 jarvis-oma.service"
echo "Stop speaking: systemctl --user kill --signal=SIGUSR2 jarvis-oma.service"
