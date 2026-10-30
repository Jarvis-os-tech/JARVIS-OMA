"""Sovereign memory engine for JARVIS OS."""
from __future__ import annotations

from .config import Config, MemoryConfig, load_config
from .paths import DEFAULT_CONFIG_DIR, get_config_dir
from .scanner import InjectionScanner
from .store import LocalFactStore
from .chunking import chunk_text, ChunkConfig
from .knowledge import KnowledgeStore
from .vector_store import VectorStore
from .embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    OllamaEmbeddingProvider,
    StaticEmbeddingProvider,
    DeterministicFakeEmbeddingProvider,
)
from .bridge import MemoryBridge, MemoryError
from .skills import MemorySkills, DesktopSkills, SkillError
from .service_facade import UniversalMemoryService
from .importers import SiblingSessionImporter

__all__ = [
    "Config",
    "MemoryConfig",
    "load_config",
    "DEFAULT_CONFIG_DIR",
    "get_config_dir",
    "InjectionScanner",
    "LocalFactStore",
    "chunk_text",
    "ChunkConfig",
    "KnowledgeStore",
    "VectorStore",
    "EmbeddingError",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "StaticEmbeddingProvider",
    "DeterministicFakeEmbeddingProvider",
    "MemoryBridge",
    "MemoryError",
    "MemorySkills",
    "DesktopSkills",
    "SkillError",
    "UniversalMemoryService",
    "SiblingSessionImporter",
]
