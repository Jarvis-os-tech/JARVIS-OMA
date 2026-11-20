"""Install a hidden-at-startup panel into the existing shell; never start another GUI."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

PLUGIN_ID = "jarvis.widgets"


def install(config_home=None):
    root = Path(__file__).resolve().parents[1]
    config_home = Path(config_home or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    shell_config = config_home / "omarchy/shell.json"
    source = root / "ui/jarvis_widgets"
    destination = config_home / "omarchy/plugins" / PLUGIN_ID
    original = shell_config.read_bytes()
    config = json.loads(original)
    if config.get("version") != 1 or not isinstance(config.get("plugins", []), list):
        raise ValueError("Unsupported shell configuration; nothing changed")
    if destination.is_symlink():
        raise ValueError("Refusing to overwrite a linked plugin directory")
    if destination.exists():
        prior = json.loads((destination / "manifest.json").read_text())
        if prior.get("id") != PLUGIN_ID:
            raise ValueError("Destination belongs to a different plugin")
    backup_base = config_home / "omarchy/backups"
    backup_base.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="jarvis-widgets-" + time.strftime("%Y%m%d-%H%M%S") + "-", dir=backup_base))
    shutil.copy2(shell_config, backup / "shell.json")
    if destination.exists():
        shutil.copytree(destination, backup / "plugin")
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix in (".qml", ".js", ".json", ".py"):
            shutil.copy2(path, destination / path.name)
    if not any(item.get("id") == PLUGIN_ID for item in config.get("plugins", []) if isinstance(item, dict)):
        config.setdefault("plugins", []).append({"id": PLUGIN_ID})
    updated = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode()
    # A concurrent settings edit must not be overwritten by this installation.
    if shell_config.read_bytes() != original:
        raise RuntimeError("Shell settings changed during preparation; configuration not overwritten")
    descriptor, temporary = tempfile.mkstemp(prefix=".jarvis-widgets-", dir=shell_config.parent)
    try:
        os.fchmod(descriptor, shell_config.stat().st_mode & 0o777)
        with os.fdopen(descriptor, "wb") as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, shell_config)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"plugin": str(destination), "backup": str(backup), "shell_config": str(shell_config)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args()
    result = install()
    process = subprocess.run(["omarchy-shell", "shell", "rescanPlugins"], capture_output=True, text=True, timeout=5)
    result["rescan_ok"] = process.returncode == 0
    # Rescanning queues a reload. Wait for the new handler's real receipt.
    result["ready"] = False
    if result["rescan_ok"]:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                probe = subprocess.run(["omarchy-shell", "jarvis-canvas", "status"],
                                       capture_output=True, text=True, timeout=2)
                receipt = json.loads(probe.stdout)
                if probe.returncode == 0 and receipt.get("ok") is True and receipt.get("engine") == "composed-v1":
                    result["ready"] = True
                    break
            except (ValueError, AttributeError, subprocess.TimeoutExpired):
                pass
            time.sleep(0.25)
    print(json.dumps(result))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
