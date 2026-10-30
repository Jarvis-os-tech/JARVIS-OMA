# Sovereign Memory Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the sovereign, 4-tier persistent memory subsystem (`jarvis_memory`) in JARVIS OS, ported from JARVIS-OMA with full SQLite WAL knowledge storage, vector similarity caching, hybrid RRF retrieval, Obsidian markdown synchronization, and a dedicated `jarvis-memory` CLI wrapper.

**Architecture:** Peer package architecture where `jarvis_memory` lives alongside `jarvis_voice` as a clean top-level Python package with zero path-munging hacks. SQLite WAL ledger stores atomic facts, SQLite vector store handles semantic embeddings, and `MemoryBridge` provides the unified entry point.

**Tech Stack:** Python 3.11+, SQLite3 (WAL mode & FTS5), NumPy / pure-math cosine similarity, Google GenAI SDK, Pytest.

**Spec:** [`docs/superpowers/specs/2026-10-30-memory-subsystem-design.md`](file:///home/g0pi/JARVIS%20OS/docs/superpowers/specs/2026-10-30-memory-subsystem-design.md)

## Global Constraints

- Python ≥ 3.11; standard library SQLite3 and existing `.venv` dependencies.
- Zero modifications to the 7 voice-core-locked files.
- Zero regressions in existing 54 voice tests (`tests/test_*.py`).
- No legacy `sys.path.insert` shims — relative imports (`from .xxx import yyy`) within `jarvis_memory/`.
- All tests executable via `.venv/bin/pytest tests/ -v`.
- Final target: 170+ total passing tests across voice and memory.

---

### Task 1: Package Scaffold & Foundational Primitives

**Files:**
- Create: `jarvis_memory/__init__.py`
- Create: `jarvis_memory/types.py`
- Create: `jarvis_memory/security_types.py`
- Create: `jarvis_memory/paths.py`
- Create: `jarvis_memory/events.py`
- Create: `jarvis_memory/scanner.py`
- Create: `jarvis_memory/store.py`
- Create: `jarvis_memory/chunking.py`
- Create: `jarvis_memory/registry.py`
- Create: `tests/test_memory/__init__.py`
- Create: `tests/test_memory/test_memory_config.py`

**Interfaces:**
- Produces: `jarvis_memory.paths.ensure_memory_dirs()`, `InjectionScanner.scan()`, `LocalFactStore`, `chunk_text()`.

- [ ] **Step 1: Create package directory and copy foundational modules from JARVIS-OMA**

Copy `types.py`, `security_types.py`, `paths.py`, `events.py`, `scanner.py`, `store.py`, `chunking.py`, `registry.py` from `/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/` into `jarvis_memory/`.

- [ ] **Step 2: Update paths resolution in `jarvis_memory/paths.py`**

Ensure `jarvis_memory/paths.py` uses standard XDG resolution (`~/.local/share/jarvis/memory` or `~/.jarvis/memory`) without hardcoded JARVIS-OMA paths.

- [ ] **Step 3: Port and adapt `tests/test_memory/test_memory_config.py`**

Port `test_memory_config.py` from `/home/g0pi/Projects/JARVIS-OMA/tests/test_memory/test_memory_config.py` into `tests/test_memory/test_memory_config.py`.

- [ ] **Step 4: Run test to verify foundational config tests pass**

Run: `.venv/bin/pytest tests/test_memory/test_memory_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit foundational primitives**

```bash
git add jarvis_memory/ tests/test_memory/
git commit -m "feat(memory): scaffold jarvis_memory package with core types, scanner, and store"
```

---

### Task 2: SQLite Knowledge Ledger & Vector Store

**Files:**
- Create: `jarvis_memory/knowledge.py`
- Create: `jarvis_memory/vector_store.py`
- Create: `jarvis_memory/embeddings.py`
- Create: `tests/test_memory/test_memory_knowledge.py`
- Create: `tests/test_memory/test_memory_vector_store.py`
- Create: `tests/test_memory/test_memory_embeddings.py`
- Create: `tests/test_memory/test_semantic_memory_eval.py`

**Interfaces:**
- Consumes: `jarvis_memory.types`, `jarvis_memory.store`, `jarvis_memory.scanner`
- Produces: `KnowledgeStore(path: Path)`, `VectorStore(path: Path)`, `GeminiEmbeddingProvider`, `OllamaEmbeddingProvider`

- [ ] **Step 1: Copy knowledge ledger and vector store modules**

Copy `knowledge.py`, `vector_store.py`, `embeddings.py` from `/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/` into `jarvis_memory/`.

- [ ] **Step 2: Port knowledge, vector store, and embedding tests**

Port:
- `tests/test_memory/test_memory_knowledge.py`
- `tests/test_memory/test_memory_vector_store.py`
- `tests/test_memory/test_memory_embeddings.py`
- `tests/test_memory/test_semantic_memory_eval.py`

- [ ] **Step 3: Run pytest on knowledge and vector tests**

Run: `.venv/bin/pytest tests/test_memory/test_memory_knowledge.py tests/test_memory/test_memory_vector_store.py tests/test_memory/test_memory_embeddings.py tests/test_memory/test_semantic_memory_eval.py -v`  
Expected: All tests PASS.

- [ ] **Step 4: Commit knowledge and vector store modules**

```bash
git add jarvis_memory/knowledge.py jarvis_memory/vector_store.py jarvis_memory/embeddings.py tests/test_memory/
git commit -m "feat(memory): add SQLite WAL knowledge ledger and vector store"
```

---

### Task 3: Retrieval, Hybrid RRF Ranking & Session Capture

**Files:**
- Create: `jarvis_memory/retrieval.py`
- Create: `jarvis_memory/hybrid.py`
- Create: `jarvis_memory/session.py`
- Create: `jarvis_memory/summaries.py`
- Create: `jarvis_memory/summarizer.py`
- Create: `jarvis_memory/capture.py`
- Create: `jarvis_memory/extractor.py`
- Create: `tests/test_memory/test_memory_retrieval.py`
- Create: `tests/test_memory/test_memory_hybrid.py`
- Create: `tests/test_memory/test_memory_strength.py`
- Create: `tests/test_memory/test_memory_summaries.py`
- Create: `tests/test_memory/test_memory_capture.py`

**Interfaces:**
- Consumes: `KnowledgeStore`, `VectorStore`, `InjectionScanner`
- Produces: `HybridSearchEngine`, `BM25Retriever`, `SessionStore`, `MemoryCapture`

- [ ] **Step 1: Copy retrieval and session capture modules**

Copy `retrieval.py`, `hybrid.py`, `session.py`, `summaries.py`, `summarizer.py`, `capture.py`, `extractor.py` into `jarvis_memory/`.

- [ ] **Step 2: Port retrieval, hybrid search, and session tests**

Port:
- `tests/test_memory/test_memory_retrieval.py`
- `tests/test_memory/test_memory_hybrid.py`
- `tests/test_memory/test_memory_strength.py`
- `tests/test_memory/test_memory_summaries.py`
- `tests/test_memory/test_memory_capture.py`

- [ ] **Step 3: Run pytest on retrieval and session tests**

Run: `.venv/bin/pytest tests/test_memory/test_memory_retrieval.py tests/test_memory/test_memory_hybrid.py tests/test_memory/test_memory_strength.py tests/test_memory/test_memory_summaries.py tests/test_memory/test_memory_capture.py -v`  
Expected: All tests PASS.

- [ ] **Step 4: Commit retrieval and session modules**

```bash
git add jarvis_memory/ tests/test_memory/
git commit -m "feat(memory): add hybrid RRF retrieval, strength decay, and session capture"
```

---

### Task 4: Memory Bridge, Importers, Obsidian Sync & Services

**Files:**
- Create: `jarvis_memory/bridge.py`
- Create: `jarvis_memory/importers.py`
- Create: `jarvis_memory/obsidian.py`
- Create: `jarvis_memory/service.py`
- Create: `jarvis_memory/service_facade.py`
- Create: `jarvis_memory/mcp_server.py`
- Modify: `jarvis_memory/__init__.py`
- Create: `tests/test_memory/test_memory_integration.py`
- Create: `tests/test_memory/test_memory_upgrade_integration.py`
- Create: `tests/test_memory/test_obsidian_memory.py`
- Create: `tests/test_memory/test_universal_memory_importers.py`
- Create: `tests/test_memory/test_universal_memory_mcp.py`
- Create: `tests/test_memory/test_universal_memory_service.py`

**Interfaces:**
- Produces: `MemoryBridge(base_dir: Path | str)`, `ObsidianSync`, `UniversalMemoryService`, `create_mcp_server()`

- [ ] **Step 1: Copy bridge, importers, obsidian, and services**

Copy `bridge.py`, `importers.py`, `obsidian.py`, `service.py`, `service_facade.py`, `mcp_server.py` into `jarvis_memory/`.
Update `jarvis_memory/__init__.py` to export the public API.

- [ ] **Step 2: Port remaining integration, obsidian, and service test suites**

Port:
- `tests/test_memory/test_memory_integration.py`
- `tests/test_memory/test_memory_upgrade_integration.py`
- `tests/test_memory/test_obsidian_memory.py`
- `tests/test_memory/test_universal_memory_importers.py`
- `tests/test_memory/test_universal_memory_mcp.py`
- `tests/test_memory/test_universal_memory_service.py`

- [ ] **Step 3: Run the full memory test suite**

Run: `.venv/bin/pytest tests/test_memory/ -v`  
Expected: All 16 test files pass (116 tests passing).

- [ ] **Step 4: Commit bridge, obsidian sync, and integration tests**

```bash
git add jarvis_memory/ tests/test_memory/
git commit -m "feat(memory): add MemoryBridge orchestrator, Obsidian sync, and MCP server"
```

---

### Task 5: Memory Reference Assets, Vault Storage & Upstream Docs

**Files:**
- Create: `memory/memory-system/` (copied from `JARVIS-OMA/memory/codes-dev/memory-system/`)
- Create: `memory/scripts/` (copied from `JARVIS-OMA/memory/codes-dev/scripts/`)
- Create: `memory/data/obsidian-vault/` (copied from `JARVIS-OMA/memory/data/obsidian-vault/`)
- Create: `docs/memory/` (copied from `JARVIS-OMA/memory/codes-dev/docs/`)

- [ ] **Step 1: Copy upstream reference architecture, scripts, and vault data**

Copy directories from `/home/g0pi/Projects/JARVIS-OMA/memory/` into `memory/` and `docs/memory/`.

- [ ] **Step 2: Commit memory reference assets and docs**

```bash
git add memory/ docs/memory/
git commit -m "docs(memory): add upstream reference system, scripts, and vault templates"
```

---

### Task 6: Sovereign Memory CLI (`bin/jarvis-memory`) & Verification Gate

**Files:**
- Create: `jarvis_memory/__main__.py`
- Create: `bin/jarvis-memory`
- Create: `tests/test_memory/test_memory_cli.py`

**Interfaces:**
- Produces: CLI commands `stats`, `search`, `store`, `sync`.

- [ ] **Step 1: Implement `jarvis_memory/__main__.py`**

Implement CLI argument parser handling `stats`, `search <query>`, `store <fact>`, and `sync`.

- [ ] **Step 2: Create executable `bin/jarvis-memory` wrapper**

Write `bin/jarvis-memory` shell script wrapper (chmod +x) matching `bin/jarvis-voice`.

- [ ] **Step 3: Write CLI tests in `tests/test_memory/test_memory_cli.py`**

Test help flags, stats output, store command, and search command.

- [ ] **Step 4: Run full project test suite**

Run: `.venv/bin/pytest tests/ -v`  
Expected: All 170+ tests pass with zero failures.

- [ ] **Step 5: Verify CLI commands live**

Run: `bin/jarvis-memory --help` and `bin/jarvis-memory stats`  
Expected: Clean exit code 0 and valid output.

- [ ] **Step 6: Commit CLI and final verification**

```bash
git add bin/jarvis-memory jarvis_memory/__main__.py tests/test_memory/test_memory_cli.py
git commit -m "feat(cli): add jarvis-memory CLI wrapper with stats, search, store, and sync"
```
