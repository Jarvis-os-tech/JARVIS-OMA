# Memory quality evaluation

This step measures memory before changing it. UI and GUI work is deferred.

The frozen synthetic corpus compares lexical-only, vector-only, production
weighted fusion and evaluation-only reciprocal rank fusion (RRF, k=60).
All four receive the same production-filtered structured-memory candidate pool
and a 20-candidate channel budget. Results are graded at 1, 3 and 5.

Report recall, reciprocal rank, nDCG and precision for answerable questions;
report nonempty retrieval for unanswerable questions separately. A returned
topical passage is not proof that a question can be answered. This evaluation
does not run an answer generator or grade hallucinated prose.

Explicit forbidden labels cover superseded, expired, deleted, proposed and
foreign-project entries. The foreign-project case probes a desired boundary;
it does not assume the current recall API implements project filtering.
Lifecycle checks exercise correction, forgetting, restart, document refresh,
device filtering and another user's conversation boundary through MemoryBridge.

Default embeddings are supplied fixed test vectors. They test ranking and
integration deterministically, not natural-language embedding quality. Query
labels and vectors are hand-authored; even the named held-out partition is
visible in this repository and is not an independent generalization benchmark.
Optional Ollama runs use only this synthetic corpus and a specified local model.
They must report the exact model identity and may not silently fall back to
test vectors or lexical-only results.

Quality targets for production weighted fusion: held-out recall@5 >= 0.90,
no forbidden results, no nonempty results on no-answer probes, and all lifecycle
checks passing. Existing failures are reported honestly, not relabelled as
success. No retrieval algorithm or live configuration is automatically promoted.

## Run

```sh
.venv/bin/python scripts/evaluate_memory.py --report /tmp/memory-quality.json
.venv/bin/python scripts/evaluate_memory.py --strict --report /tmp/memory-quality-strict.json
.venv/bin/python scripts/evaluate_memory.py --baseline tests/fixtures/memory_quality/baseline.json --report /tmp/memory-quality-comparison.json
```

Default mode exits zero for a completed measurement even when quality targets
fail. `--strict` exits one for unmet targets. Baseline mode exits one for a new
per-query production regression and rejects incompatible suites/providers or
missing cases. Evaluation errors write failed evidence and exit two. The
checked-in baseline deliberately records existing failures; CI prevents new
regressions, not a claim that all memory-quality targets are already met.

To measure an already-installed local Ollama model on the synthetic corpus:

```sh
.venv/bin/python scripts/evaluate_memory.py --embedding ollama --model YOUR_INSTALLED_MODEL --dimension YOUR_MODEL_DIMENSION --report /tmp/memory-quality-ollama.json
```

This does not install a model or activate live semantic retrieval. Do not compare
an Ollama run against the fixed-vector baseline. Provider identity, fixture hash
and implementation hashes are recorded. Latency is shared cold/warm production
retrieval time per query, not independent per-strategy timing or a voice SLA.

## Measured baseline · 2026-11-04

18 synthetic entries, 16 query probes (11 held out), four strategies and three
cutoffs produce 64 ranked query/strategy cases. Nine bridge lifecycle checks pass.

| Strategy | Held-out recall@5 | MRR@5 | nDCG@5 |
| --- | ---: | ---: | ---: |
| Lexical | 0.667 | 0.583 | 0.580 |
| Fixed-vector | 1.000 | 1.000 | 1.000 |
| Production weighted blend | 1.000 | 1.000 | 1.000 |
| Experimental RRF | 1.000 | 1.000 | 1.000 |

These values describe the supplied vectors and hand-labelled probes, not the
accuracy of a real embedding model. The hybrid and RRF variants return passages
for all five held-out no-answer probes. Foreign-project material appears in two
held-out hybrid probes; other forbidden lifecycle states do not appear. A related
passage is not an answer, so this diagnoses missing answerability selection rather
than proving that JARVIS spoke a fabricated answer.

The first priorities are explicit scope-aware selection and answerability or
abstention evaluation. RRF has no measured ranking advantage in this pilot and
is not promoted.

A read-only status check of the installed service found conversation recording
and structured capture enabled, model-based extraction not running, and semantic
retrieval disabled. Its active backend is lexical/concept retrieval. Neither this
configuration nor the user's saved memories was changed. UI/GUI work is deferred.

Attribution: CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M.
Adamek (Impact Brussels ASBL).
