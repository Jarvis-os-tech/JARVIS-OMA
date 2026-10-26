# From Chrome voice conversation to browserless JARVIS

Analysis and implementation guide · 24 October 2026 · Asia/Kolkata

## Decision

Use JARVIS's existing Gemini Live connection with its existing optional native PipeWire companion. Finish the integration and validate the audio experience before promoting that backend. Chrome does not need to be open, and the localhost web server does not need to remain part of the production voice path.

The reference is **http://localhost:3000/**, titled **Voice Companion — Natural Spoken Conversation**. Its running server was mapped through port 3000 → process 229106 → `/home/g0pi/Downloads/voice-buddy`. A similarly named project exists elsewhere; this report uses the running Downloads copy.

**What is established:** the app's served JavaScript, local server source, and JARVIS source explain how the feature is built. **What is not established:** measured microphone quality, effective Chrome capture settings, the user's current live/demo selection, or audible latency parity. No microphone, cloud conversation, or service restart was initiated for this report.

“Browserless” means a native desktop service. The proposed conversational model still runs in the cloud. Fully offline conversation would require a separate local speech/model design.

## 1. Evidence and investigation limits

| Evidence | Result and limits |
| --- | --- |
| Local HTTP response | The requested page was served successfully and identified the voice application. |
| Server health | `/api/health` returned `status: ok` and `hasApiKey: true` at 22:34:49 IST. This checks configuration presence, not credential validity or a successful model call. |
| Served application artifacts | Captured Vite-transformed `main`, `App`, audio utilities, and demo speech code directly from localhost. URLs, byte counts, and SHA-256 hashes are retained. |
| REA 6.7.0 static analysis | Completed for these four saved JavaScript artifacts. Evidence ID: `ev_db209c325722ab8e1246d3a8662b0a6f2970c3313b80b4e6de397c662dd10906`. |
| REA coverage | Inert syntax analysis; dependencies outside the four-file capture were not included. Unresolved imports and dynamic relationships remain unknown. It did not observe a live voice exchange. |
| Browser inspection | Connected Chrome tooling exposed a blank automation tab; navigation approval review timed out. The regular browser had no usable loopback CDP endpoint. HTTP artifact acquisition and source tracing supplied the usable evidence. |
| JARVIS | Inspected unlocked orchestration, locked audio interfaces, native backend, standby, configuration, services, and selected tests. |
| Shared workspace | Initial HEAD was `bb75151`; another agent advanced the repository to `5dbcfa5` during the investigation. Line references are working-tree references, not an immutable release specification. |

Evidence files: [acquisition manifest](/home/g0pi/.codex/visualizations/2026/10/24/01a16ec4-bb93-7760-bd1b-aa1c2bc06314/voice-browser-evidence/acquisition.json), [complete REA evidence](/home/g0pi/.codex/visualizations/2026/10/24/01a16ec4-bb93-7760-bd1b-aa1c2bc06314/voice-browser-evidence/rea-static-complete.json). The first sandboxed REA attempt failed at worker startup; the successful run used the same saved artifacts with subprocess access available.

## 2. What the reference application actually does

### Normal Gemini Live mode

```mermaid
flowchart LR
  Mic[Microphone] --> Capture[Chrome capture: requested AEC, noise suppression, gain control]
  Capture --> PCM[16 kHz PCM conversion]
  PCM --> WS[Local WebSocket /live]
  WS --> Relay[Node server relay]
  Relay <--> Gemini[Gemini Live cloud model]
  Gemini --> Reply[24 kHz response PCM]
  Reply --> Relay
  Relay --> Player[Chrome audio-clock scheduling]
  Player --> Speaker[Speakers]
  Gemini -. interruption event .-> Clear[Stop queued playback]
```

1. The page opens a WebSocket to its own `/live` endpoint and sends an initialization message with the voice and conversational instructions. [App.tsx](/home/g0pi/Downloads/voice-buddy/src/App.tsx:315)
2. The Node server opens `ai.live.connect` with `gemini-3.8-live`, audio responses, and the selected voice. This is the conversation engine; Chrome supplies the capture/playback infrastructure. [server.ts](/home/g0pi/Downloads/voice-buddy/server.ts:89)
3. After the server reports connected, the page requests microphone capture with echo cancellation, noise suppression, and automatic gain control enabled. These are requested constraints; their effective values need a live `MediaStreamTrack.getSettings()` inspection. [App.tsx](/home/g0pi/Downloads/voice-buddy/src/App.tsx:254)
4. Input uses an `AudioContext` requested at 16 kHz and `createScriptProcessor(4096, 1, 1)`. Assuming that context rate is obtained, each callback contains **256 ms** of audio. Samples are converted to PCM16, base64 encoded, and sent in JSON. This implementation does **not** use an AudioWorklet for capture. [App.tsx](/home/g0pi/Downloads/voice-buddy/src/App.tsx:266)
5. The relay forwards microphone audio to `sendRealtimeInput`. No explicit VAD tuning is provided in its session setup, so the provider's effective defaults need verification. It uses WebSockets; the inspected code does not create an `RTCPeerConnection`. [server.ts](/home/g0pi/Downloads/voice-buddy/server.ts:111)
6. Response audio is decoded into 24 kHz buffers. Each buffer starts at the previous buffer's scheduled end. When the schedule has fallen behind, the player restarts at audio-context time plus 10 ms. That is a scheduling lead, **not** measured device or conversational latency. [audio.ts](/home/g0pi/Downloads/voice-buddy/src/utils/audio.ts:87)
7. A provider `interrupted` event stops and clears active playback sources. A completed model turn finalizes UI transcript state; model completion and the speaker finishing buffered audio are separate events. [App.tsx](/home/g0pi/Downloads/voice-buddy/src/App.tsx:362)

