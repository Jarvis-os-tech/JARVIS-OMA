# GitHub voice restoration — 28 October 2026

**Historical baseline:** The restoration described below was followed by fixes for self-talk and failed reconnects. Current behavior and limits are documented in [Protected speech turns](VOICE_TURN_PROTECTION_2026-10-28.md).

**VERIFIED:** GitHub was fetched before selecting the source. Commit [`2319135ed55c804fcb488f996701c32aa85de5dc`](https://github.com/Jarvis-os-tech/JARVIS-OMA/commit/2319135ed55c804fcb488f996701c32aa85de5dc) contains the exact original `agent.py` and `echo_cancel.py` blobs found in the saved JARVIS-OMA (Copy) folder. The user confirmed that copy replied clearly during a live comparison.

## Active runtime

- **VERIFIED:** The existing enabled `jarvis-oma.service` starts `/home/g0pi/Projects/JARVIS-OMA/agent.py`.
- **VERIFIED:** The root entrypoint now executes `core/stable_voice.py`: the saved GitHub voice loop with status, explicit mute/unmute and manual Stop speaking integrated through the existing `core.ipc` server. Speech transport retains the saved `pw-record`/`pw-play` approach, pacing and provider-confirmed interruptions.
- **VERIFIED:** `core/stable_echo_cancel.py` is byte-identical to the saved GitHub echo module (Git blob `a5c263e299d719c496f677eddcd7ad98873e6ccc`). No extra gain, speech gate, native companion, response scheduler or composed engine adapter is used by this live voice loop.
- **VERIFIED:** The new runtime uses the same `/run/user/1000/jarvis.sock` as the panel. Status broadcasts reflect its actual connection, microphone level and playback activity.
- **VERIFIED:** Numbered Gemini keys are supported without logging them; microphone mute masks cloud-bound frames and discards current output. Desktop tools, memory and camera integrations are paused in this speech-only runtime.
- **VERIFIED:** The prior `core.agent` import API remains available for compatibility and tests. Its experimental audio options and `config.toml` tuning do not select the current root-entrypoint voice loop.

## Verification

- **VERIFIED:** 59 selected automated tests passed: restored voice behavior, saved echo behavior, mute privacy, late-audio cancellation, IPC/subscription controls, CLI controls and protected voice integrity.
- **VERIFIED:** Root `./run.sh --check` passed with desktop skills disabled. All seven protected voice files remain intact.
- **VERIFIED:** After activation, the main service reported `audio_backend=github-reference`, `audio_source_revision=2319135`, microphone unmuted and a listening connection. The observed session recognized one speech input and received 151,200 bytes of provider audio; `pw-play` was running under the main service.
- **VERIFIED:** The panel's `orbit_status.py --subscribe` process was running against the main project's socket. The separate saved-copy process is not the selected runtime.
- **UNVERIFIED:** Acoustic quality of prolonged conversations after this final integration still requires user feedback. A received PCM count is not proof of glitch-free audible playback.

## Archive and scope

**VERIFIED:** Superseded audio sources and configurations are preserved under `/home/g0pi/Projects/JARVIS-OMA/issus voice/`, with source checksums. Protected originals were retained as required by AGENTS.md; this restoration changes the execution path rather than deleting locked files. Unrelated dirty work was preserved.

**PLANNED:** Keep speech stable on this source before reintroducing OS tools, memory or new audio processing. The prior recovery notes describe historical experiments and are superseded by this document.
