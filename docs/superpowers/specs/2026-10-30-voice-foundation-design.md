# Sovereign Voice Foundation — Design Specification

**Status:** Approved  
**Date:** 30 October 2026  
**Workspace:** `/home/g0pi/JARVIS OS`  
**Upstream Source:** `/home/g0pi/Projects/JARVIS-OMA` (JARVIS-OMA codebase, git HEAD `1403816`)

## 1. Objective

Establish a rock-solid, crash-resilient background voice daemon (`jarvisd`) that hears ambient audio, detects speech turns locally, converses in real-time via Gemini Live full-duplex streaming, and interrupts playback in <25ms. This is the **first stage** of transforming Omarchy into JARVIS OS.

### Scope Boundary

**In scope:** Voice capture, local speech detection (Silero VAD + SpeechTurnGate), Gemini Live WebSocket duplex streaming, audio playback, hard barge-in, connection recovery, IPC control socket, systemd user service lifecycle, and the 6 regression fixes from the 30 Oct audit.

**Explicitly deferred:** Memory/persistence, proactive agents, visual HUD/shell, OS rebranding, desktop tool execution, vision/camera.

### Protected Hotkey

`SUPER + H` remains untouched — it is permanently locked to system voice dictation (`linux-voice toggle`).

## 2. Inviolable Laws

1. **Barge-in <25ms** — SIGKILL to pw-play the instant RMS > 0.015 during active playback.
2. **Flash execution <3s** — Local audio pipeline operations never touch the network.
3. **3-second hand-off** — Anything taking longer gets one spoken acknowledgment, then backgrounds.
4. **Anti-stale data** — System telemetry always queried live, never from model weights.
5. **Memory ceiling** — Interactive voice owns performance cores; ~900MB RAM ceiling.
6. **Voice core lock** — Zero modifications to the 7 cryptographically locked voice core files.

## 3. Audio Pipeline

### 3.1 Capture
- `pw-record --raw --rate 16000 --channels 1 --format s16 --latency 20ms --target <echo_source> -a -`
- 512-sample (1024-byte) raw PCM frames at 16 kHz, read in an async non-blocking worker.
- PipeWire WebRTC AEC via `MonitorEchoCancellation` loopback from speaker output.

### 3.2 Playback
- `pw-play --rate 24000 --channels 1 --format s16 --latency 40ms --target <echo_sink> -a -`
- 24 kHz 16-bit PCM streamed from Gemini Live response chunks.
- Bounded backlog: max 60s of queued PCM (48000 × 60 bytes).

### 3.3 Hard Barge-In (<25ms)
- RMS energy evaluated on every 20ms microphone chunk.
- If user speaks (RMS > 0.015) while `Playback.busy` is true:
  1. SIGKILL sent to active `pw-play` subprocess.
  2. Playback queue flushed (generation fence incremented).
  3. Audio cancel event sent to streaming session.
  4. `SpokenInterruption` requires 120ms (6 frames, 4 fresh VAD positives) of speech evidence, independent of echo correlation, before confirming a barge-in.

## 4. Speech Detection & Turn Gating

### 4.1 Local VAD
- `SileroSpeechDetector` using OpenWakeWord's bundled Silero ONNX model.
- Feeds contiguous 480-sample (30ms) windows to the model; accumulates sub-480 chunks internally.

### 4.2 SpeechTurnGate
- Opens a speech turn after `trigger_frames` (default 2) consecutive VAD scores ≥ 0.5.
- Closes a turn after `silence_frames` (default 20) consecutive VAD scores < 0.25.
- Post-hold: `tail_seconds` (0.45s) suppression after any interruption or blocked period.
- Below -54 dBFS energy floor: score forced to 0.0, prevents ghost turns from electrical noise.

## 5. Connection Recovery (6 Regression Fixes)

### Fix 1: Rate-Limit Backoff Cooldown
- On 429 (`RESOURCE_EXHAUSTED`), enforce `delay = max(60.0, exponential_backoff)`.
- KeyPool rotates to next available API key before retry.

