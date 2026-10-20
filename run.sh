#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${AGENT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${AGENT_DIR}/.env"
    set +a
fi

# Match PipeWire's client period to the 20 ms audio frames. A 128-sample
# (2.7 ms) period makes the Python callback race the device at speech onset.
export PIPEWIRE_LATENCY="${PIPEWIRE_LATENCY:-1024/48000}"
export PIPEWIRE_QUANTUM="${PIPEWIRE_QUANTUM:-1024/48000}"
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
eval "$(cd -- "$AGENT_DIR" && "$PYTHON" -m core.desktop_session)"

# The application also runs network, database and desktop work. Keep the
# process on normal scheduling; PipeWire manages its audio worker priority.
exec "$PYTHON" "${AGENT_DIR}/agent.py" "$@"
