# Native PipeWire audio backend (opt-in)

This companion implements the first native audio backend for JARVIS on Linux.
The existing protected engine and its tests are unchanged. The default backend
is still `legacy`; this implementation has not established browser parity.

## Build and check

Dependencies: a C11 compiler, make, pkg-config, PipeWire development headers,
and the project's Python environment. Runtime needs a user PipeWire session,
`pw-dump`, and `pactl` for the existing private AEC module owner.

Optional native gain control also needs a C++17 compiler and the
`webrtc-audio-processing-1` development package. The build detects that package;
`WITH_WEBRTC=1` requires it, while `WITH_WEBRTC=0` builds without gain support.
Check the actual binary with `audio/plugins/native/jarvis-audio --capabilities`.

```sh
make -C audio/plugins/native check
.venv/bin/pytest -q tests/test_audio/test_native_backend.py
.venv/bin/python -m audio.plugins.native_probe --duration 20
JARVIS_AUDIO_BACKEND=native .venv/bin/python agent.py --check --no-skills
```

The local probe creates its own private AEC module, reads microphone frames
without transmitting them, renders silence, tests short turns and repeated
generation changes, and cleans up its child and AEC module. Do not run it as a
second full cloud conversation while evaluating the primary service.

To select the backend, set the following in the chosen JARVIS configuration:

```toml
[audio]
backend = "native"
native_cushion_s = 0.08
queue_max_seconds = 60
native_webrtc_gain = true
noise_suppression = true
start_muted = true
```

Alternatively use `JARVIS_AUDIO_BACKEND=native` and
`JARVIS_NATIVE_CUSHION_S=0.08`. Both are supported by the same existing systemd
service; see `systemd/native-audio.conf.example` for an optional drop-in. An
existing `.env` sourced by run.sh can override service environment settings.
Restart once after selecting the backend. Roll back by selecting `legacy` and
restarting. The binary is a build artifact and is intentionally gitignored.

`native_webrtc_gain` requires the native backend and a gain-capable helper.
Its environment override is `JARVIS_NATIVE_WEBRTC_GAIN=true`; startup mute uses
`JARVIS_START_MUTED=true`. Startup mute is applied before audio starts. Unmute
using the ordinary JARVIS control when ready. For a local device check with gain,
run `.venv/bin/python -m audio.plugins.native_probe --duration 20 --webrtc-gain`
while the primary voice service is stopped, then restart the same service.

Gain processing uses the installed WebRTC Audio Processing library, with
adaptive digital AGC1, a -3 dBFS target, 9 dB compression gain and limiter.
It runs in two 10 ms blocks after capture leaves the device callback.
PipeWire owns echo cancellation and noise suppression; those features are
disabled in this additional stage to avoid processing them twice. The linked
library version is reported by `--capabilities`; it is not an extracted Chrome
binary or a promise of identical acoustic behavior.

## Process and thread ownership

- Python owns the Gemini session, tools, memory, configuration, and private AEC
  module lifecycle. It launches/reaps one companion subprocess.
- Native PipeWire callbacks own device capture/render deadlines. They perform
  bounded sample copies, short fades, and lock-free atomic counters. They never
  call Python, allocate memory, log, or perform pipe I/O.
- Native main/control code handles framed pipe I/O and packetizes capture at
  320 samples / 20 ms. PipeWire adapts 16 kHz capture and 24 kHz playback to the
  negotiated device graph. Device consumption controls playout timing.
- Preallocated single-producer/single-consumer rings separate control and device
  execution. Capture retains at most 100 ms at the native boundary and expires
  at 150 ms in Python. Old speech is not replayed after a long outage.
- Playback has a configurable priming target and a bounded future-audio queue
  (60 seconds by default, configurable from 1–120 seconds). Consumer credit
  admits at most one second into the native transport at a time, allowing
  fast-generated long replies to drain without overrunning the device ring.
  The future queue limit is a memory ceiling, not a startup delay. Beyond that
  ceiling overflow remains an explicit failure, not silent truncation.
- Interruption discards wholly unsent packets before sending the latest flush;
  any partially written packet finishes first to preserve protocol framing.
- Generation cancellation is acknowledged by the render consumer before the
  producer publishes new-generation samples. Old epochs cannot restart output.
- The adapter verifies both endpoint directions and companion process ownership
  using native PipeWire graph objects before opening the cloud session.

The child clears inherited PIPEWIRE_NODE, PIPEWIRE_LATENCY, and PIPEWIRE_QUANTUM
for its own context; independent source/sink targets and normal graph negotiation
replace the legacy process-wide target/forced period. This does not alter the
running PipeWire server or another application's settings.

## Protocol v1

Local pipes only, little endian. Each packet has four unsigned 32-bit fields:
`magic=0x3141564a`, `type`, `generation`, `payload_bytes`. Payload limit is 32768.

| Type | Direction | Payload |
| --- | --- | --- |
| 1 AUDIO | Python → native | PCM16 mono 24 kHz; adapter sends 480 samples |
| 2 FLUSH | Python → native | Empty; generation identifies the new epoch |
| 3 MUTE | Python → native | Empty; header generation field is boolean |
| 4 COMPLETE | Python → native | Empty; permits short final bursts to drain |
| 5 STOP | Python → native | Empty; EOF also terminates cleanly |
| 101 CAPTURE | Native → Python | u64 estimated monotonic capture time, then 320 PCM16 samples |
| 102 READY | Native → Python | Two u32 PipeWire node IDs: capture, playback |
| 103 STATS | Native → Python | Eight u64: captured, rendered in epoch, starved, dropped capture samples, max callback ns, queued playback samples, playing, applied epoch |

Capture timestamps estimate sample age from callback time and ring occupancy;
they are not hardware ADC timestamps or an acoustic latency measurement.
Callbacks report execution duration, not scheduler wake lateness. Readiness
means streams and links are verified; it does not prove AEC quality or absence
of graph xruns. Native stderr is read outside callbacks and retained bounded.

## Current limits and next gates

The initial candidate uses server-confirmed interruptions; the legacy local
FFT gate is not part of this backend. The native priming target is fixed, not
yet adaptive. Existing shared network send scheduling and reconnect cleanup
retain their existing policy; a WebSocket outage can still interrupt a reply.
Native capture continues while the model thinks, allowing spoken corrections.
Frame expiry is rechecked after acquiring the network send lock. The existing
PipeWire AEC implementation is reused, so its observed graph errors still need
direct before/after measurement. Native callback metrics do not replace those
graph metrics. No automatic claim of real-time scheduling is made.

Before production promotion: test audible output and double-talk, microphone
permission/device changes, disconnect recovery, suspend/resume, graph error
deltas, and at least 60 minutes of conversation under load. Compare identical
model/VAD/device conditions with the browser baseline. Keep the legacy backend
available until these gates pass.

For the repeatable local acceptance run (no provider, silent playback), stop
the primary voice service and run:

```sh
.venv/bin/python -m audio.plugins.native_acceptance --duration 300 --output /tmp/native-acceptance.json
```

It exercises 30 turns, 20 interruption acknowledgements, failure/recovery of
its own child, and paced playback with jitter. Always restart the primary
service afterward, even if a check fails. This probe does not establish
acoustic latency, echo quality, or network recovery.
