# JARVIS-OMA: voice-to-OS debugger audit

**Date:** 27 October 2026 · **Scope:** current working tree on `main`, base `17bec36` · **Status:** findings and proposed solutions; no production fixes made in this audit.

## Severity-ranked findings

**19 findings: 8 high, 9 medium, 2 low.** The most urgent problems are credential inheritance, incomplete stop/cancel ownership, a real GUI driver mismatch, and voice interruption/standby recovery. Some findings are reproduced defects; others are explicitly marked design limitations or conditional risks. This is a broad audit, not a claim that every possible defect has been discovered.

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| J01 | High | Credentials reach audio and GUI helper processes | reproduced + live metadata |
| J02 | High | Verified coordinate clicking calls an unsupported driver tool | installed contract mismatch |
| J03 | High | “Stop all” does not stop every JARVIS job type | reproduced |
| J04 | High | Cancellation can orphan a desktop command subprocess | reproduced |
| J05 | High | Timed-out file operations can finish later without action-level tracking | reproduced |
| J06 | High | Manual interruption can resume the same old voice reply | reproduced |
| J07 | High | Audio failure during standby can leave wake-up stuck | reproduced + control-flow inspection |
| J08 | High | Desktop mutations are not serialized across simultaneous tool calls | reproduced boundary gap |
| J09 | Medium | Wake-word initialization and inference block the conversation loop | code-confirmed + historical timing |
| J10 | Medium | A resumed conversation permanently runs out of tool slots | reproduced design limit |
| J11 | Medium | A second daemon can replace a live IPC endpoint | reproduced |
| J12 | Medium | IPC limits cover subscribers but not idle command clients | reproduced |
| J13 | Medium | Desktop session refresh cannot repair stale existing variables | reproduced condition |
| J14 | Medium | “Verified changes” can still contain a functional bug | reproduced acceptance limitation |
| J15 | Medium | Typing/key tools cannot prove their intended effect | code-confirmed functional gap |
| J16 | Medium | Fast local audio acknowledgements do not establish fast voice responses | measured gap + design limitation |
| J17 | Medium | Filesystem mutation checks retain a path-substitution race | conditional code risk; previously documented |
| J18 | Low | Memory recall repeatedly scans and synchronizes whole collections | code-confirmed scaling risk; unbenchmarked |
| J19 | Low | Camera transport updates a file much faster than cloud vision consumes it | code-confirmed optimization candidate |

### Current runtime evidence

- The assistant was running the native backend, connected, with no reported active jobs or pending tool calls at the sampled instants. No restart, mute change, GUI input, account write or live agent delegation was performed for this audit.
- The running native audio helper inherited **18 credential-named environment variables**, the same count as the parent daemon. Only counts were reported; no values were printed or stored.
- Installed **Cua Driver 0.28.2** rejects `describe click_window` with exit 64. Its normal `click` schema requires `pid` and `window_id` for a window target.
- Latest sampled response timing: **p50 1.247 s / p95 4.378 s**, 12 samples, measured from the latest received transcription observation to first received provider PCM. This excludes endpointing and speaker output and is not an acoustic latency measurement.
- Audio send-lock wait was p95 **0.003 ms**, with **0 transport send timeouts** in that snapshot. The local send lock is not shown to be the dominant cause of the observed multi-second response delay.
- Across two opportunistic snapshots, playback rebuffer count rose **1 → 3**, capture-drop count **555 → 564**, and provider interruptions **1 → 5**. Counters are cumulative and can include transitions/expiry; these are not normalized failure rates or proof of a particular root cause.
- A bounded journal sample (last two hours, at most 2,500 records) contained 4 connection-ended messages, 1 tool deadline, 1 tool failure, 1 standby entry and 1 wake. It spans prior restarts and cannot be attributed solely to the latest code. Slowest observed successful tool: standby entry **2,669.9 ms**, followed by application launch **1,927.9 ms**. User speech and tool arguments were not copied.

### Detailed findings and solutions

#### J01 — Credentials reach audio and GUI helper processes (high)

