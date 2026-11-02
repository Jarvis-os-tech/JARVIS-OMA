# Reactive JARVIS island

Source for the user's installed `omarchy-jarvis-island` plugin, imported from
`~/.config/omarchy/plugins/omarchy-jarvis-island/` on 26 October 2026. The
existing media, timers, calendar, weather, notification and system integrations
are retained. Reference-only `views_ref/` copies are not part of this source.
The original plugin credits remain in `manifest.json`.

## Changes

- A two-line compact voice face and a larger, organized voice/system dashboard.
- Both compact JARVIS faces show the real battery percentage and charging state.
  Weather and the microphone button are absent from the compact faces. Voice
  controls and weather navigation remain available in the expanded dashboard;
  sound and display sliders are omitted from that dashboard.
- Cyan listening, mint speech, violet processing, amber mute/standby and quiet
  offline states, with matching companion, rim, and restrained halo lighting.
- Measured microphone input drives the listening bars and a small width response.
  Speaking/processing bars indicate activity, not measured output audio.
- CPU utilization comes from successive `/proc/stat` deltas; memory pressure uses
  `MemTotal` and `MemAvailable`. Missing/initial readings display `--`.
- The metadata-only `scripts/island_status.py` process samples the daemon at
  4 Hz during voice activity and 1 Hz otherwise. No audio, transcripts or tool
  arguments are captured by the island helper.
- Mute waits for daemon readback, serializes repeated clicks, and reports command
  errors. Playback interruption is labeled “Stop speaking.”
- Opened panels accept keyboard focus on demand and Escape closes them.

The existing weather provider is retained; unavailable weather no longer starts
with fabricated temperature/humidity values. Agent-approval hook behavior is
unchanged by this visual update.

## Preferences

The plugin's existing entry in `~/.config/omarchy/shell.json` accepts:

- `reactiveGlow: true` (default): subtle voice activity halo.
- `reducedMotion: false` (default): set true to stop companion/activity cycles,
  voice width response, edge sweeps, spring resizing and view reveal animations.
- Existing `glow` remains the separate music-glow setting.

The bridge currently uses this installation's existing absolute project paths.
Keep `scripts/island_status.py` available in the JARVIS project when deploying
these files. This plugin does not alter the locked voice core.

## Verification and rollback

Run `.venv/bin/pytest -q tests/test_core/test_island_status.py
 tests/test_core/test_island_reactive_model.py tests/test_core/test_voice_orbit.py
 tests/test_audio/test_voice_lock.py` as one command, then
`python3 scripts/verify_voice_lock.py`.

The 26 October update passed 24 focused tests. All 48 QML files parsed, and
six voice-state component previews rendered with the installed Quickshell.
The deployed plugin is backed up at
`~/.local/state/jarvis/island-backups/20261026-180029/`.
Restore that directory to the plugin path and refresh the shell to roll back.
Plugin updates should be applied together; a shell refresh may be needed to
invalidate cached imported QML types.
