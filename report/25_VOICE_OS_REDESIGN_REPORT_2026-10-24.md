# Redesigning Omarchy + JARVIS-OMA into a Voice OS

**Assessment date:** 24 October 2026, India Standard Time  
**Scope:** This installed Omarchy desktop and the JARVIS-OMA working tree  
**Repository snapshot:** `bb75151`, branch `Harness²`, including existing uncommitted work  
**Deliverable:** Architecture assessment and implementation proposal. The proposed redesign has not been installed.

## 1. Recommended direction

Build a dependable voice operating layer on the existing Linux desktop. Keep Omarchy, Hyprland, PipeWire, systemd and ordinary applications. Make JARVIS the shared entry point for commands, dictation, tasks, context and recovery.

The repository already contains much of the necessary foundation: full-duplex cloud voice, local wake-word standby, desktop and browser adapters, memory, supervised agents, proactive controls, an IPC service and a small visual overlay. The next investment should connect these pieces through one permission, execution, verification and task-state model.

The desired experience is: say a goal; see what was understood and which application or file is targeted; let authorized work proceed; receive a result backed by observable evidence; correct, cancel or undo it easily. Voice should be the primary interaction method, with equally usable text, keyboard and pointer access.

**The three most consequential decisions are:**

1. Establish one action broker and durable task journal before expanding autonomy.
2. Add a small local voice command path so essential controls survive network and provider failures.
3. Turn the current status orb and separate input bar into an accessible invocation panel, activity drawer and privacy surface.

Preserve the seven locked voice files byte-for-byte. Add new behavior through unlocked orchestration, supported composition and isolated extensions. This direction also agrees with the existing JARVIS OS decision log; it advances that plan using current implementation evidence. [E1, E2]

## 2. What was examined and what the evidence means

The assessment covers the voice/session runtime, audio extension boundaries, desktop integration, QML overlay, input bar, tool manifests, system and GUI adapters, browser control, filesystem, task execution, agent orchestration, proactive policy, memory, learning, service units, tests and existing design documents. Three focused parallel reviews examined voice, desktop interaction and capability safety.

Host checks read OS/package/hardware metadata and service status. No microphone recording, real GUI input, account reconnection, cloud inference, message sending or system reconfiguration was performed for this report. Existing source changes were present before the assessment and were preserved.

This is an architectural review with selected deep code tracing, not a line-by-line review of every vendored dependency or a penetration test. These evidence levels are deliberately separate:

| Evidence level | What it establishes |
| --- | --- |
| Source present | A code path or declared capability exists. |
| Offline automated test | Behavior under the fixtures and mocks actually exercised. |
| Installed/configured | A package, executable, service definition or plugin configuration is present. |
| Running | A process or service reports active at the time of inspection. |
| Live task verified | A real user-visible outcome has fresh postcondition evidence. |

An installed tool is not necessarily authenticated; an active service does not prove good audio; passing mocked tests does not prove correct desktop behavior. Earlier reports are historical evidence. In particular, the 18 October collection problems were addressed in later foundation work and should not be repeated as current facts. [E2]

## 3. The present machine

| Component | Observed snapshot | Implication for redesign |
| --- | --- | --- |
| OS | Omarchy 4.0.6; command reports package version 4.0.6-1 | Extend the installed distribution and preserve its update path. |
| Kernel | Linux 7.2.8-9-omarchy, x86_64 | No kernel replacement is necessary for the proposed interaction layer. |
| Desktop | Hyprland 0.56.2; Quickshell package 0.3.2.r7.g2b4501a-1 | Use compositor IPC and the existing QML shell integration. |
| Audio | PipeWire 1.6.9; WirePlumber 0.5.18 | Retain existing routing/device management. |
| Accessibility/portals | AT-SPI2 2.62.1; desktop portal 1.22.1; Hyprland backend 1.4.1 | Useful building blocks; supported interfaces and application exposure still need probing. |
| Processor | Intel Core i5-1235U, 10 cores / 12 logical CPUs | Benchmark CPU speech inference under actual desktop load. |
| Graphics | Intel Iris Xe integrated graphics in PCI inventory | Do not assume CUDA or a dedicated AI accelerator. |
| Memory | 7.4 GiB total; about 1.4 GiB available; 3.6 GiB swap used | Keep local models small and limit concurrent heavy workers. |
| Workspace filesystem | 256 GiB total; 26 GiB available; 90% used | Add bounded caches/logs and storage checks before model downloads. |
| Voice service | `jarvis-oma.service` active/running; zero recorded restarts in its current activation | Runtime is deployed. This does not certify wake, sound or tool quality. |
| Audio services | PipeWire and WirePlumber active/running | Audio services are available at inspection time. |
| Alternate unit | `jarvis.service` inactive with no loaded fragment | Consolidate naming; do not enable a second audio owner. |

The absent `omarchy-shell.service` unit does not establish that the shell is stopped; it may be launched through another session mechanism. The orb is enabled in shell configuration, and its installed QML matches the repository copy, but its live rendering was not tested.