**Evidence:** reproduced + live metadata. **Confidence:** 1.00.

**User impact:** Compromise or diagnostic dumping of a helper can expose credentials that the helper never needs.

**Cause:** NativeCompanionEngine.start omits env=, and GUI daemon autostart copies os.environ. Camera, screen capture and vision HUD launches also omit the shared sanitizer. The live daemon and its native audio child each contained 18 credential-named environment variables; only counts were inspected/reported, never values. The existing secret_env implementation is present and works, but these call sites bypass it.

**Source:** [audio/plugins/native_backend.py:156](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:156), [audio/plugins/native_backend.py:176](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:176), [skills/gui_control.py:91](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:91), [core/agent.py:369](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:369), [core/agent.py:536](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:536), [core/agent.py:1932](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1932), [core/secret_env.py:18](/home/g0pi/Projects/JARVIS-OMA/core/secret_env.py:18).

**Solution:** Apply sanitized_subprocess_env at every non-provider helper launch, preserving only needed desktop/audio variables. Audit all subprocess paths through one launch utility. Restart affected helpers after the fix. No evidence of credential exfiltration was found; rotate credentials if exposure is independently suspected.

**Acceptance:** Inject synthetic credential keys and assert they are absent from every child environment, including GUI recovery/autostart. Recheck helper environment counts without reading values.

**Isolated reproduction:** `test_native_helper_inherits_environment_without_filter; test_gui_daemon_autostart_copies_secret_variables` in [the audit probes](30_debugger_reproductions.py).

#### J02 — Verified coordinate clicking calls an unsupported driver tool (high)

**Evidence:** installed contract mismatch. **Confidence:** 1.00.

**User impact:** A desktop click can fail even when its coordinates and focus checks are correct.

**Cause:** The mandatory registry path forces verify_active=True, which selects click_window. Installed cua-driver 0.28.2 reports “Unknown tool: click_window”. Its supported click target schema also requires both pid and window_id, whereas this bridge constructs a window target without pid. Mocked tests accepted the invented atomic click contract.

**Source:** [skills/gui_control.py:232](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:232), [skills/gui_control.py:244](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:244), [skills/action_verification.py:17](/home/g0pi/Projects/JARVIS-OMA/skills/action_verification.py:17).

**Solution:** Negotiate the installed driver tool/schema contract at startup. Use supported PID/window targeting only where focus guarantees are actually available; otherwise return an explicit unavailable/fallback result. Implement a supported compositor-specific atomic adapter if strict atomic focus-and-input is required. Do not silently weaken the focus guard.

**Acceptance:** Validate generated calls against the installed driver schema and exercise one disposable-window click. Assert unsupported contracts are disabled before dispatch. The read-only command cua-driver describe click_window currently exits 64.

#### J03 — “Stop all” does not stop every JARVIS job type (high)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** The assistant can report stopped while personal Hermes helpers, task-runner steps, or model jobs continue.

**Cause:** The stop adapter stops the proactive runtime/orchestrator and evolution jobs, but does not stop _task_agents, _task_runner or _model_jobs. Their separate cleanup exists only on shutdown. The public tool description promises every active JARVIS-managed agent.

**Source:** [skills/skills.py:1183](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:1183), [proactive/runtime.py:300](/home/g0pi/Projects/JARVIS-OMA/proactive/runtime.py:300), [skills/skills.py:1091](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:1091), [skill_manifests/proactive.json:90](/home/g0pi/Projects/JARVIS-OMA/skill_manifests/proactive.json:90).

**Solution:** Introduce one admission latch and execution registry shared by every job producer. Stop admission first, cancel each job owner, retain uncertain/still-running work, and return a per-job outcome instead of unconditional stopped.

**Acceptance:** Start one fake job in each job manager; stop all must cancel each, reject new work until resume, and report any cancellation-resistant task accurately.

**Isolated reproduction:** `test_stop_all_omits_personal_helpers_tasks_and_model_jobs` in [the audit probes](30_debugger_reproductions.py).

