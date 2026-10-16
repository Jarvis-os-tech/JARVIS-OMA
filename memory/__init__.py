"""Memory subsystem root package for JARVIS-OMA."""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_CODES_DEV_DIR = _PKG_DIR / "codes-dev"
_DATA_DIR = _PKG_DIR / "data"

if str(_CODES_DEV_DIR) not in sys.path:
    sys.path.insert(0, str(_CODES_DEV_DIR))

# Expose primary data directory path
VAULT_DATA_PATH = _DATA_DIR / "obsidian-vault"

__all__ = ["VAULT_DATA_PATH", "codes_dev_dir"]

def codes_dev_dir() -> Path:
    return _CODES_DEV_DIR
