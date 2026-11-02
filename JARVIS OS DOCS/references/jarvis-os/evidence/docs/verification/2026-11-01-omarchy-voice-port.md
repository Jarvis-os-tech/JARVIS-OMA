# omarchy-voice port verification

Verified 1 November 2026 (Asia/Kolkata).

## Changes verified

- Reused the existing omarchy-voice port in `jarvis_control`, preserving local
  desktop, voice and memory extensions.
- Parsed advanced upstream control/task/vision settings from JARVIS's existing
  configuration, shared by the voice adapter and the control CLI.
- Retained built-in policy patterns when adding custom patterns.
- Rejected disabled tools before voice-adapter/CLI dispatch and rejected
  non-object JSON arguments in the CLI.
- Removed the direct-file task worker's dependency on the `omarchy_voice` shim.
- Loaded JARVIS credentials in independently started Responses workers.
- Serialized owned camera cleanup through the control worker on shutdown.
- Cached tool-name routing in the combined memory/control adapter.
- Added conditional camera/task instructions to voice, with truthful explicit
  task-status retrieval instead of promising automatic completion announcements.
- Included upstream provenance and integration documentation in installation.

## Evidence

- Targeted configuration/control/installation suite: **128 passed in 5.85s**.
- Full local suite: **486 passed, 86 subtests passed in 10.05s**.
- Additional CLI configuration/dispatch regression checks: **3 passed in 0.10s**.
- Installer exercised in a temporary home, outside the source working directory.
- Direct-file task worker import exercised with only the control package present.
- Installer shell syntax check passed.
- Installed application and control command resolve to this source checkout.

The full suite emitted one ONNX Runtime warning that CUDA is unavailable and
CPU/Azure providers are available. Restricted execution stalled on asynchronous
worker communication; the full and targeted suites passed with normal local
socket/thread access. No provider inference, paid worker execution, physical
camera inspection or live spoken-command session was performed. The running
service was not restarted by this work.

The checkout also contains changes from other sessions. This verification does
not attribute those changes to this integration. A repository whitespace check
reports existing trailing/blank-line issues outside these integration edits.