#### J04 — Cancellation can orphan a desktop command subprocess (high)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** A canceled voice action can keep executing a CLI command after JARVIS has returned to conversation.

**Cause:** DesktopSkills._run handles its own TimeoutError but has no CancelledError/finally cleanup. Provider cancellation or the outer tool deadline cancels communicate without killing/reaping the process. The isolated fake-child probe observed no kill or wait call.

**Source:** [skills/skills.py:765](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:765), [core/tool_dispatch.py:28](/home/g0pi/Projects/JARVIS-OMA/core/tool_dispatch.py:28), [core/agent.py:1629](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1629).

**Solution:** Give command execution explicit child ownership, cancellation cleanup, bounded process-group termination and reaping. Distinguish short command processes from intentionally detached application launches.

**Acceptance:** Cancel a disposable long-running child and a child with a descendant; both must terminate within a bound, with their final status observable and no inherited pipe hang.

**Isolated reproduction:** `test_registry_command_cancellation_does_not_kill_child` in [the audit probes](30_debugger_reproductions.py).

#### J05 — Timed-out file operations can finish later without action-level tracking (high)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** A file change may occur after a timeout, while the assistant appears idle or a new request is being handled.

**Cause:** BoundedWorker correctly retains a running thread slot, but cancellation cannot stop its synchronous callable. run_skill_call detaches the canceled caller and has no persistent action record for the remaining work. The probe wrote a temporary file after the timeout had returned. A historical runtime log also contains one 45-second tool timeout; it does not prove that specific action later completed.

**Source:** [core/workers.py:49](/home/g0pi/Projects/JARVIS-OMA/core/workers.py:49), [core/tool_dispatch.py:35](/home/g0pi/Projects/JARVIS-OMA/core/tool_dispatch.py:35), [skills/skills.py:1346](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:1346), [core/agent.py:1464](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1464).

**Solution:** Promote mutating worker operations into tracked jobs with stable IDs, state=outcome_unknown/still_running, target-path reservations and eventual result events. Use cooperative cancellation boundaries or isolated workers where safe. Never release action ownership just because its waiter timed out.

**Acceptance:** A canceled running mutation remains visible, blocks conflicting mutations, and publishes its eventual completion/failure. Stop-all must report work that cannot be preempted.

**Isolated reproduction:** `test_running_file_work_survives_tool_timeout` in [the audit probes](30_debugger_reproductions.py).

#### J06 — Manual interruption can resume the same old voice reply (high)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** Pressing the interrupt control can silence playback briefly, then the same answer starts speaking again.

**Cause:** interrupt_audio clears playback and advances the local generation, but does not set the existing _drop_interrupted_audio gate or cancel the remote response. Later PCM from the still-active provider turn is assigned the new local generation and accepted. SIGUSR2 has a second, narrower path that calls only stop_speaking.

**Source:** [core/agent.py:439](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:439), [core/agent.py:1564](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1564), [core/agent.py:1834](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1834), [core/agent.py:1923](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1923), [audio/downstream.py:29](/home/g0pi/Projects/JARVIS-OMA/audio/downstream.py:29).

**Solution:** Unify IPC, signal and local interrupt behavior into a turn-cancellation transition. Suppress old-turn PCM until a verified provider turn boundary and use a supported provider cancellation mechanism where available. Maintain generation fencing in the unlocked controller/plugin layers.

**Acceptance:** Feed late PCM after a manual interrupt and assert no resumed output; then a new confirmed turn must play normally. Repeat for the signal and IPC entrypoints.

**Isolated reproduction:** `test_manual_interrupt_accepts_late_old_turn_pcm_again` in [the audit probes](30_debugger_reproductions.py).

#### J07 — Audio failure during standby can leave wake-up stuck (high)

**Evidence:** reproduced + control-flow inspection. **Confidence:** 1.00.

**User impact:** After the audio helper dies or its device disappears in standby, saying “Hey Jarvis” may never wake the assistant.

**Cause:** The live supervisor includes monitor_health, but the EnterStandby branch directly awaits listen_for_wake_word. That listener waits indefinitely on the capture queue and never supervises engine health. Exceptions raised inside that except branch also bypass sibling recovery handlers.

