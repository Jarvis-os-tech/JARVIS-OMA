# Audio implementation archive

The active voice runtime is the main JARVIS project: `agent.py` executes `core/stable_voice.py`, restored from GitHub commit `2319135` with JARVIS status/mute/stop controls added. Its matching `core/stable_echo_cancel.py` is byte-identical to that GitHub revision. The service does not execute JARVIS-OMA (Copy).

The current runtime also uses `core/speech_turn.py` for local speech admission and feedback holdoff, and `core/stable_recovery.py` for connection recovery. The user confirmed it answered once and stopped. Automatic spoken interruption is temporarily disabled; manual Stop speaking remains available.

`2026-10-28-before-pipewire/` contains 23 source snapshots and the previous configuration from before activating the reference-based PipeWire transport. `SHA256.json` records the source checksums. No secrets or microphone recordings are included.

`temporary-copy-launcher/` contains the retired speech-only launcher and its tests. Its service override was removed and backed up in the user's private voice-recovery state directory.

`2026-10-28-before-github-restore/` contains snapshots of the superseded runtime, the experimental composed PipeWire adapter, and the prior configuration. The active root entrypoint bypasses that runtime. These snapshots are preserved for later repair.

`2026-10-28-before-turn-protection/` preserves the restored-but-unprotected loop before the repeat-speech and reconnect fixes, with checksums.

Protected voice files were copied rather than moved because AGENTS.md explicitly forbids modifying, deleting, or renaming them. They remain available for compatibility and tests. The native companion, PortAudio adapter, composed PipeWire adapter and advanced `core.agent` loop are not the active speech runtime. The old import API remains available for compatibility; run the project through its root entrypoint and existing service.

This is a local repair archive, excluded from Git and from the active runtime. Do not delete it or execute its snapshots as a replacement service without reviewing the current recovery notes.
