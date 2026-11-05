#!/usr/bin/env bash
# Install locally; never modifies the audio server, original JARVIS or services.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
printf '%s\n' 'Installed. Run ./run.sh --check, then ./run.sh --model YOUR_LIVE_MODEL'