**Source:** [core/agent.py:2020](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:2020), [audio/plugins/standby.py:126](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:126), [audio/plugins/native_backend.py:389](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:389).

**Solution:** Supervise wake detection and audio health together, with device recovery that preserves standby and keeps cloud audio disconnected. Return to a local recoverable-error state when recovery is exhausted.

**Acceptance:** Fail the owned helper and disconnect/reconnect a device during standby; local capture must recover or visibly report failure, without requiring a service restart or sending standby audio to the cloud.

**Isolated reproduction:** `test_standby_does_not_observe_failed_audio_health` in [the audit probes](30_debugger_reproductions.py).

#### J08 — Desktop mutations are not serialized across simultaneous tool calls (high)

**Evidence:** reproduced boundary gap. **Confidence:** 1.00.

**User impact:** Two requests can fight over focus, clipboard contents or pointer position, allowing input to reach the wrong surface.

**Cause:** Every provider function call starts an independent task; routed actions also use gather. The verification decorator has no desktop-wide action lock. ContextVar isolates metadata, not the compositor. A controlled two-action probe entered both mutation bodies simultaneously. Wrong-window typing was not attempted on the real desktop.

**Source:** [core/agent.py:1429](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1429), [core/agent.py:1672](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1672), [skills/action_verification.py:16](/home/g0pi/Projects/JARVIS-OMA/skills/action_verification.py:16), [skills/system_control.py:321](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:321).

**Solution:** Serialize foreground focus/input/clipboard transactions through one desktop action coordinator, including focus and workspace changes. Acquire it before observation and hold through verification. Keep independent read-only tools concurrent. External focus changes still require exact-target adapters and fail-closed checks.

**Acceptance:** Race two different target-window actions and a clipboard paste; each transaction must finish before the next begins, and injected external focus theft must block or safely recover.

**Isolated reproduction:** `test_gui_verification_boundary_allows_overlapping_mutations` in [the audit probes](30_debugger_reproductions.py).

#### J09 — Wake-word initialization and inference block the conversation loop (medium)

**Evidence:** code-confirmed + historical timing. **Confidence:** 1.00.

**User impact:** Entering standby can pause voice/IPC responsiveness; wake inference also shares the control loop.

**Cause:** prepare is async but constructs OpenWakeWordDetector synchronously, before setting the standby request latch. Every prediction runs synchronously in the wake loop. The bounded two-hour log sample contains an enter_standby duration of 2669.9 ms; that duration includes the whole tool and is not an isolated model-load measurement.

**Source:** [audio/plugins/standby.py:107](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:107), [audio/plugins/standby.py:119](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:119), [audio/plugins/standby.py:143](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:143).

**Solution:** Create, reset and run the detector on one dedicated serial worker. Gate microphone upload as soon as standby is accepted, prepare locally, and handle preparation failure explicitly. Warm the detector in bounded background work if resource use permits.

**Acceptance:** Inject slow initialization/prediction and verify event-loop heartbeat, IPC deadlines and the privacy gate remain responsive; all detector access must stay on its owner thread.

#### J10 — A resumed conversation permanently runs out of tool slots (medium)

**Evidence:** reproduced design limit. **Confidence:** 1.00.

**User impact:** After 256 distinct calls, all new actions fail until a fresh conversation is created.

**Cause:** The cache intentionally retains identity tombstones for safety, has a default capacity of 256, and never retires delivered identities during resumption. The rejection tells the user to start fresh, but the live handler neither rotates the conversation nor exposes a dedicated fresh-session recovery path.

**Source:** [core/connection.py:18](/home/g0pi/Projects/JARVIS-OMA/core/connection.py:18), [core/connection.py:38](/home/g0pi/Projects/JARVIS-OMA/core/connection.py:38), [core/connection.py:90](/home/g0pi/Projects/JARVIS-OMA/core/connection.py:90), [core/agent.py:1655](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1655).

