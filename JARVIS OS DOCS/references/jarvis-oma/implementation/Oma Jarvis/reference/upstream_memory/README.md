# OpenJarvis Memory System — curated source

Every code path that constitutes OpenJarvis's memory system, organized by role
in the lifecycle. Extracted from [open-jarvis/OpenJarvis](https://github.com/open-jarvis/OpenJarvis)
at commit `ccf02ec7bdda2e2b344eeb8dd986d742ff458acc` (2026-10-12).

Files are copied **verbatim**. Nothing is edited, so `diff` against upstream
always works. The only synthesized file is `99-support/config-memory-excerpt.py`,
which lifts memory-related classes out of a 2300-line config module.

Roughly 5,100 lines of Python, 3,200 lines of Rust, 4,000 lines of tests.

---

## The one thing to understand first

**The memory system is five separate stores, not one.** They share a config
section and some vocabulary, but they have different lifetimes, different
backends, and different write paths. Most confusion when reading OpenJarvis
comes from assuming they are one thing.

| # | Memory | Store | Written by | Read into | Folder |
|---|--------|-------|------------|-----------|--------|
| 1 | **Prompt files** | `SOUL.md`, `MEMORY.md`, `USER.md` | The agent itself, via a tool | Every system prompt, whole file, hard-capped | `04-prompt-files/` |
| 2 | **Auto facts** | `memory_facts.jsonl` | Background LLM thread | Injected facts block | `01-facts/` |
| 3 | **Document store** | `memory.db` (SQLite FTS5 et al.) | Explicit index commands | Top-k chunks prepended to queries | `02-document-store/` |
| 4 | **Sessions** | SQLite `session_messages` | Every chat turn | Conversation history | `05-sessions/` |
| 5 | **Knowledge graph** | `knowledge_graph.db` | `kg_*` tools, web search | Pattern queries | `02-document-store/` |

---

## The second thing: where the trust boundary actually is

This was verified against the compiled artifact, not inferred from the docs.

**Compiled into the `.so`** (`rust/`, symbol + string evidence from the
17MB unstripped `libopenjarvis_rust.so`):

- All retrieval backends — SQLite FTS5, FAISS, ColBERT, BM25, Hybrid, KnowledgeGraph
- The injection scanner — all 11 regexes present as literal strings
- Session store with consolidate/decay

**Python only — zero occurrences in the binary:**

- `trusted_for_recall`, `RECALLABLE_TRUST_TIERS`, quarantine logic
- `SOUL.md` / `MEMORY.md` / `USER.md`
- The entire fact-store trust model

Consequence: the retrieval engine is mandatory native code (`sqlite.py` raises
`MemoryBackendUnavailable` with no Python fallback), but **the entire
provenance model exists only in Python**. A decompiler audit of the shipped
artifact will not surface the trust gate.

---

## Folder map

```
01-facts/            Auto-extracted durable facts (memory #2) — Python only
  python/store.py        Fact, FactStore, LocalFactStore, trust tiers, locking
  python/extractor.py    FactExtractor — LLM distills facts from one turn
  python/service.py      MemoryService — background queue + worker thread
  (no rust/ dir: nothing about facts is compiled — verified by symbol/string
   absence of trusted_for_recall, RECALLABLE, quarantine, memory_facts)

02-document-store/   Retrieval backends (memory #3, #5)
  python/sqlite.py         thin PyO3 wrapper over the Rust store
  python/bm25.py  faiss_backend.py  colbert_backend.py  dense.py  hybrid.py
  python/knowledge_graph.py
  python/chunking.py       paragraph-aware 512/64/50 split
  python/ingest.py         file + directory walking, type detection
  python/embeddings.py     Embedder ABC, SentenceTransformerEmbedder
  python/_stubs.py         MemoryBackend ABC, RetrievalResult
  rust/sqlite.rs           THE actual FTS5 store — bm25(documents_fts, 1.0, 0.5)
  rust/faiss.rs  colbert.rs  hybrid.rs  knowledge_graph.rs  bm25.rs
  rust/traits.rs  utils.rs  backend_enum.rs
  rust/pyo3_storage.rs.fixed   post-fix bindings (defect 3)

03-context-injection/  Read path where #2 and #3 become prompts (python only)
  python/context.py    inject_context(), build_context_message(), trust filters

04-prompt-files/     Persona memory (memory #1)
  python/builder.py         SystemPromptBuilder — frozen prefix + caps
  python/memory_manage.py   the tool that lets the agent edit MEMORY.md

05-sessions/         Session history (memory #4)
  python/session.py     SessionStore, consolidate, decay, channel linking
  python/compression.py four compressors for context-window overflow
  rust_sessions.rs      the compiled store (flat, not in a rust/ subdir — the
                        Rust surface here is one file, not a module tree)

06-trust-gate/       Injection scanner — the gate on every memory write
  python/injection_scanner.py  11 patterns, Rust-preferred with Python fallback
  python/types.py               ScanFinding, ThreatLevel
  rust_injection.rs             the compiled scanner
  rust_scanner.rs               secret/PII scanner
  rust_types.rs  rust_lib.rs

07-cli/              User-facing surface
  python/memory_cmd.py    index | search | list | trust | clear | stats
  python/chat_cmd.py.fixed   post-fix chat REPL (defect 2)

99-support/          Wiring the above depends on
  config-memory-excerpt.py  memory config classes, lifted out of config.py
  knowledge_tools.py        kg_* MCP tools
  registry.py               MemoryRegistry, FactStoreRegistry
  events.py                 MEMORY_STORE / MEMORY_RETRIEVE / CHAT_EXCHANGE_COMPLETED
  routes.py.fixed           post-fix server routes (defect 2)

patches/            Fixes for the four defects — apply to upstream
  01-faiss-persistence-doc-correction.patch
  02-routes-use-configured-fact-accessor.patch
  02b-chat-cmd-use-configured-fact-accessor.patch
  03-pyo3-expose-delete-clear.patch
  04-enable-storage-suite-delete-clear-tests.patch

tests/               23 files, ~4400 lines (incl. test_trust_gate.py)

docs/                VERIFICATION.md, SHA256SUMS, DEFECT-FIXES.md
```

---

## Lifecycle

### Write path (facts)

```
chat turn completes
  └─> CHAT_EXCHANGE_COMPLETED published on the event bus
      └─> MemoryService.submit()  → queue (max 256), returns immediately
          └─> worker thread
              ├─ scan exchange  ── high/critical? → DROP the whole exchange
              ├─ FactExtractor  ── LLM → JSON array of ≤10 facts, ≤200 chars
              ├─ scan each fact ── flagged? → trust=untrusted (quarantine)
              └─ LocalFactStore.add_many_with_trust()
                  ├─ dedupe (exact, case-insensitive)
                  ├─ evict oldest past max_facts (FIFO, no salience)
                  └─ atomic flush: flock + unique temp file + os.replace
```

Never blocks the request path. Every per-job error is swallowed, including
`BrokenPipeError` on client disconnect and Rust `PanicException`.

### Read path

```
query
  ├─ facts  = load_configured_facts()   → recallable only
  ├─ results = backend.retrieve()       → top-k from memory.db
  ├─ drop quarantined docs BEFORE budgeting
  ├─ facts capped at ½ the token budget when docs exist; newest first
  ├─ fill remaining budget with docs
  └─> one system message, folded into existing system prompt, forced to index 0
        (Ollama rejects a non-initial system message)
```

### Trust tiers

| Tier | Meaning | Recallable |
|------|---------|-----------|
| `""` (legacy) | Written before provenance existed | Yes — so upgrading never silently wipes memory |
| `auto` | Auto-extracted, scanner-clean | Yes |
| `trusted` | Human vouched via `jarvis memory trust N` | Yes |
| `untrusted` | Scanner flagged this fact's own text | **No** |
| anything else | Unknown future tier | **No** — fails closed |

Asymmetric by design: a later hostile derivation **can** demote a recallable
fact, but nothing auto-promotes. Promotion requires explicit human review.

---

## Verified behavior

Executed against the built `libopenjarvis_rust.so` and the Python modules, not
read from docs:

- **Trust logic** — hostile re-derivation demotes; clean re-add does *not*
  promote back; only `promote_reviewed` restores. Confirmed.
- **Legacy + unknown tiers** — `""` recallable, unknown tier fails closed. Confirmed.
- **Concurrency** — 30 processes × 10 concurrent writes → 300/300 unique lines,
  zero corruption, zero malformed. The `flock` + unique-tempfile design holds.
- **Injection scanner** — benign prefs clean; `ignore all previous instructions`,
  `; rm -rf /`, and `<|im_start|>system` all flagged at the documented levels.
- **FTS5 query safety** — `NEAR(a b)`, `''`, `!!!` all return 0 rows without
  error. The non-alphanumeric split neutralizes FTS5 operators.
- **FIFO cap** — `max_facts=10` with 15 writes keeps exactly the newest 10.

---

## Known defects — all four fixed

Every defect found by REA has a patch in `patches/` and proof of the fix.
Full detail in [`docs/DEFECT-FIXES.md`](docs/DEFECT-FIXES.md).

```bash
git apply patches/*.patch     # applies cleanly to upstream ccf02ec
```

| # | Defect | Fix |
|---|--------|-----|
| 1 | Docs claimed FAISS is in-memory-only; it persists to SQLite | `01-faiss-persistence-doc-correction.patch` |
| 2 | `routes.py` + `chat_cmd.py` used unfiltered `list_facts()` | `02-*`, `02b-*` |
| 3 | PyO3 bindings never exposed `delete`/`clear` for BM25, Hybrid, KG | `03-pyo3-expose-delete-clear.patch` |
| 4 | Trust gate had no test; 5 stale skips hid it | `04-*` + `tests/test_trust_gate.py` |

Test suite: **226 passed / 14 skipped → 313 passed / 10 skipped.**

---

## Test status

`tests/` is upstream's memory suite plus the new `test_trust_gate.py`. Run
against a 3.12+ interpreter with the native extension importable:

```bash
PYTHONPATH=/path/to/OpenJarvis/src python -m pytest \
  tests/memory/ tests/tools/test_storage_tools.py \
  tests/tools/test_knowledge_graph.py tests/tools/test_memory_manage.py \
  tests/security/test_injection_scanner.py tests/cli/test_memory_cmd.py -q
# 313 passed, 10 skipped in ~1.5s
```

The 10 remaining skips are all genuine optional-dependency imports: `faiss`,
`colbert`, `rank_bm25`, `sentence_transformers`, PyTorch. No "known
limitation" skips remain.

Requires Python 3.12+ for the native extension — `PyErr_SetRaisedException`
in the pyo3 0.29 ABI. A 3.11 interpreter loads no memory backend at all.

---

## Design limits worth knowing

- **Auto memory is off by default.** `[memory] enabled = false`. You must opt in.
- **1000-fact cap is pure FIFO.** No salience, no recency weighting, no
  summarization. Your most important preference ages out exactly as fast as trivia.
  Selection at read time is newest-first, so it is recency-biased at both ends.
- **Fact dedupe is exact string match.** "Prefers dark mode" and "User likes
  dark mode" are two facts forever.
- **No fact correction path.** The model cannot edit facts via a tool — only
  `MEMORY.md`. The only removal is `jarvis memory clear`, which wipes everything.
- **#1 and #2 never reconcile.** Facts do not consolidate into `MEMORY.md`.
- **Chunking counts whitespace tokens**, not model tokens. `max_context_tokens`
  is likewise a whitespace approximation.
- **`context_from_memory` + cloud inference is refused** by
  `data_boundary_audit.py` — facts are local and would leak.