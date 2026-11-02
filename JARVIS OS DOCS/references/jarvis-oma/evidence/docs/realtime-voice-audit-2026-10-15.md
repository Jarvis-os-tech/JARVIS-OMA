# Realtime voice daemon: audit and fix guide

Reviewed 15 October 2026. Three agents reviewed audio, session handling, and daemon startup independently. This is a guide, not an implementation change. Existing workspace changes were preserved.

Further findings are documented in [the deeper codebase audit](realtime-voice-deep-audit-2026-10-15.md), including configuration overrides, unsupported manual speech detection, background worker cleanup, and confirmed provider notification interruption semantics.

## First repair group status

Implemented in the working tree: configuration/startup validation and saved-setting precedence; partial audio-start cleanup; missing-stream health checks; bounded audio recovery; normal process scheduling in both service templates and run.sh; consistent local/server no-interruption policy. This addresses findings 5, 7 and 9 in this guide and D01–D04 in the deeper audit. Source changes pass 119 targeted tests. The installed daemon has not been reloaded/restarted and live audio verification remains outstanding. Other findings remain open.

## Main finding

The application already streams input and output concurrently. Its remaining problems are ownership of work, bounded buffering, interruption handling, device routing, and recovery. Adding threads alone will not solve them.

The previous turn fixed nested-lock deadlocks, the reconnect queue capacity mismatch, and missing playback turn-completion signaling. These fixes remain in the working tree. They do not cover the issues below.

## Fix first: reliability and lifecycle

### 1. Prevent microphone work accumulating before the bounded queue

Evidence: audio/engine.py:210–243. Each audio callback schedules an event-loop callback. Eviction happens only when that scheduled callback runs.

Reproduced offline: 300 capture callbacks while the loop was stopped created 300 pending loop callbacks, while the bounded audio queue still contained zero frames. Its capacity therefore does not bound total pending capture work.

Fix: put timestamped frames into a bounded thread-safe buffer at capture time; schedule at most one pending drain notification. Drop obsolete capture frames according to an explicit maximum age, with counters. Keep capture callbacks short. Do not replay seconds of obsolete microphone input after a stall.

Verify: stall the main loop for one second; assert capture storage and pending notifications stay bounded and audio resumes with recent frames. Measure capture age at transmission.

### 2. Move synchronous memory work out of the session loop

Evidence: core/agent.py:379 calls record_exchange synchronously inside the receive handler. memory/codes-dev/jarvis_memory/bridge.py:431 performs session storage and structured memory writes. skills/skills.py:888–890 also calls synchronous memory operations inside an async function.

Reproduced offline by the session reviewer: a 200 ms record_exchange blocks a separate 10 ms heartbeat while handle() runs. The 150 ms tool timeout cannot preempt synchronous work occupying the same event loop.

Fix: use a bounded, dedicated memory worker that owns its database connections; pass immutable conversation snapshots to it. Audit other skill adapters for synchronous work. Do not indiscriminately move database objects across threads without checking their connection ownership.

Verify: slow database writes and memory searches must not stop capture sending, event receiving, or playback delivery. Record event-loop lag.

### 3. Own and cancel all tool tasks across reconnects

Evidence: core/agent.py:255 shields the actual execution task; :299 starts an untracked late-result task. cancel_tools() at :324 only cancels registered outer tasks. Late results retain the session object that originally launched them.

Reproduced offline: a slow tool received its speculative acknowledgement at 150 ms; after cancellation, its late-result task still sent a message to the old session.

Fix: track execution and result-delivery tasks separately under a session owner. On reconnect, cancel and await session delivery tasks. Give each session an epoch. Durable jobs may continue only with explicit ownership; queue their completion for the current session and avoid duplicate notifications. Cancellation of a thread-backed operation needs a separate cooperative strategy.

Verify: cancel a tool before and after the acknowledgement; reconnect while it runs; assert no sends to the old session and no orphan task exceptions.

### 4. Fence interrupted responses at the response level

Evidence: audio/downstream.py:27 stamps arriving data with the engine's current generation. core/agent.py:62–63 clears residual data on local interruption but does not establish a response discard boundary.

Reproduced offline: feed audio, trigger local barge-in, clear residual data, then feed a late chunk. The chunk is accepted under the new generation and playback can resume the interrupted response.

Fix: distinguish local playback generations from provider response ownership. Enter a discard state for the interrupted response and leave it only at a verified provider boundary or new response. Define the behavior for explicit stop as well as detected speech; don't discard the next legitimate response accidentally.

Verify: deliver old chunks after local interruption and before the server interruption event; none may play. The next response must play normally.

### 5. Make startup and audio recovery fail visibly and clean up

Evidence: core/agent.py initializes ipc_server only after audio startup, but its outer finally reads it at :748. An earlier startup failure can be masked by UnboundLocalError and skip cleanup. At :719–726 failed audio restart is logged and swallowed. audio/engine.py:610–613 ignores absent streams, so recovery can continue without working audio.

Fix: initialize all lifecycle resources before entering startup; close partially created streams; treat missing streams as unhealthy once running; use a bounded recovery policy with backoff. Do not report a ready voice session until capture and playback are active.

Verify: inject failures at echo startup, input open, output open, stream start, and restart. Preserve the original error, release resources, and recover or exit explicitly rather than staying silently connected.

### 6. Verify echo-cancellation routing for this process

Evidence: audio/engine.py:470 falls back to defaults when named AEC nodes cannot be resolved. The binder at :483–515 selects the first stream containing 'PipeWire ALSA', without checking process ownership, and ignores move command exit codes.

Fix: identify this process's exact capture/playback streams and verify their target nodes. Prefer deterministic device selection where supported. If routing cannot be verified, expose a degraded state or retry instead of claiming AEC is active. Bound routing subprocess timeouts.