Useful executables already found include `hyprctl`, `quickshell`, `pactl`, `wpctl`, `bwrap`, `grim`, `wl-copy`, `wl-paste`, `tesseract`, `wtype`, `nmcli`, `bluetoothctl` and `cua-driver`. Driver presence does not establish live control. `ollama`, `whisper-cli`, `piper` and `sherpa-onnx` were not on this inspection's PATH; that is not an exhaustive package or Python-module absence claim.

**Hardware conclusion:** Start with local activation plus compact speech/command handling and optional cloud reasoning. A large always-loaded local language model is a poor initial fit for this memory snapshot. Evaluate a memory upgrade only after checking this laptop's upgradeability and measuring the prototype; a purchase is not a prerequisite for the first implementation.

## 4. Existing capabilities: retain, connect and strengthen

The working-tree inventory contains **24 JSON manifests with 192 unique declared tools** and **92 application test modules**. Counts include the existing untracked learning manifests. These counts describe declarations and files, not 192 freshly verified live features.

| Domain | Implemented foundation | Main missing part |
| --- | --- | --- |
| Conversation | Gemini Live audio, transcripts, reconnect, resumption, model fallback | Complete local command lane; predictable degraded behavior. |
| Audio | AEC, bounded queues, generation fencing, native/legacy backends | Prove extension integration and interruption parity across selected backends. |
| Activation | On-device Hey Jarvis listener during standby | Explicit startup mode, microphone ownership and wake-plus-command continuity. |
| Desktop | Launch apps, windows/workspaces, system controls, OCR/screen observation | Consistent exact targets, result readback and ambiguity resolution. |
| GUI/browser | Accessibility targets, observation freshness, bound browser sessions | Per-application acceptance matrix and reliable workflow recovery. |
| Interface | IPC-driven orb, separate text/attachment input bar, vision PiP integration | Shared conversation, task, decision and evidence views. |
| Files | Read/write/search/move/copy/trash/delete and bounded multi-step jobs | Folder grants, transactional bulk work and stronger outcome checks. |
| Agents | Discovery, bounded supervision, owned cancellation, visible terminals | Durable jobs, common authority/resource limits and independent acceptance. |
| Proactive work | Policy, ledger, persisted pause/stop, independent file verification | Apply these controls consistently to ordinary tool calls as well. |
| Memory | Facts, profiles, sessions, correction, lexical/optional semantic recall, scoped MCP | Clear retention/deletion across all stores and context disclosure controls. |
| Connectors | Google Workspace, GitHub, search, phone and other adapters | Fresh authentication/readiness and operation-specific verification. |
| Learning | Opt-in evidence, offline harness checks, reviewed proposals | Controlled evaluation against baseline; no assumption of automatic improvement. |

The current capability catalog correctly returns `runtime_verified=False`. Reuse that honesty in the product. Some older planning tables still mark semantic GUI discovery or service control as future work even though adapters exist; refresh status from source and tests before assigning implementation tasks. [E3-E11]

## 5. Priority findings

### P0: A common authorization boundary is missing

Ordinary `Skills.execute` checks the tool name and argument schema, then calls the adapter. The proactive policy can distinguish read-only, reversible, external, destructive and unknown effects, but it is not a shared gate at this ordinary dispatch boundary. Strict schemas help correctness; they do not decide whether a specific file, account or external effect is authorized. [E3, E8]

Introduce a broker at this choke point, then route voice, typed input, workflows and agent requests through it. Keep existing user preferences, including previously authorized autonomy, as explicit scoped policy. Do not force repeated approval for work already authorized. Ask only for a missing grant or a materially different effect, with concrete targets and consequences.

### P0: Filesystem grants are broader than an everyday voice interface should assume

Filesystem operations accept expanded absolute paths. Critical-root deletion guards are useful, but protecting exact roots does not provide project/folder scoping. Writes are not constrained to a granted workspace, and some overwrite paths remove a destination before the replacement completes. The built-in defaults enable filesystem autonomy and permanent deletion. These are source-level design concerns, not demonstrated attacks. [E6]

Add folder-scoped grants, separate read/write/delete authority, credential exclusions and safe path resolution. Default cleanup workflows to Trash and a recoverable manifest. Stage large moves/copies and verify content before disposing of originals. Existing explicit permission can still authorize broader work; represent that permission rather than infer it from model text.

### P0: Success needs observable proof

`manage_window` and `switch_workspace` can ignore the fallback dispatch result and return success. Several file-task checks establish existence rather than exact contents or copy completeness. Better readback patterns already exist in other system adapters and in proactive verification. [E5, E6, E8]

Make `executed` different from `verified`. Verify workspace identity, focused window ID, audio device/volume, file hashes or application/API versions as appropriate. If readback is unavailable, report an unverified request rather than an accomplished task.

### P1: Local wake detection is not offline voice operation

Normal conversation opens a Gemini Live connection; fallback models remain in the same provider family. Standby performs local wake detection and closes the voice session. General offline transcription, command execution and spoken responses are not an integrated alternative path. [E4]

Implement a narrow local lane first. Keep emergency controls and essential desktop actions usable during network loss. Local/cloud route changes must not replay a stale command.

### P1: Audio extension support needs explicit integration

