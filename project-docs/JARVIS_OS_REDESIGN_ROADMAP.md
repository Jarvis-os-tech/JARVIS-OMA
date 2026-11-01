# JARVIS OS — Research and Redesign Roadmap

Date: 27 October 2026  
Status: **Planning only. No implementation or deployment is authorized by this document.**

## 1. Product definition and confirmed constraints

JARVIS OS is a personal Linux operating environment whose primary interaction is conversation. JARVIS coordinates applications, files, hardware, tasks, agents, and personal context. Its future shell is an ambient top Dynamic Island with a clean desktop and no traditional dock, once replacement functionality is ready.

Linux remains the kernel. Arch-derived packages, drivers, Hyprland, Wayland, and PipeWire can remain foundations. Omarchy is the starting environment being redesigned, not a kernel. JARVIS OS will own the user experience, integration contracts, configuration, release process, and eventually distribution identity.

**Confirmed by the user:**

- Plan the whole redesign before building it. Earlier pasted commands and blueprints are context.
- Voice is the main interface; CLI, keyboard, mouse, and accessibility controls remain supporting interfaces.
- **Super+H belongs to the existing speech-to-text dictation workflow. Preserve it.**
- Dictation inserts text into applications. JARVIS conversation interprets intentions and may operate the computer. These are separate modes.
- Establish working voice and OS integration before implementing the visual redesign.
- Preserve all seven locked audio-core files and their public interfaces.
- Store the plan as clean Markdown in project-docs.
- Conserve available model usage through bounded research and small, testable work packages.

This roadmap sets the implementation order. The [master specification](JARVIS_PERSONAL_VOICE_OS_MASTER.md) retains the broader requirements and source history. Historical documents describe earlier states and are not proof of present readiness.

## 2. Research conclusions

### A. Build on the existing operating system interfaces

