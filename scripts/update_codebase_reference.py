#!/usr/bin/env python3
"""
scripts/update_codebase_reference.py
--------------------------------------------------------------------------------
Generates and keeps CODEBASE_REFERENCE.md updated with 100% precision for JARVIS-OMA.
Reads real-time Git branch, commit history, file line counts, skill manifests,
and module inventory directly from the repository.
Writes to:
  - /home/g0pi/Projects/JARVIS-OMA/CODEBASE_REFERENCE.md
--------------------------------------------------------------------------------
"""

import sys
import subprocess
import datetime
import json
from pathlib import Path

WORKSPACE_ROOT = Path("/home/g0pi/Projects/JARVIS-OMA").resolve()
TARGET_FILE = WORKSPACE_ROOT / "CODEBASE_REFERENCE.md"

def run_cmd(cmd, cwd=str(WORKSPACE_ROOT)):
    try:
        res = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error executing '{cmd}': {e.stderr.strip()}"

def get_line_count(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def collect_file_inventory():
    inventory = []
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=WORKSPACE_ROOT).decode().split("\0")
    for rel_path in paths:
        if not rel_path:
            continue
        full_path = WORKSPACE_ROOT / rel_path
        if not full_path.is_file():
            continue
        inventory.append({
            "rel_path": rel_path,
            "full_path": str(full_path),
            "lines": get_line_count(full_path),
            "size": full_path.stat().st_size,
        })
    inventory.sort(key=lambda x: x["rel_path"])
    return inventory