The extension registry and composition wrapper exist, but the main runtime reads the engine capture queue directly and the locked downstream router calls the base output method. Merely registering a processor does not place it in that stream. Native companion playback also differs from the wrapper's expected method. Generic processor exceptions continue with the previous frame, so this is unsuitable as the authoritative privacy boundary. [E4]

Build explicit adapters in unlocked modules using supported public interfaces; retain generation fencing. Gate transmission and persistence at their actual boundaries and fail closed on a permission error. Do not patch or replace locked core methods.

### P1: Task state and cancellation are fragmented

Ordinary filesystem and agent job dictionaries are process-local, while proactive controls/ledger already have durable state. Interrupting speech does not establish cancellation of a submitted file operation or external action. [E6-E8]

Adopt one journal and distinguish stop speaking, cancel this task, stop all automation, standby and microphone off. After a restart, classify uncertain effects as interrupted or unknown and reconcile them before retrying.

### P1: Privacy is a set of independent controls

Session recording and structured capture are enabled by built-in defaults. The bridge saves user and assistant transcript text; structured scanning later in that flow does not prove raw transcript redaction. Tool arguments can also enter logs. Standby closes the voice session but does not stop every background application from networking. [E4, E9]

Expose independent microphone capture, cloud audio, screen/camera sharing, transcript storage, fact learning and background-network states. Current software mute keeps capture streams open and substitutes silence; releasing capture is a proposed supervisor lifecycle, not the current mute toggle. Fact forgetting must not be presented as deletion of transcripts, exports, indexes and backups.

### P1: The shell needs a shared interaction model

The orb is a compact indicator with tiny labels and a hidden double-tap mute action. It refuses keyboard focus and exposes no conversation, task evidence or decision queue. Its animation is procedural; the defined level and reduced-motion properties are not connected by the overlay. Hard-coded development paths reduce portability. [E10]

Retain the orb as optional status, with a labeled level meter only when backed by actual RMS. RMS in a status snapshot is not periodic telemetry; the meter needs a bounded update cadence. Put real interaction in an accessible panel tied to shared state.

### P2: Installation and authority need separation

Service units launch a mutable developer checkout. They restart on failure but do not establish worker compartments. Multiple voice-related bindings are configured on the host; they do not prove multiple active listeners, but they create an ownership question. Some legacy chat/task/window-label UI prototypes target a different project and are disabled. [E7, E10, E11]

Package versioned releases with rollback; keep the development tree separate. Use one attention/microphone coordinator. Port useful legacy UI patterns after connecting them to JARVIS events, rather than enabling an obsolete backend.

## 6. Target architecture

```text
Voice / typed command / keyboard / accessible UI
                         |
            Interaction and attention supervisor
      [mode, transcript, target, clarification, privacy]
                         |
             Intent + bounded task plan
                         |
          Policy and action broker <--- trusted user grants
                         |
             Durable task/action journal
                         |
       Existing typed adapters and restricted workers
    desktop | browser | files | connectors | coding agents
                         |
       Fresh observation + capability-specific verifier
                         |
       Result/evidence -> shell, voice, history, memory

Underlying platform: Omarchy + Hyprland + PipeWire + systemd
Audio foundation: existing locked core, composed through unlocked adapters
```

Begin with modules in the existing application and a bounded worker pool. Avoid creating many resident services on an approximately 8 GB machine before boundaries are stable. Later separate the audio/session process, network/model process and restricted workers where this improves fault and permission isolation.

Reuse the current manifest loader, proactive ledger/control, memory scopes and evolution proposal pipeline. Introduce versioned shared contracts rather than a second framework with independent task truth.

| Shared object | Required contents |
| --- | --- |
| Intent | Original request, source/turn ID, goal, language, mode, constraints and exact target candidates. |
| Desktop snapshot | Window/application IDs, workspace, accessibility/frame IDs, observation time and privacy filters. |
| Capability | Schema/version, dependencies, effect class, resource scope, cancellation, verification and undo behavior. |
| Action | Task/step ID, principal, arguments, trusted policy decision, deadline, idempotency key and status. |
| Task | Plan/dependencies, checkpoints, active steps, artifact links, evidence, recovery state and resource budget. |
| Event | Version, sequence number, timestamp, task/action ID, event type and redacted payload. |
| Grant | User origin, allowed effect/resources, duration, revocation state and policy revision. |

Use snapshot-plus-subscription for the UI: a newly opened panel reads current state and then follows ordered events. Support reconnect/replay and slow subscribers. Do not let a panel reconstruct permission or task state by guessing from logs. A mode-0600 socket protects access from other users; it does not isolate mutually untrusted processes running as the same user.

The proposed task lifecycle is:

```text
received -> interpreted -> planned -> authorized -> queued -> running
                                                       -> verifying
                                                       -> succeeded
                                                       -> failed
                                                       -> cancelled
                                                       -> interrupted / unknown
```

`awaiting_authorization` is a branch used only when authority is missing. An existing valid grant proceeds directly. Admission stops immediately when global stop is set; owned cancellable workers terminate; an irreversible in-flight effect is reported with its actual outcome or uncertainty.