Verify: run another audio application, reorder stream listings, fail a move command, and change devices. Other applications must stay untouched and the assistant must use the intended AEC paths.

### 7. Make daemon scheduling portable

Evidence: systemd/jarvis.service:19–20 enforces realtime round-robin scheduling. install-service.sh:7–20 installs that unit. run.sh also attempts whole-process realtime priority. The alternate repository unit differs.

Historical journal evidence on 15 October 2026, Asia/Kolkata: 07:56:58–07:57:15 contained status=214/SETSCHEDULER and restart counter 81. The installed jarvis-oma unit inspected by the daemon reviewer currently omits enforced round-robin scheduling; its current runtime status could not be queried through the restricted user bus. Reinstalling from the repository can reintroduce the old failure.

Fix: keep application startup functional without realtime privileges; consolidate service definitions and installer behavior. If scheduling changes are justified by measurements, prioritize the audio worker specifically rather than all desktop/network work.

Verify: installation and startup on an ordinary user account without realtime permissions; compare installed and repository unit behavior.

## Then improve smoothness and observability

### 8. Control playback buffering and measure timing

Evidence: audio/engine.py:107 uses an unbounded SimpleQueue. The sample clocks at :218 and :313 only count frames; callback device timestamps are not used. The empty-frame hangover at :355 delays a state transition but emits silence, so it does not conceal network jitter. Several latency configuration fields are not connected to the stream constructors.

Fix: add buffer-duration telemetry and explicit limits; use a small measured startup/rebuffer target and a policy for excessive backlog. Do not drop arbitrary middle sections of speech to enforce capacity. Measure underruns before increasing buffers. Use device timestamps and frame age to diagnose actual drift before choosing correction/resampling. Capture at 16 kHz and playback at 24 kHz is intentional, not itself a clock defect.

Verify: replay realistic bursty arrivals, 20–200 ms gaps, long responses, and slow devices. Record queue duration, underruns, first-audio latency, and final drain time. Confirm configuration changes actually affect runtime behavior.

### 9. Wire interruption preferences consistently

Evidence: core/config.py maps no-interrupt to provider activity handling, but core/agent.py:624–639 does not pass the corresponding preference to NativeAudioEngine.allow_barge_in. Local interruption can remain enabled while server interruption is disabled.

Fix: give local and server interruption policy a single explicit configuration source. Keep mute and explicit stop behavior separately defined.

Verify: no-interrupt prevents automatic local flushing while explicit stop still works.

### 10. Make shutdown bounded and observable

Historical journal evidence: at 22:48:25 on 15 October 2026, the user service exceeded its ten-second stop timeout and Python was killed. This confirms a shutdown failure occurred, but does not identify its exact cause.

Fix: supervise all workers, stop input delivery, cancel session tasks, close devices and release AEC with bounded cleanup deadlines. Expose which cleanup stage times out. Do not simply raise the timeout before identifying the blocking step.

Verify: stop during speaking, a slow tool, disconnected network, and failed routing; complete cleanup within the service deadline with no orphan jobs or AEC nodes.

### 11. Preserve valid sessions and coordinate notifications

Evidence: core/agent.py:729 clears the resumption handle on ordinary errors without distinguishing a rejected resume from a network error after a successful connection. Background completions and proactive events at :213, :234, and :289 immediately submit completed user turns, including while conversation is active.

Fix: track connection phases and preserve valid handles across recoverable transport failures. Apply a common bounded, timestamp-aware capture policy for reconnects. Queue routine notifications until a suitable conversation boundary; give urgent notifications an explicit policy. Verify provider behavior rather than assuming every submitted turn is harmless during speech.

Verify: drop the network after successful resumption, then reconnect without losing valid context. Complete several tools while the user speaks; confirm no duplicate or competing response turns.

## Recommended implementation sequence

1. Repair startup/recovery and service scheduling so failures are visible and recoverable.
2. Bound capture before event-loop dispatch and isolate synchronous memory work.
3. Own session tasks and implement interruption response boundaries.
4. Verify exact device routing and interruption configuration.
5. Add playback buffer control, timing measurements, and shutdown diagnostics.
6. Compare against the browser with matching model, voice, instructions, tools, and speech detection settings.

Use logical ownership boundaries: audio worker; session/network supervisor; bounded tool/memory workers. A dedicated audio process provides stronger isolation if measurements show Python contention; a wholesale language rewrite is not required to start fixing the confirmed defects.

## Acceptance checks

These are proposed project targets, not measured guarantees:

- A 30-minute full-duplex session completes without process restart, frozen state, or unbounded memory growth.
- Audio continues while deliberately slow memory and tool operations run.
- Interrupted response audio never resumes; the next valid response plays completely.
- Network renewal, device loss, and failed restart lead to explicit recovery or an actionable failed state.
- Stopping the daemon finishes within its service deadline.
- Measure speech-end to first audible response, capture frame age, playback queue duration, event-loop lag, underruns, and reconnect count. Compare distributions with the browser on the same machine and network.

Current local config uses 300 ms speech-end silence; 800 ms is the code default, not the active config file value. Do not tune latency using the wrong baseline.

## Verification and limits

The root reviewer ran 75 audio, echo-cancellation, and core-session tests successfully. Passing these offline tests does not cover the reproduced backlog, stale response, or real hardware behavior above. Add targeted regressions before implementation changes.

Journal observations came from `journalctl --user -u jarvis-oma.service -n 120 --no-pager -o short-iso`. Historical entries also showed AEC lookup fallback and DNS failures; they are not proof of current runtime state or a single cause for every reported crash.

No daemon restart, deployment, or runtime code changes were performed during this audit. A real microphone/speaker session and a matching browser session remain necessary to establish parity.
