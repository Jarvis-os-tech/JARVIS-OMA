# Native PipeWire audio backend (opt-in)

This companion implements the first native audio backend for JARVIS on Linux.
The existing protected engine and its tests are unchanged. The default backend
is still `legacy`; this implementation has not established browser parity.

## Build and check

Dependencies: a C11 compiler, make, pkg-config, PipeWire development headers,
and the project's Python environment. Runtime needs a user PipeWire session,
`pw-dump`, and `pactl` for the existing private AEC module owner.

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
queue_max_seconds = 10
```

Alternatively use `JARVIS_AUDIO_BACKEND=native` and
`JARVIS_NATIVE_CUSHION_S=0.08`. Both are supported by the same existing systemd
service; see `systemd/native-audio.conf.example` for an optional drop-in. An
existing `.env` sourced by run.sh can override service environment settings.
Restart once after selecting the backend. Roll back by selecting `legacy` and
restarting. The binary is a build artifact and is intentionally gitignored.

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
- Playback has a configurable priming target and bounded backlog (1–10 s).
  Overflow is an explicit failure and recovery event, not silent truncation.
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
are unchanged; a WebSocket outage can still interrupt a reply. The existing
PipeWire AEC implementation is reused, so its observed graph errors still need
direct before/after measurement. Native callback metrics do not replace those
graph metrics. No automatic claim of real-time scheduling is made.

Before production promotion: test audible output and double-talk, microphone
permission/device changes, disconnect recovery, suspend/resume, graph error
deltas, and at least 60 minutes of conversation under load. Compare identical
model/VAD/device conditions with the browser baseline. Keep the legacy backend
available until these gates pass.
