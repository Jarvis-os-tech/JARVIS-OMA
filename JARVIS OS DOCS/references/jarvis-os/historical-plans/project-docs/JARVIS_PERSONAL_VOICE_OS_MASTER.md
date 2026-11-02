# JARVIS Personal Voice-First OS — Master Specification

**Status:** Planning reference; historical findings require current verification
**Date:** 27 October 2026  
**Repository:** /home/g0pi/Projects/JARVIS-OMA  
**Authority:** This file is the active master context for building JARVIS OS: a personal voice-first Linux operating environment with its own shell, system control, and identity.

## Current product decision — functional integration before visual design

**Current scope is planning only.** The [research and redesign roadmap](JARVIS_OS_REDESIGN_ROADMAP.md) is the current implementation-order reference. Super+H remains the user's existing dictation shortcut. Earlier command examples are context, not instructions to modify the running desktop.

The user confirmed on 27 October 2026 that the product is **JARVIS OS**. Voice is the primary interface. Linux supplies the kernel and device foundations; Hyprland, PipeWire, and other working components can remain implementation dependencies. Omarchy is the migration source, not the intended product identity.

Build and verify working voice-to-system integration first. Visual redesign, HUD effects, themes, and branding follow that milestone. The ordered execution plan here takes precedence over any historical plan that puts visual design first:

1. Reliable voice controls and canonical `jarvis` commands, connected to the actual daemon.
2. Login startup, desktop shortcuts, explicit microphone ownership, and service recovery.
3. Speech-to-tool routing for applications, windows, workspaces, audio, brightness, files, and diagnostics, with observable results.
4. Persistent tasks, memory, event coordination, and bounded proactive operation; extend the existing SQLite event bus and ledger rather than assuming they are missing.
5. JARVIS shell and visual redesign using the verified state/control interfaces.
6. Packaged JARVIS OS identity, installation, updates, and rollback. Preserve distribution metadata during migration; replacing `/etc/os-release` with three lines is not a functional OS migration.

Command-line tools are the control and recovery interface supporting voice and the shell. They are not the primary user interaction. Typed/keyboard controls must remain usable when a provider or microphone is unavailable.

“Always on” means available while the machine and required services are running, with checkpoints and recovery across sleep/reboot. Desktop perception requires a valid user session. Background work across logout needs a separately designed lifecycle; enabling a graphical-session service does not establish that capability.

## 1. Purpose

JARVIS is intended to feel like a persistent personal presence living in the user's computer: voice-first, multimodal, locally aware, able to operate the desktop and connected services, able to remember personal context, and able to perform bounded work proactively while remaining observable, interruptible, secure, and recoverable.

This is not a plan for an unrestricted AI process. It is a supervised personal computer system with:

- full-duplex voice and interruption;
- screen, camera, desktop, device, and system awareness;
- a shared context and memory layer;
- safe capability adapters with permissions and verification;
- planning, task execution, and proactive background work;
- multi-agent delegation with durable job state;
- visible control, audit, pause, stop, and recovery mechanisms.

The repository and automated tests are the source of truth for implemented behavior. This master file is the source of truth for the consolidated design intent, known gaps, acceptance criteria, and implementation order.

## 2. Current reality

The project has a strong foundation but is not yet a complete autonomous personal OS. Existing code covers voice, vision, desktop control, filesystem work, memory, connectors, proactive runtime, and agent delegation. Several capabilities are still partial because they lack a shared control plane, durable state, event routing, continuous perception, or live-hardware verification.

### Capability maturity

