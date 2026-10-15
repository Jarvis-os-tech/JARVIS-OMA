#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${AGENT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${AGENT_DIR}/.env"
    set +a
fi

# Hardening PipeWire Quantum Buffer allocations for Ultra-Low Latency
export PIPEWIRE_LATENCY="${PIPEWIRE_LATENCY:-128/48000}"
export PIPEWIRE_QUANTUM="${PIPEWIRE_QUANTUM:-128/48000}"
export PYTHONUNBUFFERED=1

PYTHON="${AGENT_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON=python3

log_info() { echo -e "\e[32m[JARVIS-AUDIO-INIT]\e[0m $*"; }

# Attempt RT class configuration; gracefully degrade on standard kernels
if command -v chrt >/dev/null 2>&1 && chrt --rr 50 true >/dev/null 2>&1; then
    log_info "Elevating voice process to Real-Time SCHED_RR priority 50..."
    exec chrt --rr 50 "$PYTHON" "${AGENT_DIR}/agent.py" "$@"
else
    log_info "Standard scheduling active (SCHED_RR not permitted without RT privileges)."
    exec "$PYTHON" "${AGENT_DIR}/agent.py" "$@"
fi
