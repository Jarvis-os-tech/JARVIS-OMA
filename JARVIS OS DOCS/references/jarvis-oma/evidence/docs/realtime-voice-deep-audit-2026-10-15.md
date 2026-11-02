# Realtime voice: deeper codebase audit

15 October 2026. Companion to [the first audit](realtime-voice-audit-2026-10-15.md). Three additional agents reviewed configuration/audio, tools/background jobs, and memory/IPC. The root reviewer checked integration paths and reproduced typed-message loss. Runtime code was not changed and services were not restarted.

## First repair group implemented

The current working tree now fixes D01–D04: saved settings survive absent CLI overrides, resolved settings reach runtime, 24 kHz playback and automatic VAD are enforced until alternatives exist, and invalid settings fail before audio acquisition. Local interruption policy also follows NO_INTERRUPTION.

Startup initializes cleanup resources before acquisition. Audio opens are transactional, missing/inactive streams fail health checks, and recovery makes at most retries + 1 reopen attempts with backoff before exiting explicitly. Owned streams are closed even after partial failure; cleanup errors do not replace the original startup exception. Repository service templates and run.sh use normal process scheduling instead of requiring whole-process realtime privileges.

Validation: 119 targeted configuration, startup, recovery, audio, echo and session tests passed. Shell syntax and scoped whitespace checks passed. systemd-analyze user-unit verification could not complete because this sandbox rejects required socket options. The installed user service has not been reloaded or restarted; these changes are source changes pending runtime activation and live device verification.

## Second repair group implemented (16 October 2026)

Microphone callbacks now copy into a bounded producer buffer, coalesce event-loop wakeups and discard expired frames. Memory operations, session capture, file operations, todo storage and proactive persistence run on bounded serial workers. The live response handler queues memory and greeting writes, so disk latency cannot pause receipt of the next audio response. Proactive ticks remain owned across cancellation and worker shutdown waits for in-flight jobs.

Background tool, agent-job and proactive notices now use a bounded queue. The sender waits for the current model turn and local playback to finish before submitting each notice as a new turn, and keeps unsent notices across a connection renewal.

Live microphone testing confirmed most replies now finish. Intermittent crackling remained during Jarvis speech, so playback now waits for a short configurable cushion of PCM frames and fades across starvation/recovery edges. Rebuffer events are counted, logged, and exposed in IPC status for live diagnosis. The listener reported less crackling after these changes, but some remained.

During a silent-listener test, the audio state entered `barged_in` twice. The local microphone voice gate can mistake speaker echo for user speech and duck or flush Jarvis in the middle of words. Local barge-in is now opt-in (`audio.local_barge_in=false` by default); Gemini Live's interruption events still handle actual user speech.

The active `config.toml` had overridden the improved playback default with `playback_latency_ms=20`, so earlier default changes had not increased the live buffer. It now uses 100 ms. The launcher also forced PipeWire to a 128/48000 period (2.7 ms), much shorter than the 20 ms Python audio frames; it now requests 1024/48000 (21.3 ms). A temporary transcript timeline correlated user speech, model response boundaries, interruptions, and playback warnings. In the final marked live test, the listener reported no crackle, while IPC reported zero playback rebuffer and callback errors. Transcript logging was then disabled again in the active config.

On October 16, a later session recorded two rare playback rebuffers with zero output callback errors. A 240 ms network cushion reduced the audible issue but still rebuffered three times, including once at its former 320 ms cap. The cushion is now 320 ms at startup and adds 80 ms after a rebuffer, up to 600 ms for that session. Rebuffer logs record only the age of the last incoming audio packet, without speech content, to distinguish network gaps from device callback failures. The user reported no crackle during the subsequent live test; IPC showed zero playback rebuffers and zero output callback errors afterward.

On a later interruption-focused test, the listener reported crackle when speaking over Jarvis. The active VAD configuration had high start/end sensitivity, only 150 ms prefix padding and a 300 ms end-of-speech pause; it now uses low sensitivities, 300 ms padding and an 800 ms pause. Barge-in now fades the next queued speech waveform with a raised-cosine edge rather than holding a single sample. The previously unused `playback_cushion_s` now controls network prebuffering independently of hardware latency; the active value is 160 ms. The final live interruption test reported no crackle and zero rebuffer or output-callback errors. Diagnostic transcript logging was disabled afterward.

