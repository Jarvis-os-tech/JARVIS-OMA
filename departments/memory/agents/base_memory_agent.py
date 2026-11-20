"""Base agent class for the JARVIS OS Memory Department.
Provides secret redacting, database handles, and Obsidian vault access.
"""

from abc import ABC
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

from core.secret_env import is_secret_name

from ..config import config, MemoryConfig
from ..db import MemoryDatabase

logger = logging.getLogger("departments.memory.agents")

# High-entropy & API credential signatures to redact
SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),                      # Google / Gemini API key
    re.compile(r"(nvapi-[A-Za-z0-9_-]{32,})"),                   # NVIDIA NIM API key
    re.compile(r"(ghp_[0-9a-zA-Z]{36})"),                        # GitHub Personal Access Token
    re.compile(r"(gho_[0-9a-zA-Z]{36})"),                        # GitHub OAuth Token
    re.compile(r"(sk-[a-zA-Z0-9_-]{32,})"),                      # OpenAI / generic secret key
    re.compile(r"(Bearer\s+[A-Za-z0-9\._\-]{20,})", re.IGNORECASE), # Bearer tokens
    re.compile(r"((?:password|secret|token)\s*[:=]\s*['\"][^'\"]{4,}['\"])", re.IGNORECASE),
]


def write_private_text(path: Path, content: str) -> None:
    """Replace a complete private file while preserving the previous version on write failure."""
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            staged.write(content)
            staged.flush()
            os.fsync(staged.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@dataclass
class MemoryCandidate:
    id: str
    layer: str                                 # 'working', 'semantic', 'episodic', 'procedural'
    category: str                              # 'preference', 'hardware', 'rule', 'episode', 'task'
    title: str
    content: str
    importance: float = 0.5                    # 0.0 to 1.0
    provenance: str = "inferred_agent"         # 'explicit_user' vs 'inferred_agent'
    ttl_expires_at: Optional[int] = None
    obsidian_path: Optional[str] = None
    related_to: List[str] = field(default_factory=list) # List of related node IDs
    relation_type: str = "relates_to"


class BaseMemoryAgent(ABC):
    """Abstract base class for all 5 memory department agents."""

    agent_id: str = "M0"
    agent_name: str = "BaseMemoryAgent"

    def __init__(self, cfg: Optional[MemoryConfig] = None, db: Optional[MemoryDatabase] = None):
        self.cfg = cfg or config
        self.db = db or MemoryDatabase(self.cfg.db_path)
        self.logger = logging.getLogger(f"departments.memory.{self.agent_name}")

    def mask_secrets(self, text: str) -> str:
        """Replace all API keys, bearer tokens, and secrets with [REDACTED_SECRET]."""
        sanitized = text
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    def redact_diagnostics(self, value):
        if isinstance(value, dict):
            return {str(key): "[REDACTED_SECRET]" if is_secret_name(str(key)) or str(key).lower() == "authorization"
                    else self.redact_diagnostics(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.redact_diagnostics(item) for item in value]
        if isinstance(value, str):
            return self.mask_secrets(value)
        return value

    def ensure_obsidian_subfolder(self, layer_folder: str) -> Path:
        """Ensure an Obsidian layer directory exists."""
        target = self.cfg.obsidian_vault_path / layer_folder
        target.mkdir(parents=True, exist_ok=True)
        return target
