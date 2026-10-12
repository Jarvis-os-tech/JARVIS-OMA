#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${AGENT_DIR}/.venv/bin/python" ]]; then
    exec "${AGENT_DIR}/.venv/bin/python" "${AGENT_DIR}/agent.py" "$@"
fi
exec python3 "${AGENT_DIR}/agent.py" "$@"
