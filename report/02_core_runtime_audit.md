I have completed the deep Ponytail Systems Audit of the **JARVIS-OMA Core Voice Agent Runtime & Streaming** ([`core/agent.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py), [`agent.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent.py), [`core/config.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/config.py)) and sent the full structured report to the parent orchestrator via `send_message`.

### Summary of Completed Investigation
1. **Streaming Flow & Lifecycle Breakdown**:
   - Documented Gemini Live bidirectional WebSocket protocol (PCM16 16kHz upstream / 24kHz downstream via [`DownstreamRouter`](file:///home/g0pi/Projects/JARVIS-OMA/audio/downstream.py)).
   - Traced [`supervise()`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L48-L68) worker lifecycles and early teardown semantics.
   - Analyzed two-stage barge-in: local pre-emptive audio frame dropping ([`_on_local_barge_in`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L289-L292) + `_drop_interrupted_audio`) and server-side interruption confirmation.
   - Audited the notice queue (`collections.deque` + `asyncio.Event`), lifecycle state machine, and IPC UNIX domain socket broadcast plane.
   - Analyzed signal traps (`SIGUSR1` for mute, `SIGUSR2` for interruption, `SIGTERM` for graceful shutdown).
   - Verified reconnection flows: [`RenewConnection`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L70), [`EnterStandby`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L74) wake-word transitions, and exponential backoff with jitter.

2. **Identified Issues & Edge Cases**:
   - **Heap Memory Leak**: Unbounded accumulation in `self.tool_responses` ([`core/agent.py:827, 1076`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L827)).
   - **Supervisor Cascade Fragility**: Secondary services (calendar sync, task monitor, telephony) bundled inside `supervise()`, causing optional worker failures to kill active voice conversations.
   - **Disk Thrashing**: Continuous 15 FPS MJPEG camera writes to `/tmp` via `ffmpeg` subprocesses for periodic 1 FPS samples.
   - **State Machine Contention**: Hand-rolled 50Hz RMS frame counter ([`observe_mic_activity`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L162-L182)) competing and racing against Gemini Live native VAD.

3. **Ponytail Ladder Findings & Recommendations**:
   - **`delete:`** Unbounded `tool_responses` dictionary, duplicated notice expiration loops, redundant HTTP error checks, dead `stop_event.wait()` phone hangs.
   - **`stdlib:`** Replace hand-rolled `collections.deque` + `asyncio.Event` with standard library `asyncio.Queue`.
   - **`native:`** Eliminate intermediate disk writes in screenshot capture; stream directly from memory buffers.
   - **`yagni:`** Decouple camera daemon, Bluetooth telephony alert formatting, and proactive calendar observation out of [`LiveVoice`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py#L78).
   - **`shrink:`** Extract 280-line prompt monolith; prune 50Hz heuristic RMS state transitions; isolate optional workers from voice supervision.
   - **Projected Net Reduction**: **~893 LOC (-36%)** across the runtime with zero changes to locked voice files.
