# Memory Subsystem

The unified memory system for JARVIS-OMA consolidates all memory code, upstream references, tests, documentation, and data into this dedicated subsystem directory.

## Directory Structure

```
memory/
├── README.md               # Overview of memory organization and usage
├── __init__.py             # Memory package entrypoint
├── codes-dev/              # Development code, implementations, tests, and scripts
│   ├── jarvis_memory/      # Sovereign 4-Tier Memory Engine (bridge, knowledge, vector_store, embeddings)
│   ├── memory-system/      # Upstream reference memory bundle (01-facts to 07-cli, 99-support)
│   ├── scripts/            # Vault sync & registration utility scripts
│   ├── tests/              # Memory subsystem unit & integration test suite
│   └── docs/               # Architecture specs and semantic vector benchmarks
└── data/                   # Persistent data, vaults, and storage
    └── obsidian-vault/     # Obsidian Markdown vault, graph notes, and memory map
```

## Subsystems

1. **Active Engine (`codes-dev/jarvis_memory/`)**:
   - `bridge.py`: Main bridge unifying SQLite knowledge ledger, FTS5 index, SQLite vector cache, and Obsidian synchronizer.
   - `vector_store.py`: High-performance SQLite vector cache with cosine similarity math.
   - `embeddings.py`: Gemini API and Ollama embedding provider client adapters.
   - `knowledge.py`: SQLite WAL database storing facts, profiles, and FTS5 full-text indexing.
   - `store.py`: File-locked atomic JSONL fact store.
   - `session.py`: Conversation transcripts & multi-turn persistence.
   - `obsidian.py`: Live bidirectional Markdown note generation for Obsidian.

2. **Upstream Reference (`codes-dev/memory-system/`)**:
   - Upstream curated reference implementation preserving modular tiers (01-facts through 07-cli).

3. **Vault Data (`data/obsidian-vault/`)**:
   - Obsidian markdown notes (`JARVIS-OMA Memory/`), memory map, daily summaries, profile cards, and graph connections.
