#!/usr/bin/env bash
set -euo pipefail

DEST_SHARE="${HOME}/.local/share/pma-voice-only"
DEST_BIN="${HOME}/.local/bin"
DEST_SYSTEMD="${HOME}/.config/systemd/user"

echo "==> Stopping and disabling omarchy-voice.service..."
systemctl --user disable --now omarchy-voice.service 2>/dev/null || true

echo "==> Removing systemd unit and binary links..."
rm -f "${DEST_SYSTEMD}/omarchy-voice.service"
rm -f "${DEST_BIN}/omarchy-voice"
systemctl --user daemon-reload

echo "==> Uninstalled PMA voice service."
echo "Note: Configuration at ~/.config/pma-voice-only was preserved."