| Capability | Current maturity | Required next step |
|---|---|---|
| Full-duplex voice | Existing foundation | Prove native acoustic quality, latency, interruption, and recovery on hardware |
| Audio/AEC/native companion | Existing but needs live proof | Verify PipeWire graph, device-clock behavior, extension composition, and failure recovery |
| Desktop and hardware control | Partial | Complete capability contracts, permissions, readback verification, service/device coverage, and rollback |
| Continuous perception | Partial | Build a timestamped shared DesktopState and bounded change observer |
| 24/7 operation | Partial | Harden one user service, watchdog, health checks, crash recovery, and durable state recovery |
| Event-driven coordination | Partial | Extend the existing SQLite EventBus and ActivityLedger across OS components, with typed event envelopes |
| Multi-agent delegation | Existing foundation | Add supervisor roles, task graphs, durable jobs, recovery, resource limits, and acceptance verification |
| Personal task management | Partial | Connect goals, deadlines, routines, calendar, reminders, and proactive policy |
| Smart home/IoT | Mostly missing | Add discovery, device registry, state model, permissions, adapters, and automation rules |
| Proactive autonomy | Partial | Add explicit autonomy levels, triggers, approval gates, quiet hours, and undo paths |
| Authentication/presence | Partial | Add local identity, continuous presence state, re-authentication, and sensitive-action gates |
| Local memory | Existing foundation | Link memories to actions, projects, goals, evidence, and durable session recovery |
| User control surface | Partial | Build activity center, approval queue, task timeline, health panel, and emergency stop |

## 3. Product principles

1. Voice-first, not voice-only. Voice is the primary interface, but text, screen, camera, notifications, and control panels must expose the same state.
2. Observe before acting. Every meaningful action starts with fresh evidence and ends with verification.
3. Permission is explicit. Risk, target, data access, and reversibility determine whether an action is automatic, confirmable, or blocked.
4. The user remains in control. Local mute, interrupt, pause, stop-all, emergency stop, and recovery must work even when the model, network, or a tool is stalled.
5. Bounded autonomy. JARVIS may act proactively only within configured scope, time, resource, and risk limits.
6. Local-first privacy. Audio, presence, credentials, memory, and device state stay local unless the user-approved capability requires an external service.
7. Evidence over claims. A process exit, model response, or adapter result is not success without verification evidence.
8. Graceful degradation. Missing providers, devices, desktop identifiers, or connectors must produce accurate degraded state rather than silently pretending capability.
9. Open-closed voice core. Locked voice files remain unchanged; new audio behavior is implemented through extension points or isolated modules.
10. Recoverability. Plans, jobs, events, memory revisions, and actions need identity and durable state so restarts do not duplicate or lose work.

## 4. Target system architecture

~~~text
User
  ├─ voice / text / screen / camera / notifications
  ↓
Interaction Gateway
  ↓
Intent + Context Manager
  ├─ Conversation State
  ├─ DesktopState Observer
  ├─ Memory Service
  ├─ Presence + Authentication
  └─ Permission + Risk Engine
  ↓
Planner + Supervisor
  ├─ Capability Registry
  ├─ GUI Controller
  ├─ System / Hardware Controller
  ├─ Filesystem + Project Tools
  ├─ External Connectors
  ├─ Smart Home / IoT Gateway
  └─ Multi-Agent Scheduler
  ↓
Execution Adapters
  ├─ Linux / Omarchy / Hyprland
  ├─ PipeWire / native audio
  ├─ Accessibility / GUI driver
  ├─ Applications / browsers
  ├─ Coding agents
  ├─ Cloud services
  └─ Local IoT protocols
  ↓
Verification + Audit + Events + Recovery
  ↓
Voice, dashboard, notifications, memory, and control socket
~~~

### One service owner

There must be one supported user service owning the microphone/AEC lifecycle, native audio child, conversation supervisor, control socket, and worker supervision. The project standard is jarvis-oma.service and its matching control path. Competing service units must not own the same microphone or socket.

### Shared control-plane objects

All major subsystems should converge on typed, serializable objects.

#### DesktopState

Timestamped focused application, windows, workspaces, visible text, accessibility metadata, screen/camera metadata, audio state, connected devices, system health, active project, user presence, JARVIS tasks, and agent jobs.