## 7. Redesign the everyday experience

### Five connected surfaces

1. **Status strip/orb:** explicit local/cloud mode, microphone state, sharing state and pending attention. Provide a clear single-click control and keyboard equivalent. Use readable text, high contrast and reduced motion.
2. **Invocation panel:** recognized words, editable transcript, mode selector, target chips, attachments, command examples and concise results. Restore application focus on dismissal.
3. **Activity drawer:** running/queued tasks, progress, waiting decisions, cancel/pause, artifacts, verified outcomes and recovery choices.
4. **Temporary target labels:** numbered windows or controls when ambiguous, bound to current exact IDs. Expire on focus/layout changes and refresh observations before action.
5. **Privacy and health panel:** current microphone owner, capture/cloud/storage settings, selected devices, provider health, local fallback and diagnostic status.

Do not make a voice OS dependent on voice-only interaction. Passwords, code editing, quiet environments and microphone failure require usable keyboard/text routes. Ensure screen-reader names, tab order, scalable text and visible focus on the interactive surfaces.

### Clear interaction modes

| Mode | User-visible promise |
| --- | --- |
| Microphone off | JARVIS releases capture; wake listening is also off. Other applications have separate microphone permissions. |
| Local wake | On-device activation listener; no voice-session audio upload. |
| Hold-to-talk | Capture/transmit only under the selected policy while the control is held. |
| Command | Interpret authorized operating actions with exact targets. |
| Dictation | Produce editable text for a bound field/document; dictated prose is not executed as commands. |
| Conversation | Interactive dialogue with clearly shown local/cloud route and storage policy. |
| Private session | Explicit capture, transmission and retention settings; the UI names what remains enabled. |
| Reconnecting/fault | Explain unavailable functions and preserve task truth and draft text. |

All modes above describe the proposed contract. Hold-to-talk needs dedicated transport/session integration: current configuration rejects disabling provider VAD because manual activity signals are not implemented. Keep capture, transport, memory and task state as separate fields; do not encode all of them in one color or one lifecycle string. Lock-screen and suspend events should revoke foreground context and suspend capture according to explicit local policy. Voice should not bypass the existing login/unlock security boundary; a wake word or recognized voice is not authentication.

### Representative workflows

**“Open my project and continue the work.”** Resolve the project, load its approved context, restore the chosen application/workspace, show the proposed task and attach any agent to an isolated workspace. Report results from tests/artifacts, not the agent's exit code alone.

**“Put this into the other browser.”** Show Browser 1/2 labels, select a stable window/tab/element ID, preview dictation, insert only into the bound target and verify the result. If the target changed, reacquire it instead of reusing coordinates.

**“Organize my Downloads.”** Show a concrete preview with affected counts and destinations, apply the existing folder grant, move through recoverable stages, verify counts/hashes as needed and expose an undo manifest. Do not permanently delete an inferred category of files.

**“Prepare a meeting.”** Preview apps, documents, output/input devices and notification changes. Apply and verify each change; record reversible deltas. “Restore my workspace” reverts only the changes owned by that routine, preserving later user edits. This cross-application restore is proposed.

**“Stop.”** Immediately stop speech. If a task is active, show/announce whether it was cancelled, is already complete, or contains an irreversible effect in progress. Keep distinct explicit controls for stop all automation, microphone off and stop sharing.

**Network disappears.** Switch to available local essentials, retain drafts and show the last verified state. Do not silently retry a send or apply a stale buffered instruction when the network returns.

## 8. Voice and audio plan

Retain cloud speech-to-speech for rich conversation where permitted. Add a local route:

```text
Local activation -> local STT / constrained recognizer -> intent grammar
                -> action broker -> verified desktop action -> local TTS/earcon
```

First target volume, brightness, workspace changes, app launch, status and emergency controls. A local keyword/grammar recognizer may cover this lane without a local language model. “Offline OS” should initially mean this published set of essential tasks, not unlimited offline conversation.

For a prototype, benchmark **sherpa-onnx** for CPU local recognition and speech components, with **whisper.cpp** as an alternative transcription benchmark. These are candidates, not installed or selected implementations. Match each model to the language, hardware, latency and license requirements. The projects document local speech capabilities and CPU-oriented execution; neither establishes performance on this machine. [W1, W2]

Keep inference out of audio callbacks and off the voice networking event loop. Limit buffers and worker concurrency. Prove input/output format conversion, chunking and cancellation generations with the actual selected native or legacy backend. The native companion currently disables its own acoustic local barge-in path, so interruption equivalence requires measurement. [E4]

For “Hey Jarvis, open Calendar” in one breath, define a bounded local pre-roll and a wake boundary. Buffering must remain transient while local-only, expire quickly, and be released only under the active transport policy. Current queue draining and wake acknowledgement ordering do not prove that the full post-wake command survives connection setup.

Keep provider model IDs configurable and display the actually connected route after fallback. Existing session resumption/compression should be exercised during planned disconnects and long sessions. Provider documentation describes connection/session management, but local tests must establish how JARVIS preserves task identity and prevents duplicate effects. No paid model probe was run for this assessment. [W3]

