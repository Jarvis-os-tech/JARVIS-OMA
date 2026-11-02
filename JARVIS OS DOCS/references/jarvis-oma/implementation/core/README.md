# Core Feature Package (`core/`)

The `core/` package provides the main conversation runtime, worker coordination, and configuration parsing for JARVIS-OMA.

## Components

- **`agent.py` (`LiveVoice`)**:
  - Full-duplex voice interaction loop using Google's Gemini Live API via WebSockets.
  - Three concurrent workers:
    1. **Audio Capture Worker**: Pipes 16 kHz mono PCM from PipeWire AEC directly to the Gemini Live session.
    2. **Event Processing Worker**: Handles server-to-client events (audio output parts, text transcripts, tool calls, and interruptions).
    3. **Native Playback**: Routes 24 kHz mono PCM through the persistent PortAudio/AEC stream with generation-fenced interruption flush.
  - Signal handling (`SIGINT`, `SIGTERM`), session resumption caching, and dynamic CLI argument parsing.

- **`config.py` (`Config`, `load_config`)**:
  - Multi-source configuration loader supporting TOML (`config.toml`), JSON (`config.json`), CLI flags, and environment variables (`JARVIS_*`, `GEMINI_*`).
  - Hierarchical configuration sections: `VoiceConfig`, `SkillsConfig`, `MemoryConfig`, `ProactiveConfig`, and custom command overrides.

## Usage

```python
from core.config import load_config
from core.agent import LiveVoice, main

# Load active configuration
config = load_config()

# Entrypoint
if __name__ == "__main__":
    main()
```