#### Intent

Original request, interpreted goal, constraints, urgency, target, ambiguity, clarification state, and originating interaction channel.

#### Plan

Goal, ordered steps, dependencies, expected outcomes, risk, required capabilities, approval gates, deadline, autonomy level, and recovery policy.

#### Action

Action identity, capability, arguments, actor, target, permission decision, preconditions, start/end time, result, verification evidence, undo information, and idempotency key.

#### Job

Durable task identity, plan identity, owner, assigned agent, workspace, state, progress, output, artifacts, timeout, cancellation state, retry count, and recovery checkpoint.

#### Evidence

Screenshots, state snapshots, command results, test results, hashes, readback data, user approval, or external response associated with a claim.

#### MemoryRecord

Fact/profile/document/session/decision type, source, trust, timestamp, scope, revision, embedding/index references, retention policy, and correction history.

## 5. Event model

Important transitions must be emitted to a durable, bounded event stream. Event envelopes need an event ID, type, timestamp, source, correlation ID, causation ID, actor, sensitivity, payload schema version, and retention class.

Required event families:

~~~text
user.requested
user.interrupted
voice.started
voice.turn_started
voice.turn_completed
voice.muted
voice.unmuted
vision.changed
desktop.changed
presence.changed
intent.created
clarification.requested
plan.created
plan.paused
plan.resumed
approval.requested
approval.granted
approval.denied
action.started
action.completed
action.failed
verification.passed
verification.failed
job.created
job.progressed
job.completed
job.failed
job.cancelled
agent.started
agent.progressed
agent.completed
device.discovered
device.changed
memory.created
memory.corrected
memory.forgotten
system.warning
system.degraded
system.recovered
jarvis.paused
jarvis.resumed
jarvis.stop_all
~~~

The event bus must not become an unbounded queue. Events require backpressure, retention, sensitive-payload filtering, subscriber isolation, and recovery behavior.

## 6. Capability contract

Every voice-callable capability must declare:

- name and description;
- input schema and normalized aliases;
- domain and ownership;
- required permissions;
- risk level;
- read-only/state-changing classification;
- preconditions and freshness requirements;
- execution adapter;
- verification method;
- failure and retry behavior;
- undo or rollback behavior;
- idempotency and duplicate-execution rules;
- audit and evidence fields;
- offline/degraded behavior.

### GUI action contract

~~~text
fresh observation
  → target selection
  → permission/risk decision
  → action
  → new observation
  → semantic verification
  → evidence + audit event
~~~

Coordinate actions must be tied to a fresh frame. Accessibility, native APIs, or CLI adapters take precedence over coordinate automation. Modal authentication prompts must never be autonomously approved.

## 7. Voice and audio architecture

The audio path is a real-time subsystem, not ordinary application code:

~~~text
Microphone
  → PipeWire/WebRTC AEC cleaned source
  → native capture owner
  → bounded 16 kHz frames
  → optional extension processors
  → conversation sender
  → Gemini Live
  → generation-tagged 24 kHz response frames
  → bounded playback queue
  → native device-clock renderer
  → AEC reference sink / speakers
~~~

Requirements:

- native device deadlines remain independent of model, network, tool, and memory work;
- input framing remains bounded and age-limited;
- playback is paced by the device clock;
- response generations fence stale chunks after interruption or reconnect;
- mute stops transmission and clears or fences playback according to policy;
- local interrupt works during network/tool stalls;
- extension processors are optional, bounded, observable, and actually wired into the live path;
- no allocation, blocking I/O, or unbounded queue growth in audio callbacks.

### Locked voice files

These files are immutable project boundaries:

~~~text
audio/engine.py
audio/downstream.py
audio/echo_cancel.py
audio/__init__.py
echo_cancel.py
tests/test_audio/test_engine.py
tests/test_audio/test_echo_cancel.py
~~~

