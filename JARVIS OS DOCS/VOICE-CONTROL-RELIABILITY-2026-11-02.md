# Voice and PC control reliability — 2 November 2026

The running JARVIS service now uses the tested voice/control changes below.
The current scope is everyday voice and PC control. The WhatsApp messaging
workflow is deferred at the user's request.

## Changes applied

- Preserve the active speech turn while tools are running, including when the
  provider sends an intermediate spoken acknowledgement. Previously this could
  revoke authorization and prevent later steps of the same request.
- Keep the two-second sentence-pause allowance. Long spoken interruptions no
  longer trigger the five-second missing-response watchdog while speech is active.
- Attach 79 everyday/memory tools to the live voice session, with all 247 tools
  still registered for execution and specialist discovery. Ordinary PC commands
  are instructed to call native controls immediately.
- Share completion semantics across voice, device execution and filesystem
  tasks. Blocked, queued, partial, explicitly unfinished and unverified results
  cannot be promoted to completed work. Dependent actions stop for inspection.
- Use a full XKB keyboard map with conventional physical keycodes for focused
  shortcuts. A real GTK test reproduced Return reaching the application without
  activating its entry when using the previous small injector map.
- Pace literal typing and keep its keyboard connection alive briefly after the
  last character. A real test reproduced successful process exit with only a
  prefix received by the application. Input delivery remains explicitly
  unverified until its application effect is observed.
- Verify application windows after desktop-file launches. Launcher acceptance
  alone no longer proves an application opened.
- Resolve exact window addresses and reject ambiguous class targets.

## Desktop selection repair

The installed `wl-clip-persist` service was configured with `--clipboard both`.
Its takeover of PRIMARY selection cancelled the GTK entry's selected text a few
milliseconds after Ctrl+A. The fixture's Wayland trace confirmed source
cancellation; its focus remained active.

Changed the user service to `--clipboard regular` and restarted only that
service. Ordinary clipboard persistence remains enabled. Selected text stays
owned by the application; PRIMARY content is no longer persisted after its
owner exits. This follows the project's documented
[PRIMARY selection limitation](https://github.com/Linus789/wl-clip-persist)
and the [Hyprland clipboard guidance](https://wiki.hypr.land/Useful-Utilities/Clipboard-Managers/).

Configuration: `/home/g0pi/.config/systemd/user/wl-clip-persist.service`.
Backup: the same path with `.before-jarvis-selection-fix-20261102` appended.

## Verification and measured speed

The final full suite passed **1,231 tests and 142 subtests** in 46.19 seconds.
Two existing warnings concern unavailable CUDA execution; CPU execution remains
available. All 67 focused voice/control/result tests also passed after the
completion-flag guard update. Installed module hashes match the release manifest.

Live testing created a dedicated GTK window with a unique title and owned PID.
It read back the entire field, observed the entry's activation signal, selected
all text, and verified complete replacement text beginning with a dash. The
fixture always closed its own window. The workflow passed on fresh windows and
through the running daemon's execution socket. No external messages were sent.

| Running-service check | Observed time |
| --- | ---: |
| Current workspace query, median of 4 | 33 ms |
| Current volume query, median of 4 | 74 ms |
| Current brightness query, median of 4 | 100 ms |
| Enter with actual fixture activation | 192 ms |
| Complete 30-character field readback | 547 ms |

Separate reversible native checks verified volume and brightness changes in
47 ms and 99 ms respectively. Original per-channel volume and brightness were
restored. These direct-executor measurements exclude voice interpretation and
execution-socket overhead.

An isolated provider comparison using a read-only volume request measured first
audio at 1,596 ms with the full catalog and 1,354 ms with the compact catalog.
There was one sample per configuration. This used a text request and discarded
output audio: it excludes the microphone, sentence-pause allowance, speaker
playback and room acoustics. It is not an end-to-end spoken latency guarantee.

After activation the voice service reported connected/listening, an unmuted
microphone, no audio issue and no capture backlog. Human conversation in the
room remains necessary to assess perceived speech timing and interruption
behavior; automated checks do not establish universal perfection.

The final status check found standby after a successful `enter_standby` tool
call, with no error or microphone issue. Standby was preserved. “Hey Jarvis”
resumes listening.

## Installed release and recovery

Current release:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261102T054244280Z-core-voice-controls`.

Previous runtime:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261102T053905543Z-core-voice-controls`.

The pre-core-control release is also retained:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261102T044534055Z-pc-default-control`.

Activation compiled the changed modules, checked the staged catalog and keyboard
mapping, validated voice configuration, and required connected/control-enabled
health checks. Activation supports automatic rollback on failed health checks.
The release manifest records its parent and hashes of overlaid modules.

Only the voice/control changes were overlaid. The catalog constructor/property
was spliced into the installed skills module to preserve unrelated in-progress
Hermes changes in the checkout. Credentials, pairing and memory were retained.

See [verification evidence](VOICE-CONTROL-EVIDENCE-2026-11-02.json) for timings,
release details and validation scope.