**Solution:** Use a bounded durable action journal with explicit session namespaces, or rotate at a quiet, action-free boundary before capacity is reached. Keep completed identity evidence across uncertain reconnects; never solve this by forgetting effects and replaying them.

**Acceptance:** Run more than 256 calls across reconnects; new actions remain available and duplicate effects never execute twice.

**Isolated reproduction:** `test_completed_calls_exhaust_cache_after_256_actions` in [the audit probes](30_debugger_reproductions.py).

#### J11 — A second daemon can replace a live IPC endpoint (medium)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** The controller can connect to a different daemon while the first daemon still owns audio; shutdown of one instance may remove another instance’s socket path.

**Cause:** start unlinks an existing path without checking whether a live owner is listening. close removes the path without checking inode ownership. In a private temporary directory, the second server replaced the endpoint while the first remained serving.

**Source:** [core/ipc.py:76](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:76), [core/ipc.py:300](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:300).

**Solution:** Acquire a per-user instance lock before audio startup. Probe ownership and liveness before replacing stale sockets; record the bound inode and unlink only that inode. Reject a second live instance cleanly.

**Acceptance:** Start two instances against one private runtime path. The second must refuse, the first must stay reachable, and stale-socket recovery must still work.

**Isolated reproduction:** `test_second_ipc_server_replaces_first_live_endpoint` in [the audit probes](30_debugger_reproductions.py).

#### J12 — IPC limits cover subscribers but not idle command clients (medium)

**Evidence:** reproduced. **Confidence:** 1.00.

**User impact:** Buggy or hostile same-user clients can accumulate sockets/tasks and degrade control responsiveness.

**Cause:** The server adds every connection to _clients and waits on readline without a first-request deadline or global client admission cap. max_subscribers does not apply until subscribe. Four idle clients remained admitted with max_subscribers=1. This is a local-user availability boundary, not a demonstrated remote exploit.

**Source:** [core/ipc.py:90](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:90), [core/ipc.py:98](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:98).

**Solution:** Add a total client cap, a short request-read deadline, request shape/size validation and response-drain deadlines. Preserve the already bounded subscriber queues.

**Acceptance:** Many silent/partial clients must be rejected or expire while a healthy status request still completes within its budget.

**Isolated reproduction:** `test_idle_ipc_clients_bypass_subscriber_limit` in [the audit probes](30_debugger_reproductions.py).

#### J13 — Desktop session refresh cannot repair stale existing variables (medium)

**Evidence:** reproduced condition. **Confidence:** 1.00.

**User impact:** After a compositor/session change, voice may remain connected while Hyprland/Wayland controls fail.

**Cause:** recover_desktop_environment only fills missing variables and preserves stale existing values. The login hook imports fresh values into the systemd manager, then starts an already-active service; that does not alter the running process environment. A full graphical-session restart may restart the unit, so this finding applies to surviving services or bad overrides.

**Source:** [core/desktop_session.py:20](/home/g0pi/Projects/JARVIS-OMA/core/desktop_session.py:20), [scripts/desktop-session.sh:10](/home/g0pi/Projects/JARVIS-OMA/scripts/desktop-session.sh:10), [systemd/jarvis-oma.service:4](/home/g0pi/Projects/JARVIS-OMA/systemd/jarvis-oma.service:4).

**Solution:** Validate socket liveness and session identity, distinguish intentional configuration overrides from stale inherited values, and refresh/restart the controller at an idle boundary when the compositor epoch changes.

**Acceptance:** Simulate a new compositor socket with old environment variables while the voice service survives. Fresh desktop controls must use the new session without duplicate daemons.

**Isolated reproduction:** `test_desktop_recovery_retains_invalid_existing_identifiers` in [the audit probes](30_debugger_reproductions.py).

#### J14 — “Verified changes” can still contain a functional bug (medium)

**Evidence:** reproduced acceptance limitation. **Confidence:** 1.00.

**User impact:** An agent job can be announced completed even though its changed code produces the wrong result.

**Cause:** The independent verifier checks digests and syntax, deliberately avoiding arbitrary project code. Replacing add(a,b)=a+b with add(a,b)=0 passed and produced announcement_state=completed, while functional_verified remained false. Existing scope labels are honest, but the completion headline is stronger than the evidence.

