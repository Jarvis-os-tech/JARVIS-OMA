# Memory Department — JARVIS OS

A sovereign, multi-agent cognitive memory department for JARVIS OS. Separates storage across four distinct memory layers (Working, Semantic, Episodic, Procedural), runs with zero background RAM daemon overhead using SQLite FTS5 and recursive graph edges, and provides event-driven day rollover compaction for Obsidian notes.

---

## 🏛️ Four-Layer Memory Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. WORKING MEMORY (Hot Path: <5ms)                                                     │
│ • Transient state, active conversation buffer, active Hyprland window focus.           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. SEMANTIC MEMORY (Facts & Preferences: <30ms)                                        │
│ • Durable facts, user preferences, hardware configurations, project constraints.       │
│ • Syncs with Obsidian: 04 Semantic Memory/Facts/                                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. EPISODIC MEMORY (Time-Indexed Experiences: <50ms)                                   │
│ • Past session summaries, tool execution logs, and daily journals.                    │
│ • Syncs with Obsidian: 03 Episodic Memory/Conversations/YYYY-MM-DD.md                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. PROCEDURAL MEMORY (Learned Skills & Workflows: <10ms)                               │
│ • Learned solutions to runtime errors, tool guidelines, and workflow rules.           │
│ • Injected directly into Gemini Live instructions; syncs to 05 Procedural Memory/     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 The 5 Specialist Agents

```
departments/memory/
├── README.md                          # Department charter & guide
├── config.py                          # DB paths, Obsidian vault config, thresholds
├── schema.sql                         # SQLite WAL schema (nodes, edges, FTS5, traces)
├── db.py                              # Zero-RAM SQLite driver & recursive CTE engine
├── department.py                      # Department Lead & public API
└── agents/
    ├── base_memory_agent.py           # Base agent (secret redaction, DB/vault helpers)
    ├── a1_extractor_gatekeeper.py     # Write Path (Airlock: noise filter, provenance & TTL)
    ├── a2_consolidation_agent.py      # Update Path (ADD, UPDATE, SUPERSEDE, NO-OP)
    ├── a3_reflection_agent.py         # Learning Loop (Failure analysis -> procedural rules)
    ├── a4_retrieval_router.py         # Read Path (Sub-25ms FTS5 + Recursive Graph search)
    ├── a5_day_rollover_compactor.py   # Event-Driven Day Rollover & Compactor
    └── a6_vault_pruner_agent.py       # Vault Janitor & Empty File Cleaner
```

### 1. `a1_extractor_gatekeeper.py` (Write Path)
* Masks secrets and API keys via regex signatures (`AIza...`, `ghp_...`, `sk-...`).
* Drops chit-chat and low-signal noise.
* Rates importance (0.0 to 1.0) and assigns **Provenance** (`explicit_user` vs `inferred_agent`).
* Assigns **TTL** (temporary vs permanent).
* Traps failed tool calls into `episodic_traces` for replay test generation.

### 2. `a2_consolidation_agent.py` (Update Path)
* Evaluates candidates against existing knowledge using a **4-Way Decision Matrix**:
  * `ADD`: New node inserted into `memory_nodes`.
  * `UPDATE`: Existing node updated with fresh details.
  * `SUPERSEDE`: Contradicted facts archived with an edge: `(new) -[supersedes]-> (old)`.
  * `NO-OP`: Duplicate facts reinforce the existing node's `reinforcement_count`.
* Generates typed graph edges (`caused_by`, `fixed_by`, `relates_to`).
* Syncs formatted Markdown notes to the Obsidian vault.

### 3. `a3_reflection_agent.py` (Self-Learning Loop)
* Runs during system idle / overnight.
* Clusters failure traces from `episodic_traces`.
* Synthesizes new **Procedural Rules** in `state/procedural_rules.json` and Obsidian `05 Procedural Memory/`.
* Packages replay test harnesses for `orchestration/evolution.py` sandbox verification.
* Updates the living `user_profile.json`.

### 4. `a4_retrieval_router.py` (Read Path)
* Runs in **<25ms** synchronously before speech synthesis.
* Executes SQLite **FTS5 BM25** search + **Recursive CTE Graph Traversal** across `memory_edges`.
* Assembles a compact 250-word context packet for prompt injection into Gemini Live / Needle SLM.

### 5. `a5_day_rollover_compactor.py` (Event-Driven Compactor)
* Triggers whenever a new day file is born (not reliant on midnight clock timers; works after sleep/suspend).
* Scrubs raw command output, JSON dumps, and small talk from yesterday's daily file.
* Carries forward open `- [ ]` checklist tasks into today's fresh note.
* Overwrites yesterday's raw file with a clean 40–50 line executive Markdown summary.
* Logs rollover metrics to `daily_rollover_log` and SQLite episodic memory.

### 6. `a6_vault_pruner_agent.py` (Vault Janitor & Empty File Cleaner)
* **Sole Mandate:** Detects and removes 0-byte files, whitespace-only files, and blank frontmatter stubs.
* **Safety Guards:** Protects master dashboards (`00 HOME.md`, `INDEX.md`), ignored directories (`.obsidian/`, `.raw_backups/`), and today's active file.
* **Dangling Link Cleaner:** Cleans references in `INDEX.md` when an empty note is purged so no broken `[[wikilinks]]` remain.
