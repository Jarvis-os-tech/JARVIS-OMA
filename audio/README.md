# Audio Feature Package (`audio/`)

The `audio/` package manages low-latency desktop audio capture, playback routing, and acoustic echo cancellation (AEC) for JARVIS-OMA.

## Components

- **`echo_cancel.py` (`EchoCancellation`)**:
  - Dynamically loads and configures PipeWire's WebRTC Echo Canceller module (`libpipewire-module-echo-cancel`).
  - Creates dedicated, isolated virtual nodes:
    - Capture source: clean 16 kHz mono PCM feed from the physical microphone.
    - Playback sink: reference-routed 24 kHz mono PCM sink for agent vocal responses.
  - Automatic volume restoration and state cleanup on session exit or unexpected failure.
  - Supports configurable microphone volume capping to eliminate physical feedback distortion.

## Architecture

```text
Physical Mic ────> [PipeWire WebRTC AEC] ────> 16 kHz PCM ────> Gemini Live
Physical Speaker <── [Echo-Cancel Sink] <──── 24 kHz PCM <──── Gemini Live
```

## Usage

```python
from audio.echo_cancel import EchoCancellation

echo = EchoCancellation()
await echo.start(volume_percent=35)
try:
    ...
finally:
    await echo.close()
```
