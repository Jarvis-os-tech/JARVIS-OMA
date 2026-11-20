# JARVIS OS — Sovereign Voice, Desktop Control & Persistent Memory Operating System

A voice-first, persistent memory personal AI operating system foundation for Linux and Omarchy. JARVIS OS integrates ambient acoustic interaction, sub-second local actuation, a multi-tier memory vault, modular external connectors, and durable multi-agent orchestration into a unified platform.

---

## 🏛️ System Architecture

JARVIS OS provides five tightly coupled, sovereign subsystems:

```
                                  ┌───────────────────────────────┐
                                  │       User Speech / CLI       │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                         ┌─────────────────────────────────────────────────┐
                         │   Human Interaction Engine (HIE) / voice_layer  │
                         │  • Silero VAD Turn Gating                       │
                         │  • Cactus-Needle Local Command Router (<200ms)  │
                         │  • Instant Situational Spoken Acknowledgements │
                         │  • Gemini Live Duplex Streaming                 │
                         │  • Interruption & Playback Cancellation Fence   │
                         └───────┬─────────────────────────────────┬───────┘
                                 │                                 │
                   Local Command │                    Cloud Action │
                                 ▼                                 ▼
┌──────────────────────────────────────────────┐  ┌────────────────────────────────────────────────┐
│         Sovereign Desktop Control            │  │          Hermes Agent Orchestration            │
│              (jarvis_control)                │  │                (orchestration)                 │
│  • Wayland Keyboard & Pointer Actuators      │  │  • Multi-Tier Agent Dispatching (FastAPI REST) │
│  • Hyprland Window & Workspace Management    │  │  • Durable Hermes Gateway & State Lineage      │
│  • Natural Language Parsing Service          │  │  • Standardized Task Event Lifecycle Contracts │
│  • Action Evidence Collector & Policy Gate   │  │  • Visual Notification Cards & Desktop Notices │
└──────────────────────┬───────────────────────┘  └────────────────────────┬───────────────────────┘
                       │                                                   │
                       └─────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │    Sovereign 4-Tier Memory & Knowledge      │
                      │               (jarvis_memory)               │
                      │  • SQLite WAL Knowledge Ledger              │
                      │  • Semantic Vector Embeddings Cache         │
                      │  • Reciprocal Rank Fusion (BM25 + Cosine)   │
                      │  • Automated Vault Cleaning & Quality Eval  │
                      │  • Bidirectional Obsidian Synchronization   │
                      │  • Model Context Protocol (MCP) Server      │
                      └──────────────────────┬──────────────────────┘
                                             │
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │          Connectors & Integrations          │
                      │                (connectors)                 │
                      │  • Composio Tool Authentication & Bridge    │
                      │  • API-Anything Generic REST/GraphQL        │
                      │  • Integration Health & Status Probes       │
                      └─────────────────────────────────────────────┘
```

---

## 🚀 Key Subsystems

### 1. Human Interaction Engine & Voice Core (`voice_layer`)
* **Ambient Acoustic Ear**: Continuous PipeWire audio capture (16 kHz PCM, 20 ms frames) with local Silero VAD turn gating.
* **Cactus-Needle Local Command Router**: Embedded high-speed speech recognizer executing offline desktop commands (volume, brightness, app launching, window workspaces, mute, standby) without sending audio to the cloud.
* **Situational Conversational Acknowledgements**: Pre-rendered, affirmative spoken acknowledgements (`On it`, `Looking into that`) matched dynamically to task context (agent tasks, browser searches, file operations, system actions) to eliminate cloud latency without annoying empty vocal fillers ("Ah", "Haa").
* **Duplex Cloud Streaming**: Resilient Gemini Live WebSocket session with automatic reconnection backoff, wake confirmation, and session resumption.
* **Playback Fencing & Interruption**: Generation-tracked audio buffer instantly halts and flushes speaker queues whenever speech is detected.

### 2. Sovereign Desktop Actuation & Control (`jarvis_control`)
* **Wayland Actuators**: Emulated input receipts via `wlr-virtual` / `uinput` for reliable Wayland keyboard typing, modifier chords, and pointer navigation.
* **Hyprland Window Management**: Programmatic workspace switching, window focus, tiling geometry, minimization, and process lifecycle management.
* **Natural Language Parsing Worker**: Dedicated local parsing service translating natural speech phrases into structured desktop actuator commands.
* **Safety & Execution Policy**: Gated execution boundary with denied shell patterns, confirmation words for irreversible actions, and dry-run preview capabilities.
* **Action Evidence Collector**: Structured telemetry recording timestamps, action parameters, verification receipts, and failure outcomes.

