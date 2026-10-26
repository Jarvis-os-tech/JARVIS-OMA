#!/usr/bin/env bash
set -euo pipefail
JARVIS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
JARVIS_STATE="${JARVIS_LEARNING_DIR:-${JARVIS_ROOT}/.jarvis-learning}"
cd -- "$JARVIS_ROOT"
"${JARVIS_ROOT}/.venv/bin/python" -m learning --state-dir "$JARVIS_STATE" init
if [[ "${1-}" == "--setup-only" ]]; then
    "${JARVIS_ROOT}/.venv/bin/python" -m learning --state-dir "$JARVIS_STATE" status
    "${JARVIS_ROOT}/.venv/bin/python" -m learning --state-dir "$JARVIS_STATE" doctor
    exit 0
fi
exec "${JARVIS_ROOT}/run.sh" --learning-dir "$JARVIS_STATE" "$@"