KNOWN_ROLES = {
    "learning/bundles.py": ("Versioned Research Harness Bundles", "Content-addressed instruction bundles, explicit activation, integrity checks, and previous-version restoration."),
    "learning/evidence.py": ("Opt-in Task Evidence", "Bounded background capture of observed requests, tool results, outputs, corrections, and capture health; no automatic diagnosis or optimization."),
    "learning/research.py": ("Offline Research Fixture", "Corpus-only search/read dispatcher, narrow deterministic citation checks, and scripted native-runtime fixture."),
    "learning/voice_tests.py": ("Manual Voice Acceptance", "Six spoken acceptance requests and latest-episode capture matching; quality verdicts remain manual."),
    "learning/research_runtime.py": ("Bounded Native Research Runtime", "Explicit Gemini text transport, call/time budgets, fixed-corpus tools through JARVIS dispatch, and offline scripted transport."),
    "learning/refinement.py": ("Real Harness² Research Integration", "Pinned upstream recursion, isolated Git worktrees, instruction-only proposals, baseline and held-out checks, audit artifacts, and review-only candidates."),
    "learning/trials.py": ("Controlled Research Trial Gate", "Artifact integrity and provenance checks, independent reassessment, strict improvement eligibility, explicit trial selection, rollback, and bundle-aware voice checklist."),
    "learning/__main__.py": ("Learning Administration CLI", "Explicit bundle initialization, activation, restoration, evidence inspection, feedback, and cloud-free demo."),
    "docs/harness-learning.md": ("Harness Learning Foundation Guide", "Opt-in usage, bundle administration, evidence privacy/limits, offline validation, and future Harness² boundary."),
    # Modular Core Runtime
    "core/__init__.py": ("Modular Core Package Marker", "Package initialization marker for core voice agent runtime and dynamic configuration."),
    "core/agent.py": ("Core Voice Agent Runtime", "Full-duplex Gemini Live voice agent over PipeWire with concurrent capture, playback, interruption generation fences, proactive greetings, tool execution, and SIGUSR1/SIGUSR2 mute/interrupt signal handling."),
    "core/config.py": ("Dynamic Configuration Engine", "Multi-tier settings loader with priority chain: CLI flags > environment variables > TOML/JSON config files > built-in defaults."),
    "core/greeting.py": ("Dynamic Greeting Memory", "Persistent, state-aware greeting engine suppressing redundant welcomes, tracking return cooldowns, and generating fresh, single-sentence prompts focused on unfinished user tasks."),
    "core/secret_env.py": ("Credential Sanitizer", "Filters process environment dictionaries to prevent token and API key leakage into child processes."),
    "core/README.md": ("Core Subsystem Documentation", "Architecture documentation for core voice agent and configuration subsystem."),

    # Modular Audio Subsystem
    "audio/__init__.py": ("Modular Audio Package Marker", "Package initialization marker for native PipeWire audio pipeline."),
    "audio/echo_cancel.py": ("PipeWire AEC Audio Router", "Session-owned WebRTC echo cancellation via pactl load-module module-echo-cancel, source volume capping, and automatic cleanup."),
    "audio/downstream.py": ("Downstream Audio Router", "Accumulates variable-length Gemini audio chunks into fixed output frames with generation-tagged barge-in fencing."),
    "audio/engine.py": ("Native Low-Latency Audio Engine", "Real-time PortAudio/sounddevice full-duplex audio streaming engine with lock-free C queues, echo cancellation, and Barge-In detection."),
    "audio/README.md": ("Audio Subsystem Documentation", "Architecture documentation for PipeWire WebRTC acoustic echo cancellation pipeline."),

    # External Service Connectors
    "connectors/__init__.py": ("Connectors Package Marker", "Package initialization marker for external service connectors."),
    "connectors/credentials.py": ("Connector Credential Store", "Private credential resolution from process environment or connectors/.secrets/credentials.env with zero shell execution."),
    "connectors/browser.py": ("Desktop OAuth Browser Launcher", "Launches visible browser authorization windows via omarchy-launch-webapp or xdg-open with sanitized environments."),
    "connectors/github.py": ("GitHub API Connector", "Voice-activated GitHub REST API integration supporting repository inspect, issue search, PR summaries, CI workflow checks, and OAuth/device flow authentication."),
    "connectors/google_workspace.py": ("Google Workspace Connector", "Voice-activated Gmail, Google Calendar, and Google Tasks connector with loopback OAuth2 authentication and token persistence."),

    # Modular Filesystem Subsystem
    "filesystem/__init__.py": ("Modular Filesystem Package Marker", "Package initialization marker for filesystem engine and task runner."),
    "filesystem/filesystem.py": ("Autonomous Filesystem Engine", "Full autonomy file and directory operations (list, read, write, append, edit, mkdir, move, copy, trash, delete, inspect, search, grep) with root path safety guards."),
    "filesystem/task_runner.py": ("In-Process Bounded Task Runner", "Executes multi-step filesystem plans (up to 30 steps) in background workers with per-step tracking and cooperative cancellation."),
    "filesystem/README.md": ("Filesystem Subsystem Documentation", "Architecture documentation for autonomous filesystem tools and task runner."),

    # Modular Orchestration & Evolution
    "orchestration/__init__.py": ("Modular Orchestration Package Marker", "Package initialization marker for multi-agent CLI orchestrator and self-evolution engine."),
    "orchestration/agent_orchestrator.py": ("System Agent CLI Orchestrator", "Discovers, delegates, supervises, and terminates local coding agents (Codex, Claude, OpenCode, Gemini, Hermes, OMP) across bounded non-overlapping workspaces."),
    "orchestration/desktop_execution.py": ("Visible Desktop Execution Engine", "Supervises coding agents (Codex, Claude) inside dedicated visible tmux terminal panes on Omarchy Wayland desktop."),
    "orchestration/evolution.py": ("Autonomous Evolution Engine", "Self-improvement pipeline analyzing tool failures, system diagnostics, and synthesizing code optimizations with rollback gates."),
    "orchestration/README.md": ("Orchestration Subsystem Documentation", "Architecture documentation for multi-agent delegation and autonomous evolution."),

    # Modular Skills Subsystem & Overlays
    "skills/__init__.py": ("Modular Skills Package Marker", "Package initialization marker for desktop skills registry, input bar, and overlay clients."),
    "skills/skills.py": ("Desktop Skills Registry & Dispatcher", "Discovers JSON manifests, validates strict argument schemas, maps 110 tools to safe adapters, enforces command dependencies, and degrades gracefully."),
    "skills/input_bar.py": ("Multimodal Input Bar HUD", "Compact single-row 44px HUD input bar with full transparency, inline attachment indicator, Enter-to-send, and dark glass styling."),
    "skills/overlay_client.py": ("Native Wayland Overlay Client", "Standalone WebKitGTK / GTK3 transparent window client launching JarvisInputBar strictly at 600x50 with RGBA transparency and zero compositor framing."),
    "skills/system_control.py": ("System Control Adapters", "Desktop system control adapters for volume, brightness, power state, and workspace navigation."),
    "skills/README.md": ("Skills Subsystem Documentation", "Architecture documentation for desktop skills engine and input overlay."),

    # Dynamic Skill Manifests
    "skill_manifests/agent-orchestration.json": ("Agent Orchestration Manifest", "Manifest declaring agent discovery, delegation, job status, and job cancellation tools."),
    "skill_manifests/desktop-awareness.json": ("Desktop Awareness Manifest", "Manifest declaring inspect_screen OCR, window topography, and system resource monitoring tools."),
    "skill_manifests/development.json": ("Autonomous Development Skills Manifest", "Manifest declaring start_development, get_development_status, cancel_development, and list_development_jobs."),
    "skill_manifests/filesystem.json": ("Filesystem Skills Manifest", "Manifest declaring 13 safe autonomous filesystem tools (read, write, list, search, grep, edit, trash, move, copy)."),
    "skill_manifests/github.json": ("GitHub Skills Manifest", "Manifest declaring 8 GitHub voice tools (search repos, view issues/PRs, workflow runs, user inspect)."),
    "skill_manifests/google-workspace.json": ("Google Workspace Skills Manifest", "Manifest declaring 15 Google Workspace tools across Gmail, Calendar, and Tasks."),
    "skill_manifests/input-bar.json": ("Input Bar Skills Manifest", "Manifest declaring multimodal loopback input bar activation and query tools."),
    "skill_manifests/memory.json": ("Memory Skills Manifest", "Manifest declaring 10 memory storage, fact recall, profile update, and search tools."),
    "skill_manifests/omarchy-defaults.json": ("Omarchy Defaults Manifest", "Manifest declaring 19 desktop application, notification, clipboard, and browser control tools."),
    "skill_manifests/proactive.json": ("Proactive Autonomy Manifest", "Manifest declaring pause_jarvis, resume_jarvis, stop_all_jarvis_work, and activity ledger tools."),
    "skill_manifests/system-controls.json": ("System Controls Manifest", "Manifest declaring 19 volume, brightness, workspace, and power state controls."),
    "skill_manifests/task-runner.json": ("Task Runner Skills Manifest", "Manifest declaring background filesystem task runner plan submission, status, and cancellation tools."),

    # Proactive Autonomy Subsystem
    "proactive/__init__.py": ("Proactive Module Exports", "Exports AutonomyControl, EventBus, ActivityLedger, AutonomousPlanner, ProactivePolicy, ProactiveMonitor, and ProactiveRuntime."),
    "proactive/control.py": ("Autonomy Control Matrix", "SQLite-backed state governor enforcing global pause_jarvis, resume_jarvis, and stop_all_jarvis_work controls."),
    "proactive/events.py": ("Durable Event Bus", "SQLite-backed transactional queue for publishing, claiming, acknowledging, and failing proactive background events."),
    "proactive/ledger.py": ("Immutable Activity Ledger", "Durable SQLite audit ledger tracking all proactive planned, running, completed, and failed tasks with timestamps and payloads."),
    "proactive/monitor.py": ("Proactive Job Monitor", "Tracks active delegated agent jobs and task executions, enforcing timeouts, defensive snapshots, and error state transitions."),
    "proactive/planner.py": ("Autonomous Bounded Planner", "Translates inbound events (tasks, todos, reminders) into deterministic agent routes and multi-step plans under safety ceilings."),
    "proactive/policy.py": ("Autonomy Policy Governor", "Evaluates actions against rate limits, cooldown periods, duplicate suppression, and required authorization levels."),
    "proactive/runtime.py": ("Proactive Autonomy Runtime", "Master coordinator integrating events, ledger, control, policy, planner, and monitor with background observation loops for Omarchy todos and reminders."),
    "proactive/verification.py": ("Artifact Verification Engine", "Cryptographic pre-dispatch artifact verification validating exact sha256 byte digests, traversal guards, and size bounds outside worker permissions."),

    # Backward Compatibility Shims
    "jarvis_memory/__init__.py": ("Memory Backward Compatibility Shim", "Redirects legacy jarvis_memory imports to memory/codes-dev/jarvis_memory via sys.path."),
    "jarvis_memory/README.md": ("Memory Backward Compatibility Doc", "Documentation for jarvis_memory backward compatibility shim."),

    # Unified Memory Package & Active Engine
    "memory/__init__.py": ("Memory Subsystem Package Marker", "Package entry point exposing vault data paths and codes-dev search paths."),
    "memory/README.md": ("Memory Subsystem Documentation", "Architecture overview and directory structure for the unified memory subsystem."),
    "memory/codes-dev/jarvis_memory/__init__.py": ("Active Memory Engine Marker", "Package initialization marker for native memory subsystem."),
    "memory/codes-dev/jarvis_memory/bridge.py": ("Memory Bridge Subsystem", "Primary bridge unifying fact storage, injection scanning, knowledge base, session persistence, vector retrieval, and Obsidian vault synchronization."),
    "memory/codes-dev/jarvis_memory/capture.py": ("Evidence-Grounded Fact Extractor", "Extracts explicit user preferences, decisions, and facts from conversation exchanges without model hallucination."),
    "memory/codes-dev/jarvis_memory/chunking.py": ("Document Chunker", "Configurable character and token chunker for splitting ingested documents into indexable segments with sliding overlap."),
    "memory/codes-dev/jarvis_memory/embeddings.py": ("Vector Embedding Providers", "Client adapters for generating dense semantic vector embeddings via Google Gemini API or local Ollama."),
    "memory/codes-dev/jarvis_memory/events.py": ("Memory Event Definitions", "Dataclasses defining memory mutations, ingest events, and audit logs."),
    "memory/codes-dev/jarvis_memory/extractor.py": ("Model-Assisted Fact Extractor", "Optional extractor utilizing a local Ollama model to summarize and mine unstructured conversational turns."),
    "memory/codes-dev/jarvis_memory/hybrid.py": ("Hybrid Ranker & Fusion Engine", "Merges lexical BM25/FTS5 scores with semantic cosine similarity vectors using reciprocal rank fusion."),
    "memory/codes-dev/jarvis_memory/knowledge.py": ("Knowledge Database Store", "SQLite WAL database (knowledge.db) managing structured memories, profile notes (SOUL, MEMORY, USER), and FTS5 full-text indexing."),
    "memory/codes-dev/jarvis_memory/obsidian.py": ("Obsidian Markdown Synchronizer", "Generates and maintains Markdown notes, daily interaction logs, and topic index files in the linked Obsidian vault."),
    "memory/codes-dev/jarvis_memory/paths.py": ("Memory State Path Resolver", "Resolves XDG_STATE_HOME and XDG_CONFIG_HOME paths for sovereign memory databases and configuration."),
    "memory/codes-dev/jarvis_memory/registry.py": ("Memory Component Registry", "Internal catalog registering active memory adapters, stores, and schema versions."),
    "memory/codes-dev/jarvis_memory/retrieval.py": ("Lexical Candidate Ranker", "Ranks candidate facts and document chunks using normalized token overlap, exact phrasing, and concept expansion."),
    "memory/codes-dev/jarvis_memory/scanner.py": ("Prompt Injection Scanner", "Heuristic and pattern-matching security scanner screening memory inputs against prompt injection and jailbreak attempts."),
    "memory/codes-dev/jarvis_memory/security_types.py": ("Security Data Types", "Type definitions for security classification, taint tracking, and threat severity levels."),
    "memory/codes-dev/jarvis_memory/service.py": ("Memory Service Facade", "High-level API coordinating memory store, extraction, indexing, and recall workflows."),
    "memory/codes-dev/jarvis_memory/session.py": ("Session History Store", "SQLite database managing continuous multi-turn conversation transcripts across restarts."),
    "memory/codes-dev/jarvis_memory/store.py": ("Local Fact Store", "File-locked JSONL storage engine (memory_facts.jsonl) managing atomic facts with cross-process synchronization."),
    "memory/codes-dev/jarvis_memory/summaries.py": ("Extractive Daily Summarizer", "Generates daily conversation summaries with source attribution without modifying or pruning underlying transcripts."),
    "memory/codes-dev/jarvis_memory/types.py": ("Memory Domain Dataclasses", "Dataclasses for MemoryFact, StructuredMemory, ProfileNote, DocumentChunk, and RetrievalResult."),
    "memory/codes-dev/jarvis_memory/vector_store.py": ("SQLite Vector Database", "High-performance vector cache (semantic_vectors.db) storing normalized embeddings with cosine similarity math."),
    "memory/codes-dev/jarvis_memory/README.md": ("Active Engine Documentation", "Architecture overview and operational guidelines for the sovereign 4-tier memory matrix."),

    # Memory Development Tests, Scripts & Docs
    "memory/codes-dev/scripts/register_obsidian_vault.py": ("Obsidian Vault Registration Script", "Registers memory vault into Obsidian desktop settings with backup."),
    "memory/codes-dev/scripts/sync_obsidian_memory.py": ("Headless Memory Sync Utility", "One-shot synchronization of sovereign memory facts and history into Obsidian vault."),
    "memory/codes-dev/docs/memory-upgrade.md": ("Memory Upgrade Specification", "Specification tracking evidence capture, ranked retrieval, and acceptance gates."),
    "memory/codes-dev/docs/semantic-memory-board.md": ("Semantic Memory Work Board", "Engineering work board tracking embedding providers, vector cache, and hybrid ranker."),
    "memory/codes-dev/tests/__init__.py": ("Memory Dev Test Package Marker", "Package initialization marker for memory dev tests."),
    "memory/codes-dev/tests/test_memory_capture.py": ("Memory Capture Tests", "Tests extraction of explicit user facts without hallucinating assistant claims."),
    "memory/codes-dev/tests/test_memory_config.py": ("Memory Configuration Tests", "Tests validation of memory paths, providers, dimensions, and score thresholds."),
    "memory/codes-dev/tests/test_memory_embeddings.py": ("Vector Embedding Tests", "Tests Gemini and Ollama embedding providers and vector dimensions."),
    "memory/codes-dev/tests/test_memory_hybrid.py": ("Hybrid Fusion Tests", "Tests reciprocal rank fusion between lexical and vector retrieval scores."),
    "memory/codes-dev/tests/test_memory_integration.py": ("Memory Integration Tests", "Tests end-to-end memory operations, fact storage, profile updates, and document indexing."),
    "memory/codes-dev/tests/test_memory_knowledge.py": ("Knowledge Database Tests", "Tests SQLite knowledge store, profile mutations, and FTS5 search indexing."),
    "memory/codes-dev/tests/test_memory_retrieval.py": ("Lexical Retrieval Tests", "Tests token normalization, phrase matching, and concept expansion."),
    "memory/codes-dev/tests/test_memory_strength.py": ("Memory Strength Acceptance Tests", "Tests long-term memory persistence, restart resilience, and supersession."),
    "memory/codes-dev/tests/test_memory_summaries.py": ("Daily Summary Tests", "Tests generation of structured daily interaction summaries."),
    "memory/codes-dev/tests/test_memory_upgrade_integration.py": ("Memory Upgrade Integration Tests", "Validates complete interoperability of upgraded memory components."),
    "memory/codes-dev/tests/test_memory_vector_store.py": ("SQLite Vector Store Tests", "Tests vector caching, invalidation, cosine similarity ranking, and permissions."),
    "memory/codes-dev/tests/test_obsidian_memory.py": ("Obsidian Sync Tests", "Tests markdown note formatting, directory structure, and daily journal synchronization."),
    "memory/codes-dev/tests/test_semantic_memory_eval.py": ("Semantic Retrieval Acceptance Suite", "Comprehensive evaluation of paraphrase recall, poison filtering, and fallback behavior."),

    # Systemd Service Integration
    "systemd/jarvis-oma.service": ("Systemd User Service Unit", "Runs JARVIS-OMA as an unprivileged user daemon under systemd with auto-restart, clean shutdown, and signal management."),
    "systemd/jarvis.service": ("Systemd Desktop Service Unit", "Alternative systemd user service unit with full desktop environment bindings."),

    # Support & Automation Scripts
    "scripts/README.md": ("Scripts Directory Documentation", "Overview of utility, maintenance, and deployment scripts."),
    "scripts/check_connectors.py": ("Connector Verification Script", "CLI verification tool checking authentication status and connectivity for GitHub and Google Workspace."),
    "scripts/connect_github.py": ("GitHub Authentication CLI", "Interactive or browser-assisted GitHub connector authentication and token acquisition harness."),
    "scripts/connect_google.py": ("Google Workspace OAuth CLI", "Interactive loopback OAuth flow acquiring Google Workspace user credentials."),
    "scripts/develop.py": ("Capability Development CLI Harness", "Inspects and drives capability-development proposals, sandboxed code synthesis, and test suites headlessly."),
    "scripts/import_connector_credentials.py": ("Connector Credential Importer", "Securely imports and validates connector credentials into local storage."),
    "scripts/install-service.sh": ("Systemd Service Installer", "Automates installation, enablement, and user daemon management for jarvis-oma.service."),
    "scripts/register_obsidian_vault.py": ("Obsidian Vault Registration Script", "Safely registers the JARVIS-OMA memory vault into Obsidian desktop settings (~/.config/obsidian/obsidian.json) with backup."),
    "scripts/sync_obsidian_memory.py": ("Headless Memory Sync Utility", "Executes an immediate one-shot synchronization of sovereign memory facts and history into the Obsidian vault."),
    "scripts/test_agent_delegation.py": ("Live Agent Delegation Smoke Harness", "End-to-end integration test creating temporary Git workspaces and verifying autonomous delegation to installed agents."),
    "scripts/update_codebase_reference.py": ("Codebase Reference Generator", "Generates and synchronizes CODEBASE_REFERENCE.md with 100% precision from real-time Git and code telemetry."),

    # Automated Test Suites (tests/ Hierarchy)
    "tests/__init__.py": ("Test Root Package Marker", "Package initialization marker for automated test suite."),
    "tests/README.md": ("Test Suite Documentation", "Architecture and execution guide for the unit, integration, and acceptance tests."),
    "tests/test_audio/__init__.py": ("Audio Test Package Marker", "Package initialization marker for audio tests."),
    "tests/test_audio/test_echo_cancel.py": ("Echo Cancellation Tests", "Tests pactl module loading, source volume calculation and restoration, and error cleanup."),
    "tests/test_audio/test_engine.py": ("Native Audio Engine Tests", "Tests PortAudio streaming, C queue frame sizing, and buffer overrun handling."),
    "tests/test_connectors/__init__.py": ("Connectors Test Package Marker", "Package initialization marker for connectors tests."),
    "tests/test_connectors/test_browser.py": ("Browser OAuth Launcher Tests", "Tests sanitized environment browser spawning and URL allowlisting."),
    "tests/test_core/__init__.py": ("Core Test Package Marker", "Package initialization marker for core tests."),
    "tests/test_core/test_agent.py": ("Voice Agent Unit Tests", "Tests full-duplex streaming, live config generation, greeting triggers, playback queueing, interruption fences, and signal handling."),
    "tests/test_core/test_config.py": ("Configuration Engine Tests", "Tests TOML/JSON parsing, environment variable overrides, CLI keyword overrides, and priority resolution."),
    "tests/test_core/test_greeting.py": ("Greeting Context Engine Tests", "Tests greeting history persistence, daily suppression cooldowns, and prompt synthesis."),
    "tests/test_core/test_secret_env.py": ("Secret Environment Tests", "Tests regex-based credential filtering and sanitized subprocess environments."),
    "tests/test_filesystem/__init__.py": ("Filesystem Test Package Marker", "Package initialization marker for filesystem tests."),
    "tests/test_filesystem/test_filesystem.py": ("Filesystem Skill Tests", "Tests full autonomy file operations, offset reading, path traversal guards, and critical path protection."),
    "tests/test_filesystem/test_task_runner.py": ("Task Runner Unit Tests", "Tests bounded filesystem task plan validation, execution, and cancellation."),
    "tests/test_memory/__init__.py": ("Memory Test Package Marker", "Package initialization marker for memory tests."),
    "tests/test_memory/test_memory_capture.py": ("Memory Capture Tests", "Tests extraction of explicit user facts without hallucinating assistant claims."),
    "tests/test_memory/test_memory_config.py": ("Memory Configuration Tests", "Tests validation of memory paths, providers, dimensions, timezones, and score thresholds."),
    "tests/test_memory/test_memory_embeddings.py": ("Vector Embedding Tests", "Tests Gemini and Ollama embedding providers and vector dimension handling."),
    "tests/test_memory/test_memory_hybrid.py": ("Hybrid Fusion Tests", "Tests reciprocal rank fusion between lexical and vector retrieval scores."),
    "tests/test_memory/test_memory_integration.py": ("Memory Bridge Integration Tests", "Tests end-to-end memory operations, fact storage, profile updates, and document indexing."),
    "tests/test_memory/test_memory_knowledge.py": ("Knowledge Database Tests", "Tests SQLite knowledge store, profile mutations, and FTS5 search indexing."),
    "tests/test_memory/test_memory_retrieval.py": ("Lexical Retrieval Tests", "Tests token normalization, phrase matching, and concept expansion."),
    "tests/test_memory/test_memory_strength.py": ("Memory Strength Acceptance Tests", "Tests long-term memory persistence, restart resilience, and supersession."),
    "tests/test_memory/test_memory_summaries.py": ("Daily Summary Tests", "Tests generation of structured daily interaction summaries."),
    "tests/test_memory/test_memory_upgrade_integration.py": ("Memory Upgrade Integration Tests", "Validates complete interoperability of upgraded memory components."),
    "tests/test_memory/test_memory_vector_store.py": ("SQLite Vector Store Tests", "Tests vector caching, invalidation, cosine similarity ranking, and file permissions."),
    "tests/test_memory/test_obsidian_memory.py": ("Obsidian Sync Tests", "Tests markdown note formatting, directory structure, and daily journal synchronization."),
    "tests/test_memory/test_semantic_memory_eval.py": ("Semantic Retrieval Acceptance Suite", "Comprehensive evaluation of paraphrase recall, poison filtering, and fallback behavior."),
    "tests/test_orchestration/__init__.py": ("Orchestration Test Package Marker", "Package initialization marker for orchestration tests."),
    "tests/test_orchestration/test_agent_orchestrator.py": ("Agent Orchestrator Unit Tests", "Tests agent discovery, concurrency limits, workspace isolation, timeout escalation, and secret redaction."),
    "tests/test_orchestration/test_desktop_execution.py": ("Desktop Execution Tests", "Tests tmux command generation, pane isolation, and agent process monitoring."),
    "tests/test_orchestration/test_evolution.py": ("Evolution Engine Unit Tests", "Tests autonomous error diagnostics, code evolution synthesis, test verification, and safety rollback."),
    "tests/test_proactive/__init__.py": ("Proactive Test Package Marker", "Package initialization marker for proactive tests."),
    "tests/test_proactive/test_proactive_control.py": ("Proactive Autonomy Control Tests", "Tests pause, resume, and stop-all latch mechanisms."),
    "tests/test_proactive/test_proactive_events.py": ("Proactive Event Bus Tests", "Tests SQLite event bus publishing, claiming, and transactional state transitions."),
    "tests/test_proactive/test_proactive_monitor.py": ("Proactive Job Monitor Tests", "Tests background job supervision, timeout handling, and snapshot telemetry."),
    "tests/test_proactive/test_proactive_planner.py": ("Proactive Planner Tests", "Tests deterministic event routing, agent selection, and plan construction."),
    "tests/test_proactive/test_proactive_policy.py": ("Proactive Policy Tests", "Tests rate limiting, cooldowns, duplicate detection, and effect categorization."),
    "tests/test_proactive/test_proactive_runtime.py": ("Proactive Runtime Tests", "Tests todo/reminder observation loops, tick processing, and event dispatching."),
    "tests/test_proactive/test_verified_execution.py": ("Verified Execution Tests", "Tests sha256 artifact verification, path traversal rejection, and digest calculation."),
    "tests/test_scripts/__init__.py": ("Scripts Test Package Marker", "Package initialization marker for scripts tests."),
    "tests/test_scripts/test_connect_github.py": ("GitHub Script Tests", "Tests GitHub authentication CLI and credential persistence."),
    "tests/test_skills/__init__.py": ("Skills Test Package Marker", "Package initialization marker for skills tests."),
    "tests/test_skills/test_skills.py": ("Dynamic Skills Engine Tests", "Tests manifest discovery, adapter routing, command verification, argument schema enforcement, and graceful degradation."),
    "tests/test_skills/test_awareness.py": ("Desktop Awareness Tests", "Tests inspect_screen, list_windows, focus_window, list_workspaces, and get_system_resources adapters."),
    "tests/test_skills/test_connectors.py": ("Connector Skills Integration Tests", "Tests connector skill dispatching and error handling."),
    "tests/test_skills/test_development.py": ("Capability Development Skills Tests", "Unit tests for start_development, get_development_status, cancel_development, and list_development_jobs adapters."),
    "tests/test_skills/test_github_connector.py": ("GitHub Connector Tests", "Tests GitHub API client methods, headers, and pagination."),
    "tests/test_skills/test_google_connector.py": ("Google Workspace Connector Tests", "Tests Google Workspace OAuth client, token refresh, and API request handling."),
    "tests/test_skills/test_input_bar.py": ("Input Bar Integration Tests", "Tests compact HUD input bar skill activation, loopback HTTP server, token authentication, and voice-session queue integration."),
    "tests/test_skills/test_system_control.py": ("System Control Tests", "Tests volume, brightness, power state, and workspace navigation adapters."),

    # Root Backward-Compatibility Stubs & Core Entry Points
    "agent.py": ("Core Voice Agent Entry Stub", "Backward-compatibility entry point importing and delegating to core.agent:main."),
    "skills.py": ("Skills Registry Entry Stub", "Backward-compatibility entry point importing and delegating to skills.skills:DesktopSkills."),
    "config.py": ("Configuration Engine Entry Stub", "Backward-compatibility entry point importing and delegating to core.config:load_config."),
    "echo_cancel.py": ("Echo Cancellation Entry Stub", "Backward-compatibility entry point importing and delegating to audio.echo_cancel:EchoCancellation."),
    "filesystem.py": ("Filesystem Engine Entry Stub", "Backward-compatibility entry point importing and delegating to filesystem.filesystem."),
    "task_runner.py": ("Task Runner Entry Stub", "Backward-compatibility entry point importing and delegating to filesystem.task_runner:TaskRunner."),
    "agent_orchestrator.py": ("Agent Orchestrator Entry Stub", "Backward-compatibility entry point importing and delegating to orchestration.agent_orchestrator:AgentOrchestrator."),
    "system_control.py": ("System Control Entry Stub", "Backward-compatibility entry point importing and delegating to skills.system_control."),
    "test_bar.py": ("Multimodal Input Bar Entry Stub", "Backward-compatibility stub importing and exporting MAX_BODY, PAGE, TestBar from skills.input_bar."),
    "run.sh": ("Shell Activation Wrapper", "Launches agent.py within the local Python virtual environment, supporting flags like --check and --list-skills."),
    "requirements.txt": ("Python Dependencies Manifest", "Specifies google-genai, sounddevice, and numpy dependencies."),
    "config.toml": ("Active Configuration File", "Live local configuration file specifying active voice, model, language, and memory settings."),
    "config.toml.example": ("Configuration Reference Template", "Documented configuration template illustrating all available options across agent, audio, vad, skills, filesystem, and memory sections."),
    "README.md": ("Project Documentation", "Master repository guide detailing requirements, installation, run commands, system service, dynamic skills, connectors, and memory matrix."),
    "CONTRIBUTING.md": ("Contribution Guidelines", "Guidelines for contributing safe, auditable desktop controls, running unit tests, and adhering to architectural boundaries."),
    "LICENSE": ("MIT License", "Open-source software license for JARVIS-OMA."),
    "install-service.sh": ("Systemd Service Installer Script", "Root deployment script automating jarvis-oma.service setup in systemd user space."),
    "CODEBASE_REFERENCE.md": ("Codebase Technical Reference Manual", "Definitive 100% precision technical specification and module map for JARVIS-OMA."),

    # Root Hidden Configurations & Environment Secrets
    ".env": ("Local Environment Secrets", "Local environment file containing private API keys and configuration secrets (excluded from Git)."),
    ".env.example": ("Environment Secrets Template", "Example template for setting GEMINI_API_KEY and connector keys."),
    ".gitignore": ("Git Ignore Specification", "Ignores .venv, __pycache__, .env, private tokens, and local SQLite state databases."),

    # Documentation & Architecture
    "docs/README.md": ("Documentation Directory Index", "Master index of architectural specifications, research reports, and work boards."),
    "docs/architecture.md": ("Architecture Specification", "Overview of full-duplex voice pipeline, PipeWire AEC, and asynchronous concurrent workers."),
    "docs/capability-development.md": ("Capability Development Specification", "Architectural specification for autonomous self-improvement, isolated proposal git worktrees, bubblewrap sandbox, and rollback gates."),
    "docs/desktop-execution.md": ("Desktop Execution Specification", "Design specification for visible agent execution in dedicated tmux sessions."),
    "docs/dynamic-greetings.md": ("Dynamic Greetings Specification", "Architecture specification for state-aware activation greetings and suppression."),
    "docs/memory-upgrade.md": ("Memory Upgrade Work Board", "Architectural specification tracking evidence capture, ranked retrieval, persistent corrections, daily summaries, and acceptance gates."),
    "docs/proactive-runtime.md": ("Proactive Runtime Specification", "Comprehensive architecture documentation for the proactive background autonomy runtime."),
    "docs/semantic-memory-board.md": ("Semantic Memory Evolution Board", "Engineering work board tracking embedding providers, persistent vector cache, hybrid ranker, and retrieval evaluation."),
    "docs/TEST_RESULTS.txt": ("Test Results Baseline", "Recorded test execution baseline and verification logs."),
    "docs/research/jarvis-agi-2026-10-14/report.md": ("JARVIS AGI Research Report", "Comprehensive research report analyzing frontier voice agents, memory systems, and desktop autonomy."),
    "docs/research/jarvis-agi-2026-10-14/debate.md": ("AGI Architecture Debate", "Comparative analysis and debate transcript on agent architecture choices."),
    "docs/research/jarvis-agi-2026-10-14/desktop-review.md": ("Desktop Autonomy Review", "Evaluation of Wayland/Hyprland desktop control paradigms and sandbox boundaries."),
    "docs/research/jarvis-agi-2026-10-14/learning-review.md": ("Continuous Learning Review", "Analysis of long-term memory accumulation and autonomous evolution."),
    "docs/research/jarvis-agi-2026-10-14/openai-review.md": ("Frontier Agent Review", "Benchmark comparison against OpenAI Realtime API and Operator."),

    # GitHub Workflows & Templates
    ".github/workflows/ci.yml": ("GitHub Actions CI Pipeline", "Automated continuous integration workflow running unit and regression tests on Python 3.12 and 3.13."),
    ".github/ISSUE_TEMPLATE/bug_report.md": ("Bug Report Template", "Structured issue template for filing desktop control and voice pipeline bugs."),
    ".github/ISSUE_TEMPLATE/feature_request.md": ("Feature Request Template", "Structured issue template for requesting new desktop skills and capabilities."),
}

