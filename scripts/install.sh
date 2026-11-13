#!/usr/bin/env bash
# scripts/install.sh — Install JARVIS Voice Core
set -euo pipefail

INSTALL_HOME="$(realpath -m -- "${JARVIS_INSTALL_HOME:-${HOME}}")"
RUNTIME_ROOT="$INSTALL_HOME/.local/share/jarvis-runtime"
RELEASES_DIR="$RUNTIME_ROOT/releases"
CURRENT_LINK="$RUNTIME_ROOT/current"
BIN_DIR="$INSTALL_HOME/.local/bin"
SERVICE_DIR="$INSTALL_HOME/.config/systemd/user"
CONFIG_DIR="$INSTALL_HOME/.config/jarvis-voice"

echo "Installing JARVIS Voice Core..."

mkdir -p "$RELEASES_DIR" "$BIN_DIR" "$SERVICE_DIR" "$CONFIG_DIR"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Install a fresh standalone release only when there is no active release.
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
    [[ -d "$CURRENT_LINK" ]] || { echo "Existing runtime current pointer is invalid: $CURRENT_LINK" >&2; exit 1; }
    INSTALL_DIR="$(readlink -f "$CURRENT_LINK")"
    FRESH_INSTALL=0
else
    INSTALL_DIR="$(mktemp -d "$RELEASES_DIR/install.XXXXXXXX")"
    FRESH_INSTALL=1
    for package in voice_layer jarvis_voice jarvis_memory jarvis_control skills \
                   core connectors filesystem orchestration proactive audio ui \
                   plugins skill_manifests quickshell scripts learning contracts configs departments teaching_mode packaging; do
        # Only copy existing directories to support both lean checkouts and legacy structures
        if [[ -e "$REPO_DIR/$package" ]]; then
            cp -r "$REPO_DIR/$package" "$INSTALL_DIR/"
        fi
    done
    cp "$REPO_DIR/agent.py" "$REPO_DIR/agent_orchestrator.py" "$REPO_DIR/task_runner.py" "$INSTALL_DIR/"
    cp -r "$REPO_DIR/bin" "$INSTALL_DIR/"
    cp "$REPO_DIR/requirements.txt" "$REPO_DIR/requirements-dev.txt" "$REPO_DIR/config.toml.example" "$INSTALL_DIR/"
    cp "$REPO_DIR/LICENSE" "$REPO_DIR/PROVENANCE.json" "$INSTALL_DIR/"
    mkdir -p "$INSTALL_DIR/docs"
    cp "$REPO_DIR/JARVIS OS DOCS/references/jarvis-os/implementation/docs/omarchy-voice-port.md" "$INSTALL_DIR/docs/"
fi

