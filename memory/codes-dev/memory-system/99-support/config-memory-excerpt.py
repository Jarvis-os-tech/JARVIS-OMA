"""Memory-related config extracted from openjarvis/core/config.py (2300+ lines).

The full file mixes ~40 config sections. These are the only pieces the memory
system reads. Kept verbatim except for the module header, which notes the
original location and line numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Original: src/openjarvis/core/config.py, class MemoryFilesConfig (~line 1655)
# ---------------------------------------------------------------------------


@dataclass
class MemoryFilesConfig:
    """Persistent memory-file paths and nudge settings."""

    soul_path: str = field(default_factory=lambda: str(get_config_dir() / "SOUL.md"))
    memory_path: str = field(
        default_factory=lambda: str(get_config_dir() / "MEMORY.md")
    )
    user_path: str = field(default_factory=lambda: str(get_config_dir() / "USER.md"))
    nudge_interval: int = 10
    persona_name: str = ""  # named persona dir under <config-dir>/personas/<name>/


# ---------------------------------------------------------------------------
# Original: src/openjarvis/core/config.py, class SystemPromptConfig (~line 1668)
# Caps applied when loading the three prompt files.
# ---------------------------------------------------------------------------


@dataclass
class SystemPromptConfig:
    """Limits and strategy for system-prompt assembly."""

    prefix: str = ""
    soul_max_chars: int = 4000
    memory_max_chars: int = 2500
    user_max_chars: int = 1500
    skill_desc_max_chars: int = 60
    truncation_strategy: str = "head_tail"


# ---------------------------------------------------------------------------
# Original: src/openjarvis/core/config.py, class StorageConfig (~line 954)
#
# This single dataclass configures BOTH the document retrieval store AND the
# automatic long-term fact service. That conflation is a known wart: the
# `[memory]` and `[tools.storage]` TOML sections both land here, and
# `MemoryConfig = StorageConfig` is a backward-compatibility alias.
# ---------------------------------------------------------------------------


@dataclass
class StorageConfig:
    """Storage (memory) backend settings.

    Covers both the retrieval/document store (``default_backend``, ``db_path``,
    chunking, context injection) and the automatic long-term memory service
    (``enabled``, ``backend``, ``extraction_model``, ``max_facts``,
    ``facts_path``) configured under ``[memory]`` in ``config.toml``.
    """

    # -- document retrieval store -----------------------------------------
    default_backend: str = "sqlite"
    db_path: str = field(default_factory=lambda: str(get_config_dir() / "memory.db"))
    context_top_k: int = 5
    context_min_score: float = 0.0  # NOTE: 0.0 lets a 0.0-score doc through; trust filter is the only gate
    context_max_tokens: int = 2048
    chunk_size: int = 512
    chunk_overlap: int = 64

    # -- automatic fact service -------------------------------------------
    enabled: bool = False  # start the memory service with serve/chat
    backend: str = "local"  # fact-store backend ("local" = on-disk JSONL)
    extraction_model: str = ""  # model for fact extraction ("" = active model)
    max_facts: int = 1000  # cap on stored facts (oldest evicted past the cap)
    facts_path: str = field(
        default_factory=lambda: str(get_config_dir() / "memory_facts.jsonl")
    )


# Backward-compatibility alias
MemoryConfig = StorageConfig


# ---------------------------------------------------------------------------
# Original: src/openjarvis/core/config.py, AgentConfig.context_from_memory
# (~line 1141) — the master switch for prompt-time injection.
# ---------------------------------------------------------------------------

# context_from_memory: bool = True  # inject relevant memory context into prompts


# ---------------------------------------------------------------------------
# Event types the memory system publishes/subscribes.
# Original: src/openjarvis/core/events.py lines 31-33
# ---------------------------------------------------------------------------

# MEMORY_STORE = "memory_store"
# MEMORY_RETRIEVE = "memory_retrieve"
# CHAT_EXCHANGE_COMPLETED = "chat_exchange_completed"


# ---------------------------------------------------------------------------
# Default TOML template (config.py ~line 2263). Copied verbatim.
# ---------------------------------------------------------------------------

DEFAULT_TOML = """
[agent]
default_agent = "simple"
max_turns = 10
context_from_memory = true

[tools.storage]
default_backend = "sqlite"

# Automatic long-term memory: extracts durable facts from conversations in the
# background and persists them. Starts/stops with `jarvis serve` and
# `jarvis chat`; manage stored facts with `jarvis memory list` / `clear`.
[memory]
enabled = false               # set true to enable the memory service
backend = "local"             # fact-store backend (local = on-disk JSONL)
extraction_model = ""         # model for fact extraction ("" = active model)
max_facts = 1000              # cap on stored facts
"""