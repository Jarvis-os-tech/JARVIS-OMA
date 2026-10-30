"""Memory configuration and validation."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
import json
import logging
import math
import os
from pathlib import Path
import tomllib
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    """Persistent memory and optional local background extraction settings."""
    enabled: bool = True
    path: str = ""  # Default resolves to XDG_STATE_HOME/jarvis/memory
    max_facts: int = 1000
    context_max_chars: int = 6000
    record_sessions: bool = True  # Continuous conversation memory across restarts
    auto_capture: bool = False
    extraction_model: str = ""
    extraction_url: str = "http://127.0.0.1:11434"
    obsidian_vault: str = ""
    obsidian_auto_sync: bool = True
    obsidian_timezone: str = "Asia/Kolkata"
    structured_capture: bool = True  # Local evidence-grounded extraction
    semantic_retrieval: bool = False  # Requires configured embedding model
    semantic_provider: str = "gemini"
    semantic_model: str = ""
    semantic_url: str = "http://127.0.0.1:11434"
    semantic_dimension: int = 768
    semantic_min_score: float = 0.55

    def validate(self) -> None:
        for name in (
            "enabled",
            "record_sessions",
            "auto_capture",
            "obsidian_auto_sync",
            "structured_capture",
            "semantic_retrieval",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"memory.{name} must be a boolean")
        for name in ("max_facts", "context_max_chars"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"memory.{name} must be a positive integer")
        for name in (
            "path",
            "extraction_model",
            "extraction_url",
            "obsidian_vault",
            "obsidian_timezone",
            "semantic_provider",
            "semantic_model",
            "semantic_url",
        ):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"memory.{name} must be a string")
        if self.semantic_provider not in ("gemini", "ollama"):
            raise ValueError("memory.semantic_provider must be gemini or ollama")
        if (
            isinstance(self.semantic_min_score, bool)
            or not isinstance(self.semantic_min_score, (int, float))
            or not 0 <= self.semantic_min_score <= 1
        ):
            raise ValueError("memory.semantic_min_score must be a number from 0 to 1")
        if (
            isinstance(self.semantic_dimension, bool)
            or not isinstance(self.semantic_dimension, int)
            or not 1 <= self.semantic_dimension <= 65536
        ):
            raise ValueError("memory.semantic_dimension must be an integer from 1 to 65536")
        try:
            ZoneInfo(self.obsidian_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("memory.obsidian_timezone must be a valid IANA timezone") from error
        if self.auto_capture and not self.extraction_model.strip():
            raise ValueError("memory.auto_capture requires a nonempty memory.extraction_model")
        if self.semantic_retrieval and not self.semantic_model.strip():
            raise ValueError("memory.semantic_retrieval requires memory.semantic_model")


@dataclass
class Config:
    """Root configuration container with memory section."""
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    def validate(self) -> None:
        self.memory.validate()


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in ("true", "1", "yes", "false", "0", "no"):
        raise ValueError(f"{name} must be a boolean (true/false, 1/0, yes/no)")
    return normalized in ("true", "1", "yes")


def _apply_env_overrides(config: Config) -> None:
    enabled_val = os.getenv("JARVIS_MEMORY_ENABLED")
    if enabled_val is not None:
        config.memory.enabled = _parse_bool(enabled_val, "JARVIS_MEMORY_ENABLED")

    path_val = os.getenv("JARVIS_MEMORY_PATH")
    if path_val is not None:
        config.memory.path = path_val


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration from a file or environment with defaults."""
    config = Config()
    if path is not None:
        p = Path(path)
        if p.is_file():
            content = p.read_text(encoding="utf-8")
            data: dict[str, Any]
            if p.suffix in (".toml", ""):
                try:
                    data = tomllib.loads(content)
                except Exception:
                    data = json.loads(content)
            else:
                data = json.loads(content)

            if not isinstance(data, Mapping):
                raise ValueError("Configuration mapping expected")

            memory_data = data.get("memory")
            if "memory" in data and not isinstance(memory_data, Mapping):
                raise ValueError("memory section must be a mapping")

            if isinstance(memory_data, Mapping):
                known_fields = {f.name for f in fields(MemoryConfig)}
                for key, value in memory_data.items():
                    if key in known_fields:
                        setattr(config.memory, key, value)
                    else:
                        log.warning("Unknown memory config key ignored: %s", key)

    _apply_env_overrides(config)
    config.validate()
    return config
