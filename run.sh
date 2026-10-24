#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${AGENT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${AGENT_DIR}/.env"
    set +a
fi

# Suggest a conservative client latency; negotiate the graph period separately.
export PIPEWIRE_LATENCY="${PIPEWIRE_LATENCY:-1024/48000}"
# Let AEC and device streams negotiate a compatible graph period. Forcing a
# process-wide period can conflict with the AEC's 10 ms processing blocks.
export PYTHONUNBUFFERED=1

# User services have a smaller PATH than interactive terminals. Agent CLIs are
# installed through mise; expose its stable shims without changing providers.
if [[ -d "${HOME}/.local/share/mise/shims" ]]; then
    export PATH="${HOME}/.local/share/mise/shims:${PATH}"
fi

PYTHON="${AGENT_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON=python3

# systemd may retain XDG_RUNTIME_DIR while omitting the active compositor's
# display identifiers. Recover only unambiguous values; .env values take priority.
eval "$(cd -- "$AGENT_DIR" && "$PYTHON" -m core.desktop_session --wait-seconds 20)"

# The application also runs network, database and desktop work. Keep the
# process on normal scheduling; PipeWire manages its audio worker priority.
exec "$PYTHON" "${AGENT_DIR}/agent.py" "$@"
