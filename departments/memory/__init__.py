"""JARVIS OS Memory Department.
A 5-agent sovereign cognitive memory system with 4 layers (Working, Semantic, Episodic, Procedural),
zero-RAM graph edges, FTS5 full-text search, and event-driven day rollover compaction.
"""

from .config import MemoryConfig, config
from .db import MemoryDatabase
from .department import MemoryDepartment, memory_dept
from .agents import (
    BaseMemoryAgent,
    MemoryCandidate,
    ExtractorGatekeeperAgent,
    ConsolidationAgent,
    ReflectionAgent,
    RetrievalRouterAgent,
    DayRolloverCompactorAgent,
)

__all__ = [
    "MemoryConfig",
    "config",
    "MemoryDatabase",
    "MemoryDepartment",
    "memory_dept",
    "BaseMemoryAgent",
    "MemoryCandidate",
    "ExtractorGatekeeperAgent",
    "ConsolidationAgent",
    "ReflectionAgent",
    "RetrievalRouterAgent",
    "DayRolloverCompactorAgent",
]
