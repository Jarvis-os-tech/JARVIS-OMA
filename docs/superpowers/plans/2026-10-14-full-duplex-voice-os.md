# Full-Duplex Continuous OS Voice Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform JARVIS-OMA into an unbroken, full-duplex continuous OS voice daemon on Omarchy 4 featuring zero-abort AEC streaming, 40ms/300ms ducking/barge-in, seamless GoAway session resumption, a secure 0600 UNIX control socket, and a 150ms hybrid tool execution gate.

**Architecture:** PortAudio C-thread streams run persistently without aborting, writing digital silence when idle to keep WebRTC AEC converged. A 20ms NumPy FFT bandpass (300-3400Hz) evaluates vocal energy for 40ms ducking and 300ms barge-in. Gemini Live connects with session resumption and sliding window compression, buffering in an expanded queue during GoAway. An async UNIX domain socket (0600) exposes JSON-RPC controls to voicectl/Quickshell. A 150ms hybrid latency gate executes fast tools inline and slow tools asynchronously with speculative acknowledgment and late injection.

**Tech Stack:** Python 3.12+, PortAudio / sounddevice, NumPy, PipeWire WebRTC AEC (`libpipewire-module-echo-cancel`), google-genai 2.24.0, asyncio, UNIX domain sockets.

**Spec:** `docs/superpowers/specs/2026-10-14-full-duplex-voice-os-design.md`

## Global Constraints
- Target platform: Omarchy 4 (Quattro), Arch Linux, Hyprland.
- Do NOT invoke `sd.RawOutputStream.abort()` or `stop()` during voice sessions; write zero-filled frames to DAC when idle.
- Vectorized `np.fft.rfft` on 320 samples with `300Hz <= freqs <= 3400Hz` mask and vocal ratio `vocal_energy / total_energy > 0.55` (zero pure-Python sample loops).
- Micro-fade on barge-in: 120 samples (5ms @ 24kHz) linear ramp to zero.
- Tool gate: `await asyncio.wait_for(asyncio.shield(tool_task), timeout=0.150)` with `asyncio.to_thread` execution.
- UNIX socket: `$XDG_RUNTIME_DIR/jarvis.sock`, mode `0600`.

---

### Task 1: Isochronous Audio Engine with Ducking & Barge-In (`audio/engine.py`)

**Files:**
- Modify: `audio/engine.py`
- Test: `tests/test_audio/test_engine.py`

**Interfaces:**
- Produces:
  - `NativeAudioEngine.set_reconnect_buffering(enabled: bool) -> None`
  - `NativeAudioEngine.trigger_barge_in(notify_orchestrator: bool = False) -> None`
  - `NativeAudioEngine.enqueue_playback(raw_pcm_24k: bytes, generation: Optional[int] = None) -> None`
  - Callbacks: `on_barge_in: Optional[Callable[[], None]]`, `on_state_change: Optional[Callable[[str], None]]`
  - State: `state: str` (`"listening" | "speaking" | "ducked" | "barged_in"`)

- [ ] **Step 1: Write unit tests for ducking, FFT vocal detection, and zero-abort barge-in**
Update `tests/test_audio/test_engine.py` with tests verifying:
  - 40ms vocal detection (2 frames) switches state to `"ducked"` and targets gain `0.30`.
  - 300ms vocal detection (15 frames) triggers barge-in, increments generation, drains output queue, and sets `_fade_out_pending`.
  - Output callback smoothly fades out over 120 samples on barge-in without aborting PortAudio stream.
  - Zero-floor frames are emitted when muted so upstream clock never starves.

- [ ] **Step 2: Run test to verify failure**
Run: `.venv/bin/python -m unittest tests/test_audio/test_engine.py -v`
Expected: FAIL on new ducking and FFT detection tests.

