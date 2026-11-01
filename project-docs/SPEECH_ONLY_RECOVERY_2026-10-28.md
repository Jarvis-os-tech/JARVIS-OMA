# Speech-only recovery — 28 October 2026

**Superseded:** The temporary saved-copy launcher described below is no longer active. See [GitHub voice restoration](GITHUB_VOICE_RESTORE_2026-10-28.md) for the current main-project voice runtime and restored panel connection.

## Current purpose

**VERIFIED:** The user requested clear speech-to-speech first, with OS integration deferred. The saved reference `/home/g0pi/Projects/JARVIS-OMA (Copy)` was tested live; the user confirmed: “It replied clearly.”

**VERIFIED:** The existing `jarvis-oma.service` now launches that reference with `--no-skills` through `scripts/voice_recovery.py`. Its existing graphical-login autostart remains enabled. The reference files were not edited.

## Evidence and comparison

| Label | Finding |
|---|---|
| VERIFIED | Reference offline tests freshly passed: 32 tests and 11 subtests. Launcher tests passed: 3. |
| VERIFIED | Original PortAudio engine/echo/extensions/startup/greeting/connection tests passed: 133 tests and 17 subtests. This did not prove acoustic quality. |
| VERIFIED | Reference uses `pw-record` at 16 kHz, `pw-play` at 24 kHz, a bounded playback queue and provider-confirmed interruptions. It does not use the recent native companion or PortAudio playback adapter. |
| VERIFIED | Reference VAD: high start sensitivity, low end sensitivity, 200 ms prefix, 400 ms silence, automatic provider interruptions. Extra WebRTC gain and noise suppression are disabled in this path. |
| VERIFIED | Current integrated echo-cancel graph showed rising PipeWire error counts even when application playback-error counters were zero. Disabling noise suppression alone did not remove those errors. |
| VERIFIED | A temporary 960-frame graph-clock test did not improve the counts; `clock.force-quantum` was restored to automatic (`0`). |
| VERIFIED | The clear-sounding reference comparison also had nonzero PipeWire graph-error growth. Do not equate those counters alone with audible chopping, or claim the graph has no errors. |
| VERIFIED | All seven protected audio files remain intact. |

## Operation and limits

- **VERIFIED:** Recovery selects the first configured Gemini key without printing it, removes the newer launcher's PipeWire-period environment overrides, and prevents Python cache writes in the saved reference folder.
- **VERIFIED:** Speech-only mode disables desktop tools. The old reference does not expose the main project's IPC socket, HUD controls, project-memory features or local wake-word standby. A disconnected HUD is expected in this temporary mode and does not establish that voice is offline.
- **UNVERIFIED:** Long sessions, noisy rooms, double-talk and network interruptions still require listening tests. No claim of perfect audio is supported.
- **PLANNED:** Reintegrate current OS capabilities only after confirming stable speech on this baseline. Keep the saved reference unchanged.

## Reversibility

**VERIFIED:** Service selection is isolated in `/home/g0pi/.config/systemd/user/jarvis-oma.service.d/90-voice-recovery.conf`. Removing only that override, reloading the user service manager and restarting JARVIS restores its ordinary launcher; this has not been done because recovery mode is currently intended.

**VERIFIED:** A private configuration backup from before the PortAudio restoration is saved at `/home/g0pi/.local/state/jarvis/voice-recovery/config.before-portaudio-20261028.toml`. Do not overwrite unrelated service overrides or reset the dirty project checkout.
