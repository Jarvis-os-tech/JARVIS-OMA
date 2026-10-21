"""Local memory state paths, independent of OpenJarvis configuration."""

import os
from pathlib import Path


def get_config_dir() -> Path:
    """Return the memory directory under XDG_STATE_HOME (or ~/.local/state)."""
    state_home = os.environ.get("XDG_STATE_HOME")
    root = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return root / "jarvis-oma" / "memory"


DEFAULT_CONFIG_DIR = get_config_dir()

__all__ = ["DEFAULT_CONFIG_DIR", "get_config_dir"]
