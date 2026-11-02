#!/usr/bin/env bash
# scripts/install.sh — Install JARVIS Voice Core
set -euo pipefail

INSTALL_DIR="${JARVIS_INSTALL_HOME:-${HOME}}/.local/share/jarvis-voice"
BIN_DIR="${JARVIS_INSTALL_HOME:-${HOME}}/.local/bin"
SERVICE_DIR="${JARVIS_INSTALL_HOME:-${HOME}}/.config/systemd/user"
CONFIG_DIR="${JARVIS_INSTALL_HOME:-${HOME}}/.config/jarvis-voice"

echo "Installing JARVIS Voice Core..."

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$SERVICE_DIR" "$CONFIG_DIR"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Copy package and bin if not symlinked directly to repo
if [[ "$(readlink -f "$INSTALL_DIR")" != "$(readlink -f "$REPO_DIR")" ]]; then
    for package in voice_layer jarvis_voice jarvis_memory jarvis_control omarchy_voice skills \
                   core connectors filesystem orchestration proactive audio ui \
                   plugins skill_manifests quickshell scripts; do
        cp -r "$REPO_DIR/$package" "$INSTALL_DIR/"
    done
    cp "$REPO_DIR/agent.py" "$REPO_DIR/agent_orchestrator.py" "$REPO_DIR/task_runner.py" "$INSTALL_DIR/"
    cp -r "$REPO_DIR/bin" "$INSTALL_DIR/"
    cp "$REPO_DIR/LICENSE" "$REPO_DIR/PROVENANCE.json" "$INSTALL_DIR/"
    mkdir -p "$INSTALL_DIR/docs"
    cp "$REPO_DIR/JARVIS OS DOCS/references/jarvis-os/implementation/docs/omarchy-voice-port.md" "$INSTALL_DIR/docs/"
fi

# Link python virtual environment with required dependencies
if [[ -d "${REPO_DIR}/.venv" ]]; then
    ln -sfn "$(readlink -f "${REPO_DIR}/.venv")" "$INSTALL_DIR/.venv"
elif [[ -n "${VIRTUAL_ENV:-}" && -d "${VIRTUAL_ENV}" ]]; then
    ln -sfn "${VIRTUAL_ENV}" "$INSTALL_DIR/.venv"
elif command -v python3 &>/dev/null; then
    PY_BIN="$(command -v python3)"
    mkdir -p "$INSTALL_DIR/.venv/bin"
    ln -sfn "$PY_BIN" "$INSTALL_DIR/.venv/bin/python"
    ln -sfn "$PY_BIN" "$INSTALL_DIR/.venv/bin/python3"
fi

# Ensure default config exists
if [[ ! -f "$CONFIG_DIR/config.toml" && -f "$REPO_DIR/configs/config.toml.example" ]]; then
    cp "$REPO_DIR/configs/config.toml.example" "$CONFIG_DIR/config.toml"
fi

chmod +x "$INSTALL_DIR/bin/jarvis-voice" "$INSTALL_DIR/bin/jarvis" "$INSTALL_DIR/bin/jarvis-memory" "$INSTALL_DIR/bin/jarvis-control"

# Symlink CLIs to ~/.local/bin
ln -sf "$INSTALL_DIR/bin/jarvis-voice" "$BIN_DIR/jarvis-voice"
ln -sf "$INSTALL_DIR/bin/jarvis" "$BIN_DIR/jarvis"
ln -sf "$INSTALL_DIR/bin/jarvis-memory" "$BIN_DIR/jarvis-memory"
ln -sf "$INSTALL_DIR/bin/jarvis-control" "$BIN_DIR/jarvis-control"

# Install systemd service
cp "$REPO_DIR/systemd/jarvis-voice.service" "$SERVICE_DIR/"
systemctl --user daemon-reload

echo "Installed to $INSTALL_DIR"
echo "CLIs available at: ~/.local/bin/jarvis, ~/.local/bin/jarvis-voice, ~/.local/bin/jarvis-memory, and ~/.local/bin/jarvis-control"
echo ""
echo "Control JARVIS with:"
echo "  jarvis enable   - Enable and start JARVIS service"
echo "  jarvis disable  - Disable and stop JARVIS service"
echo "  jarvis restart  - Restart JARVIS service"
echo "  jarvis status   - Check status"
