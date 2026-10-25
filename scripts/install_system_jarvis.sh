#!/usr/bin/env bash
# Script to apply JARVIS OS system-level identity and system-wide CLI
# Requires sudo/root privileges.

set -e

if [ "$EUID" -ne 0 ]; then
    echo "This script requires superuser privileges to update /etc/os-release and /usr/local/bin."
    echo "Re-running with sudo..."
    exec sudo "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== JARVIS OS System Setup ==="

# 1. Install /usr/local/bin/jarvis
echo "[1/3] Installing /usr/local/bin/jarvis..."
cp "$REPO_ROOT/scripts/jarvis" /usr/local/bin/jarvis
chmod 755 /usr/local/bin/jarvis
if [ ! -f /usr/local/bin/jarvisctl ]; then
    ln -sf "$REPO_ROOT/scripts/jarvisctl" /usr/local/bin/jarvisctl
fi

# 2. Update /etc/os-release
echo "[2/3] Updating /etc/os-release for JARVIS OS branding..."
if [ -f /etc/os-release ] && [ ! -f /etc/os-release.bak ]; then
    cp /etc/os-release /etc/os-release.bak
    echo "  Backed up original /etc/os-release to /etc/os-release.bak"
fi

YEAR=$(date +%Y)
cat << OS_EOF > /etc/os-release
NAME="JARVIS OS"
PRETTY_NAME="JARVIS OS $YEAR"
ID=jarvis-os
ID_LIKE="arch omarchy"
ANSI_COLOR="0;36"
HOME_URL="https://github.com/Jarvis-os-tech/JARVIS-OMA"
SUPPORT_URL="https://github.com/Jarvis-os-tech/JARVIS-OMA/issues"
BUG_REPORT_URL="https://github.com/Jarvis-os-tech/JARVIS-OMA/issues"
OS_EOF

# 3. Hostname setup (optional)
if [ "$1" == "--set-hostname" ]; then
    echo "[3/3] Setting hostname to jarvis-os..."
    hostnamectl set-hostname jarvis-os || true
else
    echo "[3/3] Preserving hostname (use --set-hostname if you wish to change hostname to 'jarvis-os')."
fi

echo "=== JARVIS OS System Setup Complete ==="
echo "Run 'jarvis --help' to verify the unified CLI."
