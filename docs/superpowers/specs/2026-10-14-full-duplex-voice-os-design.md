# Full-Duplex Continuous OS Voice Service Architecture Specification

**Document ID:** `SPEC-2026-10-14-FULL-DUPLEX-VOICE-OS`  
**Target Platform:** Omarchy 4 (Quattro) / Arch Linux / Hyprland  
**Repository:** `Jarvis-os-tech/JARVIS-OMA`  
**Status:** Approved for Implementation Planning  

---

## 1. Executive Summary

This specification formalizes the transformation of JARVIS-OMA from a turn-based (walkie-talkie) voice interface into an always-on, full-duplex, simultaneous listening-and-speaking OS background service, adopting the dual-stream continuous state architecture of NVIDIA PersonaPlex and OpenAI GPT-Live.

The architecture eliminates microphone gating, acoustic echo cancellation (AEC) dropouts, WebSocket disconnect stutter, and tool execution stalls by anchoring the system on four decoupled pillars:
1. **Section 1: Non-Blocking, Isochronous Audio Subsystem (`audio/engine.py`)** — Continuous hardware stream opening without stream teardowns (`abort()`/`start()`), preserving PipeWire WebRTC AEC convergence, combined with an in-callback 40ms vocal bandpass ducking gate and 300ms barge-in promotion.
2. **Section 2: Glitchless WebSocket Resumption Loop (`core/agent.py`)** — Continuous background audio buffering during 10-minute `GoAway` events, utilizing Gemini Live in-memory `session_resumption` handles and `context_window_compression` (sliding window).
3. **Section 3: Headless UNIX Domain Socket Server (`core/ipc.py`)** — Secure `0600` local socket at `$XDG_RUNTIME_DIR/jarvis.sock` with JSON-RPC interface and companion CLI `jarvisctl` (symlink-compatible with `voicectl`) for Omarchy 4 Quickshell integration.
4. **Section 4: 150ms Hybrid Latency Tool Gate (`core/agent.py` & `skills/skills.py`)** — Speculative tool acknowledgment for tasks exceeding 150ms, allowing conversational filler speech while executing background I/O without audio jitter.

---

## 2. Section 1: Non-Blocking Isochronous Audio Subsystem (`audio/engine.py`)

### 2.1 Hardware Stream Continuity & Zero-Abort Phase Lock
- **Stream Lifecycle:** PortAudio `RawInputStream` (16 kHz, 16-bit PCM mono, 20ms = 320 samples) and `RawOutputStream` (24 kHz, 16-bit PCM mono, 20ms = 480 samples) are initialized once during daemon bootstrap and remain active for the duration of the OS process.
- **Silence Generation:** When no agent speech is queued in `c_output_queue`, the `_output_callback` fills `outdata` with digital silence (`outdata.fill(0)`).
- **AEC Phase Integrity:** Removing all calls to `output_stream.abort()` and `output_stream.start()` guarantees that PipeWire's `libpipewire-module-echo-cancel` filter maintains continuous time-delay alignment between the playback reference sink and microphone capture source.

### 2.2 Time-Frequency Filter Matrix & State Machine
Every 20ms incoming microphone block is evaluated in the PortAudio C-thread callback via NumPy before enqueueing:
- **Bandpass Filter:** 2nd-order Butterworth IIR bandpass filter isolating human vocal frequencies (300 Hz – 3400 Hz) with precomputed coefficients:
  $$H(z) \text{ configured for } f_{low} = 300\text{ Hz}, f_{high} = 3400\text{ Hz}, f_s = 16000\text{ Hz}$$
- **Dynamic Energy Floor:** Tracks ambient background noise RMS across a 50-frame rolling window.
- **State Machine Stages:**
  1. **Overlap Mode (40ms Ducking Gate):** If bandpass vocal energy exceeds the threshold for $\ge 2$ consecutive frames (40ms) while the agent is speaking:
     - Set internal state to `DUCKED`.
     - In `_output_callback`, apply a 5ms linear gain ramp reducing playback amplitude from $1.0$ to $0.3$ (-10.5 dB).
     - If vocal energy drops below threshold within $<300\text{ms}$ (e.g., user acknowledges with "mm-hmm" or "yeah"), smoothly ramp gain back to $1.0$ over 10ms.
  2. **Barge-In Promotion (300ms Sustained Speech):** If vocal energy persists for $\ge 15$ consecutive frames (300ms):
     - Transition state to `BARGED_IN`.
     - Increment `active_generation` monotonically.
     - Drain all pending frames from `c_output_queue` in $O(1)$.
     - Apply an immediate 5ms linear fade-out to zero on the active DAC buffer to eliminate audible pop/click artifacts.
     - Dispatch an asynchronous barge-in notification event to `LiveVoice`.

---