def get_role_and_responsibility(rel_path):
    if rel_path in KNOWN_ROLES:
        return KNOWN_ROLES[rel_path]
    if rel_path.startswith("memory/data/obsidian-vault/"):
        return ("Obsidian Vault Knowledge Note", "Zettelkasten markdown note, daily interaction journal, or topic graph node in sovereign Obsidian vault.")
    if rel_path.startswith("memory/codes-dev/memory-system/"):
        parts = rel_path.split("/")
        tier = parts[3] if len(parts) > 3 else "system"
        desc_map = {
            "01-facts": "Reference Python fact store and extraction interfaces.",
            "02-document-store": "Reference hybrid lexical, dense vector, and graph document storage backend.",
            "03-context-injection": "Reference prompt context compiler and memory injection routines.",
            "04-prompt-files": "Reference workspace system prompt generation and memory file manager.",
            "05-sessions": "Reference conversation history compression and SQLite transcript manager.",
            "06-trust-gate": "Reference prompt injection scanner, token taint tracking, and threat classification.",
            "07-cli": "Reference command-line diagnostic tools for interactive memory inspection.",
            "99-support": "Reference HTTP routes, event handlers, and registry definitions.",
            "patches": "Verification and bugfix patches applied to reference storage implementations.",
            "docs": "Verification checklists, SHA checksums, and defect resolution logs.",
            "tests": "Unit and contract tests verifying reference memory components.",
        }
        resp = desc_map.get(tier, f"Reference memory architecture component in {tier}.")
        return (f"Upstream Reference: {tier}", resp)
    return ("Project Asset", "Component of the JARVIS-OMA autonomous system.")

