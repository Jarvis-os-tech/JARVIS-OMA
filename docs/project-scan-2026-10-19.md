# JARVIS-OMA project scan — 19 October 2026

## Result

The running service was healthy at inspection, and the offline suite passed. Source review and controlled failure simulations nevertheless identified nine reliability issues. The original scan did not change application code, restart the service, launch model agents, make phone calls, or change desktop settings. Dated updates below record subsequent repairs.

This is a review of the current working tree, including substantial uncommitted work. It is not a certification of every live integration or an exhaustive security audit.

## Verification

- Full offline suite with local IPC permitted: **603 passed, 2 skipped, 188 subtests passed**, in 28.42 seconds. The skipped checks are opt-in real Linux sandbox tests. Output: `/tmp/jarvis-scan-pytest-host.log`.
- The initial restricted run encountered local IPC restrictions and hit its 180-second limit. Those results are superseded by the complete run with local sockets available.
- Startup configuration check passed without opening audio or network connections.
- All 33 installed Python packages passed dependency compatibility checks.
- Parsed 47 Python files in the primary implementation directories and 21 files in the active memory implementation without syntax errors. Vendored projects were not exhaustively reviewed.
- All **163 registered tool declarations** resolve to callable adapters with compatible argument names. This checks wiring, not authentication, GUI accessibility, or real action success.
- Launcher/service-install shell scripts passed syntax checks.
- Live service: active/running, PID 117882, zero systemd restarts. Local status: listening, microphone unmuted, no active jobs, AEC input bound, zero reported output underflows/callback errors/dropped capture frames at that snapshot. These counters do not measure end-to-end conversation latency.

## Findings in priority order

### 1. P1 — An optional phone listener can interrupt the entire voice connection

**Update after the scan:** fixed on 19 October 2026. The phone monitor now retries exceptions and normal listener exits with bounded backoff while remaining alive alongside voice. Listener cancellation propagates and reaps its subprocess. Five new regression tests cover recovery without cancelling audio, absent telephony, cancellation during retry, and subprocess cleanup. The focused voice/phone suite passed: 52 tests and 2 subtests. Other dated repairs are recorded below.