## 9. Desktop and application control

Prefer the most semantic available interface for each operation:

1. Application/API or structured local command with scoped arguments.
2. Browser automation bound to an exact tab, or accessibility action bound to an exact node.
3. Compositor IPC for windows/workspaces.
4. Fresh screenshot/OCR and constrained coordinate input when the stronger interfaces are unavailable.

This is a capability-specific preference, not a guarantee that every application exposes accessibility. Existing GUI freshness and browser-binding safeguards should be reused rather than rebuilt. Detect missing interfaces and present a useful limitation instead of clicking blindly. [E5]

Hyprland documents separate request and event sockets, which suit a desktop state observer. AT-SPI supplies semantic accessibility objects where applications expose them. XDG portals define screen-capture and remote-input sessions, but a portal specification is not proof that the installed Hyprland backend supports every interface. Probe actual backend/version capabilities before choosing an input method. [W4-W7]

A desktop snapshot must include identity and timestamp, not just visible words. Invalidate a selection when the window closes, focus changes unexpectedly, display scale changes or the accessibility/frame snapshot expires. Readback should establish the intended content/setting, not just that an input event was delivered.

Future shell deployment belongs in user plugins/configuration with a backup and rollback. Keep packaged `/usr/share/omarchy/` unchanged during customization. Replace developer-specific absolute paths with installed entry points. Choose one microphone/attention coordinator for JARVIS, dictation and other assistants; installed hotkeys alone do not establish which currently owns audio.

## 10. Permissions, agents and recovery

Extend existing proactive effect classes into the capability catalog. Store authority outside model-controlled arguments. Retrieved webpages, OCR, files, agent messages and recalled memory are data and cannot create grants.

| Effect | Default interaction after setup |
| --- | --- |
| Read within an allowed scope | Proceed and return source/evidence. |
| Reversible local change within a grant | Proceed, verify and offer meaningful undo. |
| External communication/publication | Use an explicit applicable instruction or grant bound to recipient/destination/content. |
| Destructive or privileged change | Require an applicable concrete grant; otherwise preview the exact operation and obtain authority. |
| Unknown classification | Do not execute until effect and authority are resolved. |

Existing batch delegation defaults and recorded prior user preferences must be represented faithfully. A default flag must not be described as a new user instruction. Scope persistent autonomy by agent, workspace, effect and expiry/revocation; the user should be able to inspect it. Delegation permission does not automatically authorize messages, purchases or unrelated file access. [E7]

On this machine start with one heavy agent/model worker, then raise the limit from measured headroom. The current four-agent concurrency ceiling is a maximum capability, not a recommended operating target for available RAM. Apply timeouts, process ownership, bounded output and resource budgets. Separate workspace reservation from actual security isolation: a directory label alone does not confine a process.

Recover work by reconciling evidence. On restart, inspect the target/API/application and any surviving owned worker before deciding whether an action completed. Use idempotency keys where supported. Unknown external effects remain unknown until checked; do not promise global exactly-once execution for arbitrary applications.

Use the existing evolution workflow for isolated proposals and reviewed activation. Learning guidance cannot expand permissions, change locked voice code or deploy itself. Offline harness success demonstrates integration plumbing, not improved everyday task quality. [E7, E11]

## 11. Memory and privacy redesign

Reuse the current scoped memory service and its provenance/correction machinery. Add a user-facing lifecycle across distinct data classes:

| Data | Proposed policy and control |
| --- | --- |
| Raw audio / wake pre-roll | Transient RAM only by default; short bounded buffer; discard on mode change. Explicit opt-in for diagnostic recording. |
| Raw transcripts | Clear setup choice and adjustable retention; private sessions excluded; review/export/delete controls. |
| Learned facts | Source-linked, correctable, revocable; assistant claims are not user facts. |
| Action history | Bounded, redacted records with evidence and resource IDs; avoid duplicating private content. |
| Indexed files / vectors | Respect folder grants and removal; disclose embedding-provider exposure. |
| Agent/tool logs | Secret redaction and output limits; avoid full sensitive tool arguments. |
| Obsidian/other exports | Separate opt-in, destination visibility and tested propagation of corrections/deletions. |

Define “forget this conversation” precisely: which transcripts, derived facts, embeddings, summaries and exports are removed, and which backups remain subject to their retention policy. Report the scope honestly. Do not silently alter the existing user's memory policy during migration.

Use short-lived, task-relevant context for cloud calls. Treat screen capture, camera capture, clipboard access and memory prompt injection as separate permissions. Exclude secret fields/windows where identifiable, but do not claim OCR heuristics guarantee redaction of all sensitive content. Authoritative transport/storage gates must remain effective if an optional processor or UI crashes. [E4, E9]

## 12. Performance, resource and cost targets

The following are **proposed acceptance targets**, not measured results or guarantees. Establish a baseline on this laptop before adjusting defaults.

