"""Local memory state paths for JARVIS OS."""
import os
from pathlib import Path


def get_config_dir() -> Path:
    """Return the memory directory under XDG_STATE_HOME (or ~/.local/state)."""
    env_path = os.environ.get("JARVIS_MEMORY_PATH")
    if env_path:
        return Path(env_path)
    state_home = os.environ.get("XDG_STATE_HOME")
    root = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return root / "jarvis" / "memory"


DEFAULT_CONFIG_DIR = get_config_dir()

__all__ = ["DEFAULT_CONFIG_DIR", "get_config_dir"]