### Fix 2: Setup Timeout Resilience
- Network setup timeouts (`TimeoutError` before `session_opened=True`) retain resumable session handle instead of discarding it.
- After 2 consecutive failed resume attempts on the same handle, fall back to fresh session.

### Fix 3: Post-Connection 400 Handling
- A 400 error on a resumed session (`attempted_resume=True`, `code=400`) is treated as a resume rejection → start fresh session immediately with delay=0.
- A 400 error on a non-resumed session remains fatal.

### Fix 4: Speech Turn Gate Frame Continuity
- Quiet frames (energy < -54 dBFS threshold) must still pass through the VAD detector so internal state decay and windowing remain accurate.
- Current code: sets `score = 0.0` and skips detector call → detector state stalls.
- Fix: Call `self.detector(pcm)` for all frames above absolute silence, only short-circuit to `score = 0.0` when energy is truly zero.

### Fix 5: Interruption Detector Frame Continuity
- `SpokenInterruption.process()`: quiet frames (RMS < 0.004) currently return `None` immediately without updating the detector, desynchronizing internal silence counters.
- Fix: Still pass frames to the detector and update `_microphone` deque even when RMS is below threshold; only skip the interruption promotion logic.

### Fix 6: Cancelled Playback Generation Drain
- When a playback generation is cancelled mid-stream by barge-in, the `Playback.run()` loop must check `generation != self.generation` after each `queue.get()` and silently discard stale chunks.
- Current code: a drain timeout after cancellation can raise `PlaybackBacklogError`, ending the playback worker entirely.
- Fix: Ensure the generation fence check at line 184 continues the loop cleanly, and that `cancel_pending()` sets `_arrival` to unblock any waiting `_prime()`.

## 6. IPC & Service Lifecycle

### 6.1 Systemd User Service
```ini
[Unit]
Description=JARVIS Voice Core — ambient voice assistant
After=graphical-session.target pipewire.service wireplumber.service
PartOf=graphical-session.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
ExecStart=%h/.local/share/jarvis-voice/bin/jarvis-voice run
WorkingDirectory=%h/.local/share/jarvis-voice
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=XDG_RUNTIME_DIR=%t
Restart=always
RestartSec=2
KillMode=control-group
TimeoutStopSec=8
UMask=0077
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
```

### 6.2 Control Socket
- Path: `$XDG_RUNTIME_DIR/jarvis/control.sock` (mode 0600 inside 0700 directory).
- Commands: `status`, `status --json`, `listen toggle`, `listen start`, `listen stop`, `listen cancel`.

### 6.3 Atomic State File
- Path: `$XDG_RUNTIME_DIR/jarvis/state.json`.
- Written via write-to-temp + atomic rename.
- Fields: `listening`, `connected`, `model`, `voice`, `barge_in`, `error`, `microphone_pid`, `playback_pid`, `input_bytes`, `output_bytes`, `interruptions`, `connections`.

## 7. Configuration

```toml
# ~/.config/jarvis-voice/config.toml
model = "gemini-3.8-live"
voice = "Aoede"
device = ""  # PipeWire source; empty = system default
barge_in = true
autostart_listening = true
api_key_env = "GEMINI_API_KEY"
```

Credential loading: reads `~/.config/jarvis-voice/env` for `GEMINI_API_KEY` if not already in environment.

## 8. Acceptance Criteria

- [ ] All existing voice tests pass (334 voice + 157 core = 491 tests, 0 failures).
- [ ] All 6 regression fixes verified with dedicated test cases.
- [ ] Voice core lock verification: 7 files pass SHA256 integrity check.
- [ ] Live hardware loopback: `pw-record` capture and `pw-play` playback verified on PipeWire.
- [ ] Full-duplex conversation: live back-and-forth with Gemini Live confirmed.
- [ ] Barge-in: hard interruption stops speaker output under 25ms.
- [ ] Service lifecycle: `systemctl --user start/stop/restart jarvis-voice` works cleanly.
- [ ] IPC socket: `jarvis-voice status`, `jarvis-voice listen toggle` respond correctly.
- [ ] Crash recovery: service auto-restarts after SIGKILL within 2 seconds.