| Metric | Initial target | Measurement boundary |
| --- | --- | --- |
| UI feedback | p95 under 150 ms | Invocation/state event to visible acknowledgement. |
| Explicit local playback stop | p95 under 200 ms | Accepted interrupt control to audible output ending; test both backends. |
| Local simple command | p95 under 1.5 s | End of utterance to verified setting/app outcome. |
| Cloud first response | p95 under 3 s under declared network conditions | End of utterance to first audible useful response; record failure rate too. |
| Bounded worker stop | p95 under 2 s for cancellable work | Accepted cancel to owned worker exit; irreversible effects handled separately. |
| Idle voice/shell footprint | Aim below 500 MiB added RSS, excluding loaded STT | Measure aggregate incremental processes, including helpers. |
| Local speech footprint | Aim below 1 GiB incremental RAM | Peak under active recognition and ordinary desktop load. |
| Reliability | At least 95% success on a fixed supported-task corpus | Count wrong target, false success, cancellation and repair separately. |

Independently require zero observed unauthorized effects, wrong-target mutations and false-success claims in that corpus, with sample counts published. A 95% task-completion target is not permission for the remaining 5% to cause harmful effects; a finite clean test run also cannot prove zero future risk.

Use monotonic timestamps from activation, speech end, intent ready, policy result, action start, verification and output. Publish p50/p95 and sample counts. Configured frame durations, VAD silence and playback cushions do not establish mouth-to-ear latency by arithmetic alone.

Collect CPU/RAM peaks, swap pressure, battery impact, wake false positives, missed activations and network bytes. Start with event-driven desktop state and on-demand screenshots; avoid continuous full-screen video by default. Put storage budgets on transcripts, logs, model caches and worktrees. Do not remove existing user data automatically to meet a budget.

For cloud cost, record actual provider/model, usage units and active duration. Apply the provider's current rate to those units, with an explicit budget and task allowance. Do not estimate monthly cost from guessed token rates. Account/model availability and prices were not validated by live calls in this assessment.

## 13. Implementation sequence and review gates

This is a planning estimate for one primary engineer with review help: approximately **31-48 engineering days**, usually **8-12 calendar weeks** with integration and feedback. External application support and model performance can extend it. The estimate is not a commitment or a measured forecast.

| Phase | Estimate | Concrete result | Gate before expansion |
| --- | --- | --- | --- |
| 0. Baseline and scope | 2-3 days | Versioned inventory, test baseline, target-task corpus, explicit modes and privacy contract. | Repeatable checks and known limits recorded. |
| 1. Common action truth | 5-8 days | Broker around existing dispatch, capability effects/scopes, durable task/action journal, shared stop. | No bypass through ordinary voice, workflow or agent requests; restart/duplicate tests pass. |
| 2. Trustworthy desktop actions | 5-7 days | Fix false success, exact window/element targets, postconditions, scoped undo and ambiguity flow. | Ten representative desktop workflows verify outcomes. |
| 3. Local voice essentials | 8-12 days | Audio composition adapters, local activation/commands/STT-TTS candidate, offline fallback. | Network disconnected essentials, cancellation generations and privacy failure tests pass. |
| 4. Coherent voice shell | 6-10 days | Accessible invocation panel, shared transcript, target labels, activity/decision drawer, privacy/health. | Keyboard, screen-reader, scaling, multi-monitor and mode tests pass. |
| 5. Deployment and sustained use | 5-8 days | Versioned installation, safe service boundaries, migration/rollback, daily workflow trial. | Soak/recovery/resource tests and user task evaluation meet agreed thresholds. |

Build the panel's event contract early in Phase 1 and its visual prototype in parallel; connect execution only through the broker. Do not make GUI polish a prerequisite for fixing unsafe success claims.

### First implementation backlog

| Order | Work item | Existing starting point | Acceptance evidence |
| --- | --- | --- | --- |
| 1 | Correct window/workspace success reporting | `skills/system_control.py` | Both dispatches failing returns failure; readback confirms exact target. |
| 2 | Wrap all tool dispatch in one broker | `skills/skills.py`, `proactive/policy.py` | Model-supplied approval fields cannot grant authority; valid stored grants continue without reprompting. |
| 3 | Persist ordinary tasks and agent jobs | `filesystem/task_runner.py`, `orchestration/agent_orchestrator.py`, proactive ledger/control | Restart during each lifecycle stage yields truthful recovery state. |
| 4 | Version UI snapshots/events | `core/ipc.py`, status provider | Reconnect/replay and slow-client tests; no divergent UI task truth. |
| 5 | Add folder grants and recoverable file operations | `filesystem/filesystem.py` | Traversal/symlink cases, overwrite failure, recovery and exact content verification. |
| 6 | Introduce voice supervisor and explicit adapters | Unlocked new core/interaction modules plus `audio/extension.py` | Actual selected backend passes processor, hook, frame and stale-generation integration tests. |
| 7 | Prototype local command engine | New isolated speech/command modules | Published essentials work with cloud unavailable and no stale replay. |
| 8 | Build invocation/activity/privacy views | `ui/`, input bar and existing IPC | Accessible controls; visible exact targets; verified results and recovery. |
| 9 | Add data-lifecycle controls | Current memory bridge, scoped MCP, exports | Private mode and deletion tested across each enabled store/export. |
| 10 | Release package and rollback | `run.sh`, installer, service units | Single voice instance; clean install/upgrade/rollback; login/resume/device-loss recovery. |

