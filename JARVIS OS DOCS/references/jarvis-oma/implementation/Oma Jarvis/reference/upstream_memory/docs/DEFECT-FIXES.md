# Defect fixes

Four defects found by reverse-engineering the shipped artifact. All four are
fixed, and every fix is proven by execution — not by reading code.

Each patch applies cleanly to upstream commit
`ccf02ec7bdda2e2b344eeb8dd986d742ff458acc`:

```bash
cd /path/to/OpenJarvis
git apply /path/to/memory-system/patches/*.patch
```

The `.fixed` files next to each patch are the post-fix contents, kept for
review without needing to apply anything.

---

## 1. FAISS persistence was documented backwards

**Patch:** `01-faiss-persistence-doc-correction.patch`

Both `docs/architecture/memory.md` and `docs/user-guide/memory.md` claimed FAISS
was *"In-memory only — data is lost on restart"*, and the architecture
comparison table listed its persistence as `In-memory`.

Both claims are false. The Rust backend constructor is
`FAISSMemory(path=":memory:", dim=128)` and writes every document to a
`faiss_documents` SQLite table at the configured `db_path`.

Proven by executing the extension:

```
store a document → exit the process → fresh process
  count()              -> 1
  retrieve("concise")  -> [{"content": "The user prefers concise answers", ...}]
  sidecar file         -> faiss_p.db, tables: ['faiss_documents'], rows: 1
```

The docs were also wrong about deletion: they said soft-delete with the document
remaining in the index. The Rust code issues
`DELETE FROM faiss_documents WHERE id = ?1` — a hard delete.

**Impact:** anyone who read the docs and picked FAISS expecting scratch storage
is silently accumulating a permanent database they never asked for and do not
know how to clear.

**Fix:** corrected both files and both comparison tables, with the verified
behavior and the `:memory:` escape hatch documented.

---

## 2. Two call sites used the unfiltered fact accessor

**Patches:** `02-routes-use-configured-fact-accessor.patch`,
`02b-chat-cmd-use-configured-fact-accessor.patch`

`server/routes.py:182` and `cli/chat_cmd.py:442` both called
`memory_service.list_facts()`, which returns **every** stored fact including
quarantined `untrusted` ones. The other three call sites
(`system/orchestrator.py`, `cli/ask.py`, `sdk.py`) all use
`load_configured_facts()`, which filters.

This was not exploitable: `build_context_message()` re-filters via
`_trusted_facts()` regardless of what the caller passes. But it meant the
provenance model had two different entry points with different guarantees, and
the guarantee held only because of a second function nobody looking at
`routes.py` would know to check.

**Fix:** both sites now use `load_configured_facts()`. Verified:

```
raw list_facts()      -> 2 facts: ['auto', 'untrusted']
load_configured_facts -> 1 facts: ['auto']
PASS: quarantined fact excluded by the configured accessor
```

---

## 3. PyO3 bindings violated the `MemoryBackend` contract

**Patch:** `03-pyo3-expose-delete-clear.patch`

`MemoryBackend` (`02-document-store/python/_stubs.py:80-84`) declares `delete()`
and `clear()` as abstract methods. The Rust *traits* implement both for BM25,
Hybrid, and KnowledgeGraph — but the PyO3 wrapper classes never exposed them.

Measured against the same binary before and after:

| Class | before | after |
|---|---|---|
| `SQLiteMemory` | store, retrieve, delete, clear, count | unchanged |
| `FAISSMemory` | store, retrieve, delete, clear, count | unchanged |
| `ColBERTMemory` | store, retrieve, delete, clear, count | unchanged |
| `BM25Memory` | store, retrieve, **count** | store, retrieve, delete, clear, count |
| `HybridMemory` | store, retrieve, **count** | store, retrieve, delete, clear, count |
| `KnowledgeGraphMemory` | store, retrieve, **count** | store, retrieve, delete, clear, count |

Before the fix:

```
>>> HybridMemory(['sqlite','bm25']).delete('x')
AttributeError: 'builtins.HybridMemory' object has no attribute 'delete'
```

**Fix:** added the two methods to the three `#[pymethods]` blocks. Compiles
clean (`cargo build --release -p openjarvis-python`, 5.57s, no warnings), and
all six backends now satisfy the ABC.

---

## 4. The trust gate had no test pinning it

**Patch:** `04-enable-storage-suite-delete-clear-tests.patch` +
new `tests/test_trust_gate.py`

`context_min_score` defaults to `0.0`. An untrusted document retrieves at exactly
score `0.0`, so it passes `score >= min_score`. The compiled store applies **no**
trust filtering and returns it verbatim — verified:

```
backend returns: [('prefs.json', {'trust': 'trusted'}),
                  ('evil.txt',  {'trust': 'untrusted'})]
```

The only thing preventing a poisoned document from reaching a model prompt is
`_trusted_results()` in `03-context-injection/python/context.py`. No native-layer
enforcement, no schema constraint, no test.

**Fix:** `tests/test_trust_gate.py` — 10 tests pinning the invariant from both
sides: that the gate filters, *and* that the backend does not filter (so nobody
removes the gate on a false assumption).

Proven to actually bite — removing the filter from `context.py`:

```
5 failed, 5 passed
FAILED test_untrusted_fact_is_filtered_from_context_message
FAILED test_untrusted_document_is_filtered_from_context_message
FAILED test_untrusted_document_is_filtered_by_inject_context
FAILED test_unknown_provenance_tier_fails_closed_for_documents
FAILED test_non_mapping_metadata_fails_closed
```

With the filter restored: `10 passed`.

The patch also removes four **stale** skips from `test_storage_suite.py` that
documented defect 3 as an accepted limitation. With the bindings fixed those
skips hide passing tests. They were verified to fail against the unpatched
extension:

```
FAILED test_delete_document[bm25]      — bm25.py:91: AttributeError
FAILED test_clear_all[bm25]
FAILED test_delete_document[hybrid]
FAILED test_clear_all[hybrid]
```

---

## Result

| | before | after |
|---|---|---|
| tests passed | 226 | **313** |
| tests skipped | 14 | **10** |
| stale "known limitation" skips | 5 | **0** |

The 10 remaining skips are all genuine optional-dependency imports:
`faiss`, `colbert`, `rank_bm25`, `sentence_transformers`, and PyTorch.

Verify the whole set:

```bash
PYTHONPATH=/path/to/OpenJarvis/src python -m pytest \
  tests/memory/ tests/tools/test_storage_tools.py \
  tests/tools/test_knowledge_graph.py tests/tools/test_memory_manage.py \
  tests/security/test_injection_scanner.py tests/cli/test_memory_cmd.py -q
# 313 passed, 10 skipped
```

Requires Python 3.12+ so the native extension loads (`PyErr_SetRaisedException`
in the pyo3 0.29 ABI). A 3.11 interpreter silently loads no memory backend.