Do not modify, rename, delete, monkeypatch, or override their core functions. Implement new audio behavior through audio/extension.py, audio/plugins/, or unlocked orchestration.

### Required audio proof

Measure p50/p95 response latency, interruption latency, audio starvation, callback health, queue age, graph errors, and reconnect behavior under short turns, long turns, double-talk, device changes, and tool/vision load. Browser parity is not assumed until measured.

## 8. Continuous perception and presence

JARVIS must evolve from isolated tools into a bounded context observer. It should combine:

- focused window and application;
- open windows and workspaces;
- screen regions and OCR;
- accessibility tree when available;
- clipboard and application state where permitted;
- audio input/output and mute state;
- CPU, memory, disk, battery, temperature, process, and service state;
- connected cameras, monitors, audio nodes, Bluetooth/Wi-Fi devices, and IoT devices;
- active project/repository and current JARVIS jobs;
- calendar, reminders, todos, and user presence/idle state.

Observation must be consented, rate-limited, redacted by sensitivity, timestamped, and stored as changes or summaries rather than unlimited raw surveillance. The user needs a visible indication of listening, vision, recording, external transmission, and proactive activity.

Presence is a state machine, not a guess:

~~~text
unknown → present → active → idle → away → locked
                 ↘ privacy_pause
~~~

Sensitive actions require an appropriate presence/authentication state and may require fresh re-authentication.

## 9. 24/7 lifecycle and recovery

The always-on runtime must provide:

- boot/login startup policy;
- one service owner and one control socket;
- watchdog and heartbeat;
- dependency readiness checks;
- bounded restart with backoff;
- native audio child supervision;
- provider reconnect and session resumption;
- durable plans/jobs/events before accepting background work;
- stale-job detection and safe recovery;
- health, degraded, paused, and stopped states;
- resource budgets for CPU, memory, network, disk, and agent workers;
- clear shutdown and stop-all semantics;
- observable diagnostics without leaking credentials.

A restart must not duplicate an executed action, replay expired microphone audio, lose a user-approved plan, or silently resume an action that requires new approval.

## 10. Planning, task delegation, and proactive autonomy

The planner converts requests and allowed triggers into plans. The supervisor owns execution and recovery. Agents are workers with bounded authority, not authorities themselves.

### Agent contract

Every delegated agent receives:

- a specific objective;
- workspace/branch rules;
- allowed tools and data scope;
- time and resource limits;
- acceptance criteria;
- reporting format;
- stop conditions;
- cancellation and escalation rules.

The supervisor must support roles such as planner, researcher, programmer, tester, debugger, security reviewer, documentation writer, GUI operator, system administrator, memory curator, and IoT operator.

### Proactive policy

Autonomy levels should be explicit:

~~~text
L0 observe only
L1 suggest and notify
L2 prepare drafts/plans
L3 execute reversible low-risk actions
L4 execute approved workflows within policy
L5 never automatic: destructive, financial, credential, privacy, or irreversible actions
~~~

Each trigger needs a cause, freshness window, cooldown, quiet-hours policy, confidence threshold, user preference, required approval, and undo path. Proactive must never mean secretly acts without an audit trail.

## 11. Smart home and IoT layer

This is a major missing subsystem. Build it only after local control-plane safety is established.

Required pieces:

- local device discovery and explicit pairing;
- device registry with stable IDs, manufacturer/model, capabilities, room, owner, protocol, and trust;
- normalized device state and timestamped observations;
- adapters for selected local protocols first;
- command permissions and risk tiers;
- readback verification and eventual-consistency handling;
- scenes, routines, schedules, and presence conditions;
- offline/degraded state;
- secrets isolation and credential rotation;
- user-visible device activity and emergency stop.

The first milestone should be read-only discovery and status. State-changing device controls come only after verification, authorization, and rollback semantics exist.

## 12. Memory and personalization

