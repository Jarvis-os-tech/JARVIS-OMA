# JARVIS OS — Sovereign Voice & Persistent Memory Foundation

A voice-first, persistent memory personal AI operating system foundation for transforming Linux and Omarchy into **JARVIS OS**.

## Architecture & Principles

JARVIS OS provides two tightly-integrated sovereign subsystems:

### 1. Sovereign Voice Core (`jarvis_voice`)
- **Ambient Acoustic Ear**: Continuous PipeWire audio capture (16 kHz PCM, 20 ms frames) with local Silero VAD speech detection.
- **Gemini Live Streaming**: Bidirectional audio transport with local turn detection and automatic startup greetings.
- **Interruption & Barge-in**: Generation-fenced playback cancellation discards queued audio instantly upon speech detection.
- **Hardened Error Recovery**: Supervised capture and session workers, explicit microphone backlog errors, and exponential backoff with a 60-second cooldown floor on HTTP 429.
- **Local Control Socket**: Listens on a protected Unix domain socket (`$XDG_RUNTIME_DIR/jarvis/control.sock`, chmod `0600`) for status queries, mute toggle, and cancel signals.

### 2. Sovereign 4-Tier Memory Engine (`jarvis_memory`)
- **SQLite WAL Knowledge Ledger**: Immutable revision history, fact deduplication, and atomic JSONL fallback store.
- **Vector Store & Semantic Embeddings**: SQLite-backed embedding cache with cosine math; supports Google GenAI (`text-embedding-004`) and Ollama.
- **Hybrid RRF Retrieval**: Reciprocal Rank Fusion (RRF) combining BM25 full-text indexing and semantic vector search with memory strength decay.
- **Continuous Conversation Memory**: Multi-turn dialogue transcript persistence across system restarts with rolling turn indexing.
- **Obsidian Synchronization**: Bidirectional synchronization with Obsidian Markdown vaults (`JARVIS-OMA Memory/`).
- **MCP Server**: Stdio Model Context Protocol interface exposing memory tools to agent fleets.

---

## Directory Structure

```
JARVIS OS/
├── jarvis_voice/              # Sovereign Voice Core
│   ├── config.py              # XDG config, paths, and environment loader
│   ├── daemon.py              # LiveVoice & Gemini Live duplex loop (integrated with memory)
│   ├── ipc.py                 # Protected Unix domain control socket server
│   ├── playback.py            # PipeWire playback engine & buffer
│   ├── recovery.py            # Hardened connection recovery logic
│   └── speech.py              # Silero VAD & turn gating
│
├── jarvis_memory/             # Sovereign 4-Tier Memory Package
│   ├── bridge.py              # MemoryBridge orchestrator
│   ├── knowledge.py           # SQLite WAL knowledge ledger
│   ├── vector_store.py        # SQLite vector cache & cosine similarity
│   ├── embeddings.py          # Gemini & Ollama embedding adapters
│   ├── retrieval.py           # BM25 + FTS5 lexical retriever
│   ├── hybrid.py              # Reciprocal Rank Fusion (RRF)
│   ├── session.py             # Conversation history persistence
│   ├── capture.py             # Rule-based & heuristic fact capture
│   ├── obsidian.py            # Bidirectional Obsidian vault sync
│   ├── mcp_server.py          # Model Context Protocol stdio server
│   ├── skills.py              # Memory tool router & voice adapter
│   └── config.py              # Memory configuration & validation
│
├── bin/
│   ├── jarvis-voice           # Voice daemon CLI wrapper
│   └── jarvis-memory          # Sovereign memory CLI wrapper
│
├── memory/                    # Upstream reference models, scripts & vault templates
│   ├── memory-system/         # Reference implementations (Tiers 01-07)
│   ├── scripts/               # Obsidian vault sync scripts
│   └── data/obsidian-vault/   # Memory vault notes
│
├── tests/
│   ├── test_cli.py ...        # Voice unit & integration tests (66 tests)
│   └── test_memory/           # Memory unit & integration test suites (119 tests)
│
└── docs/                      # Architectural specifications & design plans
```

---

## Quick Start & Verification

### 1. Run Verification Suite (185 Tests)
```bash
.venv/bin/pytest tests/ -v
```

### 2. Voice CLI Control
```bash
jarvis-voice --check
jarvis-voice status
jarvis-voice listen toggle
```

### 3. Memory CLI Control
```bash
# View storage statistics
jarvis-memory stats

# Store a fact
jarvis-memory store "User prefers dark mode and concise responses."

# Search memory
jarvis-memory search "concise responses"

# Sync with Obsidian vault
jarvis-memory sync --vault memory/data/obsidian-vault
```

### 3. Install & Enable Service
```bash
scripts/install.sh
systemctl --user enable --now jarvis-voice.service
```

### 4. CLI Control
```bash
jarvis-voice status
jarvis-voice status --json
jarvis-voice listen toggle
jarvis-voice listen cancel
```

## Voice response quality and timing

The foundation follows the organized source in
`/home/g0pi/Projects/JARVIS-OMA/Oma Jarvis/voice`; see
[the audio map](docs/voice-foundation.md) for the runtime components and checks.
Replies favor a clear, relaxed voice and short answers. The configured voice and
PCM playback buffering are preserved.

`device` selects the microphone source; `output_device` selects the speaker sink.
An empty value uses the system default. The CLI respects the configured model
unless `--model` or `GEMINI_LIVE_MODEL` overrides it.

`jarvis-voice status --json` exposes `latency.speech_end_to_first_audio_ms`
(local turn close to first accepted provider audio) and
`latency.first_audio_chunk_to_write_ms` (first queued audio to playback write).
These are software timings, not measured sound reaching the speaker. A null
value means the measurement is not available. Instant replies are not guaranteed:
local endpoint detection, provider response time, network, and playback all add delay.