- [ ] **Step 3: Implement `NativeAudioEngine` in `audio/engine.py`**
Implement the continuous engine with:
  - Vectorized `np.fft.rfft` bandpass (300Hz-3400Hz bin mask) and harmonic concentration check.
  - 40ms (2 frames) ducking to 30% amplitude (`_target_gain = 0.30`) with linear interpolation.
  - 300ms (15 frames) barge-in promotion draining `c_output_queue` and setting 120-sample DAC ramp to zero.
  - Dynamic noise floor tracking via rolling 50-frame window.
  - Zero-abort stream lifecycle (never calling `abort()`/`start()`).

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/python -m unittest tests/test_audio/test_engine.py -v`
Expected: PASS (all tests green).

- [ ] **Step 5: Commit changes**
```bash
git add audio/engine.py tests/test_audio/test_engine.py
git commit -m "feat(audio): implement isochronous engine with 40ms ducking and 300ms barge-in"
```

---

### Task 2: Glitchless GoAway Session Resumption (`core/agent.py`)

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_core/test_agent.py`

**Interfaces:**
- Consumes: `NativeAudioEngine.set_reconnect_buffering(enabled: bool)`
- Produces:
  - `LiveVoice.run_continuous_session(client: genai.Client)`
  - Seamless `resume_handle` updates across `RenewConnection` on `event.go_away`.

- [ ] **Step 1: Write test for GoAway buffer expansion and reconnect**
In `tests/test_core/test_agent.py`, add a test that mocks `RenewConnection` / `event.go_away`:
  - Verifies `audio_engine.set_reconnect_buffering(True)` is invoked when `RenewConnection` is raised.
  - Verifies `async_input_queue` expands limit to 200 chunks so mic audio is preserved during reconnect.
  - Verifies `audio_engine.set_reconnect_buffering(False)` resets ceiling back to 50 on successful reconnection.

- [ ] **Step 2: Run test to verify failure**
Run: `.venv/bin/python -m unittest tests/test_core/test_agent.py -k test_goaway_reconnect`
Expected: FAIL.

- [ ] **Step 3: Implement GoAway reconnection buffering in `core/agent.py`**
In `core/agent.py`:
  - In `run()` reconnect loop, call `audio_engine.set_reconnect_buffering(True)` upon `RenewConnection`.
  - Once `client.live.connect` succeeds, call `audio_engine.set_reconnect_buffering(False)`.
  - Maintain unbroken capture while reconnecting so zero microphone frames are lost.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/python -m unittest tests/test_core/test_agent.py -k test_goaway_reconnect`
Expected: PASS.

- [ ] **Step 5: Commit changes**
```bash
git add core/agent.py tests/test_core/test_agent.py
git commit -m "feat(core): implement glitchless GoAway session resumption buffering"
```

---

### Task 3: 150ms Shielded Hybrid Latency Tool Gate (`core/agent.py`)

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_core/test_agent.py`

**Interfaces:**
- Produces: `LiveVoice.execute_tool_with_hybrid_gate(session, call, timeout_sec: float = 0.150) -> None`

- [ ] **Step 1: Write unit tests for the 150ms hybrid gate**
In `tests/test_core/test_agent.py`, add:
  - `test_tool_fast_path`: Mock tool finishing in 20ms. Verifies `session.send_tool_response` sent inline with result.
  - `test_tool_slow_path`: Mock tool sleeping 300ms. Verifies `session.send_tool_response` sent at 150ms with `status: "running_in_background"`, and `session.send_client_content` called upon completion with the final output.

- [ ] **Step 2: Run test to verify failure**
Run: `.venv/bin/python -m unittest tests/test_core/test_agent.py -k test_tool_`
Expected: FAIL.