The memory system should combine explicit user facts, profiles, sessions, documents, project context, decisions, goals, routines, and action history. Every record needs provenance, trust, revision, correction, retention, and deletion behavior.

Memory should support:

- remember, recall, correct, forget, and clear;
- SOUL, MEMORY, and USER profiles;
- lexical and semantic retrieval;
- project and repository context;
- linked plans, actions, jobs, and evidence;
- long-term goals, routines, and preferences;
- user-visible review and correction;
- injection filtering and untrusted-source boundaries;
- local SQLite/semantic persistence and optional Obsidian synchronization;
- session summaries without claiming uncertain facts.

Memory must not become an unreviewable surveillance archive. Provide retention controls, source labels, export, deletion, correction history, and a way to disable capture.

## 13. Security and privacy model

Security boundaries:

- credentials stay out of subprocess environments unless explicitly required;
- secret values never enter prompts, logs, memory, reports, or event payloads;
- external connector scopes are minimal and revocable;
- authentication prompts cannot be autonomously approved;
- destructive, financial, credential, privacy-sensitive, and irreversible operations require confirmation or are blocked;
- all actions expose actor, target, capability, permission, evidence, and result;
- untrusted web, file, agent, and connector content is data, not instruction authority;
- local control remains available when cloud services fail;
- the user can pause recording, vision, memory capture, proactive work, or all JARVIS activity.

Continuous authentication should combine local session state, lock state, presence signals, explicit user confirmation, and re-authentication expiry. Biometrics or device identity must not be assumed without a concrete local implementation and threat model.

## 14. User control surface

The eventual JARVIS shell should expose:

- current voice/listening/mute/reconnect state;
- vision and camera status;
- current intent and plan;
- active actions and verification evidence;
- agent jobs and progress;
- approvals waiting for the user;
- memory capture and recent records;
- connected devices and IoT state;
- system health and degraded dependencies;
- pause/resume/stop-all/emergency-stop controls;
- task timeline and audit history;
- saved modes: coding, research, meeting, media, focus, privacy.

Voice responses and the visual shell must consume the same events and state rather than maintaining parallel truth.

## 15. Implementation order

### Phase 0 — Baseline and boundaries

- Keep this master current.
- Inventory manifests, adapters, connectors, daemons, tests, and service units.
- Verify voice lock.
- Establish focused and full-suite baselines.
- Define status vocabulary: existing, partial, planned, blocked, verified.

### Phase 1 — Unified control plane

- Add typed Intent, Plan, Action, Job, Evidence, DesktopState, and MemoryRecord models.
- Add capability registry with domain, permission, risk, preconditions, verification, and undo.
- Add correlation IDs and idempotency keys.
- Route current skills through action records.
- Persist audit events and expose them to voice and UI.

### Phase 2 — Runtime and audio reliability

- Standardize one systemd service owner.
- Add health/readiness/watchdog/restart behavior.
- Complete native audio hardware proof.
- Add the supported extension composition boundary.
- Measure latency, interruption, queue age, graph health, and reconnect behavior.

### Phase 3 — Desktop state and GUI safety

- Build shared DesktopState snapshots and change events.
- Add accessibility-tree discovery.
- Add stale-observation protection and semantic verification.
- Add safe retries, reversible workflows, and emergency input stop.

### Phase 4 — Durable agents and tasks

- Add supervisor roles and task graphs.
- Persist job state and checkpoints.
- Add workspace/resource/permission limits.
- Add acceptance criteria, independent verification, retry, reassign, and restart recovery.

### Phase 5 — Personal memory and routines

- Link memory to plans, actions, jobs, projects, and evidence.
- Add goals, habits, routines, and explicit preference learning.
- Add review, correction, retention, export, and deletion UI.

### Phase 6 — Proactive operating shell

- Build activity center, task timeline, approval queue, health panel, and saved modes.
- Add autonomy levels, triggers, cooldowns, quiet hours, and meaningful-change notifications.

