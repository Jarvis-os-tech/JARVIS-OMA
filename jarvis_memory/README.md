# `jarvis_memory` Compatibility Bridge

This package serves as a root-level backward-compatibility shim for `jarvis_memory`.
The active production code has been consolidated into:
- [`memory/codes-dev/jarvis_memory/`](../memory/codes-dev/jarvis_memory)

All imports of `jarvis_memory` (e.g. `from jarvis_memory.bridge import MemoryBridge`) automatically resolve to `memory/codes-dev/jarvis_memory`.
