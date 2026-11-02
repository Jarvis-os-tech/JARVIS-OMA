# Verified system control through JARVIS

Common desktop requests now use `system_control` through the live voice tool
path. Volume, mute, brightness and numbered workspaces do not need command
catalogue discovery on every turn. Each change reads the current state, applies
a fixed native command and checks the resulting state before reporting success.
Other supported Omarchy commands and application/window controls continue
through their existing tools, with discovery and targeted window checks.

## Spoken examples

- “Set the volume to forty percent.”
- “Lower the volume by five percentage points.”
- “Mute the output.” / “Unmute the output.”
- “What is my current brightness?”
- “Set brightness to forty percent.”
- “Switch to workspace two.”
- “Go back.” (after a workspace switch performed by JARVIS)
- “Open the file manager.”

Use one clear request, or combine steps in their desired order. JARVIS should
perform ordinary actions without another permission question, then acknowledge
the observed result briefly. If the target remains ambiguous it should ask one
short question. Existing policy still governs held or refused operations.

## Supported fast-path actions

`volume_get`, `volume_set`, `volume_adjust`, `mute_get`, `mute_set`, `mic_mute_get`, `mic_mute_set`, `mic_mute_toggle`,
`brightness_get`, `brightness_set`, `brightness_adjust`,
`nightlight_get`, `nightlight_set`, `nightlight_toggle`,
`idle_get`, `idle_set`, `idle_toggle`,
`dnd_get`, `dnd_set`, `dnd_toggle`,
`bluetooth_get`, `bluetooth_set`, `bluetooth_toggle`,
`touchpad_get`, `touchpad_set`, `touchpad_toggle`,
`bar_get`, `bar_set`, `bar_toggle`,
`workspace_get`, `workspace_switch`, `workspace_back`.

- **Night light**: Queries temperature and state (4000K/6500K), sets explicit state or toggles via `omarchy toggle nightlight`.
- **Idle / Stay-awake**: Prevents screen sleep or restores normal idle lock via `omarchy toggle idle`.
- **Do Not Disturb (DND)**: Toggles or sets notification silencing via `omarchy toggle notification-silencing`.
- **Bluetooth**: Reads adapter power state and powers on/off/toggle via `omarchy bluetooth power`.
- **Touchpad & Bar**: Toggles or verifies hardware touchpad and Omarchy status bar visibility.
- **Microphone**: Reads hardware mic mute state or mutes/unmutes/toggles default audio source via `wpctl`.

Volume uses Omarchy's resolved physical output sink so DSP/filter-chain defaults
do not change the wrong gain. Values are bounded to 0–100%; brightness changes
are bounded to 1–100% to keep the display lit. Relative changes use percentage
points. Setting volume changes gain; mute/unmute is an explicit action.
Workspace back remembers the last successfully switched numbered workspace in
this running control session, rather than guessing from the model's memory.

## Voice integration behavior

- Tool results have explicit success/failure/confirmation/not-run states.
- Muted, unauthorized, stale, dropped and unacknowledged-interruption calls cannot execute actions.
- Startup greetings cannot initiate desktop actions.
- A failed or held action stops subsequent calls in that batch; JARVIS must
  inspect/replan instead of continuing dependent changes.
- Speech-turn and playback-generation checks prevent an old batch or event from
  finishing a newer request.
- Confirmation transcripts are ingested before a tool call carried in the same
  provider event. Actual new-turn confirmation is still required for held actions.
- Duplicate provider call IDs return the prior result without repeating the effect.
- Status includes `active_tool` and concise `last_tool` name, outcome and duration;
  arguments, page contents and private response bodies are not copied into status.
- Read-only control queries remain available in dry-run mode; setters do not execute.

## Verification on 31 October 2026

- Full suite: **295 tests and 81 subtests passed**.
- Live volume change: 39% → 38%, verified, then original per-channel values restored.
- Live brightness change: 1% → 2%, verified, then restored to 1%.
- Live workspace switch: 1 → unused 90, verified; workspace_back returned to 1.
- Live file-manager launch: org.gnome.Nautilus window verified; only the created
  test window was closed and previous focus restored.
- Live provider roundtrip: a natural-language read-only volume request called
  `system_control(volume_get)` successfully and returned 86,402 bytes of playable
  reply audio. This test bypassed the physical microphone and did not play sound.
- Seven original protected audio-core files remained unchanged.
- Installed code was backed up before deployment in
  `deployment_backup/verified-system-control-20261031-004953`.

Microphone recognition, physical speaker quality and external network conditions
are separate from these verified native state transitions. System control uses
local commands; the language/voice model still needs its provider connection.