Sources: [phone monitor](../core/agent.py#L714), [supervisor](../core/agent.py#L44), [worker registration](../core/agent.py#L1343).

The phone monitor catches a listener exception and returns. It also returns normally if the D-Bus monitor reaches EOF. `supervise()` cancels every sibling task whenever any worker ends, so an optional phone failure cancels microphone sending, response receiving and the other connection workers. A normal return can repeatedly reconnect without consuming the exception retry budget.

**Reproduced:** made the phone listener raise a controlled exception; the independent audio worker was cancelled immediately. This is a confirmed failure path, not proof that it caused the user's earlier voice interruption.

**Fix:** give optional integrations their own retry/backoff lifecycle; a phone outage must not complete the voice supervisor. Add an integration test with unavailable telephony.

### 2. P1 — “Stop all” misses teams that have not launched their first job

**Update, 20 October 2026:** fixed. Stop intent now blocks new individual jobs and teams immediately, cancels teams before remaining jobs, and survives cancellation of the requesting voice tool. Resume explicitly reopens admission after cancellation finishes. Cancelling terminal setup drains in-flight tmux commands and removes the owned session. Six new regression tests cover queued teams, running stages, persisted stop handling, setup cleanup, interrupted stop requests and in-flight tmux commands. A real temporary tmux test confirmed a cancelled team, zero launched jobs and no remaining session. Related suites passed: 69 tests plus 21 subtests for stop/proactive paths, and 136 tests plus 23 subtests for orchestration/voice/skills (two opt-in sandbox checks skipped).

Sources: [stop_all](../proactive/runtime.py#L301), [team setup](../orchestration/desktop_execution.py#L194), [team scheduler](../orchestration/agent_orchestrator.py#L279).

`stop_all()` cancels a snapshot of individual `workers`, but never cancels `team_workers`. During tmux setup a team can exist without an individual job. The stop command then reports success while setup can continue and launch an agent. The team scheduler does not check the proactive stop flag.

**Reproduced:** with an active team and an empty individual-job map, stop returned `stopped` without invoking team cancellation.

**Fix:** stop admission and cancel teams before individual jobs; verify no team can launch a subsequent stage after stop returns.

### 3. P1 — A shared-pane monitoring failure can leave an agent running without supervision

**Update, 21 October 2026:** fixed. Owned panes and sessions are now cleaned up on monitoring and partial-setup failures, terminal events are emitted consistently, and an unconfirmed cleanup leaves the job or team in `cleanup_failed` so the workspace remains reserved. Completion reports also retire the live agent process before releasing its workspace while leaving dead tmux output inspectable.

Source: [pane error handling](../orchestration/desktop_execution.py#L390).

If capture or another monitoring operation fails after launch, the exception handler marks the job failed but does not terminate its pane. The team then stops tracking that stage, and the workspace is considered free because reservation checks use job state. The previous agent may still be editing it.

**Reproduced:** a controlled capture failure produced a failed job with no pane/session cleanup call.

A related launch path at [line 222](../orchestration/desktop_execution.py#L222) records a failed team without emitting a team event or cleaning up partial session setup. A mocked tmux setup failure left the notification queue empty.

**Fix:** track pane/session ownership through cleanup, preserve workspace reservation until termination is confirmed, and emit terminal events on every exit path.

### 4. P2 — Standalone interactive jobs do not detect a finished task

**Update, 21 October 2026:** fixed. Standalone interactive jobs now use the same bounded completion-report protocol as team panes. Reports are descriptor-validated, limited to 4 KiB, reject symlinks and malformed states, and separate task completion from terminal inspectability. A task is not released until its live process has been retired successfully.

Source: [standalone completion polling](../orchestration/desktop_execution.py#L302).

The shared-team path uses a completion report, but ordinary visible `delegate_agent` jobs only complete when the entire TUI process exits. A native agent returning to its prompt after finishing the assignment remains marked running, keeps its workspace reserved, and eventually times out and loses its terminal session.

**Evidence:** source inspection; no live model call was needed or performed during this scan.

**Fix:** use an explicit task-completion protocol for standalone interactive delegation too, separately tracking the lifetime of the inspectable terminal.

### 5. P2 — Several system controls report success without a successful operation

**Update, 20 October 2026:** repaired in the system-control integration. Native state readback now verifies settings instead of trusting suppressed plugin errors. Unknown state and accepted commands without evidence remain explicit errors or unverified results. Real read-only checks confirmed audio, microphone, brightness, Wi-Fi, Bluetooth, power profile, notifications and theme retrieval on this desktop. See [current system integration](system-control-and-information.md).

Sources: [notification actions](../skills/system_control.py#L1091), [theme actions](../skills/system_control.py#L1134).

Notification mutations discard command failure codes. Theme changes can return success after a failed fallback command, and `control_theme('dark')` even returns success when neither backend exists. This supplies false evidence to the voice model.

**Reproduced:** a notification backend returning exit code 1 still yielded `status: success`; a theme call with every backend absent also yielded success.

**Fix:** check exit codes, return precise errors, and read back state where supported before claiming the requested setting took effect.

### 6. P2 — Explicit night-light on/off commands can do the opposite

**Update, 20 October 2026:** repaired. Explicit night-light and DND state requests no longer blindly toggle. Already matching states remain unchanged. Explicit night-light initialization can use the plugin's temperature setter when its daemon is unavailable; resulting temperature still requires verification. Failure, missing-state and idempotency regressions are covered in `test_plugin_control_reliability.py`.

Source: [night-light dispatch](../skills/system_control.py#L809). A similar fallback exists for DND in [notification controls](../skills/system_control.py#L1107).

Night-light `on`, `off`, and `toggle` all call `set-nightlight-toggle`. Repeating “turn it on” can turn it off. The notification shell fallback also maps both DND on and off to a toggle.

**Reproduced:** recorded identical backend commands for night-light on and off.

**Fix:** use explicit state setters, or compare current and requested state before toggling, then verify the result.

### 7. P2 — Budget mode conflicts with the native OpenCode workflow

**Update, 21 October 2026:** fixed. Budget-mode OpenCode stages now use the existing model-capable batch route, and every normalized team assignment is preflighted before a team record, worker, terminal session, or earlier stage can launch.

Sources: [budget model assignment](../orchestration/model_policy.py#L14), [native OpenCode launcher](../orchestration/desktop_execution.py#L66), [default assignments](../orchestration/personas.py#L19).

Budget mode requires and assigns an OpenCode model override, while the native OpenCode launcher rejects every model override. Default goals use native mode. Even with both budget environment variables supplied, the QA stage fails; earlier stages may already have incurred model usage.

**Reproduced:** applying budget policy with explicit model identifiers succeeded, then constructing the OpenCode native command raised `Native OpenCode uses its configured model; per-task overrides require batch mode.`

**Fix:** validate the entire execution plan before launching any stage and implement a compatible native model-selection route or explicitly select a supported execution mode.

### 8. P2 — GUI active-window verification can fail open

**Update, 21 October 2026:** fixed and security-hardened. Active-window actions require canonical Hyprland addresses, valid observed bounds, and an atomic driver operation bound to the exact target window. Missing, ambiguous, changed, or mismatched focus evidence fails closed. Bounds and focus evidence are reported separately.

Sources: [focus verification](../skills/gui_control.py#L225), [click result](../skills/gui_control.py#L157).

When `verify_active=True`, an unavailable active-window query does not stop the click. Checks also compare only process IDs, which cannot distinguish multiple windows belonging to the same process. The response reports `target_verified: true` based on the requested options rather than verified focus.

**Reproduced:** provided an observed target but made the active-window query return no result. The simulated click was still dispatched and marked target-verified.

**Fix:** require positive window-level focus evidence when requested; return an unverifiable-state error otherwise. Separate bounds verification from focus verification in results.

### 9. P2 — Some tool paths can still block the voice event loop

**Update, 21 October 2026:** fixed for the reported paths. Phone contact/history reads and bounded file verification now run in worker threads. Content matching scans at most 1 MiB and records truncation. Camera start/stop subprocess work runs off the event loop with serialized, cancellation-safe lifecycle handling.

**Partial update, 20 October 2026:** the new system-information readers and notification-history reads run outside the voice event loop; new commands have bounded timeouts/output and cleanup. This does not repair every older synchronous camera or phone-contact path described below.

Sources: [phone contacts/history adapters](../skills/skills.py#L2488), [file verification](../skills/ground_truth.py#L83), [camera startup](../core/agent.py#L117), [camera stop](../core/agent.py#L148).

Phone adapters call synchronous JSON file readers directly. File verification reads an entire file synchronously, without a size bound. Camera switching invokes synchronous subprocess operations with waits of up to one second on the conversation event loop. Slow disk or hardware operations therefore delay other tasks despite those tasks being scheduled concurrently.

**Evidence:** source inspection. Actual latency under live microphone load was not measured in this scan.

**Fix:** use bounded workers for disk operations and asynchronous subprocess lifecycle handling for camera control. Add event-loop responsiveness tests for slow files and hardware commands.

## Architecture gaps and maintenance notes

- The current default workflow is a fixed sequential Hermes → Claude → OpenCode → Claude pipeline. It runs alongside conversation; it is not a general planner that dynamically selects and parallelizes every specialist.
- Agents receive a bounded memory snapshot, not a shared full-history retrieval interface.
- Team state is in memory and is lost on restart. Completion reports are agent assertions, not independent acceptance gates.
- Harness² is not integrated; the local orchestration documentation lists it as future work. Artemis-related local files do not establish Harness² integration.
- The configured-model profile preserves existing agent setups, but does not guarantee cheap models or enforce a monetary cap.
- **Update, 21 October 2026:** manifest mirror drift is fixed. All 21 canonical manifests in `skill_manifests/` have byte-identical mirrors in `skills/manifests/`, with a regression test covering both filename sets and every parsed manifest.
- `tests/README.md` still advertises 239 tests; the current default suite collected 605 test items.

## Suggested repair order

1. Isolate optional phone failures from voice and eliminate blocking work on the voice event loop.
2. Correct team cancellation, pane cleanup, failure notifications and standalone completion tracking.
3. Correct control result reporting, explicit on/off behavior and GUI verification.
4. Validate budget execution plans before any model calls.
5. Add regression coverage for these reproduced failure paths, then perform a controlled live voice-plus-background-agent test.
