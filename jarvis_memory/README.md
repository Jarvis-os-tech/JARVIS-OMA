# JARVIS memory runtime integration

This package adapts the curated OpenJarvis sources in `../memory-system/`, commit
`ccf02ec7bdda2e2b344eeb8dd986d742ff458acc`. The source bundle is not modified.

The reused Python components are the JSONL fact store and its cross-process lock,
trust scanner and types, paragraph chunker, SQLite session store, fact extractor,
and background memory service. Import dependencies are replaced by small local
path, registry, message and event contracts. Fact loading additionally tolerates
malformed row types and timestamps.

`bridge.py` adapts these APIs to JARVIS skills, filters recall by provenance and
scanner results, and formats bounded JSON data for the Gemini Live prompt.
Fact storage and continuous conversation-text storage default on. Conversation
history never expires or prunes automatically; recent context is restored at
startup and older history can be searched. Automatic extraction remains opt-in
and runs against a configured local Ollama endpoint.

The provided retrieval wrappers require a Rust extension absent from this
environment. The bridge exposes a distinctly named Python SQLite FTS5 document
port using the bundled chunker. It neither loads nor claims to implement FAISS,
ColBERT, hybrid vector retrieval, or the native knowledge graph. `memory_status`
reports this distinction. Existing OpenJarvis `memory.db` files are not migrated;
indexed documents use `jarvis_documents.db`.

JARVIS startup and checks do not create memory files unless a write, document
index, or explicitly enabled session/extraction service requires them. Recalled
facts and profiles are sent in Gemini prompts. Audio is never saved by this package.
