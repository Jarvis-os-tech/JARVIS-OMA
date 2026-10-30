#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEST_SHARE="${HOME}/.local/share/pma-voice-only"
DEST_BIN="${HOME}/.local/bin"
DEST_CONFIG="${HOME}/.config/pma-voice-only"
DEST_SYSTEMD="${HOME}/.config/systemd/user"

echo "==> Installing PMA Voice Only runtime..."
mkdir -p "${DEST_SHARE}/bin" "${DEST_BIN}" "${DEST_CONFIG}" "${DEST_SYSTEMD}"

# Copy package and bin
cp -r "${ROOT_DIR}/pma_voice_only" "${DEST_SHARE}/"
cp "${ROOT_DIR}/bin/omarchy-voice" "${DEST_SHARE}/bin/omarchy-voice"
chmod +x "${DEST_SHARE}/bin/omarchy-voice"

# Copy metadata
cp "${ROOT_DIR}/LICENSE" "${DEST_SHARE}/LICENSE"
cp "${ROOT_DIR}/PROVENANCE.json" "${DEST_SHARE}/PROVENANCE.json"
cp "${ROOT_DIR}/README.md" "${DEST_SHARE}/README.md"

# Link CLI executable
ln -sf "${DEST_SHARE}/bin/omarchy-voice" "${DEST_BIN}/omarchy-voice"

# Default configuration if not present
if [ ! -f "${DEST_CONFIG}/config.toml" ]; then
    cp "${ROOT_DIR}/config/config.toml.example" "${DEST_CONFIG}/config.toml"
    chmod 600 "${DEST_CONFIG}/config.toml"
    echo "    Created default config at ${DEST_CONFIG}/config.toml"
fi

# Install systemd service
cp "${ROOT_DIR}/systemd/omarchy-voice.service" "${DEST_SYSTEMD}/omarchy-voice.service"
systemctl --user daemon-reload

echo "==> Installation complete!"
echo "To start the voice service:"
echo "    systemctl --user enable --now omarchy-voice.service"
echo "To check status:"
echo "    omarchy-voice status"