### 3. Sovereign 4-Tier Memory Vault (`jarvis_memory`)
* **SQLite WAL Ledger**: ACID-compliant knowledge base with fact deduplication, revision history, and atomic updates.
* **Hybrid RRF Retrieval**: Reciprocal Rank Fusion blending full-text FTS5 (BM25) with dense vector embeddings (`text-embedding-004` or Ollama).
* **Taxonomy & Categorization**: Structured schema classifying knowledge across preferences, workflow habits, technical context, entities, and temporal notes.
* **Quality & Evaluation Metrics**: Automated metrics (`evaluation.py`) assessing retrieval precision, factual recall, and stale memory decay.
* **Obsidian Vault Sync**: Continuous bidirectional sync with Obsidian markdown vaults (`JARVIS-OMA Memory/`).
* **MCP Interface**: Exposes memory tools via standard Model Context Protocol (stdio) for agent fleet consumption.

### 4. Connectors & External Integrations (`connectors/`)
* **Composio Bridge**: Out-of-the-box integration with Composio tools (GitHub, Google Workspace, Slack, Jira, etc.) with automatic session admission.
* **Agent Reach Connector**: High-performance multi-platform content reader and search engine across 15+ platforms (Reddit, YouTube transcripts, GitHub issues/discussions, Twitter/X, Bilibili, Xiaohongshu) via unified tools (`reach_read`, `reach_search`, `reach_transcript`, `reach_status`).
* **API-Anything Bridge**: Generic REST/GraphQL connector translating conversational requests into structured HTTP invocations.
* **Integration Health Status**: Live status and credential monitoring reporting connection states to system telemetry.

### 5. Hermes Multi-Agent Orchestration (`orchestration/`)
* **Hermes Gateway Worker**: Durable gateway managing background subagent execution with heartbeat monitoring and state persistence.
* **Hermes API Server**: Dedicated FastAPI REST interface (`orchestration/hermes_api.py`) exposing agent delegation endpoints.
* **Task Event Lifecycle**: Standardized UI event contracts (`task_events.py`) dispatching start, progress, milestone, receipt, and completion notifications.
* **Desktop Presentation Cards**: Rich Quickshell notification widgets rendering agent progress cards on the desktop.

### 6. Autonomous LinkedIn Department (`departments/linkedin/`)
* **12-Agent Autonomous Fleet**: Specialized multi-agent cluster powered by NVIDIA NIM for end-to-end B2B brand building, content scheduling, and profile optimization.
* **Content Sprints & Post Generation**: Autonomous content planning, viral hook formulation, formatting, and hashtag clustering.
* **Human-in-the-Loop Review Airlock**: Generated posts stage into a strict review queue (`linkedin_pending_reviews`) awaiting explicit user approval before publishing.
* **Profile Optimization & Auditing**: Automated profile sync, headline generation, skill positioning, and SEO audits.

### 7. Quickshell Sci-Fi Desktop Shell (`ui/jarvis_shell/`, `bin/jarvis-de`)
* **Native Wayland Desktop Environment**: Custom Quickshell desktop environment tailored for Hyprland and Omarchy.
* **Arc Reactor Core & Telemetry**: Dynamic CPU, GPU, memory, and network telemetry with ambient acoustic waveform visualization.
* **CyberDock & LeftNav**: Quick action application dock, workspace pager, and system control dashboard.
* **Agents Status Overview**: Real-time multi-agent activity monitors tracking active tasks, background workers, and fleet states.

### 8. Multi-Agent Memory Department (`departments/memory/`)
* **4-Layer Cognitive Hierarchy**: Strict separation across Working Memory (<5ms), Semantic Memory (<30ms), Episodic Memory (<50ms), and Procedural Memory (<10ms).
* **Zero-RAM SQLite Graph Engine**: Serverless SQLite WAL with FTS5 BM25 search and recursive CTE graph traversal—eliminating heavy background daemon RAM footprint.
* **Specialist Agent Cluster**: 6 dedicated memory agents handling extraction/redaction, 4-way consolidation (ADD, UPDATE, SUPERSEDE, NO-OP), procedural failure reflection, query routing, event-driven day rollover, and vault pruning.
* **Secret Redaction Airlock**: Ingest filter redacting sensitive credentials and keys (`AIza...`, `ghp_...`, `sk-...`) before storage.
* **Bidirectional Obsidian Sync**: Automatic structured sync with markdown vaults across daily notes and semantic category hierarchies.

---

## 📁 Repository Layout