New names such as a voice supervisor or action broker are proposed components, not files claimed to exist. Refactor the unlocked orchestration gradually; avoid a wholesale rewrite of the large runtime and skill dispatcher.

## 14. Validation plan and assessment results

### Automated checks performed for this report

The full baseline completed with **968 passed, 6 failed, 2 skipped and 265 passed subtests in 53.98 seconds**. A focused recheck reproduced all six failures, with four additional tests passing in 4.83 seconds. These issues remain unresolved; the suite is not green.

| Failing group | Observed cause or limit | What to do before release |
| --- | --- | --- |
| Harness availability: 1 test | The test expects `executable=None` to mean absent, while the adapter auto-discovers the installed `harness2` executable. | Mock discovery explicitly and distinguish unavailable from auto-discover semantics. This result alone does not show optional execution is broken. |
| Phone notifications: 4 tests | Tests mock the event listener but leave gateway discovery real; the monitor waits when no gateway is found, so injected callbacks miss the test deadlines. | Isolate gateway state and test connected/disconnected lifecycle. These failures establish neither working nor broken live phone notifications. |
| Manifest parity: 1 test | Canonical manifests include `harness-local.json` and `research-learning.json`, missing from the mirror directory. | Synchronize or explicitly consolidate the manifest trees, preserving the ongoing learning work. |

Both skipped tests are opt-in real Linux sandbox checks, so this run does not verify real sandbox isolation. No source fix was made as part of this report.

The successful baseline command was `timeout -k 5 180 env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 .venv/bin/pytest -q -o faulthandler_timeout=30`, with local socket access. Failure evidence is in `tests/test_orchestration/test_harness2_adapter.py`, `tests/test_skills/test_phone.py` and `tests/test_skills/test_system_information_wiring.py`. The restricted diagnostic run was stopped after it established environment restrictions; it is not used for the passing/failing totals above.

The voice-lock verifier reported: **all seven core files intact and unmodified**. Test collection discovered **976 tests**. The normal suite excludes preserved upstream memory bundles from discovery. The first restricted-environment execution encountered local socket restrictions, so a bounded run with local socket access was used for the usable baseline. No redesign implementation was tested because this deliverable is an assessment and proposal.

### Acceptance work required before calling it a voice OS

| Test group | Required scenarios |
| --- | --- |
| Speech/activation | Multiple speakers, supported accents/languages, background TV, quiet/noisy rooms, wake misses/false activations, one-breath wake plus command. |
| Audio | Both selected backends, speakers/headphones/Bluetooth, device removal, AEC/double talk, suspend/resume, playback stop and generation fences. |
| Privacy | No prohibited upload/storage during standby/private/off/failure/reconnect; screen/camera permissions and exporter deletion. |
| Authority | Existing grants respected; missing authority resolved; untrusted text cannot approve; folder and agent boundaries enforced. |
| Task lifecycle | Duplicate requests, crash/restart at each stage, partial operations, owned cancellation and unknown external effects. |
| Desktop | Two similar windows, closed/replaced target, scaling/multi-monitor, stale frames, unavailable accessibility and failed dispatch/readback. |
| Interface | Screen reader, keyboard-only, large text, reduced motion, focus restoration, no audio available and text fallback. |
| Deployment | Single-instance ownership, login/logout, upgrade/rollback, missing credentials/dependencies and storage pressure. |
| Daily use | A fixed corpus including project resume, dictation, app/window control, file organization, research and meeting preparation. |

Run component/offline tests in CI and controlled live acceptance on the actual desktop. Real sandbox checks are opt-in and should be reported separately. Do not equate the offline suite or a successful provider handshake with live voice-to-action readiness. A 24-hour controlled soak is a useful first release gate, followed by a week of ordinary supervised use with explicit failure logging.

## 15. Decisions to preserve and decisions still open

Preserve Linux/Omarchy as the substrate, the locked voice core, declarative adapters, source/evidence-linked memory, bounded agent ownership and reviewed capability activation. Retain accessible manual recovery throughout migration.

Decide during Phase 0: default activation mode; supported languages and essential offline commands; transcript retention; granted folders/accounts; stop/undo semantics; one microphone owner; current autonomy preference scopes; and the first ten daily workflows. These decisions refine implementation without blocking this architecture recommendation.

Defer a custom distribution image, a replacement compositor, unlimited autonomous repair, a large local reasoning model and cross-device autonomy until the local operating layer passes its acceptance gates. The practical milestone is a reliable ordinary desktop session operated mainly through voice, with visible targets, durable task truth and recoverable actions.

## Appendix A. Local evidence index

Line numbers identify the inspected working tree and may shift after concurrent edits. Links point to actual source files; proposed modules are described only in the backlog.