**Source:** [proactive/verification.py:304](/home/g0pi/Projects/JARVIS-OMA/proactive/verification.py:304), [proactive/verification.py:337](/home/g0pi/Projects/JARVIS-OMA/proactive/verification.py:337), [proactive/verification.py:383](/home/g0pi/Projects/JARVIS-OMA/proactive/verification.py:383), [orchestration/agent_orchestrator.py:298](/home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py:298).

**Solution:** Separate response_received, structurally_checked and acceptance_passed in UI/events. Add trusted predeclared task-specific acceptance checks, executed in an isolated worktree/sandbox with credentials removed and resource/network policy. Do not automatically run arbitrary agent-authored test configuration.

**Acceptance:** A syntactically valid wrong implementation must fail the trusted functional check and never appear as acceptance_passed. Structural-only work must be labeled as such.

**Isolated reproduction:** `test_structural_completion_can_pass_a_functional_regression` in [the audit probes](30_debugger_reproductions.py).

#### J15 — Typing/key tools cannot prove their intended effect (medium)

**Evidence:** code-confirmed functional gap. **Confidence:** 1.00.

**User impact:** Successful input is commonly returned as unverified; the model may retry and duplicate text or leave the user without a confirmed result.

**Cause:** The shared decorator accepts only effect_observed for non-window actions. type_text and press_key paths return success/dispatched and do not read the affected field or application state, so they are downgraded to unverified_effect. This is safer than false success, but readback/fallback execution is still missing. Some GUI actions intentionally change or close focus, which also needs action-specific postconditions.

**Source:** [skills/action_verification.py:39](/home/g0pi/Projects/JARVIS-OMA/skills/action_verification.py:39), [skills/system_control.py:364](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:364), [skills/system_control.py:383](/home/g0pi/Projects/JARVIS-OMA/skills/system_control.py:383), [skills/gui_control.py:398](/home/g0pi/Projects/JARVIS-OMA/skills/gui_control.py:398).

**Solution:** Use action-specific postconditions: accessibility field value for text, destination/tab/application state for shortcuts, and exact disappearance for close. Preserve dispatched=true/attempt ID when effects are uncertain and prohibit automatic replay of input.

**Acceptance:** Verify text once, handle focus-changing shortcuts correctly, and assert that an unverified first attempt does not lead to duplicate typing without a new observation.

#### J16 — Fast local audio acknowledgements do not establish fast voice responses (medium)

**Evidence:** measured gap + design limitation. **Confidence:** 0.99.

**User impact:** Voice can still feel slow or interrupted despite a near-zero audio send-lock wait.

**Cause:** The latest live snapshot had transcript-observation-to-first-PCM p50=1247.374 ms and p95=4377.964 ms over 12 samples, while audio writer wait p95 was 0.003 ms. Rebuffer events rose from 1 to 3 and capture-drop counters from 555 to 564 between snapshots. These small, opportunistic samples are not an acoustic benchmark; drops can include deliberate expiry and startup/standby transitions. Native local barge-in remains disabled, so speech interruption depends on provider detection. The scheduler still allows a one-second in-flight audio write, versus the suggested 150 ms; its 150 ms capture-expiry check runs before that write.

**Source:** [core/response_metrics.py:21](/home/g0pi/Projects/JARVIS-OMA/core/response_metrics.py:21), [audio/plugins/native_backend.py:83](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:83), [core/audio_scheduler.py:23](/home/g0pi/Projects/JARVIS-OMA/core/audio_scheduler.py:23), [core/agent.py:850](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:850).

**Solution:** Instrument correlated speech-end, send-start/end, provider-first-PCM, native-first-render and interruption-detection timestamps. Measure latency distributions under real conversation and contention before tuning budgets. Consider an AEC-aware local duck/barge-in plugin with false-positive tests; preserve the locked core.

