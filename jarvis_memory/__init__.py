"""Backward compatibility shim for jarvis_memory redirecting to memory/codes-dev/jarvis_memory."""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
_CODES_DEV_DIR = _PKG_DIR.parent / "memory" / "codes-dev"
_TARGET_DIR = _CODES_DEV_DIR / "jarvis_memory"

if str(_CODES_DEV_DIR) not in sys.path:
    sys.path.insert(0, str(_CODES_DEV_DIR))

__path__ = [str(_TARGET_DIR)]