| Key | Source and reason |
| --- | --- |
| E1 | [AGENTS.md](/home/g0pi/Projects/JARVIS-OMA/AGENTS.md:1): immutability, test and documentation invariants. |
| E2 | [OS decision log](/home/g0pi/Projects/JARVIS-OMA/docs/jarvis-os/decision-log.md:5), [target architecture](/home/g0pi/Projects/JARVIS-OMA/docs/jarvis-os/target-architecture.md:34), [foundation repair](/home/g0pi/Projects/JARVIS-OMA/docs/jarvis-os/foundation-repair-2026-10-19.md:1): existing direction and historical verification limits. |
| E3 | [Registry validation](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:542), [catalog status](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:699), [ordinary dispatch](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:831): declarations, runtime status and execution boundary. |
| E4 | [Capture/send path](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:735), [provider setup](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1815), [backend selection](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1932), [cloud connect](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:2065), [extension failure behavior](/home/g0pi/Projects/JARVIS-OMA/audio/extension.py:101), [composition wrapper](/home/g0pi/Projects/JARVIS-OMA/audio/extension.py:153), [native companion](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:77), [standby](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:18). |
| E5 | [Window targeting](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:153), [dispatch results](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:1229), [workspace dispatch](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:1255), [GUI freshness](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:103), [browser binding](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:333). |
| E6 | [Filesystem paths](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:32), [write behavior](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:193), [move/copy replacement](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:253), [delete guards](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:333), [task storage](/home/g0pi/Projects/JARVIS-OMA/filesystem/task_runner.py:27), [file verification](/home/g0pi/Projects/JARVIS-OMA/filesystem/task_runner.py:129), [defaults](/home/g0pi/Projects/JARVIS-OMA/core/config.py:189). |
| E7 | [Agent job storage](/home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py:185), [visible delegation policy](/home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py:308), [skill delegation](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:932), [evolution isolation and limits](/home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py:1). |
| E8 | [Effect policy](/home/g0pi/Projects/JARVIS-OMA/proactive/policy.py:17), [durable controls](/home/g0pi/Projects/JARVIS-OMA/proactive/control.py:35), [execution reconciliation](/home/g0pi/Projects/JARVIS-OMA/proactive/runtime.py:228), [independent verifier](/home/g0pi/Projects/JARVIS-OMA/proactive/verification.py:17). |
| E9 | [Memory defaults](/home/g0pi/Projects/JARVIS-OMA/core/config.py:199), [transcript persistence](/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/bridge.py:431), [scoped memory MCP](/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/mcp_server.py:37). |
| E10 | [Orbit](/home/g0pi/Projects/JARVIS-OMA/ui/omarchy-ai.orbit/OrbitOverlay.qml:8), [procedural visualization](/home/g0pi/Projects/JARVIS-OMA/ui/omarchy-ai.orbit/AuraFieldOrbit.qml:9), [input bar](/home/g0pi/Projects/JARVIS-OMA/skills/input_bar.py:189), [IPC](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:38), [status fields](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1986), [installed shell config](/home/g0pi/.config/omarchy/shell.json:95), [voice bindings](/home/g0pi/.config/hypr/bindings.lua:31). |
| E11 | [Learning boundaries](/home/g0pi/Projects/JARVIS-OMA/learning/service.py:12), [learning guide](/home/g0pi/Projects/JARVIS-OMA/docs/harness-learning.md:1), [service unit](/home/g0pi/Projects/JARVIS-OMA/systemd/jarvis-oma.service:10), [discovery/test configuration](/home/g0pi/Projects/JARVIS-OMA/pyproject.toml:1), [offline test isolation](/home/g0pi/Projects/JARVIS-OMA/tests/conftest.py:1). |

Legacy UI observations are host-specific references, not JARVIS features: [window labels](/home/g0pi/.config/omarchy/plugins/omarchy-ai.window-labels/WindowLabels.qml:8), [chat HUD](/home/g0pi/.config/omarchy/plugins/omarchy-ai.chat-hud/ChatHud.qml:9), and [task/decision HUD](/home/g0pi/.config/omarchy/plugins/omarchy-ai.assistant-huds/AssistantHuds.qml:14). Their helper paths and enablement need migration review.

## Appendix B. External technical references

Primary documentation checked on 24 October 2026. These sources establish available mechanisms; proposed architecture, resource budgets and performance targets are the assessment's recommendations.

- **W1:** [sherpa-onnx documentation](https://k2-fsa.github.io/sherpa/onnx/index.html): local recognition and deployment options.
- **W2:** [whisper.cpp project](https://github.com/ggml-org/whisper.cpp): local transcription implementation and hardware options.
- **W3:** [Gemini Live session management](https://ai.google.dev/gemini-api/docs/live-api/session-management) and [capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities): provider session, audio and tool behavior.
- **W4:** [Hyprland IPC](https://wiki.hypr.land/IPC/): compositor request and event interfaces.
- **W5:** [AT-SPI API](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/): semantic accessibility interfaces.
- **W6:** [XDG Remote Desktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html) and [ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html): session/permission/input/capture contracts.
- **W7:** [Hyprland portal backend](https://github.com/hyprwm/xdg-desktop-portal-hyprland): installed backend family; actual supported interfaces must be probed.
- **W8:** [systemd execution environment](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html): service compartment and environment options. Apply selectively after testing required desktop/audio access.

