-- JARVIS OS Sovereign Memory Graph Schema
-- 4-Layer Architecture: Working, Semantic, Episodic, Procedural
-- Zero-RAM Graph Edges & SQLite FTS5 Full-Text Search Index

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. NODES TABLE: Unified store for all 4 memory layers
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,                       -- e.g. "mem_sem_01931a2f"
    layer TEXT NOT NULL CHECK(layer IN ('working', 'semantic', 'episodic', 'procedural')),
    category TEXT NOT NULL,                    -- 'preference', 'hardware', 'rule', 'episode', 'task', 'project'
    title TEXT,                                -- Short human-readable title
    content TEXT NOT NULL,                     -- Main text content or JSON rule spec
    importance REAL DEFAULT 0.5,               -- 0.0 to 1.0 (signal rating)
    provenance TEXT DEFAULT 'inferred_agent',  -- 'explicit_user' vs 'inferred_agent'
    ttl_expires_at INTEGER,                    -- Unix timestamp (NULL = permanent memory)
    obsidian_path TEXT,                        -- Relative path in vault (e.g. "04 Semantic Memory/Facts/system.md")
    reinforcement_count INTEGER DEFAULT 1,     -- Number of times reinforced/repeated
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Indices for fast point lookups & TTL expiration
CREATE INDEX IF NOT EXISTS idx_nodes_layer ON memory_nodes(layer);
CREATE INDEX IF NOT EXISTS idx_nodes_category ON memory_nodes(category);
CREATE INDEX IF NOT EXISTS idx_nodes_ttl ON memory_nodes(ttl_expires_at);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON memory_nodes(importance);
CREATE INDEX IF NOT EXISTS idx_nodes_updated ON memory_nodes(updated_at);

-- 2. EDGES TABLE: Zero-RAM Graph for multi-hop relationship traversal
CREATE TABLE IF NOT EXISTS memory_edges (
    source_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK(relation IN ('caused_by', 'fixed_by', 'supersedes', 'relates_to', 'derived_from', 'subtask_of')),
    target_id TEXT NOT NULL,
    weight REAL DEFAULT 1.0,                   -- Strength of relationship (0.1 - 1.0)
    created_at INTEGER NOT NULL,
    PRIMARY KEY (source_id, relation, target_id),
    FOREIGN KEY (source_id) REFERENCES memory_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES memory_nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON memory_edges(relation);

-- 3. FTS5 FULL-TEXT SEARCH: Sub-5ms BM25 ranking without vector daemon
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    title,
    content,
    category UNINDEXED,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS5 synchronized with memory_nodes
CREATE TRIGGER IF NOT EXISTS trg_memory_nodes_ai AFTER INSERT ON memory_nodes BEGIN
    INSERT INTO memory_fts(id, title, content, category)
    VALUES (new.id, new.title, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS trg_memory_nodes_ad AFTER DELETE ON memory_nodes BEGIN
    DELETE FROM memory_fts WHERE id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_memory_nodes_au AFTER UPDATE ON memory_nodes BEGIN
    DELETE FROM memory_fts WHERE id = old.id;
    INSERT INTO memory_fts(id, title, content, category)
    VALUES (new.id, new.title, new.content, new.category);
END;

-- 4. EPISODIC REPLAY TRACES: Immutable log for evolution.py self-improvement
CREATE TABLE IF NOT EXISTS episodic_traces (
    id TEXT PRIMARY KEY,                       -- e.g. "trace_err_84f92a10"
    session_id TEXT NOT NULL,
    trigger_prompt TEXT NOT NULL,              -- What user or caller requested
    tool_name TEXT NOT NULL,                   -- e.g. "hyprctl_dispatch" or "shell_exec"
    tool_input TEXT NOT NULL,                  -- Exact JSON payload
    exit_code INTEGER NOT NULL,                -- 0 for success, >0 for failure
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    replay_status TEXT DEFAULT 'pending',      -- 'pending', 'replayed_passed', 'replayed_failed'
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_traces_created ON episodic_traces(created_at);
CREATE INDEX IF NOT EXISTS idx_traces_tool ON episodic_traces(tool_name);
CREATE INDEX IF NOT EXISTS idx_traces_status ON episodic_traces(replay_status);

-- 5. DAILY ROLLOVER LOG: Tracks rollover compaction events
CREATE TABLE IF NOT EXISTS daily_rollover_log (
    date TEXT PRIMARY KEY,                     -- 'YYYY-MM-DD'
    compacted_at INTEGER NOT NULL,
    raw_char_count INTEGER NOT NULL,
    compact_char_count INTEGER NOT NULL,
    tasks_carried_forward INTEGER NOT NULL,
    summary_preview TEXT
);