## 3. Section 2: Glitchless WebSocket Resumption Loop (`core/agent.py`)

### 3.1 Session Longevity Configuration
The Gemini Live connection is instantiated with parameters ensuring multi-hour session continuity:
```python
config = types.LiveConnectConfig(
    response_modalities=[types.LiveModality.AUDIO],
    system_instruction=instruction,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
    ),
    session_resumption=types.SessionResumptionConfig(handle=voice.resume_handle),
    context_window_compression=types.ContextWindowCompressionConfig(
        sliding_window=types.SlidingWindow()
    ),
    realtime_input_config=realtime_input_config,
)
```

### 3.2 10-Minute GoAway Handshake
1. When `event.session_resumption_update` arrives with `update.resumable == True`, update `voice.resume_handle = update.new_handle`.
2. When the server delivers an `event.go_away` notice:
   - Intercept the event before connection termination.
   - Do NOT terminate or restart `NativeAudioEngine`.
   - Expand `async_input_queue` buffer limit to 200 frames (4.0 seconds of capture) to absorb network reconnect latency.
   - Re-establish the WebSocket session using `resume_handle`.
   - Flush accumulated microphone frames sequentially upon reconnection.

---

## 4. Section 3: Headless UNIX Domain Socket Server (`core/ipc.py`)

### 4.1 Socket Specification
- **Path:** `$XDG_RUNTIME_DIR/jarvis.sock` (fallback `/run/user/<UID>/jarvis.sock`).
- **Permissions:** Mode `0600` (`S_IRUSR | S_IWUSR`), ensuring process-level user isolation.
- **Protocol:** Newline-delimited JSON-RPC messages.

### 4.2 Command Surface
| Command | Parameters | Description | Response Payload |
| :--- | :--- | :--- | :--- |
| `status` | None | Returns real-time daemon state | `{"status": "ok", "state": "listening"\|"speaking"\|"ducked", "muted": bool, "active_jobs": int, "model": str}` |
| `toggle_mute` | None | Toggles capture mute state | `{"status": "ok", "muted": bool}` |
| `interrupt` | None | Triggers immediate local barge-in | `{"status": "ok", "interrupted": true}` |
| `subscribe` | None | Streams state change events | Stream of `{"event": "state_change", "state": str, ...}\n` |

### 4.3 CLI Integration (`scripts/jarvisctl`)
A Python/POSIX-compliant executable `scripts/jarvisctl` provides direct shell and keybinding integration:
- `jarvisctl status [--json]`
- `jarvisctl toggle`
- `jarvisctl interrupt`
- Symlink created at `~/.local/bin/voicectl` for immediate drop-in compatibility with the Omarchy 4 Quickshell widget.

---

## 5. Section 4: 150ms Hybrid Latency Tool Gate (`core/agent.py`)

### 5.1 Execution Protocol
```text
Gemini Tool Call Received
          │
          ▼
Start asyncio.wait_for(task, timeout=0.150)
          │
    ┌─────┴─────────────────────────────────┐
    ▼                                       ▼
Completed < 150ms                       Timeout > 150ms
    │                                       │
    ▼                                       ▼
Send ToolResponse immediately           Send Speculative ToolResponse:
(Inline execution)                      {"status": "running_in_background"}
                                            │
                                            ▼
                                        Keep Task Running in Worker Thread
                                            │
                                            ▼
                                        On Task Completion:
                                        Inject Result via send_client_content
```

### 5.2 Late-Result Injection Handshake
1. At $t = 150\text{ms}$, return:
   ```json
   {
     "status": "running_in_background",
     "message": "Desktop skill in progress."
   }
   ```
2. The Gemini model produces brief conversational filler ("Checking that now...").
3. When the background future completes (e.g. at $t = 850\text{ms}$), format a system notification turn:
   ```python
   await session.send_client_content(
       turns=types.Content(
           role="user",
           parts=[types.Part(text=f"[System Notification] Tool '{call.name}' finished: {result}")]
       ),
       turn_complete=True
   )
   ```
4. Gemini smoothly vocalizes the outcome without breaking conversational momentum.

---

## 6. Implementation Rollout Plan

- **Phase 1 (Section 1 & Section 2):**
  - Implement zero-abort audio streaming, 40ms/300ms ducking and barge-in in [`audio/engine.py`](file:///home/g0pi/Projects/JARVIS-OMA/audio/engine.py).
  - Harden session resumption and GoAway reconnect buffering in [`core/agent.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/agent.py).
  - Execute automated audio engine and connection lifecycle unit tests.
- **Phase 2 (Section 3 & Section 4):**
  - Implement `core/ipc.py` and `scripts/jarvisctl`.
  - Implement 150ms hybrid tool gate in `core/agent.py`.
  - Validate Quickshell integration and full-duplex conversational flow.
