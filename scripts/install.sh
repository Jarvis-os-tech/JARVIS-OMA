#!/usr/bin/env bash
# scripts/install.sh — Install JARVIS Voice Core
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/jarvis-voice"
BIN_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"
CONFIG_DIR="${HOME}/.config/jarvis-voice"

echo "Installing JARVIS Voice Core..."

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$SERVICE_DIR" "$CONFIG_DIR"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Copy package and bin
cp -r "$REPO_DIR/jarvis_voice" "$INSTALL_DIR/"
cp -r "$REPO_DIR/bin" "$INSTALL_DIR/"
cp "$REPO_DIR/LICENSE" "$INSTALL_DIR/" 2>/dev/null || true

# Link python virtual environment with required dependencies
if [[ -d "${REPO_DIR}/.venv" ]]; then
    ln -sfn "$(readlink -f "${REPO_DIR}/.venv")" "$INSTALL_DIR/.venv"
fi

# Ensure default config exists
if [[ ! -f "$CONFIG_DIR/config.toml" && -f "$REPO_DIR/configs/config.toml.example" ]]; then
    cp "$REPO_DIR/configs/config.toml.example" "$CONFIG_DIR/config.toml"
fi

chmod +x "$INSTALL_DIR/bin/jarvis-voice"

# Symlink CLI to ~/.local/bin
ln -sf "$INSTALL_DIR/bin/jarvis-voice" "$BIN_DIR/jarvis-voice"

# Install systemd service
cp "$REPO_DIR/systemd/jarvis-voice.service" "$SERVICE_DIR/"
systemctl --user daemon-reload

echo "Installed to $INSTALL_DIR"
echo "CLI available at: ~/.local/bin/jarvis-voice"
echo ""
echo "To start voice daemon: systemctl --user enable --now jarvis-voice.service"
