#!/usr/bin/env bash
# scripts/uninstall.sh — Remove JARVIS Voice Core
set -euo pipefail

echo "Removing JARVIS Voice Core..."

systemctl --user disable --now jarvis-voice.service 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/jarvis-voice.service"
systemctl --user daemon-reload 2>/dev/null || true

rm -f "${HOME}/.local/bin/jarvis-voice"
rm -rf "${HOME}/.local/share/jarvis-voice"

echo "JARVIS Voice Core removed."