```
JARVIS OS/
├── voice_layer/               # Human Interaction Engine & Voice Core
│   ├── daemon.py              # Duplex live voice loop and state orchestrator
│   ├── needle_router.py       # Cactus-Needle local command router (<200ms)
│   ├── needle_worker.py       # Subprocess worker for offline transcription
│   ├── acknowledgements.py    # Situational acknowledgement dispatcher
│   ├── interaction.py         # Interaction lifecycle & playback fence
│   ├── playback.py            # PipeWire audio sink and output buffer
│   ├── speech.py              # Silero VAD turn gating
│   ├── standby.py             # Low-power standby state controller
│   └── assets/                # Affirmative PCM acknowledgement audio assets
│
├── jarvis_control/            # Sovereign Desktop Control & Actuation
│   ├── tools.py               # Desktop actuators & tool execution engine
│   ├── wayland_keyboard.py    # Wayland keyboard simulation and receipts
│   ├── wayland_pointer.py     # Wayland pointer simulation & coordinate mapping
│   ├── parsing_service.py     # Local natural language command parsing
│   ├── execution_policy.py    # Security admission and confirmation policies
│   ├── evidence.py            # Execution receipts & audit logging
│   └── discovery.py           # Omarchy system architecture map
│
├── jarvis_memory/             # Sovereign 4-Tier Memory Vault
│   ├── bridge.py              # MemoryBridge facade orchestrator
│   ├── knowledge.py           # SQLite WAL knowledge ledger
│   ├── vector_store.py        # Vector embedding store & cosine math
│   ├── hybrid.py              # Reciprocal Rank Fusion (BM25 + Vector)
│   ├── categories.py          # Structured taxonomy & category definitions
│   ├── evaluation.py          # Retrieval quality evaluation metrics
│   ├── vault_layout.py        # Standardized filesystem vault conventions
│   ├── obsidian.py            # Bidirectional Obsidian markdown sync
│   └── mcp_server.py          # Model Context Protocol stdio server
│
├── connectors/                # External App & Service Connectors
│   ├── agent_reach.py         # Multi-platform content reader & search (Reddit, YT, X)
│   ├── composio.py            # Composio platform tool integration
│   ├── api_anything.py        # Generic REST/GraphQL API connector
│   ├── api_service.py         # Connector dispatcher service
│   └── integration_status.py  # Health & authentication monitor
│
├── departments/               # Autonomous Specialized Departments
│   ├── linkedin/              # 12-Agent LinkedIn Department (NVIDIA NIM)
│   │   ├── agents/            # Strategy, drafting, reviewing, and publishing agents
│   │   ├── content_sprint.py  # Sprint planning and schedule manager
│   │   ├── profile_audit.py   # Profile extraction, analysis, and recommendations
│   │   └── airlock.py         # Human-in-the-loop review queue and publishing gate
│   └── memory/                # Multi-Agent Cognitive Memory Department
│       ├── agents/            # Extractor, Consolidation, Reflection, Retrieval, Rollover
│       ├── db.py              # Zero-RAM SQLite driver & recursive CTE graph engine
│       ├── schema.sql         # SQLite schema (nodes, edges, FTS5, traces)
│       └── department.py      # Department Lead & public API
│
├── ui/                        # User Interface & Desktop Shells
│   ├── jarvis_shell/          # Quickshell Sci-Fi Desktop Environment
│   │   ├── Shell.qml          # Root Quickshell desktop wrapper
│   │   ├── CyberDock.qml      # Dynamic application dock & workspace switcher
│   │   ├── TopBar.qml         # System status, telemetry & media controls
│   │   └── ArcReactorCore.qml # Animated core telemetry & acoustic visualization
│   ├── hud/                   # Orbit HUD overlay widgets
│   ├── jarvis_widgets/        # Interactive desktop widgets & pairing QR
│   └── omarchy-ai.orbit/      # System tray aura field orbit
│
├── orchestration/             # Fleet Orchestration & Multi-Agent Bridge
│   ├── hermes_api.py          # FastAPI REST endpoint for agent delegation
│   ├── durable_hermes.py      # Durable Hermes gateway worker
│   ├── task_events.py         # Task event lifecycle contracts
│   ├── task_presentation.py   # Desktop notification presentation cards
│   ├── model_routes.py        # Model routing & fallback cascades
│   └── tool_tiers.py          # Tool permission tiers & isolation
│
├── bin/                       # Executable CLI Wrappers
│   ├── jarvis                 # Unified system CLI
│   ├── jarvis-de              # Desktop Environment launcher
│   ├── jarvis-shell           # Quickshell desktop interface
│   ├── jarvis-voice           # Voice daemon CLI wrapper
│   ├── jarvis-memory          # Memory vault CLI wrapper
│   └── jarvis-control         # Desktop control CLI wrapper
│
├── packaging/                 # Arch Linux & Distribution Packaging
│   ├── PKGBUILD               # Arch package specification
│   └── jarvis-de.desktop      # Wayland session desktop entry
│
├── scripts/                   # System Maintenance & Verification Scripts
│   ├── install.sh             # System package installer
│   ├── behavior_gate.py       # Behavior regression testing gate
│   └── clean_memory_vault.py  # Memory vault maintenance utility
│
├── tests/                     # Comprehensive Pytest Test Suites (2,100+ tests)
│   ├── test_hie_*.py          # Voice interaction engine test suite
│   ├── test_control/          # Desktop actuation test suite
│   ├── test_memory/           # Memory vault test suite
│   ├── test_connectors/       # Integration & connector test suite
│   └── test_orchestration/    # Hermes agent orchestration test suite
│
├── JARVIS OS DOCS/            # Architecture specifications & audit records
```

