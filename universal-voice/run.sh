#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$BASE/.venv/bin/python" ]]; then
    printf '%s\n' 'Run ./install.sh first.' >&2
    exit 1
fi
# Run the installed copy without inheriting a parent JARVIS import path.
unset PYTHONPATH
cd /tmp
exec "$BASE/.venv/bin/python" -I -m universal_voice "$@"
