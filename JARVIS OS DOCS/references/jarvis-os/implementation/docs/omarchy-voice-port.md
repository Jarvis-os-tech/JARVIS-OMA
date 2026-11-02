# omarchy-voice integration

JARVIS uses the local omarchy-voice source at
`/home/g0pi/Projects/pma/omarchy-voice`, revision
`8ef9d6094cff87ad88903481de2b6b4e942c4e86`. The existing port is in
`jarvis_control`; its MIT copyright and license are retained in `LICENSE`.
The source checkout is not modified. Existing JARVIS voice and memory behavior
continues to run through `jarvis_voice` and `jarvis_memory`.

Desktop control, browser/page retrieval, managed terminals, durable tasks and
optional camera inspection are exposed to the Gemini voice session by
`ControlSkills` and `UnifiedSkills`. The control CLI reads the same
`$XDG_CONFIG_HOME/jarvis-voice/config.toml` file as voice.

Root switches `enable_tools`, `allow_shell`, `dry_run`, `tasks_enabled` and
`vision_enabled` control feature availability. `enable_tools` controls attachment
to voice; the control CLI remains independently usable. Tools disabled by the
other switches cannot be invoked through the adapter or control CLI.

Advanced upstream settings go in `[control]`, `[control.tasks]`,
`[control.vision]` and other upstream sections beneath `control`. Root switches
win over duplicated values in the control table. Unknown control keys are
rejected during configuration validation. See `configs/config.toml.example`.
Policy lists retain built-in confirmation/deny patterns unless their explicit
upstream replace flags are set.

Keys for configured provider environment variable names are read from JARVIS's
private `env` file; an existing environment variable wins. Durable workers load
the same file after systemd starts them independently. Camera capture starts
only on request and owned capture is stopped when the adapter closes. Closing
voice does not cancel independent durable tasks. Task completion is announced in a brief idle voice turn. While muted,
disconnected or in standby, results use local desktop notifications without
opening a cloud session. If notifications are disabled/unavailable, results
remain pending. Durable notices survive restart; terminal-watch notices remain
in memory until delivered. Acceptance by the voice transport or desktop notifier
acknowledges a notice; playback interruption can prevent it from being heard.
Background results cannot authorize tool execution and are not saved as a
user/assistant conversation exchange. `task_status` remains available for checks.

For compatibility, upstream internal task/camera paths remain under
`omarchy-voice` in the XDG state/runtime directories. Existing task data is not
moved or deleted. Set `[control.tasks].root` to select a separate task store.
The `omarchy_voice` compatibility shim is not needed by installed task workers.

## Everyday commands

```sh
jarvis task submit /path/to/task-spec.json
jarvis task list
jarvis task status TASK_ID
jarvis task read TASK_ID results.txt
jarvis task cancel TASK_ID
jarvis task resume TASK_ID --guidance "Continue the checks"
jarvis task --dry-run resume TASK_ID
jarvis vision start
jarvis vision inspect "What is this connector?"
jarvis vision stop
jarvis say --dry-run "Open a terminal"
jarvis doctor --json
jarvis listen confirm
jarvis listen cancel
```

A task specification is a JSON object with `goal`, nonempty `criteria` (an array
of acceptance criteria), and a stable `request_key`. Optional `provider` is
`responses` or `codex`; optional `network` grants network access to the task.
The typed planner uses `[control]` provider settings; it does not open the voice
microphone. Dry-run may still use the planner API for interpretation.

The private local socket confirms/cancels the same held desktop action as voice.
`listen cancel` also interrupts the current reply; independent durable tasks
require `task cancel`. Camera start/inspect respect `vision_enabled`; status and
stop remain available for cleanup. Diagnostics use the JARVIS configuration,
report key presence without values, and never open devices or invoke models.

## Checks

```sh
bin/jarvis control list
bin/jarvis control call system_query '{"topic":"time"}'
bin/jarvis control call launch_app '{"app":"firefox"}' --dry-run
.venv/bin/python -m pytest tests/test_config.py tests/test_control tests/test_installation.py
```

The installer copies voice, control, memory and desktop skill dependencies,
guides, manifests, attribution and CLIs. It
preserves existing configuration. Install with `scripts/install.sh`, then
restart an idle voice service with `jarvis restart` to load code changes.
Local tests use mocked providers and isolated installation directories; live
speech, camera/cloud inference and paid task execution need separate checks.
