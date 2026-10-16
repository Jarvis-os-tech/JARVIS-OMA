# JARVIS — Full-Duplex Voice & Vision OS for Omarchy / Arch Linux

[![CI](https://github.com/Jarvis-os-tech/JARVIS-OMA/actions/workflows/ci.yml/badge.svg)](https://github.com/Jarvis-os-tech/JARVIS-OMA/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Gemini Live API](https://img.shields.io/badge/Gemini-Live%20API-4285F4.svg)](https://ai.google.dev/)
[![Platform](https://img.shields.io/badge/platform-Omarchy%20%2F%20Arch%20Linux-1793d1.svg)](https://archlinux.org/)

**Everything for this agent is in this folder.** Copy it anywhere on an
Omarchy/Arch Linux desktop. It has no imports from the original Omarchy AI app.

`agent.py` is the conversation agent. `echo_cancel.py` provides the audio routing,
and `skills.py` connects Gemini function calls to a dynamically discovered set of
Omarchy desktop controls. Supervised local coding agents can develop capability
proposals in separate checkouts, with baseline tests, research, implementation,
sandboxed verification and review. See [capability development](docs/capability-development.md).

## Run

Requirements: Python 3.12+, a Gemini API key with Live access, working PipeWire
with `pactl` (for echo-cancellation routing), and PortAudio (`libportaudio2` / `sounddevice`).
No system service installation or restart is required.

Open a terminal **inside this folder**, then:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env  # optional: set your GEMINI_API_KEY
./run.sh --check
./run.sh --list-skills
./run.sh
```

Enter your Gemini API key at the hidden prompt. It is held in process memory and
not saved. An existing `GEMINI_API_KEY` environment variable also works. The agent
does not read the old project's credentials or `.env` files.

Speak when the terminal says **LIVE**. No wake word or button is needed. You can
speak while Gemini is speaking. Press **Ctrl+C** to stop microphone capture, close
the connection, stop playback and release the private audio routes. This version
uses stop/restart rather than a separate mute interface.

## Run as a system service (Boot & Shutdown Automation)

Install JARVIS as a systemd user service so it automatically activates on boot/login and gracefully deactivates on logout or system shutdown:

```bash
# Install and enable the systemd user service
./install-service.sh install

# Or use standard systemctl commands:
systemctl --user start jarvis.service     # Start JARVIS now
systemctl --user stop jarvis.service      # Stop JARVIS cleanly
systemctl --user status jarvis.service    # Check service status
systemctl --user restart jarvis.service   # Restart JARVIS

# Follow live service logs:
journalctl --user -u jarvis -f
```

The service is managed under `graphical-session.target` and receives `SIGTERM` on logout/shutdown, cleanly disconnecting Gemini Live, tearing down microphone streams, and releasing PipeWire echo-cancellation routes without zombie processes.

## Daemon Control Plane (`jarvisctl` / `voicectl`)

JARVIS operates a secure, mode-0600 UNIX domain socket server at `/run/user/$UID/jarvis.sock` for zero-overhead local IPC, external state monitoring, and widget integration (Quickshell, Waybar, or polybar):

```bash
# Query daemon status (JSON or formatted text)
./scripts/jarvisctl status
./scripts/jarvisctl status --json

# Mute / unmute microphone input instantly without dropping the session
./scripts/jarvisctl toggle
./scripts/jarvisctl mute
./scripts/jarvisctl unmute

# Barge-in: immediately cut off active AI speech playback
./scripts/jarvisctl interrupt

# Stream real-time daemon state and telemetry events
./scripts/jarvisctl subscribe

# Manage the background user service
./scripts/jarvisctl start
./scripts/jarvisctl stop
./scripts/jarvisctl restart
```

Optional settings and dynamic configuration:

```sh
./run.sh --voice Aoede --transcripts
./run.sh --model gemini-3.8-live
./run.sh --agent-name "Friday"
./run.sh --config ./config.toml
./run.sh --system-instruction "Custom prompt..."
./run.sh --greeting-prompt "Good morning! Jarvis online."
./run.sh --no-greet
./run.sh --no-interrupt
pactl list short sources
./run.sh --microphone YOUR_PHYSICAL_SOURCE_NAME
./run.sh --no-skills
```

Jarvis proactively greets the user upon activation and strictly answers in a single concise sentence by default. Settings can also be loaded automatically from a configuration file (`~/.config/jarvis-oma/config.toml`,
`./config.toml`, or `./config.json`; see `config.toml.example` for all options), or via environment
variables (`JARVIS_AGENT_NAME`, `JARVIS_VOICE`, `JARVIS_MODEL`, `JARVIS_CONFIG`, `JARVIS_GREET_ON_ACTIVATION`, `JARVIS_GREETING_PROMPT`, `JARVIS_SINGLE_SENTENCE`, `JARVIS_NO_INTERRUPT`, `GEMINI_LIVE_MODEL`).

## Dynamic Omarchy skills

Skills are enabled by default. At startup Jarvis reads JSON manifests from
`skill_manifests/`, validates their names and strict argument schemas, and gives
the discovered declarations to Gemini Live. The bundled manifests enable:

- **Capability development**: `start_development`, `development_status`, `list_development_jobs`, and `cancel_development` turn a concrete improvement request into a persisted, tested code proposal; proposals are not automatically activated.
- **Real-Time Vision & Camera**: `control_vision_mode` (continuous 1 FPS real-time streaming of desktop screen or hardware camera to Gemini Live), `capture_camera_frame` (direct V4L2 MJPEG hardware snapshot via high-speed C++ actuator), and `check_vision_hardware` (audits V4L2 cameras, Wayland/X11, and PipeWire).
- **Google Workspace connector**: Gmail search/read/drafts, Google Calendar events/calendars, Google Tasks, and read-only Drive, Docs, and Sheets are handled by the local OAuth connector in `connectors/google_workspace.py`. Existing accounts must reconnect once to grant the new Drive read permission; see `docs/voice-capability-wiring.md`.
- **GitHub connector & Repository Analysis**: `github_analyze_repository` (one-shot repository structure mapping and file excerpt extraction at pinned commits), `github_find_relevant_files`, `github_read_repository_files`, and issue/PR management in `connectors/github.py`.
- **Internet Search & Web Extraction**: `internet_search` (web search query connector) and `read_web_page` (headless markdown web page extractor in `connectors/browser.py`).

- **Application discovery & launch**: `list_applications`, `open_application` (XDG-compliant)
- **Web browsing**: `open_website` (safe public HTTP/HTTPS URLs)
- **Audio & display controls**: `adjust_volume`, `adjust_brightness`
- **Window & workspace management**: `switch_workspace`, `manage_window` (fullscreen, close, minimize, float, center, maximize via `hyprctl`)
- **System controls**: `lock_screen` (`loginctl`), `take_screenshot` (`grim`), `system_power` (safe sleep/hibernate via `systemctl`)
- **Network controls**: `toggle_wifi` (`nmcli`), `toggle_bluetooth` (`rfkill`)
- **Clipboard**: `read_clipboard` (`wl-paste`), `write_clipboard` (`wl-copy`)
- **Notifications**: `show_notification` with dynamic application name (`notify-send`)
- **Native reminders**: `create_reminder`, `list_reminders`, `cancel_reminder`, and `clear_reminders` through Omarchy's own reminder system
- **Todo List plugin**: create, search, edit, move, complete, reopen, delete, and clear completed tasks in the installed Omarchy Todo List widget
- **Desktop awareness & perception**: `inspect_screen` (Wayland capture + fast local OCR), `list_windows` (open apps across all workspaces), `focus_window` (bring apps to foreground), `list_workspaces`, and `get_system_resources` (real-time CPU, RAM, disk, and process monitoring)
- **Voice-controlled input bar**: say “open the input bar” to type, paste, or attach text, images, audio, PDFs, and files into the active conversation; say “close the input bar” to dismiss it
- **Proactive autonomy runtime**: persistent events and activity ledger, bounded planning and agent routing, monitored background delegation, plus global “pause Jarvis”, “resume Jarvis”, and “stop all Jarvis work” voice controls
- **Filesystem (Full Autonomy)**: `list_files`, `read_file` (with offset and pagination), `write_file`, `append_file`, `edit_file`, `make_directory`, `move_path`, `copy_path`, `trash_path`, `delete_path` (permanent removal with safety guards), `inspect_file` (file/directory metadata and line count), `search_files` (filename search), and `search_file_content` (content grep with line numbers and snippets)
- **Multi-step tasks**: `start_task`, `task_status`, `list_tasks`, and `cancel_task` for bounded background file jobs with per-step results
- **System agent orchestration**: discover and delegate to Codex, Claude Code, OpenCode, Gemini CLI, Hermes, and OMP; inspect progress and stop owned jobs
- **Persistent memory**: remember, recall, forget and clear facts; manage SOUL/MEMORY/USER profiles; index text documents for retrieval

Filesystem skills operate with full autonomy across user and project directories, running asynchronously via worker threads (`asyncio.to_thread`) to ensure zero voice streaming or PipeWire audio latency during disk I/O. Text reads support offset seeking and up to 100,000 characters per call; atomic writes and appends support up to 5 MiB. Critical system roots (`/`, `~`, `/etc`, `/usr`, `/boot`, `/bin`, etc.) are protected with safety guards against accidental deletion or displacement.

For a multi-step file request, JARVIS can inspect paths, submit a JSON plan of up
to 30 validated file actions, and report progress by task ID. Cancellation takes
effect before the next step; an operation already running may finish. Task records
are kept while this JARVIS process runs and are cleared on restart. The task
runner does not execute arbitrary shell commands or permanent deletion.

Agent orchestration uses `list_system_agents`, `delegate_agent`, `check_agent_job`,
`list_agent_jobs`, and `cancel_agent_job`. Delegate with an agent name, task prompt,
and absolute path to an existing workspace. JARVIS supervises up to four agents in
separate workspaces, reserves overlapping directories while jobs run, and retains
up to 50 job records in memory. Recent output is bounded and available through
`check_agent_job`; the live voice session receives a completion/failure notification.
Jobs time out after 15 minutes by default (configurable per job up to two hours).
Stopping JARVIS stops its owned agent processes. Completed file changes remain.

Agents use their existing login, configuration, and tool permissions. Installation
discovery does not verify login or quota. Permission requests that cannot be answered
headlessly may fail or time out; inspect the job output for details. Job records are
not restored after restarting JARVIS. This manages jobs launched by JARVIS, rather
than attaching to unrelated sessions already open in another application. Review an
agent's changes before treating a successful process exit as verified task completion.

Memory is adapted from the supplied `memory-system/` bundle; its curated originals
are preserved. State lives under `~/.local/state/jarvis-oma/memory/` by default
(or `XDG_STATE_HOME` / `[memory].path`). Memory facts and profiles are bounded and
included in Gemini's voice-session prompt, so recalled information is sent to
Google while using JARVIS. Quarantined facts and indexed documents are excluded.
Use “remember that I prefer English”, “what do you remember about me?”, or “forget
that fact”. `clear_memory` clears facts only; it preserves profiles and documents.

Text-document search uses the supplied chunker with a Python SQLite FTS5 adapter.
The original Rust vector/graph extension is not installed. JARVIS now also has an
optional semantic layer using the same in-memory Gemini API key as voice, a private
local SQLite vector cache, and deterministic lexical/semantic fusion. Persistent
conversation text is retained continuously by default (`record_sessions = true`),
without age-based resets or automatic transcript pruning. Set it to false to stop
new transcript storage and history recall. Recent context is loaded at startup;
`recall_memory` searches older saved conversations. Optional
background fact extraction uses the supplied MemoryService/FactExtractor with a
local Ollama model: set `auto_capture = true` and `extraction_model` under `[memory]`.
No extra cloud extraction calls are made. Settings are shown in `config.toml.example`.

Structured capture is on by default (`structured_capture = true`), independently
of transcript storage and optional model extraction. It conservatively captures
explicit user preferences, decisions, projects, remember requests, and task
requests. Assistant assertions never become user facts. Evidence, confidence,
source and revision status live in a separate local SQLite ledger. Clear language
and coding-agent preference changes supersede their previous value; unrelated
facts are not guessed to conflict. `correct_memory` uses a recalled memory ID,
and `memory_history` shows earlier revisions. Forget/clear also remove active
structured entries; transcripts and profiles remain intact.

Recall ranks facts, active structured memories, history and documents using
normalized words, phrases and conservative concept expansion, with scores and
match explanations. To enable stronger paraphrase recall, configure Gemini with
`semantic_retrieval = true`, `semantic_provider = "gemini"`, `semantic_model`, and
the model's `semantic_dimension`. Candidate memory text is sent to Gemini for its
first embedding; unchanged vectors are reused from the local cache. If the API is
unavailable, recall safely continues with lexical ranking and
`memory_status` reports a degraded semantic state. Exact lexical evidence remains
ahead of semantic-only matches; active corrections, trust filtering, and injection
scanning run before embedding. Summaries are separately exported under
`JARVIS-OMA Memory/Summaries`, with source message IDs and unverified assistant
outcome labels; they never replace the continuous transcript.

Obsidian visualization is configured with `[memory].obsidian_vault`. JARVIS
publishes facts, profiles, indexed documents, and continuous history as Markdown
nodes under `JARVIS-OMA Memory`. Using the earlier JARVIS vault structure as a
reference, conversations now have a continuous `Conversations/conversation.md`
journal and daily reports such as `Conversations/2026-10-13 - Tuesday.md`.
Each report contains date/day metadata, timestamped dialogue, speaker labels,
and links to adjacent days, topics, and related fact/profile notes. Calendar
grouping uses `obsidian_timezone` (default `Asia/Kolkata`) without resetting memory.
Reports are captured transcripts, not AI-generated summaries. Nodes link to
categories and shared-word topics. These links show lexical and chronological
connections, not inferred causal claims. Open the Memory Map note or Obsidian's
Graph view to explore them. Automatic sync runs every ten seconds while voice is
connected; “sync my memory vault” forces a refresh. Source memory remains in its
local stores; vault edits are not imported as instructions. Manual edits are
preserved and reported as conflicts. Forgotten, unchanged generated facts are
removed from the vault during sync. Keep personal notes outside the managed folder.

The manifests are dynamic configuration rather than executable plugins. Adapters self-declare
their required system commands (`ADAPTER_COMMANDS`). When a command is not installed on the system,
skills that depend on it are excluded gracefully at startup with a warning instead of failing during a call.

To replace the bundled set with manifests from another directory:

```sh
./run.sh --skill-dir /absolute/path/to/skill-manifests --check
./run.sh --skill-dir /absolute/path/to/skill-manifests
```

Manifests fail closed: an invalid file, duplicate name, unknown adapter,
unsupported schema, or empty directory prevents startup. `--no-skills` restores
conversation-only mode. Application names must exactly match an installed desktop
entry. Websites are limited to HTTP(S), reject embedded credentials, and block
localhost and private IP literals.

## Real-time Screen Vision & Hardware Camera Sharing

JARVIS integrates continuous visual perception and high-speed hardware camera access alongside bidirectional voice:

- **Continuous Live Streaming (1 FPS)**:
  - **Screen Sharing**: Say *"Jarvis, look at my screen"* or *"Start screen sharing"*. JARVIS captures Wayland desktop frames via `grim` and streams them as JPEG image blobs directly into the active Gemini Live bidirectional session while you converse.
  - **Camera Sharing**: Say *"Jarvis, look through the camera"* or *"Share my camera"*. JARVIS streams real-time frames from your webcam (`/dev/video0`) to the multimodal session.
  - **Stop Sharing**: Say *"Stop sharing screen"* or *"Turn off the camera"*, immediately resetting vision mode to `off`.
- **Ultra-Fast Native C++ Actuator (`vision_ctrl`)**:
  - Located at `skills/native/src/vision_ctrl.cpp`, compiled with C++17 (`make -C skills/native`).
  - Uses direct POSIX `ioctl(VIDIOC_QUERYCAP)` to query V4L2 devices in < 5ms, filtering out hardware metadata streams and identifying legitimate capture nodes.
  - Automatically detects Wayland / X11 / Mutter / PipeWire session environments.
- **On-Demand Inspection**:
  - `capture_camera_frame`: Captures a single on-demand hardware snapshot for deep inspection without continuous streaming.
  - `inspect_screen`: Grabs the active focused window or full screen with local Tesseract OCR fallback.
  - `check_vision_hardware`: Queries available camera devices, resolutions, and display server status.

## Full-duplex flow

Reminders created by voice use Omarchy's native `omarchy reminder` system, so
JARVIS and the Omarchy reminder UI share the same reminders. You can say, for
example, “remind me in 30 minutes to check the oven” or “list my reminders”.

```text
Physical microphone → private PipeWire AEC source → 16 kHz PCM → Gemini Live
Physical speaker    ← private PipeWire AEC sink   ← 24 kHz PCM ← Gemini Live
```

Three concurrent workers send microphone audio, receive Gemini events, and play
speech. Capture stays active while playback runs; there is no silence gate that
turns the microphone off during Gemini's reply. Google Live uses a WebSocket
connection through the GenAI SDK; full-duplex does not imply WebRTC transport.

Gemini's activity detection interrupts a response when you speak. On the server's
interruption event the agent terminates its playback process, empties the queued
PCM, and advances a generation counter so pending old-turn audio cannot restart
playback. A fresh player handles the next response. Interruption latency includes
server detection and network latency; there is no measured sub-100 ms guarantee.

The PipeWire echo-cancellation module uses software WebRTC AEC. Audio playback is
routed through its reference sink and capture through its clean microphone source.
These are private routes; system defaults are unchanged. The agent fails to start
if AEC setup fails instead of silently using a raw microphone with speakers.
Actual echo rejection depends on the microphone/speaker setup and needs testing.

Playback uses small chunks and a short lead buffer. The PCM queue is bounded to
ten seconds. If the consumer cannot keep up, the connection is torn down and
retried rather than blocking reception of interruption events or growing memory
without a bound. This can cause an audible gap under sustained playback overload.

## Reconnection and state

Server resumption handles remain in RAM and are offered on subsequent connections.
Context-window compression is enabled. Server connection-renewal events trigger
a reconnect. Other errors have exponential backoff capped at 30 seconds and a
configurable retry budget (`--retries 5` by default). Authentication/configuration
failures stop the process. An invalid resume handle is discarded with a warning;
that retry starts a new provider connection and reloads JARVIS's persistent memory.
Reconnects are not gapless.

Microphone capture and playback are closed between attempts. Successful resumption
depends on the server; stopping the program discards the handle. No local audio
recordings are written. Continuous conversation text is stored locally when
`memory.record_sessions` is enabled. Audio and recalled memory are sent to Google while
LIVE. Transcript fragments are printed only with `--transcripts`; your terminal
may retain scrollback. A cloud connection and its usage costs are required.

## Project Structure

JARVIS-OMA is modularized into dedicated feature packages:

```text
JARVIS-OMA/
├── run.sh                          # Main CLI launcher
├── agent.py                        # Root CLI entrypoint (forwards to core.agent)
├── config.py                       # Root config shim (forwards to core.config)
├── echo_cancel.py                  # Root audio shim (forwards to audio.echo_cancel)
├── task_runner.py                  # Root task runner shim (forwards to filesystem.task_runner)
├── agent_orchestrator.py           # Root orchestrator shim (forwards to orchestration.agent_orchestrator)
├── system_control.py               # Root system control shim (forwards to skills.system_control)
├── config.toml.example             # Configuration template
├── requirements.txt                # Package dependencies
├── README.md                       # Repository guide
│
├── core/                           # Feature: Full-Duplex Voice & Vision OS Core
│   ├── agent.py                    # Gemini Live loop, realtime audio/vision streaming
│   ├── config.py                   # Unified configuration loader (TOML, JSON, env)
│   ├── ipc.py                      # Mode-0600 UNIX domain socket server & telemetry
│   ├── greeting.py                 # Dynamic proactive greetings generator
│   ├── secret_env.py               # Protected credential and environment isolation
│   └── workers.py                  # Bounded concurrency workers & latency guards
│
├── audio/                          # Feature: Isochronous Audio Engine & Echo Cancellation
│   ├── engine.py                   # PyAudio/PortAudio isochronous loop with ducking & barge-in
│   ├── downstream.py               # Downstream router with raised-cosine residual smoothing
│   └── echo_cancel.py              # PipeWire WebRTC AEC setup & node lifecycle
│
├── connectors/                     # Feature: Integrations & Web Ecosystem
│   ├── google_workspace.py         # Gmail, Google Calendar, Google Tasks, Drive, Docs, Sheets
│   ├── github.py                   # GitHub API: repository analysis, pinned reads, PRs, issues
│   ├── internet_search.py          # Real-time web search integration
│   └── browser.py                  # Safe headless web page reader and extractor
│
├── skills/                         # Feature: Dynamic Desktop Skills Engine
│   ├── skills.py                   # Skill manifest loader & execution dispatcher
│   ├── input_bar.py                # Loopback multimodal input bar web interface
│   ├── system_control.py           # Wayland & Omarchy input simulation
│   ├── manifests/                  # Declarative JSON skill manifests
│   └── native/                     # High-Speed Native C++ Actuators
│       ├── src/vision_ctrl.cpp     # C++17 V4L2 ioctl & Wayland/X11 actuator (< 5ms)
│       └── Makefile                # Native build configuration
│
├── filesystem/                     # Feature: Filesystem Autonomy & Task Runner
│   ├── filesystem.py               # Sandboxed desktop filesystem security & ops
│   ├── task_runner.py              # Multi-step filesystem plan executor
│   └── README.md
│
├── orchestration/                  # Feature: Multi-Agent & Evolution Subsystem
│   ├── agent_orchestrator.py       # Sub-agent process supervisor (Codex, Claude, etc.)
│   ├── desktop_execution.py        # Desktop action and visual task coordination
│   └── evolution.py                # Supervised self-evolution engine in sandboxed checkouts
│
├── memory/                         # Feature: Unified Persistent & Semantic Memory
│   ├── codes-dev/                  # Fact extraction, document store, and vector search
│   │   ├── 01-facts/               # Fact extraction, schema, and storage service
│   │   ├── 02-document-store/      # Hybrid BM25, Colbert, and SQLite storage
│   │   ├── 03-context-injection/   # Dynamic context prompt builder
│   │   ├── 05-sessions/            # Session compression and state persistence
│   │   └── 06-trust-gate/          # Prompt injection scanner and trust verification
│   └── README.md
│
├── proactive/                      # Feature: Proactive Background Autonomy
│   ├── events.py                   # Event ledger & models
│   ├── monitor.py                  # Background activity & idle monitor
│   ├── planner.py                  # Autonomous task planner
│   ├── policy.py                   # User safety & interruption policy
│   ├── runtime.py                  # Proactive daemon loop & worker manager
│   ├── storage.py                  # Persistent event database
│   └── verification.py             # Ground-truth execution and validation gates
│
├── scripts/                        # Feature: Control Plane & Diagnostic Tools
│   ├── jarvisctl / jarvisctl.py    # Daemon CLI control plane & IPC client
│   ├── connect_google.py           # Voice-activated Google Workspace OAuth helper
│   ├── connect_github.py           # GitHub personal token / OAuth connection helper
│   ├── register_obsidian_vault.py  # Vault registration script
│   └── sync_obsidian_memory.py     # Manual Obsidian memory sync trigger
│
├── systemd/                        # Feature: Systemd User Services
│   ├── jarvis-oma.service          # User service unit with safe RT limits & socket activation
│   └── jarvis.service              # Standard graphical-session service unit
│
├── docs/                           # Feature: Architecture & Technical Documentation
│   ├── architecture.md             # Complete system architectural design
│   ├── voice-capability-wiring.md  # Voice pipeline and connector wiring specifications
│   ├── desktop-execution.md        # Desktop execution engine documentation
│   ├── proactive-runtime.md        # Background intelligence & safety specs
│   └── README.md
│
└── tests/                          # Feature-Aligned Test Suite
    ├── test_core/                  # Core loop, IPC, vision streaming, workers tests
    ├── test_audio/                 # Engine ducking, flush smoothing, AEC tests
    ├── test_skills/                # Skills, native vision, and awareness tests
    ├── test_connectors/            # Google, GitHub, and browser connector tests
    ├── test_filesystem/            # Filesystem & task runner tests
    ├── test_orchestration/         # Sub-agent and desktop execution tests
    ├── test_memory/                # Memory, SQLite, and Obsidian tests
    ├── test_proactive/             # Proactive engine & verified execution tests
    └── test_scripts/               # CLI & connector script tests
```

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
./run.sh --check
./run.sh --list-skills
```

The tests simulate external processes and cloud events. They cover simultaneous
input/output, all audio parts in an event, old-audio cancellation including a
process-creation race, queue bounds, multi-turn reception, worker cleanup,
resumption state, dynamic manifest validation, strict tool arguments, safe adapter
routing, URL policy and echo route cleanup. `--check` validates commands and SDK
configuration without capturing audio or opening a network connection.

See `docs/TEST_RESULTS.txt` for the actual test run. A real Gemini conversation,
echo rejection, end-to-end interruption timing, connection expiry and sustained
CPU/RAM usage have **not** been tested on live hardware for this new agent.

## Source references

Extracted from the desktop audio design of Omarchy AI; unrelated app integrations
were removed. The new transport loop follows Google's current
[Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
and [session management](https://ai.google.dev/gemini-api/docs/live-api/session-management)
documentation, checked on 2026-10-12. The local Gemini skill describes an older
model generation; current official documentation supplies the default used here.
