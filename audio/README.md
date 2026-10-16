# Audio Feature Package (`audio/`)

The `audio/` package manages low-latency desktop audio capture, playback routing, acoustic echo cancellation (AEC), and native real-time PortAudio C-thread streaming for JARVIS-OMA.

## Components

- **`engine.py` (`NativeAudioEngine`)**:
  - Direct hardware audio I/O using PortAudio C-bindings via `sounddevice` and `numpy`.
  - Audio callbacks run inside dedicated high-priority C-threads, completely bypassing Python's Global Interpreter Lock (GIL).
  - Upstream capture: non-blocking 16 kHz mono PCM queue feeding the Gemini Live WebSocket session.
  - Downstream playback: thread-safe `queue.SimpleQueue` bridge feeding the PortAudio DAC callback.
  - Generation-fenced barge-in: instant $O(1)$ ring-buffer purge via PortAudio `abort()` and queue drain.
  - Programmatic PipeWire AEC virtual node resolution with automatic retry and graceful fallback.

- **`downstream.py` (`DownstreamRouter`)**:
  - Frame accumulator that buffers variable-length Gemini WebSocket audio chunks and slices them into exact 960-byte (20 ms @ 24 kHz) matrices.
  - Padded flush on turn completion and instant residual buffer clearance on barge-in.

- **`echo_cancel.py` (`EchoCancellation`)**:
  - Dynamically loads and configures PipeWire's WebRTC Echo Canceller module (`libpipewire-module-echo-cancel`).
  - Creates dedicated, isolated virtual nodes:
    - Capture source: clean 16 kHz mono PCM feed from the physical microphone.
    - Playback sink: reference-routed 24 kHz mono PCM sink for agent vocal responses.
  - Automatic volume restoration and state cleanup on session exit or unexpected failure.
  - Supports configurable microphone volume capping to eliminate physical feedback distortion.

## Architecture

```text
Physical Mic ────> [PipeWire WebRTC AEC] ────> [sd.RawInputStream] ──(C-thread)──> [async_input_queue] ────> Gemini Live
                                                                                                                   │
Physical Speaker <── [Echo-Cancel Sink] <──── [sd.RawOutputStream] <──(C-thread)── [c_output_queue] <── [DownstreamRouter]
```

## Usage

```python
from audio import EchoCancellation, NativeAudioEngine, DownstreamRouter

echo = EchoCancellation()
await echo.start(volume_percent=80)
engine = NativeAudioEngine()
engine.start(echo.source, echo.sink)
try:
    ...
finally:
    engine.terminate()
    await echo.close()
```