The default persona selects Zephyr and short, conversational turns. Tone and prompt differences can affect perceived naturalness independently of audio engineering. Compare the same model, voice, prompt, and devices when testing parity. [personas.ts](/home/g0pi/Downloads/voice-buddy/src/data/personas.ts:3)

### Demo mode is a separate path

Demo mode uses browser SpeechRecognition, keyword-based canned responses, and `speechSynthesis`. Its animated output volume is simulated. It is not evidence of native Gemini audio or measured output loudness. The app also starts the SpeechRecognition helper during normal capture, although its result handler only produces responses in demo mode. The name “local” in the helper does not establish that a browser recognition implementation operates offline. [recognition helper](/home/g0pi/Downloads/voice-buddy/src/App.tsx:118), [demo service](/home/g0pi/Downloads/voice-buddy/src/services/demoVoiceService.ts:1)

Do not transplant these limitations into JARVIS:

- Manual interrupt sends an `interrupt` message, but the relay's handler has no provider cancellation action. Local playback can stop while later response chunks still arrive. JARVIS should retain its stronger generation fencing.
- The player has no explicit maximum scheduled-audio backlog in the inspected class. Retain bounded native queues.
- The relay has no explicit resumption configuration in this setup. Retain JARVIS's existing session recovery mechanisms.
- Do not copy the caption wiring as a proven transcript pipeline: the reference does not explicitly request input/output transcription in its Live configuration, and its input-transcript lookup differs from the documented server-content shape.

## 3. Which Chrome capabilities need a native equivalent?

| Responsibility | Chrome/reference implementation | Native JARVIS destination |
| --- | --- | --- |
| Microphone access and device timing | Browser media capture and audio service | PipeWire streams in the existing C companion |
| Echo/noise processing | Requested browser processing | Existing private PipeWire WebRTC AEC; verify real routing and quality |
| Input level normalization | Requested automatic gain control | Measure first; add an optional bounded processor only if needed |
| PCM framing | 4,096-sample browser callback, PCM16/base64 | Keep existing 320-sample/20 ms, 16 kHz capture |
| Model connection | Browser → Node relay → Gemini | Existing direct Python Gemini Live session |
| Playback clock | Scheduled AudioBufferSource nodes | Device-driven PipeWire rendering with preallocated rings |
| Interruptions | Clear audio sources on provider event | Generation cancellation across router, adapter, and native render consumer |
| Ongoing conversation | Live session plus app state | Existing session supervisor, recovery, context and standby policy |
| Start/mute/stop/status | Buttons and tab keyboard handlers | Existing IPC, hotkeys and desktop widget |
| Background lifecycle | Open browser tab plus Node server | One systemd user service and its owned native audio child |