**Acceptance:** Run a controlled audible conversation test with interruptions, double-talk, vision, long tools and network jitter. Publish end-to-end p50/p95, cut-off/false-interruption rate, and stage-level latency instead of treating the 11.6 ms local flush acknowledgement as reply latency.

#### J17 — Filesystem mutation checks retain a path-substitution race (medium)

**Evidence:** conditional code risk; previously documented. **Confidence:** 0.90.

**User impact:** A concurrent process changing parent paths between validation and mutation could redirect an authorized operation.

**Cause:** Protection checks resolve path identities, then mutation uses pathname operations later. Existing CRITICAL_PATHS checks and Python deletion safeguards are valuable but are not an end-to-end descriptor-pinned transaction. No destructive exploit was attempted; this residual limitation was already documented in report 28.

**Source:** [filesystem/filesystem.py:45](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:45), [filesystem/filesystem.py:500](/home/g0pi/Projects/JARVIS-OMA/filesystem/filesystem.py:500), [report/28_REMAINING_AUDIT_REPAIR_LOOP.md:39](/home/g0pi/Projects/JARVIS-OMA/report/28_REMAINING_AUDIT_REPAIR_LOOP.md:39).

**Solution:** Pin trusted parent directories using descriptor-relative operations and O_NOFOLLOW, revalidate identities at publication, and constrain delegated mutations to isolated roots. Preserve CRITICAL_PATHS and recoverable staging behavior.

**Acceptance:** Use a disposable adversarial parent-swap fixture and assert operations cannot reach protected/outside paths. Test rollback and retained recovery copies as well.

#### J18 — Memory recall repeatedly scans and synchronizes whole collections (low)

**Evidence:** code-confirmed scaling risk; unbenchmarked. **Confidence:** 0.90.

**User impact:** Memory tools may become slower as sessions and documents grow; no current corpus-size slowdown was established.

**Cause:** Recall lists all memory/fact entries and scans trust on each call. Semantic search reconstructs document and conversation collections and synchronizes every namespace before embedding the query. This runs on a bounded serial worker, protecting the event loop, but long recalls can queue other memory work.

**Source:** [memory/codes-dev/jarvis_memory/bridge.py:164](/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/bridge.py:164), [memory/codes-dev/jarvis_memory/bridge.py:196](/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/bridge.py:196), [memory/codes-dev/jarvis_memory/bridge.py:219](/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev/jarvis_memory/bridge.py:219), [skills/skills.py:1217](/home/g0pi/Projects/JARVIS-OMA/skills/skills.py:1217).

**Solution:** Benchmark synthetic corpora first. Move indexing/trust scanning to admission/update time, maintain incremental vector revisions, and query bounded lexical/vector indexes. Retain provenance, user-correction priority and untrusted-content gates.

**Acceptance:** Measure cold/warm recall at increasing corpus sizes; enforce bounded queue wait and verify deleted/corrected facts do not return.

#### J19 — Camera transport updates a file much faster than cloud vision consumes it (low)

**Evidence:** code-confirmed optimization candidate. **Confidence:** 0.95.

**User impact:** Camera mode performs avoidable file updates and helper work; its contribution to voice jitter has not been measured.

**Cause:** The camera streams 15 FPS MJPEG into an atomically replaced file while the cloud loop uses at most 1 FPS. The target is normally XDG_RUNTIME_DIR and may be memory-backed, so calling this proven physical disk thrashing would be inaccurate. The preview may legitimately need a higher frame rate.

**Source:** [core/agent.py:335](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:335), [core/agent.py:364](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:364), [core/vision_stream.py:12](/home/g0pi/Projects/JARVIS-OMA/core/vision_stream.py:12).

**Solution:** Separate preview and cloud consumers, keep only the newest frame in a bounded memory buffer, and produce preview frames at the UI-required rate. Profile before replacing the current mechanism.

**Acceptance:** Compare camera-on/off CPU, file-update count, capture drops and audio latency while preserving preview brightness and camera lifecycle.

## Architecture diagnosis

