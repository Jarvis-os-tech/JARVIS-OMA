# Sovereign Memory Subsystem Design — JARVIS OS

**Date:** 2026-10-30  
**Status:** Approved  
**Scope:** Integration of Sovereign 4-Tier Memory Engine into JARVIS OS  

---

## 1. Executive Summary

This specification establishes the persistent memory foundation for **JARVIS OS**. Adapted from the proven, production-grade 4-tier memory architecture of `JARVIS-OMA`, this subsystem provides sovereign, offline-first persistent knowledge storage, semantic vector retrieval, conversational session history, bidirectional Obsidian vault synchronization, and external Model Context Protocol (MCP) tooling.

The memory subsystem is packaged as a first-class root module (`jarvis_memory/`) alongside `jarvis_voice/`, completely eliminating the legacy path hacks (`sys.path.insert`) present in earlier prototypes.

---

## 2. Architecture & Subsystem Layout

```
JARVIS OS/
├── jarvis_memory/                     # Sovereign Python package
│   ├── __init__.py                    # Public API exports (MemoryBridge, KnowledgeStore, etc.)
│   ├── __main__.py                    # CLI entrypoint for python -m jarvis_memory
│   ├── bridge.py                      # Master orchestrator (FTS5 + SQLite Vector + Knowledge)
│   ├── knowledge.py                   # SQLite WAL database (facts, profiles, revisions)
│   ├── vector_store.py                # SQLite vector cache with native cosine math
│   ├── embeddings.py                  # Gemini and Ollama embedding provider adapters
│   ├── retrieval.py                   # BM25 + FTS5 lexical retrieval
│   ├── hybrid.py                      # Reciprocal Rank Fusion (RRF) & strength decay
│   ├── session.py                     # Conversation turns & transcript persistence
│   ├── capture.py                     # Real-time fact extraction from dialogues
│   ├── summarizer.py                  # Conversation & daily summarization
│   ├── obsidian.py                    # Bidirectional Obsidian markdown sync
│   ├── mcp_server.py                  # Standalone MCP memory server
│   ├── importers.py                   # Transcript & external knowledge importers
│   ├── store.py                       # Cross-process locked atomic JSONL backup store
│   ├── scanner.py                     # Prompt-injection & memory taint scanner
│   ├── chunking.py                    # Semantic boundary text chunker
│   ├── registry.py                    # Provider and backend registry
│   ├── paths.py                       # XDG and local path resolution
│   ├── service.py                     # Memory service abstraction
│   ├── service_facade.py              # Facade for agent tool invocation
│   ├── events.py                      # Internal memory events bus
│   ├── types.py                       # Data classes & type definitions
│   └── security_types.py              # Security & taint definitions
│
├── memory/                            # Subsystem reference assets & vaults
│   ├── memory-system/                 # Upstream reference implementations (Tiers 01-07)
│   ├── scripts/                       # Vault registration & synchronization utilities
│   │   ├── sync_obsidian_memory.py
│   │   └── register_obsidian_vault.py
│   └── data/obsidian-vault/           # Initial vault structure & graph templates
│
├── bin/
│   ├── jarvis-voice                   # Voice daemon CLI
│   └── jarvis-memory                  # Sovereign memory management CLI
│
├── tests/
│   ├── test_cli.py, test_daemon.py... # Existing 54 voice tests
│   └── test_memory/                   # 16 memory test suites (116 passing tests)
│
└── docs/memory/                       # Memory architecture specs & benchmark evaluations
```

---

## 3. Core Component Specifications

### 3.1 SQLite Knowledge Ledger (`knowledge.py`)
- **Engine**: SQLite in WAL (`Write-Ahead Logging`) mode with `NORMAL` synchronous mode and 60-second busy timeout.
- **Tables**:
  - `facts`: Fact ID, subject, predicate, object, confidence, source, timestamps, versioning.
  - `profiles`: Key-value user profiles with revision history.
  - `revisions`: Immutable audit log of all updates and deletions.
  - `facts_fts`: FTS5 virtual table for full-text search.

### 3.2 Vector Store & Embeddings (`vector_store.py`, `embeddings.py`)
- **Vector Storage**: SQLite-backed embedding cache with blob-encoded float arrays.
- **Distance Metric**: Exact dot-product cosine similarity calculated in Python/NumPy, bypassing heavy native library requirements.
- **Embedding Providers**: Adapter supporting Google GenAI embeddings (`text-embedding-004`) and local Ollama (`nomic-embed-text` / `all-minilm`).

### 3.3 Hybrid Retrieval & Ranking (`hybrid.py`, `retrieval.py`)
- **Algorithm**: Reciprocal Rank Fusion (RRF) with constant `k = 60`.
- **Decay Function**: Ebbinghaus-inspired temporal decay factoring memory age and reinforcement strength into final ranks.
- **Safety**: `InjectionScanner` verifies and strips prompt injection patterns prior to query execution and fact ingestion.

### 3.4 Conversation Capture & Summaries (`capture.py`, `session.py`, `summarizer.py`)
- **Session Tracking**: Multi-turn dialogue transcript logging with persistent turn indices.
- **Fact Extraction**: Rule-based heuristic and model-guided extraction of user preferences, system constraints, and biographical facts.
- **Summarization**: Rolling turn compression to maintain low token context windows.

### 3.5 Bidirectional Obsidian Synchronization (`obsidian.py`)
- **Vault Mapping**: Frontmatter-rich markdown files representing entities, daily memory notes, and structured profiles.
- **Conflict Handling**: Last-write-wins with hash-based change detection to prevent loop thrashing.

---

## 4. CLI Interface (`bin/jarvis-memory`)

A dedicated executable wrapper providing instant inspection and manipulation:
- `jarvis-memory stats`: Displays count of active facts, stored vectors, sessions, and database disk usage.
- `jarvis-memory search <query> [--limit N]`: Executes hybrid search and renders scored results.
- `jarvis-memory store <fact> [--subject S] [--source SRC]`: Directly writes a fact into knowledge and vector storage.
- `jarvis-memory sync [--vault PATH]`: Triggers full Obsidian vault synchronization.

---

## 5. Verification & Testing Requirements

1. **Subsystem Port**:
   - Zero syntax errors or missing relative imports.
   - Clean XDG default path resolution without hardcoded user directories.
2. **Unit & Integration Suite**:
   - All 16 ported memory test files located in `tests/test_memory/` must pass cleanly (116/116).
3. **Full Suite Zero-Regression Gate**:
   - Running `.venv/bin/pytest tests/ -v` must execute all 170 tests (54 voice + 116 memory) with 100% pass rate.
4. **CLI Validation**:
   - `bin/jarvis-memory --help` and `bin/jarvis-memory stats` return clean exit codes (0).
