#!/usr/bin/env bash
set -euo pipefail

# Resolve symlinks to target script directory
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

export QML_IMPORT_PATH="$SCRIPT_DIR:${QML_IMPORT_PATH:-}"

# Toggle: Kill any existing instance if running
if pgrep -f "quickshell.*jarvis_shell/Shell.qml" >/dev/null; then
  pkill -f "quickshell.*jarvis_shell/Shell.qml" || true
  exit 0
fi

exec quickshell --path "$SCRIPT_DIR/Shell.qml" "$@"
