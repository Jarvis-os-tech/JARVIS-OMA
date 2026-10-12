#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${AGENT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${AGENT_DIR}/.env"
    set +a
fi
if [[ -x "${AGENT_DIR}/.venv/bin/python" ]]; then
    exec "${AGENT_DIR}/.venv/bin/python" "${AGENT_DIR}/agent.py" "$@"
fi
exec python3 "${AGENT_DIR}/agent.py" "$@"