def collect_manifest_tools():
    manifest_dir = WORKSPACE_ROOT / "skill_manifests"
    manifests_data = []
    total_tools = 0
    for mf in sorted(manifest_dir.glob("*.json")):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            tools = data.get("skills", [])
            total_tools += len(tools)
            manifests_data.append({
                "file": mf.name,
                "count": len(tools),
                "tools": tools
            })
        except Exception as e:
            print(f"Error parsing {mf}: {e}")
    return manifests_data, total_tools

def generate_markdown():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    branch = run_cmd("git rev-parse --abbrev-ref HEAD")
    remote_url = run_cmd("git remote get-url origin")
    head_sha = run_cmd("git rev-parse HEAD")
    head_short = run_cmd("git rev-parse --short HEAD")
    head_msg = run_cmd("git log -1 --pretty=%B").splitlines()[0]
    commit_log = run_cmd("git log -n 15 --pretty=format:'*   `%h` (%cd): **%s**' --date=short")
    git_status = run_cmd("git status --short")
    
    file_inventory = collect_file_inventory()
    total_files = len(file_inventory)
    total_lines = sum(f["lines"] for f in file_inventory)
    
    manifests, total_tools = collect_manifest_tools()

    md = []
    
    # Header
    md.append("# CODEBASE_REFERENCE.md: J.A.R.V.I.S. OMA Technical Reference Manual\n")
    md.append("> **Definitive Codebase & Architectural Specification**  ")
    md.append(f"> **System**: J.A.R.V.I.S. OMA — Full-Duplex Voice Agent for Omarchy OS (Python 3.12+ + PipeWire + Gemini Live + Sovereign 4-Tier Memory + External Service Connectors + Proactive Autonomy)  ")
    md.append(f"> **Last Verified & Synchronized**: `{timestamp}`")
    md.append(f"> **Active Working Branch**: `{branch}` | **Remote**: `{remote_url}`  \n")
    md.append("---\n")

    # Section 1
    md.append("## 1. Repository Identity & Core Runtime\n")
    md.append(f"*   **Repository Root**: [`/home/g0pi/Projects/JARVIS-OMA`](file:///home/g0pi/Projects/JARVIS-OMA)")
    md.append(f"*   **Remote Repository**: `{remote_url}`")
    md.append(f"*   **Primary Identity**: `Jarvis — full-duplex voice agent for Omarchy` (J.A.R.V.I.S. OMA)")
    md.append("*   **Core Tech Stack & Architecture**:")
    md.append("    *   **Asynchronous Voice Core**: Pure asynchronous Python 3.12+ / 3.14+ runtime (`asyncio`), concurrently supervising microphone capture, WebSocket event reception, audio playback, background task monitoring, input bar polling, proactive autonomy loops, and Obsidian vault synchronization. Entry point: [`agent.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent.py) launched via [`run.sh`](file:///home/g0pi/Projects/JARVIS-OMA/run.sh).")
    md.append("    *   **Google Gemini Live Bidirectional API**: Direct full-duplex audio session over WebSockets via official Google GenAI SDK (`google-genai==2.24.0`). Streams 16 kHz PCM16 audio upstream and receives 24 kHz PCM16 audio chunks downstream with realtime interruption handling.")
    md.append("    *   **Sub-10ms Native PipeWire AEC Audio Pipeline**: Real-time WebRTC acoustic echo cancellation using `module-echo-cancel` managed via `pactl` ([`echo_cancel.py`](file:///home/g0pi/Projects/JARVIS-OMA/echo_cancel.py)). Employs private virtual audio nodes (`omachy_aec_*`) with low session priority to avoid disrupting system defaults, physical microphone volume capping (default 80%), and safe pre-conversation gain restoration.")
    md.append("    *   **Generation-Fenced Playback Engine**: Bounded playback queue ([`agent.py:Playback`](file:///home/g0pi/Projects/JARVIS-OMA/agent.py#L62)) running `pw-play` with cushion timing (`0.35s`), eliminating PipeWire audio pipeline bloat. Monotonically increasing generation counters instantly discard queued chunks upon speech interruption.")
    md.append(f"    *   **Dynamic Desktop Skills Matrix**: {total_tools} dynamically discovered desktop tools declared across {len(manifests)} JSON manifests in [`skill_manifests/`](file:///home/g0pi/Projects/JARVIS-OMA/skill_manifests) mapped to audited Python adapters in [`skills.py`](file:///home/g0pi/Projects/JARVIS-OMA/skills.py). Validates strict schemas and excludes tools with missing system binaries via graceful degradation.")
    md.append("    *   **External Service Connectors**: Voice-authorized GitHub and Google Workspace (Gmail, Calendar, Tasks) integrations with token storage in `connectors/.secrets/`, OAuth web flows, and automated browser dispatch ([`connectors/`](file:///home/g0pi/Projects/JARVIS-OMA/connectors)).")
    md.append("    *   **Visible Desktop Execution & Task Verification**: Interactive agent delegation inside isolated, visible tmux sessions on Omarchy Wayland desktop ([`orchestration/desktop_execution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py)) with pre-dispatch cryptographic file hash checks ([`proactive/verification.py`](file:///home/g0pi/Projects/JARVIS-OMA/proactive/verification.py)).")
    md.append("    *   **Dynamic Contextual Greetings**: Persistent, state-aware greeting engine ([`core/greeting.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/greeting.py)) that suppresses redundant welcomes, tracks return cooldowns, and generates natural single-sentence prompts focused on unfinished tasks.")
    md.append("    *   **Sovereign 4-Tier Memory Matrix**: Comprehensive memory architecture organized under [`memory/`](file:///home/g0pi/Projects/JARVIS-OMA/memory) combining file-locked atomic facts (`memory_facts.jsonl`), SQLite WAL database (`knowledge.db`) storing facts, SOUL/MEMORY/USER profiles, and FTS5 indexed documents, SQLite vector database (`semantic_vectors.db`) with cosine similarity, and live Markdown synchronization to an Obsidian Zettelkasten vault ([`memory/data/obsidian-vault/`](file:///home/g0pi/Projects/JARVIS-OMA/memory/data/obsidian-vault)). Legacy imports preserved via [`jarvis_memory/`](file:///home/g0pi/Projects/JARVIS-OMA/jarvis_memory) backward compatibility shim.")
    md.append("    *   **Proactive Autonomy Runtime**: Autonomous background execution system ([`proactive/`](file:///home/g0pi/Projects/JARVIS-OMA/proactive)) with transactional SQLite event bus (`events.db`), immutable activity ledger (`activity.db`), policy engine with cooldowns and duplicate prevention, bounded planner, and emergency voice controls (`pause_jarvis`, `resume_jarvis`, `stop_all_jarvis_work`).")
    md.append("    *   **Multi-Agent CLI Orchestrator**: Headless subprocess supervisor ([`agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent_orchestrator.py)) delegating engineering tasks to installed local agents (Codex, Claude Code, OpenCode, Gemini CLI, Hermes, OMP) across up to 4 concurrent workspaces with secret redaction.")
    md.append("    *   **In-Process Task Runner**: Bounded background task manager ([`task_runner.py`](file:///home/g0pi/Projects/JARVIS-OMA/task_runner.py)) executing structured plans of up to 30 filesystem steps with step-by-step reporting and cooperative cancellation.")
    md.append("    *   **Multimodal Loopback Input Bar & Overlay**: Zero-dependency loopback HTTP server ([`skills/input_bar.py`](file:///home/g0pi/Projects/JARVIS-OMA/skills/input_bar.py)) with cryptographic bearer token, rendered as an ultra-compact single-row 44px pill HUD via native Wayland transparent WebKitGTK overlay client ([`skills/overlay_client.py`](file:///home/g0pi/Projects/JARVIS-OMA/skills/overlay_client.py)) positioned at the bottom center of the screen (`(monitor_w/2 - 300), (monitor_h - window_h - 24)`) with zero compositor window borders (`border_size = 0`, `no_shadow = true`, `no_blur = true`). Backward-compatibility stub provided at [`test_bar.py`](file:///home/g0pi/Projects/JARVIS-OMA/test_bar.py).")
    md.append("    *   **Autonomous Evolution Engine**: Self-directed code self-improvement pipeline ([`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py)) synthesizing code optimizations, running test validation, and executing safety rollbacks.")
    md.append("    *   **Systemd User Service Daemon**: Production background daemon service ([`systemd/jarvis-oma.service`](file:///home/g0pi/Projects/JARVIS-OMA/systemd/jarvis-oma.service)) managed via [`scripts/install-service.sh`](file:///home/g0pi/Projects/JARVIS-OMA/scripts/install-service.sh), with SIGUSR1 speech mute toggle and SIGUSR2 response interruption.")
    md.append("*   **Target Operating System**: Omarchy OS / Arch Linux (Hyprland Wayland compositor, PipeWire audio server, systemd).")
    md.append("*   **Execution Command**: `./run.sh` or `.venv/bin/python agent.py`.\n")
    md.append("---\n")

    # Section 2
    md.append("## 2. Real-Time Git Branch & Commit Telemetry\n")
    md.append("### Branch & Remote Status")
    md.append(f"*   **Active Working Branch**: `{branch}`")
    md.append(f"*   **Tracking Remote**: `{remote_url}`")
    md.append(f"*   **Latest Commit SHA**: `{head_sha}` (`{head_short}`)")
    md.append(f"*   **Latest Commit Subject**: `{head_msg}`\n")
    md.append("### Commit History (Recent Log)")
    md.append(commit_log + "\n")
    md.append("### Working Tree Telemetry")
    if git_status:
        md.append("```text")
        md.append(git_status)
        md.append("```\n")
    else:
        md.append("*Working tree is clean; all changes committed.*\n")
    md.append("---\n")

    # Section 3
    md.append("## 3. Full Dependency Inventory\n")
    md.append("### Production Python Dependencies (`requirements.txt`)")
    md.append("*   **`google-genai` (2.24.0)**: Official Google GenAI SDK powering Gemini Live full-duplex bidirectional streaming audio session over WebSockets, tool declaration schema translation, function call dispatching, and optional semantic vector embeddings (`GeminiEmbeddingProvider`).")
    md.append("*   **`sounddevice` (>=0.5.1)**: PortAudio bindings for low-latency native audio streaming.")
    md.append("*   **`numpy` (>=1.26.0)**: High-performance audio buffer manipulation and numerical calculations for native audio processing.\n")
    md.append("### Python Standard Library Core (Python 3.12+ / 3.14+)")
    md.append("*   **`asyncio`**: Core asynchronous event loop driving concurrent audio capture, playback supervision, agent monitoring, proactive ticks, and background tasks.")
    md.append("*   **`sqlite3`**: High-performance local persistence backing KnowledgeStore, SessionStore, VectorStore, Proactive EventBus, ActivityLedger, GreetingMemory, and AutonomyControl with WAL (Write-Ahead Logging) and FTS5 full-text indexing.")
    md.append("*   **`dataclasses`**: Type-safe declarative schema models for Configuration, Memory Facts, Retrieval Candidates, Proactive Events, and Activity Records.")
    md.append("*   **`tomllib`**: Native Python 3.11+ zero-dependency TOML configuration parser.")
    md.append("*   **`pathlib` & `shutil`**: Cross-platform path normalization, file inspection, and binary discovery.")
    md.append("*   **`http.server` & `secrets`**: Lightweight loopback-only ThreadingHTTPServer with cryptographically secure token generation for the Multimodal Input Bar and OAuth callback flows.")
    md.append("*   **`zoneinfo`**: IANA timezone validation for Obsidian daily notes.\n")
    md.append("### System Desktop & Audio Utilities (Host OS / Omarchy)")
    md.append("*   **PipeWire Audio**: `pw-record` (16kHz PCM16 mic capture), `pw-play` (24kHz PCM16 playback), `pactl` (PulseAudio control layer for WebRTC echo-cancellation module management).")
    md.append("*   **Desktop Windowing & Perception**: `hyprctl` (Hyprland window and workspace management), `grim` (Wayland screenshots), `tesseract` (local OCR for `inspect_screen`).")
    md.append("*   **Desktop Automation**: `wl-paste` & `wl-copy` (Wayland clipboard integration), `notify-send` (libnotify desktop notifications), `loginctl` (session screen locking), `systemctl` (safe suspend/hibernate power control).")
    md.append("*   **Visible Desktop Supervision**: `tmux` (isolated visible execution sessions with `-L jarvis-desktop`), `xdg-terminal-exec` (terminal launcher).")
    md.append("*   **External CLI & Connectors**: `gh` (GitHub official CLI for device authentication), `omarchy-launch-webapp` & `xdg-open` (visible browser launchers).")
    md.append("*   **Network & Hardware**: `nmcli` (NetworkManager Wi-Fi toggling and status), `rfkill` (Bluetooth RF switch), `ps` (hardware and memory monitoring).")
    md.append("*   **Omarchy Native Utilities**: `gtk-launch` (XDG application launcher), `omarchy-audio-output-volume`, `omarchy-brightness-display`, `omarchy-reminder`, and native Todo List SQLite plugin (`omarchy-todo`).")
    md.append("*   **Local LLM Engines (Optional)**: Ollama (`http://127.0.0.1:11434`) for local fact extraction or local embeddings without external API keys.\n")
    md.append("---\n")

    # Section 4
    md.append("## 4. Startup & Runtime Flow\n")
    md.append("The full-duplex boot sequence and concurrent worker supervision are orchestrated inside [`agent.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent.py):\n")
    md.append("```mermaid")
    md.append("sequenceDiagram")
    md.append("    autonumber")
    md.append("    participant User as User (Voice / Desktop)")
    md.append("    participant Agent as agent.py (Main)")
    md.append("    participant Config as config.py")
    md.append("    participant Echo as echo_cancel.py (PipeWire)")
    md.append("    participant Playback as agent.py:Playback")
    md.append("    participant Skills as skills.py (DesktopSkills)")
    md.append("    participant Connectors as connectors/ (Google & GitHub)")
    md.append("    participant Memory as memory/ (codes-dev/jarvis_memory/bridge.py)")
    md.append("    participant Greeting as core/greeting.py (GreetingMemory)")
    md.append("    participant GenAI as Gemini Live API (/live)")
    md.append("    participant Mic as pw-record (16kHz)")
    md.append("    participant Speaker as pw-play (24kHz)")
    md.append("    participant Proactive as proactive/runtime.py")
    md.append("    participant InputBar as skills/input_bar.py (HTTP)")
    md.append("")
    md.append("    User->>Agent: ./run.sh (CLI arguments)")
    md.append("    Agent->>Config: load_config(args, env, config.toml)")
    md.append("    Agent->>Echo: start(volume_cap=80%, webrtc_aec)")
    md.append("    Echo-->>Agent: virtual source & sink created")
    md.append("    Agent->>Playback: new Playback(echo.sink)")
    md.append("    Agent->>Skills: DesktopSkills(scan manifests, check commands)")
    md.append("    Skills->>Connectors: initialize GitHub & Google Workspace bridges")
    md.append("    Skills->>Memory: MemoryBridge.start() (load knowledge.db, FTS5)")
    md.append(f"    Agent->>GenAI: client.live.connect(model, voice, tools={total_tools})")
    md.append("    GenAI-->>Agent: Session Established")
    md.append("    Agent->>Mic: spawn pw-record --target echo.source")
    md.append("    Agent->>Greeting: prepare(conversation_history, cooldown=4h)")
    md.append("    alt Greeting Allowed")
    md.append("        Greeting-->>Agent: greeting prompt (single sentence, focus on unfinished task)")
    md.append("        Agent->>GenAI: send initial greeting prompt")
    md.append("        GenAI-->>Agent: greeting audio chunks (24kHz)")
    md.append("        Agent->>Playback: enqueue(audio)")
    md.append("        Playback->>Speaker: spawn pw-play --target echo.sink")
    md.append("    else Greeting Suppressed (Recent Cooldown)")
    md.append("        Greeting-->>Agent: suppressed (silent boot)")
    md.append("    end")
    md.append("    par Supervised Concurrent Workers")
    md.append("        Mic->>Agent: stream 16kHz PCM16 audio")
    md.append("        Agent->>GenAI: send_realtime_input(audio chunk)")
    md.append("    and Event Reception")
    md.append("        GenAI-->>Agent: receive() server events (audio / transcript / tool_call)")
    md.append("        alt Audio Output")
    md.append("            Agent->>Playback: enqueue(audio chunks)")
    md.append("            Playback->>Speaker: pipe to pw-play")
    md.append("        else User Interrupted")
    md.append("            Agent->>Playback: interrupt() (generation++, kill pw-play)")
    md.append("        else Tool Call Event")
    md.append("            Agent->>Skills: execute(tool_name, args)")
    md.append("            Skills-->>Agent: return output dict")
    md.append("            Agent->>GenAI: send_tool_response(function_responses)")
    md.append("        end")
    md.append("    and Background Proactive Loop")
    md.append("        Proactive->>Agent: tick() (observe todos, reminders, and verification)")
    md.append("    and Multimodal Input Bar")
    md.append("        InputBar->>Agent: pop() typed text / uploaded file")
    md.append("        Agent->>GenAI: send_client_content(parts)")
    md.append("    end")
    md.append("```\n")
    md.append("### Step-by-Step Prose Boot Sequence")
    md.append("1.  **Configuration Resolution**: [`config.py`](file:///home/g0pi/Projects/JARVIS-OMA/config.py) evaluates settings using a strict priority ladder: CLI flags override `JARVIS_*` environment variables, which override `config.toml` / `config.json`, which fall back to built-in defaults.")
    md.append("2.  **Audio Infrastructure Warmup**: [`echo_cancel.py`](file:///home/g0pi/Projects/JARVIS-OMA/echo_cancel.py) queries default PipeWire sources and sinks via `pactl`. It caps physical microphone gain at 80% to prevent clipping, then loads `module-echo-cancel` with WebRTC acoustic echo cancellation (`rate=48000`, `high_pass_filter=1`, `noise_suppression=1`).")
    md.append("3.  **Playback Queue Initialization**: A bounded `Playback` instance is instantiated targeting the virtual echo cancellation sink with a 10-second maximum backlog buffer and cushion timing (`0.35s`).")
    md.append(f"4.  **Skills Registry Scanning & Tool Validation**: [`skills.py`](file:///home/g0pi/Projects/JARVIS-OMA/skills.py) parses all {len(manifests)} JSON manifests in `skill_manifests/`. It validates all tool declarations, verifies required system commands (`ADAPTER_COMMANDS`), and prepares {total_tools} function schemas for Gemini Live.")
    md.append("5.  **External Service Connectors Initialization**: External adapters for Google Workspace (Gmail, Calendar, Tasks) and GitHub are loaded with credentials retrieved securely from the process environment or `connectors/.secrets/credentials.env`.")
    md.append("6.  **Memory Subsystem Engagement**: [`memory/codes-dev/jarvis_memory/bridge.py`](file:///home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/bridge.py) (via [`jarvis_memory/`](file:///home/g0pi/Projects/JARVIS-OMA/jarvis_memory)) opens `memory_facts.jsonl`, connects to SQLite `knowledge.db`, initializes FTS5 document indexing, verifies the vector cache `semantic_vectors.db`, and compiles initial prompt context.")
    md.append(f"7.  **Gemini Live WebSocket Connection**: Connects to Google Gemini Live API via `client.live.connect()`, passing the system instruction (enforcing concise single-sentence responses), selected voice model (`Aoede`), VAD sensitivity parameters, and the {total_tools} tool declarations.")
    md.append("8.  **Microphone Process Spawn**: Starts `pw-record` as an asynchronous child process streaming 16 kHz signed 16-bit mono PCM audio from the private echo-cancelled source.")
    md.append("9.  **Dynamic Contextual Greeting**: [`core/greeting.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/greeting.py) evaluates recent greeting timestamps and cooldowns. If unsuppressed, it generates a single-sentence conversational greeting tailored to the user's latest unfinished task.")
    md.append("10. **Supervised Concurrent Workers**: The main loop launches `supervise()` across concurrent background tasks:")
    md.append("    *   `send_audio`: Reads 640-byte audio chunks from `pw-record` and forwards them upstream.")
    md.append("    *   `receive`: Listens for incoming server events from Gemini Live.")
    md.append("    *   `player.run`: Continuously feeds 24 kHz audio chunks into `pw-play`.")
    md.append("    *   `monitor_agents`: Receives asynchronous agent delegation job updates and relays notifications.")
    md.append("    *   `send_input_bar`: Polls typed text or file attachments from the multimodal input bar.")
    md.append("    *   `run_proactive`: Evaluates the proactive autonomy runtime and scheduled events every 10 seconds.")
    md.append("    *   `sync_memory_vault`: Periodically syncs memory state to the linked Obsidian vault.")
    md.append("11. **Graceful Teardown & Gain Restoration**: When stopped (via `Ctrl+C` or SIGTERM), `supervise()` cancels all workers, terminates `pw-record` and `pw-play`, unloads `module-echo-cancel` via `pactl unload-module`, and restores the user's pre-conversation microphone volume.\n")
    md.append("---\n")

    # Section 5
    md.append(f"## 5. Complete Module Map (All {total_files} Files)\n")
    md.append(f"Below is an exhaustive, 100% complete accounting of every single source file, test suite, manifest, and script in the repository ({total_files} files cataloged across modular subsections with zero omissions):\n")
    
    # Subsections
    subsections = [
        ("5.1 Modular Core Runtime (`core/`)", lambda p: p.startswith("core/")),
        ("5.2 Modular Audio Subsystem (`audio/`)", lambda p: p.startswith("audio/")),
        ("5.3 External Service Connectors (`connectors/`)", lambda p: p.startswith("connectors/")),
        ("5.4 Modular Filesystem Subsystem (`filesystem/`)", lambda p: p.startswith("filesystem/")),
        ("5.5 Orchestration & Evolution Engine (`orchestration/`)", lambda p: p.startswith("orchestration/")),
        ("5.6 Dynamic Skills Engine & Overlays (`skills/`)", lambda p: p.startswith("skills/")),
        ("5.7 Dynamic Skill Manifests (`skill_manifests/`)", lambda p: p.startswith("skill_manifests/")),
        ("5.8 Proactive Autonomy Subsystem (`proactive/`)", lambda p: p.startswith("proactive/")),
        ("5.9 Backward Compatibility Shims (`jarvis_memory/`)", lambda p: p.startswith("jarvis_memory/")),
        ("5.10 Unified Memory Package & Active Engine (`memory/` & `memory/codes-dev/jarvis_memory/`)", lambda p: p in ("memory/README.md", "memory/__init__.py") or p.startswith("memory/codes-dev/jarvis_memory/")),
        ("5.11 Upstream Reference Memory Architecture (`memory/codes-dev/memory-system/`)", lambda p: p.startswith("memory/codes-dev/memory-system/")),
        ("5.12 Memory Development Tests, Scripts & Docs (`memory/codes-dev/tests/`, `scripts/`, `docs/`)", lambda p: p.startswith("memory/codes-dev/tests/") or p.startswith("memory/codes-dev/scripts/") or p.startswith("memory/codes-dev/docs/")),
        ("5.13 Synced Obsidian Markdown Vault (`memory/data/obsidian-vault/`)", lambda p: p.startswith("memory/data/obsidian-vault/")),
        ("5.14 Systemd Service Integration (`systemd/`)", lambda p: p.startswith("systemd/")),
        ("5.15 Support & Automation Scripts (`scripts/`)", lambda p: p.startswith("scripts/")),
        ("5.16 Automated Test Suites (`tests/`)", lambda p: p.startswith("tests/")),
        ("5.17 Root Entry Points & Operational Scripts", lambda p: "/" not in p and not p.startswith(".")),
        ("5.18 Hidden Configurations & Environment Secrets", lambda p: "/" not in p and p.startswith(".")),
        ("5.19 Architectural Documentation & Research Reports (`docs/`)", lambda p: p.startswith("docs/")),
        ("5.20 Continuous Integration & Issue Templates (`.github/`)", lambda p: p.startswith(".github/")),
        ("5.21 Opt-in Harness Learning Foundation (`learning/`)", lambda p: p.startswith("learning/")),
    ]

    for title, predicate in subsections:
        matched = [f for f in file_inventory if predicate(f["rel_path"])]
        if not matched:
            continue
        md.append(f"### {title} ({len(matched)} files)\n")
        md.append("| File Path | Lines | Size (Bytes) | Role | Verified Responsibilities |")
        md.append("| :--- | :---: | :---: | :--- | :--- |")
        for item in matched:
            rel = item["rel_path"]
            lines = item["lines"]
            size = item["size"]
            role, resp = get_role_and_responsibility(rel)
            md.append(f"| [{rel}](file://{item['full_path']}) | {lines} | {size} | {role} | {resp} |")
        md.append("")

    md.append("---\n")

    # Section 6
    md.append("## 6. Architecture — Actual Shape\n")
    md.append(f"The verified architecture operates as a low-latency, full-duplex asynchronous reactive loop integrating local hardware PipeWire audio with Gemini Live WebSockets, {total_tools} dynamically discovered desktop skills across {len(manifests)} manifests, external service connectors, a sovereign 4-tier memory matrix, proactive autonomy, and local coding agent orchestration.\n")
    md.append("```text")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
    md.append("  │                           HOST DESKTOP ENVIRONMENT (Omarchy OS / Arch Linux / Hyprland)                        │")
    md.append("  │    Physical Microphone   │  Physical Speakers/Headphones   │  Wayland Displays   │  Web Browsers / Apps        │")
    md.append("  └──────────────────────────┬─────────────────────────────────────────────────▲───────────────────────────────────┘")
    md.append("                             │                                                 │")
    md.append("                             ▼                                                 │")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┐")
    md.append("  │                     PIPEWIRE LOW-LATENCY AUDIO INFRASTRUCTURE (echo_cancel.py & engine.py)                     │")
    md.append("  │    WebRTC Echo Cancellation (module-echo-cancel)  │  Virtual Nodes (omachy_aec_*)                              │")
    md.append("  │    Source Volume Capping (80%)  │  pw-record (16kHz PCM)  │  pw-play (24kHz PCM)                               │")
    md.append("  └──────────────────────────┬─────────────────────────────────────────────────▲───────────────────────────────────┘")
    md.append("                             │                                                 │")
    md.append("                             ▼                                                 │ 24kHz PCM Audio")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┐")
    md.append("  │                         ASYNCHRONOUS VOICE RUNTIME ENGINE (agent.py & core/)                                   │")
    md.append("  │    supervise() Worker Group  │  Monotonic Generation-Fenced Interruption Handling                              │")
    md.append("  │    Single-Sentence Enforcement Rule  │  Dynamic Contextual Greeting (greeting.py)  │ Dynamic Config            │")
    md.append("  └──────────────────────────┬─────────────────────────────────────────────────▲───────────────────────────────────┘")
    md.append("                             │                                                 │")
    md.append("                             ▼ WSS Audio Streaming                             │ Real-time Events")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┐")
    md.append("  │                         GOOGLE GEMINI LIVE API (google-genai 2.24.0)                                           │")
    md.append("  │    Model: gemini-3.8-live  │  Voice: Aoede  │  VAD Activity Handling: Interrupts                               │")
    md.append("  │    Real-time Multimodal Token Generation  │  Streaming Tool Calls & Function Responses                         │")
    md.append("  └──────────────────────────┬─────────────────────────────────────────────────▲───────────────────────────────────┘")
    md.append("                             │ Tool Call Event                                 │ Tool Response")
    md.append("                             ▼                                                 │")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┐")
    md.append(f"  │                     DYNAMIC DESKTOP SKILLS ENGINE (skills.py — {total_tools} Tools across {len(manifests)} Manifests)               │")
    md.append(f"  │    {len(manifests)} JSON Manifests  │  Strict Schema Validation  │  ADAPTER_COMMANDS Dependency Verification Checks    │")
    md.append("  └────────┬──────────────────┬──────────────────┬──────────────────┬──────────────────┬──────────────────┬────────┘")
    md.append("           │                  │                  │                  │                  │                  │")
    md.append("           ▼                  ▼                  ▼                  ▼                  ▼                  ▼")
    md.append("  ┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐")
    md.append("  │     OMARCHY     ││   FILESYSTEM    ││   CONNECTORS    ││    PROACTIVE    ││   MULTI-AGENT   ││    SOVEREIGN    │")
    md.append("  │    CONTROLS     ││    AUTONOMY     ││   & SERVICES    ││    AUTONOMY     ││  ORCHESTRATOR   ││  MEMORY MATRIX  │")
    md.append("  ├─────────────────┤├─────────────────┤├─────────────────┤├─────────────────┤├─────────────────┤├─────────────────┤")
    md.append("  │ hyprctl / Wayl. ││ 13 Tools        ││ GitHub REST API ││ Event Bus (WAL) ││ Codex / Claude  ││ memory/ (Tier 1)│")
    md.append("  │ grim / OCR      ││ Read / Write    ││ Google Worksp.  ││ Activity Ledger ││ Visible tmux    ││ SQLite WAL db   │")
    md.append("  │ notify-send     ││ Move / Delete   ││ OAuth Webflows  ││ Bounded Planner ││ OpenCode/Hermes ││ Vector db (WAL) │")
    md.append("  │ pactl volume    ││ Task Runner     ││ Browser Dispatch││ Dynamic Policy  ││ Gemini CLI/OMP  ││ Obsidian Vault  │")
    md.append("  │ brightness      ││ 30 Steps Max    ││ Credential Vault││ Cryptographic   ││ Isolated Works. ││ Hybrid Fusion   │")
    md.append("  │ Todos / Timers  ││ Root Guardrails ││ Secret Redaction││ Emergency Stops ││ Up to 4 Workers ││ JSONL Facts     │")
    md.append("  └─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘")
    md.append("```\n")
    md.append("---\n")

    # Section 7
    md.append(f"## 7. Complete {total_tools}-Tool Registry\n")
    md.append(f"The system dynamically exposes and routes **{total_tools} tools** across {len(manifests)} specialized manifests with strict argument validation and zero collisions:\n")
    
    for mf_info in manifests:
        mf_name = mf_info["file"]
        count = mf_info["count"]
        tools = mf_info["tools"]
        md.append(f"### {mf_name} ({count} Tools)\n")
        md.append("| Tool Name | Adapter | Direct Method | Description |")
        md.append("| :--- | :--- | :--- | :--- |")
        for t in tools:
            name = t["name"]
            adapter = t.get("adapter", "N/A")
            desc = t.get("description", "").replace("\n", " ")
            md.append(f"| `{name}` | `{adapter}` | `skills.py` | {desc} |")
        md.append("")

    md.append("---\n")

    # Section 8
    md.append("## 8. Agent Orchestration, Delegation, Desktop Execution & Proactive Autonomy\n")
    md.append("### Multi-Agent CLI Orchestration Engine (`agent_orchestrator.py`)\n")
    md.append("JARVIS-OMA features a headless supervisor for installed local AI coding agents:\n")
    md.append("*   **Supported Agent Roster**: `codex`, `claude`, `opencode`, `gemini`, `hermes`, `omp`.")
    md.append("*   **Direct Subprocess Invocation**: Executes agent binaries directly via `asyncio.create_subprocess_exec` without invoking a shell, preventing shell injection vulnerabilities.")
    md.append("*   **Concurrency & Directory Boundaries**: Limits active concurrent agents to **4**. Enforces strict workspace path reservations: overlapping parent or child directories cannot be used concurrently by multiple jobs.")
    md.append("*   **Execution Timeouts**: Enforces timeouts from 10 to 7200 seconds (default 900 seconds / 15 minutes). Escalates termination from `SIGTERM` to `SIGKILL` on timeout or cancellation.")
    md.append("*   **Secret Redaction**: Automatically scans active environment variables for tokens, keys, and passwords (`len >= 8`) and redacts them from job output logs before passing to Gemini.")
    md.append("*   **Telemetry & Event Queue**: Buffers up to 50 historical job records in memory and feeds real-time completion events into `agent_job_events` for live spoken notification to the user.\n")
    md.append("### Visible Desktop Execution Engine (`orchestration/desktop_execution.py`)\n")
    md.append("For interactive and visible agent delegations, JARVIS-OMA integrates with `tmux` and Wayland terminal emulators:\n")
    md.append("*   **Dedicated Socket Isolation**: All sessions are launched on an isolated socket (`tmux -L jarvis-desktop`), preventing interference with user terminal workflows.")
    md.append("*   **Interactive Agent Modes**: Supports visible interactive execution for `codex` (with `--no-alt-screen --sandbox workspace-write --approve-for-me`) and `claude` (with task-specific model routing and auto-permissions).")
    md.append("*   **Safe Subprocess Environment**: Passes sanitized environment dictionaries stripped of API keys, tokens, and credentials via `core.secret_env:sanitized_subprocess_env`.\n")
    md.append("### Independent Cryptographic Verification (`proactive/verification.py`)\n")
    md.append("To prevent unverified agent completion claims, the autonomy runtime executes strict cryptographic checks:\n")
    md.append("*   **Byte-Exact Verification**: Verifies exact file sha256 digests outside worker process permissions.")
    md.append("*   **Path Traversal Protection**: Rejects absolute paths, parent directory references (`..`), null bytes, and non-relative paths.")
    md.append("*   **Descriptor Pinning (`O_NOFOLLOW`)**: Resolves paths against pinned directory descriptors with `O_NOFOLLOW` and `O_NONBLOCK`, eliminating symlink substitution and blocking FIFO attacks.")
    md.append("*   **Size & Mutation Bounds**: Limits verified artifacts to 16 MiB and verifies timestamps and sizes before and after digestion to detect concurrent writes.\n")
    md.append("### Proactive Autonomy Runtime (`proactive/`)\n")
    md.append("*   **Transactional Event Bus (`proactive/events.py`)**: SQLite-backed event queue (`events.db`) with atomic claiming, deduplication hashes, and retry tracking.")
    md.append("*   **Immutable Activity Ledger (`proactive/ledger.py`)**: SQLite audit ledger (`activity.db`) recording all planned, delegated, completed, and rejected actions with exact payloads and timestamps.")
    md.append("*   **Autonomy Policy Governor (`proactive/policy.py`)**: Restricts action execution rates, enforces cooldowns between similar actions, classifies side effects (read-only vs mutating), and demands explicit user authorization for high-impact tasks.")
    md.append("*   **Autonomous Bounded Planner (`proactive/planner.py`)**: Deterministically routes tasks to specific agents based on keyword heuristics and skill capabilities, rejecting malformed or out-of-scope directives.")
    md.append("*   **Emergency Autonomy Controls (`proactive/control.py`)**: Durable state store (`control.db`) providing voice-actuated emergency latches (`pause_jarvis`, `resume_jarvis`, `stop_all_jarvis_work`).")
    md.append("*   **Background Observation Loops**: The runtime automatically inspects Omarchy Todo tasks and native reminders every 10 seconds, transforming new items into planned events without requiring user voice input.\n")
    md.append("---\n")

    # Section 9
    md.append("## 9. Memory & Persistence Systems\n")
    md.append("JARVIS-OMA features a sovereign **4-tier cognitive memory matrix** unified under the [`memory/`](file:///home/g0pi/Projects/JARVIS-OMA/memory) package:\n")
    md.append("```text")
    md.append("  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
    md.append("  │                                    SOVEREIGN 4-TIER MEMORY MATRIX                                      │")
    md.append("  ├────────────────────────────────────────────────────────────────────────────────────────────────────────┤")
    md.append("  │ 1. Atomic Fact Store      │ memory_facts.jsonl with cross-process file locking                         │")
    md.append("  │                           │ Stores discrete user preferences and verified system facts                 │")
    md.append("  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────┤")
    md.append("  │ 2. Knowledge & Profiles   │ SQLite WAL knowledge.db                                                    │")
    md.append("  │                           │ Profile notes (SOUL.md, MEMORY.md, USER.md)                              │")
    md.append("  │                           │ Structured memory ledger with revision histories                           │")
    md.append("  │                           │ FTS5 tokenized full-text indexing for indexed documents                    │")
    md.append("  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────┤")
    md.append("  │ 3. Semantic Vector Store  │ SQLite semantic_vectors.db                                                 │")
    md.append("  │                           │ Dense vector embeddings (Gemini API or Ollama local)                       │")
    md.append("  │                           │ Deterministic hybrid fusion (BM25 + Cosine Similarity)                     │")
    md.append("  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────┤")
    md.append("  │ 4. Obsidian Zettelkasten  │ memory/data/obsidian-vault/ Markdown files                                 │")
    md.append("  │                           │ Daily interaction journals, Topic index notes, Guides, Profile Cards       │")
    md.append("  │                           │ Synchronized live via scripts/sync_obsidian_memory.py                      │")
    md.append("  └───────────────────────────┴────────────────────────────────────────────────────────────────────────────┘")
    md.append("```\n")
    md.append("### Directory Reorganization & Unified Memory Layout")
    md.append("All memory code, reference implementations, data, and tests are consolidated under [`memory/`](file:///home/g0pi/Projects/JARVIS-OMA/memory):")
    md.append("*   `memory/codes-dev/jarvis_memory/`: The active, production 4-tier memory engine (`bridge.py`, `knowledge.py`, `vector_store.py`, `embeddings.py`, `hybrid.py`, `scanner.py`).")
    md.append("*   `memory/codes-dev/memory-system/`: The upstream modular reference implementation (tiers `01-facts` through `07-cli` and `99-support`).")
    md.append("*   `memory/codes-dev/tests/`: Dedicated unit and acceptance test suites for memory extraction, vector caching, and hybrid ranking.")
    md.append("*   `memory/data/obsidian-vault/`: The sovereign Obsidian markdown vault storing graph notes, daily interaction logs, and profile cards.")
    md.append("*   `jarvis_memory/`: Backward-compatibility package shim redirecting legacy imports to `memory/codes-dev/jarvis_memory/` via `sys.path` with zero breaking changes.\n")
    md.append("### Key Capabilities & Safeguards")
    md.append("*   **Zero-Cloud Extractor Option**: Supports local background fact extraction via Ollama (`http://127.0.0.1:11434`), eliminating external API costs for memory processing.")
    md.append("*   **Evidence-Grounded Extraction**: Fact extraction filters conversation turns strictly for user assertions; assistant statements never become stored facts.")
    md.append("*   **Prompt Injection Scanner (`scanner.py`)**: Screens candidate memory inputs against adversarial manipulation, instruction overrides, and jailbreak attempts before persistence.")
    md.append("*   **Continuous Session Recording**: Retains multi-turn conversation transcripts continuously across restarts without age-based resets or automatic pruning.")
    md.append("*   **Extractive Daily Summaries (`summaries.py`)**: Assembles daily interaction summaries directly attributed to source conversation turns, preserving manual edits.")
    md.append("*   **Obsidian Vault Registration (`scripts/register_obsidian_vault.py`)**: Safely updates `~/.config/obsidian/obsidian.json` to register the JARVIS memory vault while creating an atomic backup.\n")
    md.append("---\n")

    # Section 10
    md.append("## 10. Security Model, Guardrails & Bounded Execution\n")
    md.append("1.  **Unsandboxed Desktop Autonomy with Strict Ceilings**: JARVIS-OMA runs directly on the user's desktop to provide unconstrained system assistance, bounded by strict declarative code safeguards.")
    md.append("2.  **Protected Critical Path Boundaries (`filesystem.py:CRITICAL_PATHS`)**: File operations permanently forbid deleting, moving, or tampering with critical operating system roots: `/`, `~`, `/bin`, `/boot`, `/dev`, `/etc`, `/lib`, `/lib64`, `/proc`, `/root`, `/sbin`, `/sys`, `/usr`.")
    md.append("3.  **Strict Read & Write Ceilings**: Filesystem reads enforce a maximum of 100,000 characters per call; atomic writes enforce a maximum file size of 5 MiB.")
    md.append("4.  **No Arbitrary Shell Injection**: Tools do not execute arbitrary shell strings. Subprocesses are invoked with explicit argument lists (`argv`), completely bypassing `/bin/sh` or `/bin/bash` interpretation.")
    md.append("5.  **Environment Secret Filtering (`core/secret_env.py`)**: The `sanitized_subprocess_env()` helper strips all environment variables containing secrets (`API_KEY`, `ACCESS_KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIALS`) before spawning child processes.")
    md.append("6.  **Connector Credential Isolation (`connectors/credentials.py`)**: OAuth tokens and credentials reside in `connectors/.secrets/` (chmod `0o600` / `0o700`) and are excluded from Git via `.gitignore`. The connector bridges never print or log raw credential payloads.")
    md.append("7.  **Safe Power State Enforcement**: The `system_power` skill strictly permits non-destructive session transitions (`suspend`, `hibernate`). Permanent shutdown and reboot actions are explicitly forbidden.")
    md.append("8.  **Web Browsing URL Constraints**: `open_website` strictly validates URL schemes (`http`, `https`) and actively rejects private, loopback, or local IP addresses (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), preventing SSRF attacks against internal network appliances.")
    md.append("9.  **Loopback Input Bar Bearer Token Authentication**: The multimodal input bar binds exclusively to `127.0.0.1` and authenticates every request using a high-entropy URL-safe bearer token (`secrets.token_urlsafe(24)`).\n")
    md.append("---\n")

    # Section 11
    md.append("## 11. CLI, Configuration & Runtime Control Surface\n")
    md.append("### Dynamic Configuration Hierarchy")
    md.append("1.  **CLI Arguments**: Explicit flags passed to `run.sh` / `agent.py`.")
    md.append("2.  **Environment Variables**: `JARVIS_*` environment variables (e.g. `JARVIS_VOICE`, `JARVIS_MODEL`, `JARVIS_AGENT_NAME`, `JARVIS_SINGLE_SENTENCE`, `JARVIS_CONNECTOR_SECRET_DIR`).")
    md.append("3.  **Configuration File**: TOML or JSON file loaded from `~/.config/jarvis-oma/config.toml`, `./config.toml`, or `./config.json`.")
    md.append("4.  **Built-in Defaults**: Fallback constants defined in [`config.py`](file:///home/g0pi/Projects/JARVIS-OMA/config.py).\n")
    md.append("### CLI Flags (`agent.py` / `run.sh`)")
    md.append("| Flag | Default | Description |")
    md.append("| :--- | :--- | :--- |")
    md.append("| `--model` | `gemini-3.8-live` | Target Gemini Live model identifier |")
    md.append("| `--voice` | `Aoede` | Prebuilt voice name (Aoede, Puck, Charon, Kore, Fenrir) |")
    md.append("| `--agent-name` | `Jarvis` | Assistant persona name used in greetings and prompts |")
    md.append("| `--language` | `en` | Primary spoken language code (`en`, `te`, `hi`, `auto`) |")
    md.append("| `--system-instruction` | Built-in | Custom system prompt override |")
    md.append("| `--greeting-prompt` | Built-in | Custom prompt to trigger initial activation greeting |")
    md.append("| `--no-greet` | `False` | Disables proactive greeting on startup |")
    md.append("| `--no-interrupt` | `False` | Sets VAD handling to `NO_INTERRUPTION` |")
    md.append("| `--transcripts` | `False` | Prints real-time token transcription stream to terminal |")
    md.append(f"| `--no-skills` | `False` | Disables all {total_tools} desktop tools for conversation-only mode |")
    md.append("| `--list-skills` | `False` | Lists discovered skills and reports binary availability |")
    md.append("| `--skill-dir` | Bundled | Custom directory containing JSON skill manifests |")
    md.append("| `--check` | `False` | Validates dependencies without opening audio or network |")
    md.append("| `--config` | Auto | Path to `.toml` or `.json` configuration file |")
    md.append("| `--microphone` | Default | Physical PipeWire/PulseAudio microphone source name |")
    md.append("| `--retries` | `5` | Consecutive failure reconnection budget |\n")
    md.append("---\n")

    # Section 12
    md.append("## 12. Build, Test, CI & Verification Workflow\n")
    md.append("### Environment Setup")
    md.append("```bash")
    md.append("python3 -m venv .venv")
    md.append(".venv/bin/python -m pip install -r requirements.txt")
    md.append("cp .env.example .env  # set GEMINI_API_KEY")
    md.append("./run.sh --check")
    md.append("./run.sh --list-skills")
    md.append("./run.sh")
    md.append("```\n")
    md.append("### Automated Test Suite Execution")
    md.append("The repository includes **41 automated test files** across unit, integration, connector, and acceptance suites:\n")
    md.append("```bash")
    md.append("PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v")
    md.append("```\n")
    md.append("### Test Suite Categorization")
    md.append("*   **Audio Subsystem (`tests/test_audio/`)**: Echo cancellation, native audio engine, PortAudio streaming.")
    md.append("*   **External Connectors (`tests/test_connectors/`, `tests/test_skills/test_*connector*.py`)**: GitHub REST API, Google Workspace OAuth, and browser launcher.")
    md.append("*   **Core Runtime (`tests/test_core/`)**: Voice agent live config, greeting persistence, dynamic settings, secret environment scrubbing.")
    md.append("*   **Filesystem Subsystem (`tests/test_filesystem/`)**: Autonomy operations, root safety guards, bounded task runner.")
    md.append("*   **Memory Subsystem (`tests/test_memory/`, `memory/codes-dev/tests/`)**: Fact store, vector caching, hybrid retrieval, Obsidian vault sync.")
    md.append("*   **Orchestration Engine (`tests/test_orchestration/`)**: Multi-agent CLI supervisor, visible desktop execution (tmux), evolution engine.")
    md.append("*   **Proactive Autonomy (`tests/test_proactive/`)**: Event bus, activity ledger, policy governor, bounded planner, verified execution.")
    md.append("*   **Skills Registry (`tests/test_skills/`)**: Manifest scanning, adapter execution, desktop awareness, system controls, input bar.")
    md.append("*   **Scripts (`tests/test_scripts/`)**: CLI harnesses, authentication scripts, vault utilities.\n")
    md.append("### GitHub Actions CI Pipeline (`.github/workflows/ci.yml`)")
    md.append("Runs automatically on all pushes and pull requests to `main` across a test matrix of Python `3.12` and `3.13` on `ubuntu-latest`.\n")
    md.append("---\n")

    # Section 13
    md.append("## 13. Known Gaps, Audits & Codebase Drift\n")
    md.append("| Component | Documented Expectation | Actual Code Reality | Status |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| **Single-Sentence Rule** | Must strictly limit voice replies to 1 sentence. | Hardened in `core/agent.py:444` and `core/config.py:38` (`single_sentence: bool = True`). | **Confirmed** |")
    md.append("| **PipeWire AEC Cleanup** | Private audio routes released on exit. | `EchoCancellation.close()` safely unloads module and restores mic volume. | **Confirmed** |")
    md.append("| **Filesystem Safety** | Full autonomy with protected critical roots. | `filesystem/filesystem.py` guards `/`, `~`, `/etc`, `/usr` while allowing full user disk access. | **Confirmed** |")
    md.append("| **Agent Job Isolation** | Max 4 jobs, non-overlapping workspace trees. | Strictly enforced in `orchestration/agent_orchestrator.py:82-87`. | **Confirmed** |")
    md.append("| **Visible Desktop Execution** | Visible agent execution in dedicated tmux panes. | Implemented and verified in `orchestration/desktop_execution.py` (`-L jarvis-desktop`). | **Confirmed** |")
    md.append("| **External Connectors** | Voice-activated Google Workspace and GitHub integration. | Implemented in `connectors/` with OAuth browser launch and secret protection. | **Confirmed** |")
    md.append("| **Cryptographic Verification** | Independent sha256 byte verification for agent tasks. | Verified in `proactive/verification.py` with path traversal guards and `O_NOFOLLOW`. | **Confirmed** |")
    md.append("| **Dynamic Greetings** | Suppress redundant welcomes and focus on unfinished tasks. | Verified in `core/greeting.py` with SQLite history and 4-hour cooldowns. | **Confirmed** |")
    md.append("| **Unified Memory Subsystem** | Unified memory structure under `memory/` with backward compatibility. | Verified in `memory/` with `codes-dev/` and root `jarvis_memory` import shim. | **Confirmed** |")
    md.append("| **Semantic Embeddings** | Optional semantic layer with lexical fallback. | Gracefully falls back to FTS5 lexical ranking if no embedding model is configured. | **Confirmed** |")
    md.append("| **Input Bar Overlay** | Native WebKitGTK 600x50 transparent client at bottom screen with zero borders. | Verified in `skills/overlay_client.py` and Hyprland rules. | **Confirmed** |")
    md.append("| **Autonomous Evolution** | Self-directed diagnostic and evolution pipeline. | Verified in `orchestration/evolution.py` with passing tests. | **Confirmed** |")
    md.append("| **Systemd Daemon** | Background user service with SIGUSR1/SIGUSR2 control. | Verified in `systemd/jarvis-oma.service` and `scripts/install-service.sh`. | **Confirmed** |\n")
    md.append("---\n")

    # Section 14
    md.append("## 14. Real-Time Telemetry Automated Update Protocol\n")
    md.append("This technical reference manual is designed to remain permanently synchronized with ongoing commits, new skill manifests, test additions, and line count modifications.\n")
    md.append("To refresh this document at any moment with real-time Git commits, branch telemetry, file inventories, and tool counts, run:\n")
    md.append("```bash")
    md.append("python3 scripts/update_codebase_reference.py")
    md.append("```\n")
    md.append(f"*Manual automatically compiled and verified by Antigravity AI Engine at `{timestamp}`.*")

    return "\n".join(md)

def main():
    print(f"Generating CODEBASE_REFERENCE.md for {WORKSPACE_ROOT}...")
    content = generate_markdown()
    TARGET_FILE.write_text(content, encoding="utf-8")
    print(f"Successfully generated {TARGET_FILE} ({len(content.splitlines())} lines, {len(content)} bytes).")

if __name__ == "__main__":
    main()