### Phase 7 — IoT and wider autonomy

- Implement read-only device discovery first.
- Add verified state-changing device adapters.
- Add scenes and routines with approval and rollback.
- Add cross-device and remote-agent support only after local safety and recovery are mature.

## 16. Definition of done for real personal voice-first OS

JARVIS is ready for that claim only when all of the following are evidenced on the target machine:

1. A single service starts, remains healthy, and recovers from provider, desktop, audio, and tool failures.
2. The user can speak naturally, interrupt immediately, and continue after reconnection without stale or duplicated audio/actions.
3. JARVIS maintains a fresh, privacy-controlled shared desktop/context state.
4. Every meaningful action has permission, identity, verification, evidence, and recovery behavior.
5. Plans and jobs survive restart without duplicate execution.
6. Proactive work is policy-bound, visible, interruptible, and quiet when nothing meaningful changes.
7. Multi-agent work has durable coordination, resource limits, acceptance criteria, and independent verification.
8. Local memory is useful, provenance-aware, correctable, exportable, and deletable.
9. Hardware and IoT controls are discovered, authorized, verified, and recoverable.
10. Continuous authentication/presence protects sensitive actions.
11. Voice, text, dashboard, notifications, and control tools reflect the same event/state history.
12. Focused tests pass, live hardware checks are recorded, voice-lock integrity passes, and known limitations are documented honestly.

## 17. Immediate engineering backlog

### P0 — foundation blockers

- Define and implement shared control-plane models.
- Define the shared event envelope and extend the existing durable event store in proactive/events.py and proactive/ledger.py.
- Establish one service owner and health state machine.
- Add durable action/job identities and idempotency.
- Complete native audio live-path composition and measurement.
- Preserve locked voice files and verify them in CI.

### P1 — reliability and safety

- Shared DesktopState observer.
- Capability permission/risk/verification contracts.
- Accessibility discovery and stale-frame protection.
- Agent supervisor with durable restart recovery.
- Proactive autonomy levels and approval queue.
- Presence/authentication state machine.

### P2 — personal intelligence

- Goals, routines, preference learning, and project continuity.
- Activity center and task timeline.
- Memory-action-plan linking.
- Read-only IoT discovery and device registry.

### P3 — expansion

- Verified IoT state-changing adapters.
- Cross-device support.
- Remote agents.
- Broader application and browser automation.

## 18. Verification gates

Before claiming a capability:

~~~text
1. Static source inspection
2. Unit tests
3. Focused integration tests
4. Failure/recovery tests
5. Permission and secret-boundary tests
6. Live hardware or service evidence where applicable
7. Voice-lock verification
8. Full-suite comparison against a clean baseline
9. User-visible limitation and rollback note
~~~

Required project checks include:

~~~sh
.venv/bin/pytest -q
python3 scripts/verify_voice_lock.py
bash -n run.sh
~~~

The earlier startup recovery report recorded focused tests and voice-lock integrity passing, with wider-suite failures and the daemon left stopped. Section 21 records the subsequent experiment and its rollback. No new full-suite clean-pass claim is made.

## 19. Consolidated source and historical record

This master was synthesized from the project material listed below. The original design/audit files are retained in the project archive at project-docs/archive/ after consolidation.

### Voice, audio, and runtime

- docs/realtime-voice-audit-2026-10-15.md
- docs/realtime-voice-deep-audit-2026-10-15.md
- docs/browser-parity-audio-research-2026-10-21.md
- report/01_audio_core_audit.md
- report/02_core_runtime_audit.md
- report/04_daemon_ipc_audit.md
- report/07_standby_privacy_audit.md
- report/11_SUPPLEMENTAL_VERIFIED_FINDINGS.md
- report/13_CONSOLIDATED_ANALYSIS_AND_SOLUTIONS.md
- report/26_CHROME_VOICE_TO_NATIVE_JARVIS_GUIDE_2026-10-24.md