- [ ] **Step 3: Implement `execute_tool_with_hybrid_gate` in `core/agent.py`**
Wrap tool execution in:
```python
tool_task = asyncio.create_task(
    asyncio.to_thread(self.skills.execute, call.name, call.args or {})
)
try:
    result = await asyncio.wait_for(asyncio.shield(tool_task), timeout=timeout_sec)
    async with self.send_lock:
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(id=call.id, name=call.name, response={"result": result})
            ]
        )
except asyncio.TimeoutError:
    async with self.send_lock:
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=call.id,
                    name=call.name,
                    response={
                        "status": "running_in_background",
                        "message": f"Skill '{call.name}' is executing in background; acknowledge briefly.",
                    },
                )
            ]
        )
    async def _inject_when_done():
        try:
            late_result = await tool_task
        except Exception as exc:
            late_result = {"error": str(exc)}
        async with self.send_lock:
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=f"[System Notification] Background tool '{call.name}' finished: {late_result}")],
                ),
                turn_complete=True,
            )
    asyncio.create_task(_inject_when_done())
```

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/python -m unittest tests/test_core/test_agent.py -k test_tool_`
Expected: PASS.

- [ ] **Step 5: Commit changes**
```bash
git add core/agent.py tests/test_core/test_agent.py
git commit -m "feat(core): implement 150ms shielded hybrid latency tool gate"
```

---

### Task 4: Headless UNIX Domain Socket Server (`core/ipc.py` & `scripts/jarvisctl`)

**Files:**
- Create: `core/ipc.py`
- Create: `scripts/jarvisctl`
- Create: `tests/test_core/test_ipc.py`
- Modify: `core/agent.py` (start IPC server during bootstrap)

**Interfaces:**
- Produces:
  - `IPCServer(socket_path: Optional[str], voice: LiveVoice, engine: NativeAudioEngine)`
  - Methods: `start() -> None`, `stop() -> None`, `broadcast(event: dict) -> None`
  - CLI: `scripts/jarvisctl {status, toggle, mute, unmute, interrupt, subscribe}`

- [ ] **Step 1: Write unit tests for IPC Server**
Create `tests/test_core/test_ipc.py` verifying:
  - Socket created with mode `0600`.
  - Command `{"command": "status"}` returns state, muted status, and active telemetry.
  - Command `{"command": "toggle_mute"}` toggles mute and updates engine.
  - Command `{"command": "interrupt"}` triggers `engine.trigger_barge_in()`.
  - Command `{"command": "subscribe"}` yields streamed JSON events when `broadcast()` is called.

- [ ] **Step 2: Run test to verify failure**
Run: `.venv/bin/python -m unittest tests/test_core/test_ipc.py -v`
Expected: FAIL (module `core.ipc` does not exist).

- [ ] **Step 3: Implement `core/ipc.py` and `scripts/jarvisctl`**
- In `core/ipc.py`:
  - Determine socket path via `$XDG_RUNTIME_DIR/jarvis.sock` (fallback `/run/user/<uid>/jarvis.sock` or `~/.cache/jarvis.sock`).
  - Set permissions `0600` via `os.chmod`.
  - Process JSON-RPC lines using `asyncio.start_unix_server`.
- In `scripts/jarvisctl`:
  - Python CLI tool with `--json` output flag.
  - Symlink installed at `~/.local/bin/voicectl` for drop-in Quickshell bar widget compatibility.
- In `core/agent.py`:
  - Instantiate and start `IPCServer` inside `run()`, linking `on_state_change` and `on_barge_in` callbacks to `ipc_server.broadcast`.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/python -m unittest tests/test_core/test_ipc.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**
```bash
git add core/ipc.py scripts/jarvisctl tests/test_core/test_ipc.py core/agent.py
git commit -m "feat(ipc): add headless 0600 UNIX domain socket server and jarvisctl CLI"
```

---

### Task 5: End-to-End System Verification & Regression Suite

**Files:**
- Modify: `tests/`
- Documentation: `docs/superpowers/plans/2026-10-14-full-duplex-voice-os.md`

- [ ] **Step 1: Run full test suite across the entire repository**
Run: `.venv/bin/python -m unittest discover -s tests -v`
Expected: 100% PASS across all audio, core, skills, and connector suites.

- [ ] **Step 2: Verify Omarchy 4 integration links**
Run: `scripts/jarvisctl status --json`
Ensure permissions and paths are aligned with Quickshell expectations.

- [ ] **Step 3: Commit final plan verification checkpoint**
```bash
git commit --allow-empty -m "chore: full-duplex continuous OS voice service verified"
```