The audio callbacks and priority scheduler have useful isolation, but the system does not yet have one owner for an action from request through cancellation and verified effect. Provider tasks, synchronous workers, subprocesses, GUI actions and delegated jobs each maintain separate lifecycles. This permits canceled or supposedly stopped work to continue outside the state shown to the user.

The GUI issue is a concrete contract failure: mocks model a tool the installed driver does not implement. Local focus checks improve safety but do not serialize competing actions or make an external focus change atomic. Adding more prompt instructions cannot repair those execution boundaries.

Voice interruption is similarly split between local playback flushing, controller state and provider turn state. A local generation fence works only if late provider bytes are correctly associated with the canceled turn. Standby also leaves the normal audio-health supervisor behind.

The reduced tool catalog and syntax verifier improve startup context and evidence quality, but need lifecycle recovery and explicit evidence levels. A passing syntax check must not become a functional completion claim. Memory provenance defenses were observed; no actual memory-contamination incident was established in this audit.

## Ordered implementation plan

| Order | Work | Findings | Exit condition |
|---|---|---|---|
| 1 | Close helper credential inheritance | J01 | Apply the existing sanitizer consistently and validate child environments. |
| 2 | Restore trustworthy stop/cancel behavior | J03, J04, J05 | Unify job ownership, admission and cancellation; keep uncertain effects visible. |
| 3 | Repair voice interruption and standby recovery | J06, J07, J09 | Unify turn cancellation, supervise standby health and move detector work off-loop. |
| 4 | Make GUI actions match the installed driver and execute serially | J02, J08, J15 | Contract-test real schemas; coordinate foreground actions and add action-specific readback. |
| 5 | Harden daemon/session lifecycle | J10, J11, J12, J13 | Add safe cache rotation, singleton ownership, client deadlines and compositor epoch refresh. |
| 6 | Separate structural evidence from accepted outcomes | J14 | Use explicit evidence levels and trusted isolated functional checks. |
| 7 | Measure actual voice responsiveness | J16 | Correlate all latency stages and perform controlled acoustic acceptance before tuning. |
| 8 | Close residual mutation races and optimize measured bottlenecks | J17, J18, J19 | Harden path ownership, then benchmark indexing and camera transport. |

Apply fixes in small reviewable groups. Convert each defect reproduction into a regression that expects the repaired behavior. Preserve `core/secret_env.py`, `CRITICAL_PATHS`, descriptor/O_NOFOLLOW protections and all seven locked voice files. Voice repairs belong in the controller, extension or plugin layers; autonomous/evolution verification runs belong in isolated worktrees.

## Verification and coverage limits

- **Fresh isolated audit checks: 13 passed.** These deliberately assert the current faulty/limited behavior. Passing them means a finding was reproduced, not that JARVIS is fixed.
- **Fresh existing regressions: 138 passed + 30 subtests.** Covered session/cache logic, audio scheduling/contention, IPC/backpressure, native backend, standby, GUI action boundaries, tool tiers and workspace verification.
- **Voice lock: all 7 protected files verified intact.**
- Earlier implementation validation in this conversation: **1,300 passed + 385 subtests; 2 opt-in tests skipped**. That full suite was not rerun for this audit. Its passing result does not invalidate the new reproductions.
- Earlier silent-device acceptance measured 11.6 ms maximum local flush acknowledgement and zero starvation during its 30-second paced test. Those measurements did not include speech recognition, provider reasoning, double-talk, or end-to-end audible response.
- No real click/type/scroll was performed, no microphone recording was started, no network fault was injected, and no external account write or real agent task was used. Suspend/resume, dock/Bluetooth device churn, hour-long conversations, wake false-positive rates, and acoustic AEC quality still require controlled acceptance.
- Filesystem path-substitution risk and memory/camera scaling findings are code-level risks; no destructive exploit or production-scale benchmark was attempted.

### Reproduce the audit checks

```sh
.venv/bin/pytest -q report/30_debugger_reproductions.py --tb=short
python3 scripts/verify_voice_lock.py
```

Artifacts: [machine-readable report](30_DEBUGGER_AUDIT_2026-10-27.json) · [isolated reproductions](30_debugger_reproductions.py).