### OS, desktop, and hardware

- docs/architecture.md
- docs/desktop-execution.md
- docs/system-control-and-information.md
- docs/GUI_CONTROL.md
- docs/artemis-desktop-mobile-architecture.md
- docs/jarvis-munder-integration-blueprint.md
- docs/jarvis-munder-function-inventory.md
- report/03_desktop_skills_audit.md
- report/06_vision_hud_audit.md
- report/12_audit_reproductions.py

### Autonomy, agents, and tasks

- docs/autonomous-orchestration.md
- docs/proactive-runtime.md
- docs/capability-development.md
- docs/model-routing.md
- report/08_orchestration_evolution_audit.md
- report/09_filesystem_autonomy_audit.md
- report/10_connectors_harness_audit.md

### Memory and personalization

- docs/universal-memory.md
- docs/memory-upgrade.md
- docs/semantic-memory-board.md
- report/05_memory_matrix_audit.md

### Implementation fixes and integration findings

- report/00_MASTER_IMPROVEMENT_REPORT.md
- report/14_FIX_01_UNICODE_READ.md
- report/14_FIX_01_POLICY.json
- report/15_FIX_02_EMPTY_FILE_TASKS.md
- report/16_FIX_03_MALFORMED_SEARCH_URLS.md
- report/17_FIX_04_DEFAULT_DEVELOPMENT_AGENT.md
- report/18_FIX_05_MONITOR_JOB_IDENTITIES.md
- report/19_FIX_06_POLICY_FINITE_TIMESTAMPS.md
- report/20_FIX_07_EXPLICIT_SUBPROCESS_ENVIRONMENT.md
- report/21_FIX_08_EXTENSION_PLAYBACK.md
- report/22_FIX_09_ADJUSTMENT_TEST_PARITY.md
- report/23_FIX_10_CALENDAR_TIMEZONE.md
- report/24_CALENDAR_IST_AND_MANAGEMENT.md
- docs/startup-capability-recovery-2026-10-27.md

### Master blueprint set

- docs/jarvis-os/vision-and-principles.md
- docs/jarvis-os/master-blueprint.md
- docs/jarvis-os/target-architecture.md
- docs/jarvis-os/capability-map.md
- docs/jarvis-os/roadmap.md
- docs/jarvis-os/decision-log.md
- docs/jarvis-os/foundation-repair-2026-10-19.md
- docs/jarvis-os/verification-matrix-2026-10-18.md
- docs/jarvis-os/README.md

## 20. Record of consolidation

- The requested PDF output/pdf/voice-os-redesign-report-2026-10-24.pdf was not present in the checkout.
- The Markdown design and audit sources listed above were present and were used as the authoritative available context.
- The archive retains earlier documents and supporting report artifacts, including the audit reproduction script and policy JSON. Runtime source code and service units remain in their project locations.
- The archive preserves historical context. This master supplies requirements; the linked redesign roadmap supplies current research, priorities, dependencies, and acceptance gates.
- The master must be updated whenever a roadmap item changes status or a new verification result is obtained.

## 21. Planning correction and rollback — 27 October 2026

The user clarified that the supplied integration examples were context for planning, not authorization to build. Super+H is reserved for the user's existing dictation workflow.

The preceding implementation experiment was rolled back: the original desktop bindings and autostart file were restored byte-for-byte against the saved backups, JARVIS returned to inactive/disabled, and the IPC/CLI/test changes introduced in that experiment were removed. Earlier unrelated working-tree edits were preserved. The 142-test result and temporary live activation belong to that reverted experiment and must not be reported as the current release state.

The current work product is the [research and redesign roadmap](JARVIS_OS_REDESIGN_ROADMAP.md). It preserves the functional-first order, defines the future Dynamic Island shell, and records the observed implementation defects as planned work packages. No shortcut, service, OS identity, or shell migration is to be performed from the roadmap alone.