Chromium's published architecture separates OS audio work from the renderer and uses shared memory for samples. Its callback guidance prohibits blocking and allocation in deadline-sensitive work. The transferable requirement is predictable audio deadlines; copying Chromium's entire process architecture is unnecessary. [Chromium audio architecture](https://raw.githubusercontent.com/chromium/chromium/main/media/audio/README.md)

WebRTC APM provides speech enhancement including echo cancellation, noise suppression and gain control. PipeWire's echo-cancel module exposes a cleaned microphone source and a speaker-reference sink; both directions matter. These components can operate without a browser. [WebRTC APM](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/audio_processing/g3doc/audio_processing_module.md), [PipeWire echo cancellation](https://docs.pipewire.org/page_module_echo_cancel.html)

## 4. JARVIS already has most of the foundation

| Existing implementation | Evidence | Remaining work |
| --- | --- | --- |
| Direct Gemini Live streaming | [core/agent.py](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:2069) | Compare effective model, voice, VAD and prompt settings with the reference |
| 16 kHz input / 24 kHz output | [core/config.py](/home/g0pi/Projects/JARVIS-OMA/core/config.py:50) | Keep framing consistent across processors and backends |
| Server interruption and residual clearing | [core/agent.py](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1407) | Test cancellation during processing, queued playback and reconnection |
| Resumption and context compression | [core/agent.py](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1838) | Distinguish planned renewal, failure, mute and user cancellation |
| Optional native C PipeWire companion | [native README](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native/README.md:1) | Prove audible quality, recovery and parity before promotion |
| Native endpoint/process ownership checks | [native_backend.py](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native_backend.py:137) | Test device changes and graph failures |
| Local Hey Jarvis standby | [standby.py](/home/g0pi/Projects/JARVIS-OMA/audio/plugins/standby.py:89) | Make startup mode and wake-plus-first-command continuity explicit |
| Local controls and desktop service | [core/ipc.py](/home/g0pi/Projects/JARVIS-OMA/core/ipc.py:12), [service unit](/home/g0pi/Projects/JARVIS-OMA/systemd/jarvis-oma.service:1) | Standardize one unit name and effective configuration |

The native companion already has preallocated sample rings, capture aging, bounded backlog, short-turn drain handling and render-side generation acknowledgement. Its initial cushion is 80 ms. Its README explicitly says browser parity is unproven. It relies on server-confirmed interruption and uses fixed, rather than adaptive, priming.

The checked-in legacy configuration has a 320 ms cushion, requested 100 ms playback latency, and 500 ms VAD silence. Class defaults and older reports differ. These numbers belong to different stages; summing them does not produce a measured response time. [config.toml](/home/g0pi/Projects/JARVIS-OMA/config.toml:6)

An earlier read-only host snapshot found `jarvis-oma.service` running, PipeWire and WirePlumber active, and JARVIS idle/muted with model `gemini-3.8-live`. Other agents subsequently worked on service startup/shutdown. Recheck status before any rollout; this report does not claim those earlier states still hold.

### Concrete integration gap: extensions are not wired into the live path

Startup constructs the native or legacy engine directly. The microphone sender consumes `engine.async_input_queue` directly. The extension registry only processes input when its processed-input method is used. Registering a processor by itself therefore changes nothing in the current live path. [startup](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:1932), [sender](/home/g0pi/Projects/JARVIS-OMA/core/agent.py:753), [wrapper](/home/g0pi/Projects/JARVIS-OMA/audio/extension.py:208)

The wrapper's output helper calls the legacy `enqueue_playback` API; the native adapter exposes `enqueue_output(generation, chunk)`. Passing an already-created engine into the existing wrapper also skips the constructor's callback attachment. A composition adapter needs to reconcile these explicit interfaces and hook wiring. The older report's raw-bytes queue bug is no longer current: the legacy helper now uses generation-safe submission.

## 5. Target design and conversation process

```mermaid
flowchart TB
  Unit[One systemd user service] --> Python[Python conversation supervisor]
  Python --> Native[Owned native PipeWire companion]
  Mic[Physical microphone] --> AEC[Private PipeWire WebRTC AEC]
  AEC --> Native
  Native --> Input[Bounded 16 kHz capture and extension adapter]
  Input --> Python
  Python <--> Cloud[Gemini Live]
  Cloud --> Python
  Python --> Output[Generation-tagged 24 kHz output and extension adapter]
  Output --> Native
  Native --> Reference[AEC reference sink]
  Reference --> Speakers[Physical speakers]
  UI[Hotkey / jarvisctl / desktop widget] <--> Python
  Python --> Workers[Bounded tool and memory workers]
```

Normal operation:

1. The desktop session starts one JARVIS service. It selects live conversation or local wake standby according to explicit configuration.
2. The audio owner verifies the capture and playback routes. The native child continuously services device deadlines independently of model/tool work.
3. In live mode, cleaned microphone frames pass through the bounded processing path to Gemini. In wake standby, cloud audio transmission is closed and local wake detection owns consumption.
4. Gemini identifies speech turns and generates audio. Incoming PCM is framed, tagged with the current response generation, and rendered on the device clock.
5. A real interruption cancels the old generation, clears residual audio, and prevents late chunks from reviving that response.
6. Tool work proceeds outside device callbacks. Local mute and interrupt remain responsive even when the network or a tool stalls.
7. Reconnection restores only valid conversation state. Expired microphone audio is discarded; already-executed tool actions are not replayed.

## 6. Step-by-step implementation plan

### Step 1 — Establish a reproducible reference

**Action:** Record whether the reference is in normal Live mode; select the same voice, model, device, language and short prompt for both applications. Capture actual browser track settings, context sample rates and latency properties during an approved test call. Measure a fixed set of short turns, long turns and interruptions.

**Output:** A baseline table with p50/p95 response and interruption latency, audio-cut counts, conditions and raw timing evidence. Until this exists, describe parity as unmeasured.

### Step 2 — Freeze the boundary and choose one service

**Action:** Verify all seven locked files. Keep changes in unlocked orchestration, `audio/extension.py`, and isolated modules under `audio/plugins/`. Preserve the existing engine implementations and avoid monkeypatching. Coordinate with sibling agents before changing service state.

**Operational choice:** Use `jarvis-oma.service`, matching `jarvisctl`. The root installer targets `jarvis.service`, while the scripts installer targets `jarvis-oma.service`; do not run both. Normalize that difference in a separate implementation change.

**Exit condition:** One daemon owns the microphone/AEC lifecycle and the control socket; a saved rollback configuration exists.

### Step 3 — Verify the native companion already present

**Action:** Build and self-test it, then run offline adapter checks. Do not write a second native engine before evaluating this one.

```bash
cd /home/g0pi/Projects/JARVIS-OMA
python3 scripts/verify_voice_lock.py
make -C audio/plugins/native check
.venv/bin/pytest -q tests/test_audio/test_native_backend.py tests/test_audio/test_extension_playback.py tests/test_audio/test_standby.py tests/test_core/test_config.py
```

The build command is a future implementation step; this analysis tested the already-existing binary only. In a coordinated maintenance window, the existing local probe can then inspect routing and silent playback:

```bash
.venv/bin/python -m audio.plugins.native_probe --duration 20
```

That probe **opens the microphone locally**, creates a private AEC route, and renders silence. It does not demonstrate audible speech quality and was not run for this report. Avoid competing microphone owners during the comparison.

### Step 4 — Wire a real extension composition boundary

**Action:** Add an explicit adapter, for example `audio/plugins/voice_pipeline.py`, using `AudioExtensionRegistry`. Wire it through unlocked orchestration. Keep raw engine ownership explicit.

- Input processing must actually run before `send_realtime_input`; preserve mute, standby, cancellation and capture-age behavior.
- Output processing must fit the existing router's complete-frame contract. Capture the generation before processing, reject stale results, and dispatch through the appropriate existing public enqueue API.
- Connect hooks through supported constructor callbacks or orchestration event dispatch. Do not replace core methods at runtime.
- Keep optional heavy analysis off the audio callback and out of the serial microphone send deadline. Bound every tap queue.

**Exit tests:** A processor demonstrably changes one transmitted frame; dropped frames never transmit; output processing preserves 20 ms framing; interruption during processing rejects the stale result; hooks fire once in the intended order on both backends.

### Step 5 — Match acoustic behavior through measurement

**Action:** Verify that playback actually passes through the AEC reference sink and capture comes from its cleaned source. Test speaker-only playback, user-only speech and simultaneous speaking. Monitor PipeWire graph errors alongside native callback metrics.

JARVIS already uses WebRTC-based AEC; its existing configuration disables analog/digital AGC. The browser requests AGC. This is a useful experiment, not proof of the cause of better sound. If needed, add bounded post-AEC level normalization as an extension, checking clipping, noise pumping and low-volume speech. Do not stack two independent echo cancellers.

**Exit condition:** No repeated self-interruption during speaker-only output, clear user speech during double-talk, and no unexplained graph-error growth in the test interval.

### Step 6 — Tune playback and interruption separately

**Action:** Start with native 80 ms priming as the existing candidate setting. Sweep smaller/larger values under the same network conditions; log starvation and end-of-speech-to-speaker timing. Consider adaptive priming only if measured arrival jitter warrants it.

Retain 20 ms capture framing. Do not copy the browser's 256 ms callback or equate its 10 ms scheduling lead with a native buffer target. Separate local stop, server-confirmed interruption, model turn completion and audible drain in state/metrics.

**Exit tests:** Short utterances below the priming target still finish; interrupt at the start/middle/end of a reply; delayed old packets cannot resume speech; mute clears playback and prevents upstream transmission.

### Step 7 — Protect conversation scheduling and recovery

**Action:** Measure microphone queue age and send-lock wait time. The current session shares a send lock with other messages. If contention is material, introduce one bounded outbound owner with priority and expiry rules for control, microphone, tool results and optional vision. Do not merely add competing socket writers.

Retain existing resumption and context compression. Classify planned connection renewal separately from fatal failure, user stop and backend loss. Current cleanup cancels playback on reconnect; change that behavior only with tests proving which generation may safely finish. Tool calls need stable identities and deduplication across resumed sessions.

**Exit tests:** Tool/vision load does not accumulate stale speech; a brief outage recovers without replaying old microphone frames; interrupted responses remain cancelled; repeated tool execution does not occur on reconnect. Gemini's documented resumption mechanism restores session state across connections, but cannot guarantee gapless sound. [Session management](https://ai.google.dev/gemini-api/docs/live-api/session-management)

### Step 8 — Make hands-free startup explicit

**Action:** Define two modes: immediate Live connection, or local-only Hey Jarvis standby followed by Live activation. The current code has standby behavior but initial startup enters the Live path. Add startup policy in unlocked configuration/orchestration if local standby is desired.

Define how the first command after the wake phrase is preserved without replaying stale standby audio. Keep a bounded pre-roll only with explicit policy and tests. Provide visible listening/muted/reconnecting state and reliable local mute/interrupt controls. Do not depend on the browser's SpeechRecognition helper or its demo TTS for the native Live path.

**Exit tests:** Wake works with Chrome closed; mute works with the network disconnected; wake mode does not stream microphone audio to Gemini before activation.

### Step 9 — Controlled service rollout and rollback

After Steps 1–8 pass, edit the **effective** JARVIS configuration, merging into the existing audio section:

```toml
[audio]
backend = "native"
native_cushion_s = 0.08
queue_max_seconds = 10
```

The queue limit is a safety ceiling, not desired latency. Verify `JARVIS_CONFIG`, environment overrides, user configuration and the repository configuration in precedence order. `run.sh` sources `.env`, so a service-level variable can be overridden later. Do not expose secrets when inspecting those files.

During the coordinated rollout window:

```bash
cd /home/g0pi/Projects/JARVIS-OMA
JARVIS_AUDIO_BACKEND=native .venv/bin/python agent.py --check --no-skills
systemctl --user restart jarvis-oma.service
.venv/bin/python scripts/jarvisctl.py status
journalctl --user -u jarvis-oma.service -n 80 --no-pager
```

These are instructions, not actions performed by this report. Verify readiness and audio with Chrome closed. Roll back by setting the effective backend to `legacy` and restarting the same unit. Keep the legacy binary/configuration path available.

Use a **systemd user service** tied to the graphical session. This meets browserless desktop operation and accesses the user's PipeWire session. Operation before login or across logout is a different requirement; do not convert it into a root audio daemon implicitly.

### Step 10 — Promote only after the acceptance run

| Scenario | Acceptance evidence |
| --- | --- |
| 30 matched conversational turns | p50/p95 end-of-speech → first audible reply; compare against the reference |
| 20 interruptions | Stop delay and cancelled-generation replay count; replay count must be zero |
| Speaker-only and double-talk | False interruption count, intelligibility notes, clipping and AEC graph errors |
| Short and long responses | Complete short-turn tails; bounded backlog; no silent truncation |
| 60-minute conversation under ordinary desktop/tool load | Dropout count, callback duration, capture age, graph-error deltas, CPU and memory trend |
| Network loss and provider reconnect | Recovery outcome, expired frames discarded, no duplicated actions |
| Device unplug/replug and suspend/resume | Explicit loss/recovery state; no orphan companion or AEC owner |
| Browser closed | Start, wake/live, speak, interrupt, mute and status all function independently |

As initial engineering targets, aim for p95 interruption-to-silence below 250 ms, response p95 no worse than the matched browser baseline by more than 150 ms, and no unexplained audible cuts in the soak. These are proposed gates, not measured achievements or provider guarantees. Measure acoustic latency separately from enqueue timestamps; native callback execution time is not scheduler wake lateness.

## 7. Suggested implementation order

1. **Integration change:** composition adapter, actual input/output wiring, hook correctness and focused tests.
2. **Measurement change:** per-turn timing, capture age, backlog, interruption reason and PipeWire error deltas without raw-audio recording by default.
3. **Reliability change:** bounded send scheduling, explicit reconnect policy, device recovery and startup standby semantics.
4. **Deployment change:** single service name, configuration readback, matched comparison, rollout and rollback record.

Delay optional gain control, adaptive buffering and additional speech models until a measured gap justifies each one. The first milestone is a complete native conversation with Chrome closed, not a new UI or a new voice stack.

## 8. Validation performed for this report

| Check | Result |
| --- | --- |
| Native adapter, extension playback, standby and configuration tests | 37 tests and 44 subtests passed |
| Agent, legacy engine, AEC and lock selection, with IPC included | 153 tests and 10 subtests passed; 9 IPC tests initially failed during sandbox-forbidden Unix socket binding |
| IPC rerun with local socket access, excluding lifecycle test | 8 passed, 1 deselected |
| Full IPC retry | The lifecycle test stalled and was terminated; it remains unresolved, not passing |
| Existing native executable `--self-test` | Passed; existing binary, not a fresh compilation |
| Voice-lock verifier | All 7 protected files intact |
| REA saved-script analysis | Completed; static partial-application coverage |
| Acoustic/browser parity | Not measured |

Across the completed selections: **198 passing tests and 54 passing subtests**, with **one unresolved IPC lifecycle test**. Passing fixture tests do not prove real device, network or audible performance.

Reproduction commands for the completed selections:

```bash
cd /home/g0pi/Projects/JARVIS-OMA
.venv/bin/pytest -q -o cache_dir=/tmp/jarvis-voice-inventory-pytest tests/test_audio/test_native_backend.py tests/test_audio/test_extension_playback.py tests/test_audio/test_standby.py tests/test_core/test_config.py
.venv/bin/pytest -q -o cache_dir=/tmp/jarvis-voice-inventory-pytest tests/test_core/test_agent.py tests/test_core/test_ipc.py tests/test_audio/test_engine.py tests/test_audio/test_echo_cancel.py tests/test_audio/test_voice_lock.py
timeout --kill-after=5s 30s .venv/bin/pytest -q -o cache_dir=/tmp/jarvis-chrome-report-pytest tests/test_core/test_ipc.py -k 'not test_agent_run_ipc_server_lifecycle'
audio/plugins/native/jarvis-audio --self-test
python3 scripts/verify_voice_lock.py
```

The middle command records the initial mixed result, not an all-green suite. Diagnose the lifecycle test before treating it as a deployment gate.

## 9. Primary technical references

- [Gemini Live audio formats and capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities): PCM input/output and event semantics. Input is natively 16 kHz; output is 24 kHz PCM16. The API can resample declared input rates, but JARVIS's current native contract deliberately fixes 16 kHz.
- [Gemini Live WebSocket reference](https://ai.google.dev/api/live): the model session is independent of a browser frontend.
- [Chromium audio architecture](https://raw.githubusercontent.com/chromium/chromium/main/media/audio/README.md): native audio service and callback responsibilities.
- [WebRTC Audio Processing Module](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/audio_processing/g3doc/audio_processing_module.md): reusable speech-processing functionality.
- [PipeWire stream API](https://docs.pipewire.org/group__pw__stream.html): native device stream lifecycle and processing callbacks.
- [Media Capture and Streams](https://w3c.github.io/mediacapture-main/): distinction between requested constraints and actual track settings.

The localhost source and saved artifacts establish the reference's implementation. The official documents explain the underlying components; they do not substitute for the remaining real-call comparison.

## 10. Native integration and rollout — 25 October 2026

The earlier sections record the analysis-stage snapshot. The following work is
now implemented and enabled on this machine; the acceptance comparison with
Chrome remains outstanding.

### What was implemented

- The saved REA analysis of the JavaScript served by localhost:3000 informed the
  native pipeline. Browser APIs were mapped to system components; Chrome code
  was not copied into Python. REA remains a separate project.
- `audio/plugins/native/webrtc_gain.cpp` links the installed standalone WebRTC
  Audio Processing library (reported version 1.3). Gain control uses adaptive
  digital AGC1 with a limiter, -3 dBFS target and 9 dB compression gain. Capture
  is processed as two 10 ms blocks outside the PipeWire device callback.
- PipeWire retains echo cancellation and noise suppression. The added gain
  stage disables its own AEC and noise suppression to avoid duplication.
- `ExtendedAudioEngine` is connected to the real capture-send and playback
  boundaries. Extensions preserve frame length, mute state and cancellation
  generations. Failed processors retain the last valid PCM frame; the native
  capture queue and its expiry behavior remain intact.
- The native helper advertises build capabilities. Configuration checks reject
  requested gain if the helper lacks support. Startup mute is applied before
  starting audio. IPC status exposes the backend and gain selection.
- The existing Gemini realtime conversation, tools and system service remain
  responsible for dialogue. No Chrome process or browser page is required by
  this audio path.

### Reproduce the build and startup

1. Install the native dependencies listed in `audio/plugins/native/README.md`,
   including `webrtc-audio-processing-1` development headers for gain support.
2. Run `make -C audio/plugins/native WITH_WEBRTC=1 check`. Verify
   `audio/plugins/native/jarvis-audio --capabilities` reports `webrtc_gain: true`.
3. Select the following settings in the effective configuration:

   ```toml
   [audio]
   backend = "native"
   native_webrtc_gain = true
   native_cushion_s = 0.08
   noise_suppression = true
   start_muted = true
   ```

4. Run `.venv/bin/python agent.py --check --no-skills`. Confirm environment and
   `.env` overrides do not select different audio settings.
5. With the primary service stopped, run
   `.venv/bin/python -m audio.plugins.native_probe --duration 20 --webrtc-gain`.
   This reads microphone frames locally and renders silence; it sends nothing
   to a provider. Restart the primary service after the check, including if the
   probe fails.
6. Restart `jarvis-oma.service` and verify IPC reports native audio, gain enabled,
   AEC input bound and muted. Use the normal unmute control for a listening test.
7. Complete the spoken acceptance scenarios in section 6 before claiming
   equivalence to Chrome. To roll back, select `backend = "legacy"` and
   `native_webrtc_gain = false`, then restart the same unit. Keep startup mute
   enabled if preserving the current muted state.

### Verification performed during rollout

| Check | Observed result |
| --- | --- |
| Entire audio test directory plus core agent/config tests | 208 passed, 74 subtests passed |
| IPC tests with local socket access | 9 passed; earlier lifecycle stall resolved |
| Native build target and self-tests | Ring/cancellation self-test and WebRTC gain self-test passed |
| Gain test | Disabled path bit-exact; 80,000 enabled samples; quiet RMS gain 1.60; loud peak 23,438 |
| Gain capability | `webrtc-audio-processing-1`, version `1.3`, available |
| Local real-device probe | 20-second sustained phase passed; 640-byte input frames; links verified; 489,120 rendered samples; zero starved samples |
| Maximum callback duration in that probe | 123,094 ns; this is execution duration, not acoustic latency or scheduling jitter |
| Startup after activation | Native backend, gain enabled, AEC input bound, muted, service active; zero service restarts at initial verification |
| Follow-up service verification | Idle, muted, one gain-enabled native companion, zero starved samples and zero service restarts |
| Protected voice files | All seven lock hashes verified intact |

Active configuration is in the ignored repository `config.toml`. A pre-rollout
backup was saved outside the repository in the session artifact directory as
`native-rollout-config-before.toml`. The unit itself was not replaced.

These checks establish native device operation and automated contract coverage.
They do not establish audible browser parity, double-talk quality, network
recovery under load or crash-free operation. The service was deliberately left
muted, matching its pre-rollout state.

## 11. Smoothness fixes and matched-reference checks — 25 October 2026

### Reference identity

The user supplied [Jarvis-os-tech/voice-buddy](https://github.com/Jarvis-os-tech/voice-buddy),
checked out separately at commit `bc73eb90e42bed273939c5268ce1c250b9394a2f`.
Its `src/App.tsx` and `src/utils/audio.ts` exactly match the original TypeScript
embedded in the previously captured source maps. The earlier REA findings
therefore apply to these files. The temporary reference server was bound to
loopback; synthetic requests used the existing Gemini credential without
copying it into repository files. No live microphone audio was sent by the
comparison scripts.

### Reproduced issues fixed

1. **Long replies cut off:** the reference produced a 287,041-sample reply
   (about 12 seconds) fast enough to exceed JARVIS's previous 10-second backlog
   ceiling. The first native replay failed with an explicit backlog error.
   Native delivery now maintains a bounded 60-second future-audio queue by
   default (configurable up to 120 seconds), while consumer credit admits only
   one second into the device transport. All three replies then replayed fully.
   This ceiling bounds memory; it does not delay startup by 60 seconds.
2. **Cancellation delayed by pending audio:** wholly unsent packets are now
   discarded before the latest flush. A partially written packet retains its
   suffix so cancellation cannot corrupt the pipe protocol. Repeated interrupts
   reassert the current mute state.
3. **Mic frames becoming stale while waiting:** native capture timestamps are
   rechecked after acquiring the network send lock. An expired frame is dropped
   before transport; a following fresh frame still sends.
4. **Corrections lost while thinking:** native capture now remains live while
   the model prepares a response. This matches the reference's continuous-input
   behavior; capture expiry prevents stale requests without closing the mic for
   a whole turn. Standby and mute remain authoritative.
5. **Consecutive-turn buffer bypass:** completion on an exact render-callback
   boundary now resets priming, so the following reply receives its intended
   cushion. Empty zero-cushion playback no longer falsely counts starvation.

The native C regressions were reproduced against the original render code and
pass after the fix. Added tests cover jitter, short turns, 100 cancellations,
partial-write cancellation, long-response credit, continuous input while
thinking, and expiry at the actual send boundary. All protected voice files
remain unchanged.

### Measured results

- **Final regression suite:** 244 tests and 74 subtests passed, covering audio,
  agent/configuration, IPC, startup and worker lifecycle. Voice-lock verification
  confirmed all seven protected files intact.

- **Final local device run:** 300 seconds under one controlled CPU-load worker,
  15,000 paced input-to-render test frames and 7,200,000 rendered samples;
  zero starved playback samples and zero dropped capture frames. The run uses
  silence, so these are transport/device checks, not subjective sound ratings.
- **Turn and interrupt checks:** 30 completed turns and 20 interruptions;
  maximum interruption acknowledgement 80.53 ms, p95 79.96 ms. These are native
  acknowledgement times, not measured speaker-to-ear silence latency.
- **Owned-helper crash recovery:** 52.88 ms in this run. This does not measure
  provider-network reconnection or physical-device replacement.
- **Resource observations:** helper RSS grew by one 4,096-byte page; maximum
  callback execution 2.04 ms. Maximum capture delivery gap, including forced
  recovery, was 161.61 ms. This is a five-minute check, not a leak proof or
  a 60-minute conversation soak.
- **Identical provider audio replay:** 72,961 / 90,001 / 287,041 supplied samples
  all completed without starvation. The native fixed-frame router added
  479 / 239 / 479 trailing zero samples respectively, each under 20 ms.
- **Chrome reference scheduler:** the actual saved `AudioQueuePlayer` ran in
  Chrome's `OfflineAudioContext` with the same provider chunk timing, grouped
  to its 128-sample rendering quanta. Scheduled inter-chunk gaps were
  1,775 / 1,263 / 1,135 samples. This controlled scheduler result is not a
  measurement of the user's original live browser call or acoustic output.
- **Real JARVIS/Gemini speech loop:** two synthetic spoken turns completed using
  JARVIS's actual sender, receiver and configuration, with zero stale frames
  sent. End-of-input to first reply audio was approximately 845 ms and 1,011 ms.
  Device output was tested separately using the exact captured PCM.
- **Original relay with browser-equivalent 256 ms mic batching:** the same two
  inputs completed in approximately 1,321 ms and 1,416 ms to first reply audio.
  The runs share model and voice but differ in provider VAD configuration and
  occur at different times. Two nondeterministic trials do not establish a
  statistically reliable latency advantage.

### Reproduction and remaining limits

Use `audio/plugins/native_acceptance.py` for the local repeatable run described
in the native README. The session artifact directory contains
`native-smoothness-acceptance.json`, `native-provider-replay.json`,
`voice-reference-stream.json`, `jarvis-chrome-provider-comparison.json`,
`native-live-synthetic-conversation.json`, and
`reference-live-synthetic-conversation.json`, along with the local replay and
capture scripts. The reference fixtures contain only synthetic test speech.

The implementation fixes the observed cutoffs and timing defects and matches
continuous input and uninterrupted playout in the exercised scenarios. It does
**not** certify identical microphone/room acoustics, double-talk echo quality,
all network conditions, device unplug/suspend recovery, or crash-free operation.
A real spoken A/B comparison and the longer acceptance scenarios in section 6
remain necessary for those claims. The service is left muted, as before.

## 12. Follow-up repair for intermittent breaks — 26 October 2026

Earlier inspection found the following possible failure paths. Those historical
log entries did not establish the cause of the user's active conversation breaks:

- A PipeWire playback stream could lose its target after a sink, dock, or
  session-graph change. Recovery previously reopened the native child against
  stale private AEC nodes. Native stream recovery now closes and recreates the
  private echo-cancel graph before reopening the companion, then verifies both
  graph directions again.
- Repeated provider transport timeouts could reach a 30–35 second retry delay.
  An initial change reset the retry budget at every successful connection;
  section 13 corrects that because repeated worker failures must remain bounded.
  Ordinary transient
  reconnects use short exponential delays capped at 8 seconds; HTTP 429 keeps
  its deliberate longer backoff.

The native helper self-tests, startup/recovery tests, and audio pipeline tests
passed after this repair. The service was rebuilt and restarted successfully;
it is idle, using the native backend, and remains muted. The latest status has
zero restarts and no immediate `target not found` error.

## 13. Current disconnects and latency report review — 26 October 2026

Timestamped logs show abnormal WebSocket closures (1006) at 17:21:42 and
17:27:35 IST. In both cases, the running code discarded its provider resumption
handle and started a fresh conversation. The first reconnect reached LIVE at
17:21:46. This proves a conversation continuity defect; it does not prove the
network cause or explain every perceived interruption.

Repairs in the unlocked conversation coordinator:

- Preserve the provider resume handle on transport errors. Discard it only if
  a resumed connection's setup is explicitly rejected (400/1008), or if the
  provider marks its handle nonresumable. Provider model switching and standby
  retain their existing separate policies.
- Keep retry limits for unexpected worker failures, including failures after a
  successful connection. SDK-wrapped abnormal transport close codes qualify for
  transient retry. Rate-limit backoff remains intact.
- Delay background notices while the user is speaking, a reply is pending,
  tools are executing, playback is active, or JARVIS is muted. A delayed startup
  greeting is suppressed if the conversation has already started. This avoids
  unsolicited `send_client_content(turn_complete=True)` preempting that turn.
- Count and log provider interruption events without recording transcript text.
  IPC exposes `provider_interruptions` for future symptom correlation.

The 17:27 live status showed 832 starved native samples (about 34.7 ms total at
24 kHz) and 10 rebuffers over that process lifetime. The counters do not identify
which utterance was affected. Zero PortAudio underflows does not imply zero
native starvation. The playback cushion remains 80 ms.

### Review of the supplied latency analysis

The external report is useful as a hypothesis list, not a measured latency
waterfall. A TCP connection time cannot establish a particular server region,
per-turn RTT, or symmetric one-way delay. Dividing characters by four estimates
tokens; it does not measure provider prefill work on every streaming turn.

The current local catalog contains 203 declarations, with 88,058 serialized
schema characters and a 30,504-character default instruction. The existing
Groq option reduces that to 78 declarations and 34,885 schema characters, while
leaving the instruction unchanged. It does not reduce the catalog to about ten
tools. It also adds a second provider request for local commands, so reduced
setup size alone does not prove faster command execution.

The proposed 280 ms/HIGH endpointing and 40 ms playback cushion are not enabled
while premature interruptions remain under investigation. Google's guidance
warns that short silence thresholds can split natural pauses; see
[Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities).
No locked voice file or runtime monkeypatch is needed for the repairs above.

Local verification: 251 tests and 74 subtests passed across the audio suite,
agent, startup/retry, configuration, greeting, new continuity regressions and
Groq router tests. Another 38 tests and 9 subtests passed for IPC, background
workers, mute and video/audio contention; those tests require permission to
create temporary local Unix sockets. Total: 289 tests and 83 subtests.
Voice-lock verification passed for all seven files.
These checks prove the exercised control flow, not subjective Chrome parity or
instantaneous cloud responses.

### Approved synthetic cloud timing comparison

After explicit user approval, six real Gemini calls exercised LiveVoice's
sender/receiver with identical synthetic PCM and the local default system
instruction/tool declarations. Two rounds used reversed profile ordering.
Tools were never executed, no microphone was captured, and physical speaker
output was not measured. The live learning bundle was not included. Timing
begins at the final submitted speech frame after trimming the fixture's silent
tail with a fixed amplitude threshold; it is not a human speech-end annotation.

| Profile | Round 1, first audio | Round 2, first audio |
| --- | ---: | ---: |
| Gemini tools, 500 ms end pause | 2,942.5 ms | 1,751.8 ms |
| Gemini tools, 350 ms end pause | 2,110.0 ms | 1,190.5 ms |
| Groq routing declarations, 350 ms end pause | 1,514.5 ms | 1,367.8 ms |

All six completed with zero stale microphone frames in the test. Two trials per
profile do not isolate the effect from provider/network variance or establish
percentiles. The router profile measures Gemini voice delivery only, not the
extra Groq request required to execute a desktop command.

Applied locally: `config.toml` now uses `silence_duration_ms = 350`, retaining
LOW end sensitivity and the 80 ms native cushion. This is a reversible latency
tradeoff: a user pause longer than the endpoint threshold can end a turn sooner.
The Groq router remains disabled because it did not consistently improve on the
350 ms profile and command execution latency was not exercised. No IP addresses
were pinned and the protected downstream code was not altered.

Raw results: `latency-profile-comparison.json` in the session artifact directory.
The approved test script is saved there as `jarvis-latency-compare.py`.

### Provider interruption follow-up

After the first repair restart, the new counter recorded 11 provider-triggered
interruptions by 17:34:28 IST. These are separate from connection failures and
do not prove false detection: transcripts and a synchronized room recording
were not collected. As a mitigation for the reported self-cutoffs, local
`start_sensitivity` was reduced from HIGH to LOW while retaining server barge-in,
LOW end sensitivity, 350 ms end pause and 80 ms playback cushion. This requires
real conversation validation; the six timing trials above used HIGH start
sensitivity, so their numbers are not a measurement of this final adjustment.
