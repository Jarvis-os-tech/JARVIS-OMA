# Semantic memory agent board

| Card | Owner | Scope | Acceptance gate | State |
| --- | --- | --- | --- | --- |
| SEM-1 Embedding provider | Pasteur/Main | `jarvis_memory/embeddings.py`, provider tests | Gemini API-key + optional localhost provider, bounded output | Complete |
| SEM-2 Persistent vector cache | Poincare | `jarvis_memory/vector_store.py`, store tests | Restart-safe, model/content invalidation, 0600 permissions | Complete |
| SEM-3 Hybrid ranker | Bernoulli | `jarvis_memory/hybrid.py`, ranker tests | Deterministic fusion, current-state filter, provenance | Complete |
| SEM-4 Retrieval evaluation | Descartes | semantic acceptance/evaluation tests | Paraphrase, correction, deletion, poison, fallback, restart | Complete |
| SEM-5 Runtime integration | Main | config, bridge, skills, docs | Full suite, startup check, API key remains in memory | Complete |

Pipeline: source candidates → hydrate provenance/current state → trust and status
filters → lexical scorer + optional local semantic scorer → hybrid selector →
non-blocking cache maintenance.

The deployed configuration uses Gemini API-key embeddings because a local model is
not normally available. The API key is supplied in memory by the voice runtime and
is never persisted in the vector cache. Existing lexical/concept retrieval remains
the safe fallback when the API is unavailable.

Verification: all 194 core/Jarvis/memory tests pass. Two pre-existing Hermes CUA
environment tests remain outside this feature: the installed backend reports
`warning` instead of `success`, so its expected job payload is unavailable.