Hyprland exposes a request socket and a separate event stream. Its documentation warns that an unclosed request connection can stall the compositor. Proposed design: use bounded requests for actions, a persistent event subscription for observation, and a fresh snapshot after reconnect; do not poll the full desktop continuously. [Hyprland IPC](https://wiki.hypr.land/ipc/)

Quickshell PanelWindow supports screen-edge anchoring, reserved space, and optional keyboard focus. It is a suitable candidate for the Island. Proposed design: the shell renders shared state; its animations never own task execution or microphone lifecycle. The UI must be able to restart independently. Verify these APIs against the installed Quickshell version before implementation. [Quickshell PanelWindow](https://quickshell.org/docs/v0.3.2/types/Quickshell/PanelWindow/)

### B. Treat real-time audio as its own timing domain

PipeWire echo cancellation uses linked capture/source and sink/playback streams. It is software processing in this design, not evidence of hardware AEC. The existing native companion already isolates device callbacks from Python work. Preserve that separation, verify the actual reference routing, and measure conversation latency under tool load. “Zero latency” is not a meaningful acceptance criterion. [PipeWire echo cancellation](https://pipewire.pages.freedesktop.org/pipewire/page_module_echo_cancel.html)

### C. Separate persistent background work from the graphical session

systemd documents graphical-session.target for services whose lifetime follows the desktop session. A task scheduler that must survive logout needs a different lifecycle from an Island tied to a screen. User lingering can keep a user manager alive across logout, but does not supply a desktop, unlocked credentials, or microphone access. Treat across-logout operation as an explicit later feature. [Graphical session lifecycle](https://www.freedesktop.org/software/systemd/man/256/systemd.special.html), [User lingering](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html)

Observe login, lock, and sleep transitions through the supported login manager interface. Before suspend, checkpoint tasks and release session resources; after resume, re-observe the environment before continuing. These are proposed recovery rules, not guarantees provided automatically by a service restart. [systemd-logind interface](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html)

### D. Map intent to explicit outcomes

The supplied snippets contain several semantic traps:

| User request | Required meaning | Implementation implication |
|---|---|---|
| “Pause music” | Selected player becomes paused | Use Pause, not a toggle that can resume playback |
| “Resume music” | Selected player becomes playing | Use Play and check supported controls |
| “Go to workspace 2” | Change the viewed workspace | Distinguish from relocating a window |
| “Move this window to workspace 2” | Move the bound window | Verify that window's resulting workspace |
| “Tile this left” | Position the intended window according to the selected layout | Directional movement alone does not promise half-screen geometry |
| “Fullscreen this” | Enter fullscreen explicitly | Match installed dispatcher semantics; do not confuse maximize with fullscreen |
| “Mute Jarvis” | Stop JARVIS voice input according to its policy | Distinguish from muting the physical microphone for all applications |
| “Stop speaking” | Cancel the current response and stale playback | Do not silently unmute the microphone |
| “Switch to test mode” | Change the selected tested runtime safely | Do not equate a restart attempt with a successful switch |

MPRIS provides separate Pause, Play, and PlayPause methods plus playback state and capability properties. Hyprland documents separate workspace/window operations and distinguishes fullscreen from maximize. Installed versions and this host's Lua-based configuration must be checked before adopting examples. [MPRIS Player interface](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html), [Hyprland dispatcher reference, version 0.54.0](https://wiki.hypr.land/0.54.0/Configuring/Dispatchers/)

### E. Use bounded, consented perception

The ScreenCast portal provides a session-based screen-sharing interface and PipeWire stream access. Proposed design: prefer user-selected capture where supported, track capture session lifetime, and expose when observation is active. Window changes and resource telemetry should not require continuous screenshots. Accessibility and native application data should precede expensive image interpretation when available. [XDG ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)

### F. Add smart-home reach through a gateway

Home Assistant's WebSocket API supports authentication, events, and commands. It is a candidate integration boundary that avoids implementing every device protocol inside JARVIS. It is not an installed dependency established by this research. Evaluate it only after the desktop release is dependable; first discover devices and observe their state, then introduce approved controls. [Home Assistant WebSocket API](https://contributors.home-assistant.io/core/internals/websocket-api/)

Bloom and Sentient-OS are visual references supplied by the user. No particular repository or implementation was identified or evaluated here; their internals are not assumed.

## 3. Repository baseline: reuse, strengthen, investigate

These findings come from inspected project files. They are narrower than an exhaustive code or security audit.

| Area | Existing evidence | Planning conclusion |
|---|---|---|
| Voice runtime | core/agent.py, core/audio_scheduler.py, audio/plugins/native_backend.py | Extend existing ownership and bounded scheduling; do not start another audio engine |
| Audio extensions | audio/extension.py and native companion README | Public extension boundary exists; check actual pipeline wiring and hardware behavior |
| Local control | core/ipc.py, scripts/jarvisctl.py, scripts/jarvis | CLI and IPC already exist; repair and version their contract |
| Shell connection | scripts/orbit_status.py and ui/omarchy-ai.orbit/OrbitOverlay.qml | Existing event subscription is a starting point; redesign does not begin from zero |
| Desktop actions | skills/system_control.py, skills/system_extensions.py, manifests | Many controls exist; improve targeting, explicit semantics, and outcome readback |
| Durable events | proactive/events.py and proactive/ledger.py | SQLite event queue and activity ledger already exist; extend rather than duplicate |
| Proactivity | proactive/runtime.py, monitor.py, system_watch.py | Existing monitoring and bounded work; establish crash recovery and user policy |
| Agent coordination | orchestration and archived autonomous-orchestration.md | Delegation exists; durable team recovery needs verification and further work |
| Memory | jarvis_memory, memory, universal-memory-mcp | Determine actual runtime owner before consolidating storage or removing compatibility layers |
| Production/test | scripts/jarvis_mode.py | Existing switching is a prototype, not a proven release pipeline |
| System startup | two repository service templates/installers | Choose one canonical owner and design a reversible migration |

### Concrete findings to carry into implementation

- CLI explicit mute/unmute sends set_mute while the inspected IPC server only implements toggle_mute.
- Bare jarvis voice currently toggles; nested voice actions need a defined parser contract.
- Autostart code can mishandle repeatedly commented startup lines and does not consistently report service failures.
- Directional desktop movement reports an unverified result; a successful process exit is not layout verification.
- Desktop input verification needs review where unchanged focus upgrades delivery into success.
- The inspected mode switcher copies configuration/credentials, shares the production virtual environment, and can return success when restart did not succeed.
- Its promotion checks are conditional on files being present. A missing test runner or lock verifier must block future promotion, not silently skip verification.
- Existing reports and live checks establish useful pieces, not “all features complete” or “24/7 verified.”

These are backlog items. The implementation experiment from the preceding chat turn was rolled back after the user clarified that this is planning work.

## 4. Target architecture

~~~text
User
 ├─ Dictation: Super+H → existing STT → focused application's text input
 └─ JARVIS conversation → selected activation method → intent/context
                                                     │
                              policy + capability registry + task supervisor
                                                     │
                           observed state → targeted action → result verification
                                                     │
                  desktop / system / applications / files / agents / connectors
                                                     │
                                  durable events + task state + memory
                                                     │
                                voice feedback + future Dynamic Island
~~~

Microphone routing must coordinate dictation, JARVIS, meetings, and other approved audio clients. “One JARVIS owner” means one JARVIS capture/playback lifecycle; it does not mean removing other useful microphone applications.

### Runtime boundaries

| Component | Owns | Failure behavior |
|---|---|---|
| Voice runtime | Capture, response playback, interruptions, provider session | Local controls remain usable; old speech and cancelled responses are not replayed |
| Control runtime | Capability contracts, intent/action identities, task supervision | Action history survives; UI disconnect does not duplicate work |
| Observer workers | Desktop/session/resource changes | Stale or unavailable state is explicit |
| Background workers | Plans, connectors, agents, summaries | Bounded concurrency and cancellation; restart reconciliation |
| Memory service | Personal facts, profiles, revisions and retrieval | Degraded retrieval is reported; action success does not depend on an embedding call |
| JARVIS shell | Island, task views, notifications, settings, accessibility | Restart independently; no ownership of audio or tasks |
| OS adapters | Small typed operations through supported interfaces | Return evidence, unavailable status, or failure; no fabricated success |

These are ownership boundaries. Separate processes/services should be introduced only where lifecycle or fault isolation requires them. Avoid turning every module into a new daemon.

### Shared contracts

Define versioned Intent, Action, Job, Evidence, DesktopState, and Event schemas. Each action carries the original request, target identity, session identity, policy decision, idempotency key, cancellation state, expected effect, observed effect, and timestamps.

Results must distinguish: unavailable, needs clarification, awaiting approval, dispatched, verified, failed, cancelled, and outcome unknown. Retry according to capability semantics. Do not promise exactly-once external effects when a crash occurs after dispatch but before recording the result.

Events carry sequence/revision and correlation IDs. A new subscriber receives a snapshot before subsequent changes; reconnect detects gaps and resynchronizes. Slow UI consumers must never block voice or control work.

## 5. Dependency-ordered delivery roadmap

Every phase below is planned. A documentation milestone does not authorize changing live services or user configuration.

| Phase | Outcome | Depends on | Release gate |
|---|---|---|---|
| P0 | Baseline, inventory, and agreed product contracts | This roadmap | Known working workflows and rollback paths recorded |
| P1 | Shared control and state contracts | P0 | CLI, voice and shell clients agree on commands and outcomes |
| P2 | Reliable voice plus dictation coexistence | P1 | Activation, mute, interruption and recovery demonstrated |
| P3 | Verified OS and application actions | P1–P2 | Spoken acceptance scenarios succeed with readback |
| P4 | Personal memory, perception and durable tasks | P1–P3 | Restart recovery and privacy behavior demonstrated |
| P5 | Installable session integration and isolated releases | P2–P4 | Reversible deployment on a test user/session |
| P6 | Dynamic Island shell and complete desktop experience | P3–P5 | Shell parity and independent recovery pass |
| P7 | Daily-use JARVIS OS release and identity | P5–P6 | Upgrade/rollback, migration and daily-workflow gates pass |
| P8 | IoT and cross-device autonomy | Stable P7 | Device-specific authorization and outcome verification |

Design sketches for P6 may happen during planning. Implementing the replacement shell or hiding the current dock waits until earlier functionality is ready. No calendar estimate is committed before P0 establishes scope, baseline, and available engineering capacity.

### P0 — Establish the redesign baseline

Deliverables:

- Inventory services, actual enabled state, microphone clients, desktop bindings, shell plugins, packages, local modifications, and provider dependencies.
- Identify config owners: upstream defaults, generated files, personal overrides, package-managed files, and JARVIS-owned files.
- Record supported hardware, compositor/shell versions, display scaling, language/accent needs, and ordinary daily workflows.
- Separate offline automated tests from live audio/desktop tests and document current failures.
- Register protected user workflows: Super+H dictation, meetings, existing shortcuts, lock screen, accessibility, and emergency recovery.
- Decide primary-machine migration first versus a redistributable installation image later.

Gate: the baseline allows every proposed migration to state what changes, who owns it, how it is tested, and how it is undone.

### P1 — Establish the OS command and event contracts

Deliverables:

- Reconcile the existing CLI/IPC mismatch; make explicit operations idempotent.
- Standardize capability availability, command arguments, timeouts, cancellation, and truthful errors.
- Connect existing event and activity storage to action IDs and stable targets.
- Separate machine-readable state from spoken summaries and presentation labels.
- Define access to the local endpoint and bounded message/subscriber handling.
- Define compatibility rules so old shell clients can report unsupported commands.

Gate: offline integration tests demonstrate repeated mute, failed commands, unavailable backend, reconnect, slow subscriber, cancellation, and consistent state across clients.

### P2 — Make voice dependable alongside dictation

Deliverables:

- Separate dictation, command conversation, optional wake standby, physical microphone mute, JARVIS mute, and stop-speaking states.
- Choose a JARVIS activation method after checking shortcut conflicts. Super+H stays unchanged.
- Define audio coexistence during STT dictation, calls, playback, and screen sharing.
- Preserve native callback isolation; verify AEC routing, capture age, generation cancellation, short reply drain, and device changes.
- Measure p50/p95 recognition-to-action and response latency under idle and tool load.
- Decide cloud/local provider policy from measured quality, hardware requirements and usage costs. Wake model and separate STT/TTS components are evaluation choices, not automatic dependencies.
- Define offline capabilities explicitly; native audio alone does not make cloud speech understanding available offline.

Gate: a live test covers quiet speech, ordinary background noise, simultaneous speech/playback, interruptions, reconnect, microphone removal, and dictation coexistence. Publish measured results instead of zero-latency claims.

### P3 — Make voice operate the computer reliably

Deliverables:

- Application launch and focus by stable target; window/workspace operations with precise semantics.
- Audio devices, output volume, JARVIS input, physical mic, brightness, media, network, Bluetooth, battery and power operations with supported readback.
- Filesystem, project, terminal and browser tasks through existing typed adapters.
- A bounded conversational plan for multi-step requests; ask only for material ambiguity.
- Read-only healer/crash status first; automatic repair requires a separately specified policy.
- Lock/sleep/logout handling and explicit state when a display, service or credential is unavailable.

Gate: repeat the acceptance scenarios in section 7, including failure injection. Confirm effects on the exact target; distinguish delivery from success and report partial completion.

### P4 — Add continuous context and personal agency

Deliverables:

- Event-driven DesktopState with freshness and session boundaries; optional consented screen/camera observations.
- Integrate fact/profile/document memory with project decisions, task history and sources.
- Durable goals, reminders and task checkpoints; reconcile work interrupted by crash or logout.
- Agent job ownership, isolated workspaces, resource budgets, acceptance checks and cancellation.
- Quiet hours and meaningful-change notifications; user-defined autonomy per capability.
- Presence/lock state and step-up authentication where needed. A wake word is not proof of identity.

Gate: a restarted daemon can explain pending work without replaying irreversible actions. Correct/forget/export operations behave as documented. Pausing perception or background work persists correctly.

### P5 — Package the working integration

Deliverables:

- One canonical service entry point and installer; migrate old names without running duplicate JARVIS audio owners.
- Distinguish desktop-session dependencies from optional background work across logout.
- Test startup readiness, delayed desktop sockets, unavailable providers, suspend/resume and rollback.
- Replace hardcoded checkout/user paths with install-time configuration.
- Separate development configuration, sockets, data stores and dependency environments from production.
- Add read-only diagnostics showing actual runtime identity, service state, capability health and failures.
- Keep Omarchy compatibility adapters until their replacements pass acceptance checks.

Gate: install, uninstall, upgrade and rollback succeed on a test account/session. A broken test build cannot silently corrupt production memory or leave the machine without working interaction.

### P6 — Build the ambient JARVIS shell

Deliverables:

- A top Dynamic Island showing current voice state, active work, media, time/battery and workspace access.
- Expanded task history, approvals, settings, app access, notifications and recovery controls.
- Measured audio levels drive any waveform; a decorative animation must not imply that capture or processing is active.
- Arbitration for simultaneous activity: critical errors and approvals, active conversation, calls/media, background work, and quiet idle state.
- Multi-monitor placement, scaling, full-screen behavior, reduced motion, keyboard access, readable contrast and focus management.
- A clear distinction between listening, muted, local standby, disconnected, processing, speaking and failed.
- A shell-parity checklist before retiring the bar/dock: launcher, workspace navigation, tray, network/audio controls, notifications, lock/power access and accessibility.

Gate: the Island can crash/restart without stopping voice or losing tasks. It neither steals typing focus nor hides essential controls. Remove the old dock only after the replacement is validated and rollback is available.

### P7 — Release the JARVIS OS experience

Deliverables:

- Own the login/session presentation, lock-screen integration, settings, notifications, help, sound policy, release identity and update channel.
- Preserve distribution compatibility metadata and licenses; perform identity changes through packaging.
- Inventory residual Omarchy dependencies and classify each as retain, adapt, replace or retire.
- Freeze a tested release revision with package/config/schema versions and migration instructions.
- Provide offline recovery instructions and a known-good fallback session.
- Evaluate a reproducible installer/image after the primary-machine release is stable.

Gate: daily workflows pass on the intended hardware; upgrade and rollback include compatible state restoration; no critical feature depends on an undocumented manual edit.

### P8 — Extend to devices and other machines

Deliverables:

- Evaluate a Home Assistant bridge or another selected gateway with explicit scope.
- Device registry, locations, ownership, fresh state, unavailable state and action history.
- Begin with read-only observations, then bounded controls and routines.
- Separate computer presence from trusted authorization for household actions.
- Add remote agents/devices with authenticated connections and per-device capabilities.

Gate: disconnected or ambiguous devices cannot be reported as successfully controlled. Physical actions have suitable authorization, acknowledgement and recovery behavior.

## 6. Production and development workflow

main/dev names describe branches, not reliability. Candidate releases must identify the exact tested revision and configuration.

1. Plan a bounded work package and its acceptance scenarios.
2. Build in an isolated worktree. Keep production configuration and personal data separate.
3. Run offline tests, voice-lock verification and migration checks.
4. Exercise simulated desktop/audio adapters before a live session.
5. Select the candidate explicitly; checkpoint running work and record the previous runtime.
6. Transfer JARVIS audio ownership once, verify readiness, then start the candidate conversation.
7. If readiness fails, return to the prior runtime and report the failed switch.
8. After user acceptance, promote the tested revision with a release record and rollback path.

The current mode switcher needs the findings in section 3 resolved before it can enforce this process. A voice request to switch mode should acknowledge the pending restart, preserve its intent, and verify the result after the service is available again.

## 7. End-to-end acceptance scenarios

| Scenario | Evidence required |
|---|---|
| Dictate into an editor with Super+H | Text reaches the intended field; no JARVIS activation or keybinding change |
| Activate JARVIS with its chosen method | Visible/control state matches actual capture and provider state |
| “Open terminal on workspace 2” | Correct application/window and destination workspace read back |
| “Tile this left” | Original target identity retained; layout outcome observed |
| “Go to workspace 2” vs “Move this window to workspace 2” | Distinct actions and correct results |
| “Pause music” twice | Chosen player remains paused |
| “Mute Jarvis” twice | JARVIS remains muted without changing unrelated app microphone policy |
| Interrupt a response during a slow tool | Playback stops; stale response cannot resume; task cancellation follows stated intent |
| Network disconnect and recovery | No expired microphone replay or duplicate tool effects |
| Sleep, resume, lock and unlock | Correct state boundaries, fresh observations and documented privacy behavior |
| Restart while a task is active | Durable record reconciled; uncertain outcome not blindly retried |
| Correct/forget personal memory | Subsequent retrieval follows the correction/deletion policy |
| Restart only the shell | Voice and jobs remain coherent; shell resubscribes to fresh state |
| Fail a test-mode switch | Prior production remains recoverable; failure is reported |
| Roll back a release | Previous runtime and compatible data state restore correctly |

Set numerical latency, resource and reliability targets after measurement in P0/P2. Any draft targets must be labeled proposals. Track interruption latency, wrong-target actions, repeated effects, crashes, recovery time, idle resource use, and provider usage independently.

## 8. First implementation backlog — not started

| ID | Work package | Dependency | Completion evidence |
|---|---|---|---|
| JOS-001 | Baseline and protected-workflow inventory | Planning accepted | Current manifest and rollback records |
| JOS-002 | Voice/CLI/IPC command contract | JOS-001 | Contract tests against actual server |
| JOS-003 | Explicit mute/error/autostart corrections | JOS-002 | Idempotence and failure tests |
| JOS-004 | Dictation/conversation coexistence | JOS-002 | Super+H unchanged; audio coexistence scenarios |
| JOS-005 | Exact-target desktop action/readback | JOS-002 | Workspace, window and media acceptance tests |
| JOS-006 | Audio performance and recovery baseline | JOS-004 | Timing records and acoustic observations |
| JOS-007 | Durable action/event/job recovery | JOS-002 | Crash-before/after-dispatch tests |
| JOS-008 | Production/test environment isolation | JOS-001, JOS-007 | Failed-switch rollback and state-isolation tests |
| JOS-009 | Session/service packaging | JOS-003, JOS-006, JOS-008 | Test-session install and recovery |
| JOS-010 | Island state specification and shell parity | JOS-002; implementation after JOS-009 | UX state matrix and recovery tests |

Detailed memory, autonomy, identity and device work packages follow their phase requirements. Keep each implementation package narrow enough to review with its tests and rollback.

## 9. Decisions and open design choices

| Decision | Status |
|---|---|
| Product identity: JARVIS OS, voice primary | Confirmed |
| Linux kernel retained; Omarchy is the migration source | Confirmed direction |
| Super+H remains dictation | Confirmed |
| Functional integration before visual implementation | Confirmed |
| Dynamic Island as future shell center; dock retired after parity | Target design |
| Separate dictation and assistant activation | Required; activation method undecided |
| Always-listening, wake-only or push-to-talk default | Undecided; compare privacy, latency and convenience |
| Cloud, local or hybrid speech/model routing | Evaluate against this hardware and actual usage |
| Work across logout | Optional scope; do not infer from login autostart |
| Authentication/presence method | Undecided; keep system authentication authoritative |
| Exact IoT gateway and devices | Deferred until local release |
| Redistributable OS image | Later product decision after working desktop release |
| Bloom/Sentient visual reference repositories | Not supplied; no implementation assumptions |

## 10. Usage-conscious execution

Research is bounded to the inspected code and primary documentation cited above. Do not spend the remaining account allowance generating competing full redesigns.

For future work: one package per implementation cycle; read the relevant files; use offline tests first; run live checks only when they answer an unresolved question; record evidence and next actions in this folder. Update status with tested revision and date rather than repeatedly regenerating the whole specification.

Planning handoff: review this architecture and resolve activation, provider policy, and distribution scope before selecting the first implementation package. Until implementation is requested, do not change hotkeys, shell plugins, services, package identity or audio behavior.

