# Remaining omarchy-voice integration gaps

Verified 1 November 2026 (Asia/Kolkata).

## Implemented

- Durable task notices and watched terminal results now reach the Gemini voice
  loop. A single monitor survives provider reconnects and private standby.
- Idle voice announces one result at a time. Muted/offline/standby delivery uses
  local desktop notifications; no new cloud session is opened for delivery.
- Notices are acknowledged after transport/notifier acceptance. Failed delivery
  remains pending. Durable task notices survive restarts; terminal-watch notices
  remain in memory during the current daemon lifetime. A spoken result may be
  interrupted after acceptance; this is not a guarantee that the user heard it.
- Background results cannot execute model-requested tools, interrupt active
  speech, bypass a pending confirmation or become a saved conversation exchange.
- Local `jarvis listen confirm` and `jarvis listen cancel` operate on the voice
  adapter's held action through the protected control socket. Cancellation also
  interrupts the current reply; cancelling independent tasks is separate.
- `jarvis task` provides submit/list/status/read/cancel/resume, `jarvis vision`
  provides start/inspect/status/stop/quit, and `jarvis say` invokes the configured
  typed planner. These commands use the same JARVIS control settings.
- `jarvis doctor` checks enabled features and configured credential names without
  invoking providers or opening devices. It replaces the old-app diagnostics.
- The installer now includes the complete desktop skill dependency packages,
  resources and entry modules, preventing silent loss of capabilities outside
  the source checkout.

## Verification

Full suite: **509 tests and 86 subtests passed in 16.01 seconds**.

Coverage includes synthetic provider sessions, untrusted result tool rejection,
busy/muted speech, standby delivery, retries, durable notices across adapter
restarts, terminal output preservation, concurrent speech on send failure,
local confirmation/cancellation, asynchronous socket confirmation, CLI settings,
and installing/importing desktop skills from an isolated temporary home.

Shell syntax and whitespace checks for the touched implementation paths passed.
The full suite reports one existing ONNX Runtime warning about CUDA being
unavailable; CPU/Azure providers are available.

Live `jarvis doctor --json`: **passed**, including voice and enabled task
runtime/credential checks. Camera support is implemented but disabled in the
current JARVIS configuration. Tests do not establish physical-camera operation,
provider model access, paid task execution or audible announcement delivery.

The installed application points to this source checkout. A live status check
found the running service processing a delayed response, so it was not restarted.
The completed integration loads on its next restart.