---

## 🛠️ CLI Tools & Everyday Usage

### Unified `jarvis` CLI
```bash
# Query system status, connectivity, and active models
jarvis doctor

# View real-time system monitor
jarvis monitor

# Execute desktop command directly
jarvis task "open firefox and navigate to github.com"
```

### Voice Core CLI (`jarvis-voice`)
```bash
# Check dependencies and audio devices without opening streams
jarvis-voice --check

# Inspect live status, latency metrics, and connection state
jarvis-voice status
jarvis-voice status --json

# Toggle active listening or enter low-power standby
jarvis-voice listen toggle
jarvis-voice standby

# Discard current speech and cancel active playback
jarvis-voice listen cancel
```

### Sovereign Memory CLI (`jarvis-memory`)
```bash
# View storage statistics and fact counts
jarvis-memory stats

# Store a verified personal fact
jarvis-memory store "User preferences: dark theme, 400ms turn silence, local command priority."

# Hybrid search across knowledge base
jarvis-memory search "theme preferences"

# Sync with external Obsidian vault
jarvis-memory sync --vault ~/Documents/Obsidian/JarvisVault
```

### Desktop Control CLI (`jarvis-control`)
```bash
# Run system discovery
jarvis-control discovery

# Test keyboard typing receipt
jarvis-control type "Hello from JARVIS OS"

# Focus specific window by title
jarvis-control focus "Terminal"
```

### Quickshell Sci-Fi Desktop Shell (`jarvis-shell` / `jarvis-de`)
```bash
# Launch the full JARVIS Wayland desktop session
jarvis-de

# Launch or preview the Quickshell desktop shell
jarvis-shell
```

### Autonomous LinkedIn Department
```bash
# Plan a 7-day content sprint
jarvis task "plan a 7-day LinkedIn sprint on Voice AI and Agentic Systems"

# Audit local profile strategy
jarvis task "audit my LinkedIn profile positioning"

# Review staged posts in the review queue
jarvis task "show pending LinkedIn reviews"
```

### Multi-Platform Agent Reach
```bash
# Search across social platforms and developer communities
jarvis task "search reddit for local LLM inference setups"

# Read article, discussion, or issue directly from URL
jarvis task "read https://github.com/astral-sh/uv/issues/1000"

# Fetch YouTube video transcript
jarvis task "fetch transcript for https://youtu.be/example"
```

### Cognitive Memory Department
```bash
# Store knowledge with secret redaction and 4-way consolidation
jarvis task "remember that our production port is 8080 and dark theme is preferred"

# Query semantic and episodic memories via recursive graph search
jarvis task "what do you know about our production configuration?"
```

---

## ⚙️ Service Management (systemd)

JARVIS OS runs as modular systemd user services:

```bash
# Install core packages and link binaries
./scripts/install.sh

# Enable and start user services
systemctl --user daemon-reload
systemctl --user enable --now jarvis-voice.service
systemctl --user enable --now jarvis-api-agent.service
systemctl --user enable --now jarvis-monitor.service
systemctl --user enable --now jarvis-shell.service
systemctl --user enable --now jarvis-os-speaker.service

# Check service status
systemctl --user status jarvis-voice.service
systemctl --user status jarvis-shell.service
systemctl --user status jarvis-os-speaker.service
journalctl --user -u jarvis-voice.service -f
```

---

## 🧪 Testing & Verification

JARVIS OS includes an exhaustive regression suite with over 2,100 unit and integration tests.

### 1. Run Full Python Test Suite
```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

### 2. Run Behavior Gate Checks
```bash
python scripts/behavior_gate.py --report
```

---

## 🔒 Security & Policy Boundaries

1. **Execution Admission**: Destructive shell invocations (e.g., `rm -rf`, disk formatting, system reboot) require explicit confirmation gates.
2. **Data Protection**: Personal facts and transcripts remain in sovereign local storage (SQLite WAL + Obsidian markdown) without telemetry or third-party leakage.
3. **Local Socket Permissions**: Control sockets in `$XDG_RUNTIME_DIR/jarvis/` are restricted to mode `0600` (user-only).