Offline validation covers audio buffering, worker cancellation and shutdown, proactive SQLite contention, and existing voice and skill behavior. The interruption change passed 115 focused tests, and the smoother speech onset passed 116. A later diagnostic-trace test passed independently; the full focused suite has an intermittent unrelated `--help` subprocess timeout under load. The final live conversation reported no crackle.

The remaining audit findings below include AEC route verification and task ownership. The numbered findings preserve the original audit evidence and reproduction locations; line numbers may have shifted after implementation.

## Most important new conclusion

Background notifications can themselves cut off speech, even if playback and networking are healthy. core/agent.py:213,234,289 sends proactive notices, job events, and late tool results as completed user turns. The provider's current documentation states that send_client_content with turn_complete=true interrupts generation. These notices need conversation-aware scheduling, not immediate insertion as new user speech.

This strengthens finding 11 in the first audit from a provider-behavior risk to a documented interruption mechanism. It does not prove a particular production cutoff came from a notification; log response boundaries and notification times to establish that.

Source: [Gemini Live capabilities, model comparison/client content](https://ai.google.dev/gemini-api/docs/live-api/capabilities). The same guide specifies 24 kHz output and the manual activity markers required when automatic detection is disabled.

## Additional findings

Priority P1 means fix before judging voice reliability or browser parity. P2 means a concrete correctness, resource, or growth issue that should follow. Configuration-triggered defects are distinguished from failures in the active configuration.

### D01 — P1: saved model, voice and skills settings are overridden

Location: core/agent.py:769–770,801–811,689–690.

Ordinary command-line defaults are passed as explicit configuration overrides. A saved model, voice, or skills.enabled=false can be replaced even when the user supplies no corresponding option. Connection setup also reads args.model/voice instead of the resolved configuration.

Offline reproduction: configured model='configured-model', voice='Kore', skills.enabled=false became gemini-3.8-live, Aoede, true under main's default overrides.

Fix: optional command-line overrides should default to None. Resolve defaults once in Config and consistently use the resolved values for validation, startup, status and connection setup. Preserve an explicit disable flag separately from an unspecified flag.

Regression: saved and environment settings survive a launch with no overrides; explicit options still win. A disabled skills configuration must not silently enable desktop actions.

### D02 — P1 when configured: output rate changes speech speed and pitch

Location: core/agent.py:366,629; audio/engine.py:536; audio/downstream.py:21.

Provider audio is 24 kHz PCM; the engine plays those samples at the configured output sample rate without resampling. Offline reproduction: 24,000 provider samples occupy 0.5 seconds at 48 kHz instead of one second.

Fix: enforce 24 kHz output until a real resampler exists, or resample before device-rate framing. Distinguish provider format from hardware format.

Regression: one second of a known tone retains duration and frequency at every supported output device rate. This defect does not affect a correctly configured 24 kHz output.

### D03 — P1 when configured: disabling automatic speech detection has no replacement

Location: core/agent.py:563–570,155–172.

vad.enabled=false disables provider speech detection. The audio sender never emits activity_start/activity_end markers. The provider requires those markers in this mode; there is no implemented manual turn boundary.

Fix: reject this mode with a specific configuration error until supported, or implement manual activity detection with speech prebuffering, coordinated start/end markers, and interruption semantics.

Regression: a manually bounded speech segment produces a response; no permanently open input turn or clipped onset.

### D04 — P1 when configured: invalid audio settings reach resource startup

Location: core/config.py:381; audio/engine.py:131,143.

Only memory configuration is validated. Offline reproduction: input_frame_ms=0 loads, then engine construction raises ZeroDivisionError. Types, positive rates and frame durations, valid gains, and coherent detection thresholds are not comprehensively checked.

Fix: validate all audio and speech-detection configuration before loading AEC or opening devices. Unsupported combinations should fail with a useful configuration error.

Regression: zero/negative durations, wrong types, unsupported output rates, and invalid ranges fail before resource acquisition.

### D05 — P1: filesystem operations can monopolize the voice loop

Location: skills/skills.py:949–951; filesystem/filesystem.py:142–172; filesystem/task_runner.py:64–98.

Async adapters directly execute synchronous filesystem operations. Content searches can inspect up to 5,000 files of up to 1 MiB each; recursive copies and deletions can be slow. Awaiting these adapters does not introduce a scheduling yield. Several task steps can finish without allowing voice work or cancellation commands to run.

Fix: bounded filesystem workers and cooperative cancellation at safe operation boundaries. Preserve per-workspace ordering where concurrent writes could conflict.

Regression: slow search/copy while speaking leaves capture age and event-loop lag bounded; cancellation stops later steps without corrupting the current file operation.

### D06 — P1: proactive polling can block voice on database locks

Location: proactive/runtime.py:95–105; proactive/events.py:65–74,175–176; core/agent.py:191–218.

The periodic proactive tick uses synchronous SQLite transactions on the voice event loop. Claiming work obtains a write transaction even with no pending events. SQLite's busy timeout is 30 seconds.

Offline reproduction: a real temporary write lock held for 200 ms caused a 231 ms event-loop heartbeat gap. This expands the first audit's blocking inventory beyond memory.

Fix: move proactive persistence to an owned worker; use bounded contention retries and avoid blocking voice while waiting for the database.

Regression: hold the database lock during repeated ticks; audio and session receiving must continue and the tick must fail/retry predictably.

### D07 — P2: a todo refresh synchronously waits for desktop commands

Location: skills/skills.py:1135–1152,1164–1182.

Todo writes synchronously notify the desktop through two subprocess calls, each allowing a one-second timeout.

Offline reproduction: two injected 150 ms commands produced a 301 ms heartbeat gap.

Fix: asynchronous notification subprocesses or an owned worker; coalesce refreshes and separate the data-write result from notification failure.

Regression: a stalled desktop refresh does not stop audio or undo a successful todo write.

### D08 — P1/P2: command cancellation leaves child processes alive

Location: skills/skills.py:513–528.

_run kills and waits for the process only on timeout. Coroutine cancellation escapes without terminating or reaping the command. Fixing session task cancellation alone will not fix this subprocess ownership gap.

Offline reproduction: cancel a harmless sleeping child command; its coroutine ends while the child remains alive. The reviewer explicitly killed and reaped the audit child.

Fix: bounded terminate/kill/reap cleanup for owned commands on cancellation and errors; handle helper process groups where necessary. Keep intentionally launched GUI applications under a distinct lifetime policy.

Regression: timeout, cancellation and shutdown leave no owned command or helper process behind.

### D09 — P2: filesystem task workers are missing from shutdown

Location: filesystem/task_runner.py:64–98,115–124; skills/skills.py:798–804.

TaskRunner creates workers but has no close path; DesktopSkills.close_agent_jobs closes other components without stopping these workers.

Offline reproduction: a fake filesystem step remained active after close_agent_jobs returned. The outer asyncio runner may later cancel tasks, but this component does not own a safe shutdown sequence.

Fix: stop accepting plans, request cancellation, await safe step boundaries with a deadline, and mark interrupted jobs accurately before closing dependencies.

Regression: shut down with queued and running plans; no later steps start and no workers outlive the component.

### D10 — P2: interactive delegated tasks cannot signal normal completion

Location: skills/skills.py:321; orchestration/desktop_execution.py:121–139.

The default desktop orchestrator detects the interactive composer to submit work, but considers work complete only when the terminal pane dies. A CLI that returns to its composer while keeping the pane alive is still marked running and eventually timed_out, retaining workspace reservations until then.

Offline state-machine reproduction: a submitted task with a completion display and idle composer, but a live pane, became timed_out. Real CLI integration remains to be verified.

Fix: use a supported structured completion signal or monitored one-shot execution protocol; do not infer success from arbitrary terminal text. Keep a terminal visible separately if desired.

Regression: successful work in a still-open terminal reaches completed and releases its workspace; a waiting approval prompt must remain pending rather than being treated as success.

### D11 — P2: memory stop/start can create duplicate or falsely running workers

Location: memory/codes-dev/jarvis_memory/service.py:65–97; memory/codes-dev/jarvis_memory/bridge.py:73,491.

stop() drops its thread handle after a timed join even if the worker remains alive. Extraction transport permits longer work than the stop deadline. A restart can create a second worker, or consume an old stop sentinel and exit while is_running remains true.

Offline reproduction: blocked worker, full one-item queue, stop(.001), then start() produced two live workers. The stale-sentinel path was also identified.

Fix: preserve ownership until confirmed exit, represent stopping explicitly, prevent premature restart, and coordinate extraction deadlines/cancellation with shutdown.

Regression: full queue, blocked extraction, timed-out stop and rapid restart never yield duplicate workers or a false running state.

### D12 — P2: startup loads lifetime conversation history into RAM

Location: memory/codes-dev/jarvis_memory/bridge.py:124–127,441; memory/codes-dev/jarvis_memory/session.py:152–153,342–356.

The bridge keeps a non-expiring session without consolidation. Session hydration loads every archived message. The 100-message trim happens only after a later successful exchange, so every restart pays the lifetime-history load first.

Offline reproduction: reopening an archive with 1,001 messages hydrated all 1,001 messages.

Fix: load a bounded recent window at startup while retaining the full archive for history queries. Use deterministic timestamp/ID ordering.

Regression: a large archive preserves all records on disk but loads only the configured context window.

### D13 — P2: slow IPC subscribers have unbounded outgoing data

Location: core/ipc.py:95–104.

Every state transition writes to subscribers without drain/backpressure, coalescing or a size limit. A stalled widget can accumulate obsolete state events.

Unit-level reproduction: a non-draining writer accumulated 1,575,000 bytes over 25,000 broadcasts. A real socket reproduction was blocked by sandbox socket restrictions; this is not a measured production leak rate.

Fix: per-client bounded delivery that coalesces state to the newest value and disconnects persistently slow consumers. Audio callbacks must never wait for the widget.

Regression: a non-reading subscriber cannot increase memory indefinitely or delay healthy clients.

### D14 — P2: IPC close does not own every connected client

Location: core/ipc.py:48–51,106–116.

A connected client can wait indefinitely before sending its first line. close() tracks subscribers only and therefore does not close that connection or await its handler.

Offline reproduction with the real handler and a pending StreamReader: close() returned while the handler and writer remained open. Event-loop teardown can eventually cancel it, but server cleanup itself is incomplete.

Fix: track all clients/handlers from acceptance, impose first-request and write deadlines, and close/cancel/await all clients during shutdown.

Regression: connect without sending a request, then close the server; all handlers and writers must terminate within the deadline.

### D15 — P2: typed input is lost on transport failure

Location: core/agent.py:174–189; skills/input_bar.py:378.

The bar acknowledges local queue acceptance. The sender removes the item before sending; on connection failure or cancellation there is no restoration or delivery status. Unlike agent-job notifications, this path has no requeue logic.

Root reproduction: enqueue one typed message and make send_client_content raise ConnectionError; the queue is empty afterward.

Fix: explicit pending/sending/delivered/failed state and message identity. Retry definitely unsent items; surface uncertain delivery when the transport might have accepted a send, rather than blindly duplicating user requests.

Regression: fail before send, cancel while waiting for the send lock, and disconnect after an ambiguous send. The UI must distinguish queued from delivered and avoid silent loss.

## Additional static concern needing a resource test

skills/input_bar.py:391–397 schedules server.shutdown but never explicitly server_close or joins the server thread. Old handlers capture a mutable owner whose token and closing flag change on reopening. Add repeated open/close tests and verify sockets, thread count and stale handler behavior before claiming a measured leak.

The extra check_skills instance in main is also never explicitly closed, but reviewers did not establish an active thread/database connection leak from its current constructors. Treat this as cleanup debt, not a proven crash cause.

## Implementation order across both audits

1. Fix lifecycle and startup failures from the first audit; resolve configuration once and validate it before opening resources (D01–D04).
2. Protect the voice loop: capture bounded at producer time, memory/filesystem/proactive work in owned bounded workers, async desktop refresh (D05–D07).
3. Repair conversation ownership: notification scheduling, old-response discard boundaries, session task ownership and command cleanup (D08).
4. Repair background completion and shutdown ownership (D09–D11, D14); preserve typed-input delivery state (D15).
5. Bound retained context and IPC delivery (D12–D13), verify device routing, and add playback timing/buffer measurements.
6. Run sustained live conversations with slow tools, locked databases, interrupted responses and network/device loss. Compare the same provider model, voice and instructions against the browser.

Each implementation change should include a regression for its stated failure. Passing ordinary happy-path tests is insufficient to establish realtime behavior.

## Test evidence and limitations

- The first audit's focused audio/echo/session run passed 75 tests.
- The deeper broad run selected 348 tests after excluding real-socket IPC/control/input-bar groups, whose socket facilities are restricted here. It recorded 345 passes, two skips, and one error caused by screenshot-test output targeting read-only /run/user/1000.
- Ordinary discovery stalled in the greeting/threaded test path. An adapted diagnostic runner with periodic event-loop ticks progressed through the broad run; even a minimal to_thread diagnostic did not complete normally in this restricted execution environment. Do not attribute that stall to a production daemon defect without reproducing outside this host.
- These results are not a full clean-suite pass. The audit used isolated offline reproductions for the specific findings above, plus code and provider-contract inspection.
- No live microphone session, deployment, daemon restart, external message, or runtime repair was performed in this deeper audit.