# Select the interpreter without changing an existing release.
if [[ -x "$INSTALL_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
elif [[ -x "$RUNTIME_ROOT/venv/bin/python" ]]; then
    PYTHON_BIN="$RUNTIME_ROOT/venv/bin/python"
elif [[ "${FRESH_INSTALL:-0}" == 1 && -d "${REPO_DIR}/.venv" ]]; then
    ln -s "$(readlink -f "${REPO_DIR}/.venv")" "$INSTALL_DIR/.venv"
    PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
elif [[ "${FRESH_INSTALL:-0}" == 1 && -n "${VIRTUAL_ENV:-}" && -d "${VIRTUAL_ENV}" ]]; then
    ln -s "${VIRTUAL_ENV}" "$INSTALL_DIR/.venv"
    PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
elif [[ "${FRESH_INSTALL:-0}" == 1 ]] && command -v python3 &>/dev/null; then
    PY_BIN="$(command -v python3)"
    mkdir -p "$INSTALL_DIR/.venv/bin"
    ln -s "$PY_BIN" "$INSTALL_DIR/.venv/bin/python"
    ln -s "$PY_BIN" "$INSTALL_DIR/.venv/bin/python3"
    PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
else
    echo "Runtime has no usable Python interpreter: $INSTALL_DIR" >&2
    exit 1
fi

# Finish config setup before making a fresh runtime reachable.
if [[ ! -f "$CONFIG_DIR/config.toml" && -f "$REPO_DIR/configs/config.toml.example" ]]; then
    cp "$REPO_DIR/configs/config.toml.example" "$CONFIG_DIR/config.toml"
fi

if [[ "$FRESH_INSTALL" == 1 ]]; then
    chmod +x "$INSTALL_DIR/bin/jarvis-voice" "$INSTALL_DIR/bin/jarvis" "$INSTALL_DIR/bin/jarvis-memory" "$INSTALL_DIR/bin/jarvis-control"
fi

# Check the payload before making it reachable through current or the CLIs.
for required in bin/jarvis-voice bin/jarvis bin/jarvis-memory bin/jarvis-control \
                orchestration/task_events.py contracts/task-event-v1.json \
                learning/__init__.py configs/config.toml.example requirements.txt; do
    if [[ ! -f "$INSTALL_DIR/$required" ]]; then
        echo "Runtime is incomplete (missing $required): $INSTALL_DIR" >&2
        exit 1
    fi
done
if [[ ! -f "$INSTALL_DIR/voice_layer/__main__.py" && ! -f "$INSTALL_DIR/jarvis_voice/__main__.py" ]]; then
    echo "Runtime voice entry point is missing: $INSTALL_DIR" >&2
    exit 1
fi
if [[ "$FRESH_INSTALL" == 0 && ! -f "$INSTALL_DIR/release.json" ]]; then
    echo "Existing runtime is missing release metadata: $INSTALL_DIR/release.json" >&2
    exit 1
fi
for command in jarvis-voice jarvis jarvis-memory jarvis-control; do
    if [[ ! -x "$INSTALL_DIR/bin/$command" ]]; then
        echo "Runtime command is missing or not executable: $INSTALL_DIR/bin/$command" >&2
        exit 1
    fi
done
"$PYTHON_BIN" - "$INSTALL_DIR" "$FRESH_INSTALL" <<'PY'
import json
import importlib.util
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
fresh = sys.argv[2] == "1"
sys.path.insert(0, str(root))
missing = []
for module in ('google.genai', 'numpy', 'sounddevice', 'onnxruntime', 'openwakeword',
               'httpx', 'pydantic', 'websockets', 'jsonschema'):
    try:
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    except (ImportError, ValueError):
        missing.append(module)
if missing:
    raise SystemExit('Missing runtime dependencies: ' + ', '.join(missing)
                     + '. Install requirements.txt in the selected Python environment first.')
from orchestration.task_events import CONTRACT
import learning

if not CONTRACT:
    raise SystemExit("Task event contract is empty")
if fresh:
    now = time.time()
    (root / "release.json").write_text(json.dumps({
        "commit": "local-install",
        "branch": "local",
        "created_at": now,
        "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "message": "Installed from local checkout",
        "schema_version": 1,
    }, indent=2) + "\n", encoding="utf-8")
else:
    metadata = json.loads((root / "release.json").read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1 or not metadata.get("commit"):
        raise SystemExit("Existing runtime release metadata is invalid")
PY
if [[ "$FRESH_INSTALL" == 1 ]]; then
    "$INSTALL_DIR/bin/jarvis-voice" --help >/dev/null
fi

if [[ "$FRESH_INSTALL" == 1 ]]; then
    # Publish only the fully copied, importable, and metadata-bearing release.
    ln -s "$INSTALL_DIR" "$CURRENT_LINK"
fi

# Symlink CLIs to ~/.local/bin
ln -sf "$CURRENT_LINK/bin/jarvis-voice" "$BIN_DIR/jarvis-voice"
ln -sf "$CURRENT_LINK/bin/jarvis" "$BIN_DIR/jarvis"
ln -sf "$CURRENT_LINK/bin/jarvis-memory" "$BIN_DIR/jarvis-memory"
ln -sf "$CURRENT_LINK/bin/jarvis-control" "$BIN_DIR/jarvis-control"
if [[ -f "$CURRENT_LINK/bin/jarvis-monitor" ]]; then
    ln -sf "$CURRENT_LINK/bin/jarvis-monitor" "$BIN_DIR/jarvis-monitor"
fi

# Install systemd services
cp "$REPO_DIR/systemd/jarvis-voice.service" "$SERVICE_DIR/"
if [[ -f "$REPO_DIR/systemd/jarvis-monitor.service" ]]; then
    cp "$REPO_DIR/systemd/jarvis-monitor.service" "$SERVICE_DIR/"
fi
systemctl --user daemon-reload

echo "Installed to $INSTALL_DIR"
echo "CLIs available at: ~/.local/bin/jarvis, ~/.local/bin/jarvis-voice, ~/.local/bin/jarvis-memory, ~/.local/bin/jarvis-control, and ~/.local/bin/jarvis-monitor"
echo ""
echo "Control JARVIS with:"
echo "  jarvis enable   - Enable and start JARVIS service"
echo "  jarvis disable  - Disable and stop JARVIS service"
echo "  jarvis restart  - Restart JARVIS service"
echo "  jarvis status   - Check status"
