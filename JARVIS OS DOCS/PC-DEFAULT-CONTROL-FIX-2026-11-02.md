# PC-default voice and control fixes — 2 November 2026

## User contract

Every new voice request targets the PC by default. Android control requires an
explicit phone/mobile/Android reference in the current request. Earlier phone
work, pairing state, and an application name do not change that default.
Ordinary clear PC commands authorize execution through existing tools; sensitive
operations retain their existing tool-policy confirmation requirements.

## Scan and reproduced causes

Inspected voice instructions, transcription ingestion, speech-turn ownership,
tool admission/execution, intent classification, unified routing, native desktop
actions, device IPC, Android control, tool schemas, and related regression tests.
Recent runtime diagnostics showed phone-control calls and an imperative request
being classified as conversation. Live PC queries established that the native
volume, workspace, and clock tools were functional.

Twenty new regression cases initially failed, establishing these software gaps:

1. The native phone tool had no current-utterance device-target requirement.
2. Polite or prefixed commands were classified as conversational inquiries,
   blocking some ordinary control actions.
3. JSON adapter failures could be reported to the provider as completed actions.

The source prompt also contained a hard-coded phone-related backlog example,
which could bias conversation toward an old phone issue.

## Implemented behavior

- Added device selection from the current utterance, excluding quoted content
  and supported negated phone references.
- Blocked native Android control for unqualified PC requests; reject PC launcher
  and common desktop tools when only the phone is explicitly targeted.
- Applied intent checks to nested domain-tool calls as well as direct calls.
- Recognized imperative actions behind polite prefixes and assistant addressing.
- Made adapter error/unsuccessful/unverified responses failures. Preserve unknown
  outcomes and stop dependent tool batches rather than presenting them as success.
- Removed the invented phone-backlog example and added explicit instructions for
  PC defaults and ordinary automatic execution.
- Retained the preceding two-second sentence-pause setting and aligned an older
  regression test with that behavior.

Existing PC telephony through OMyPhone remains distinct from native Android app
control. Native calls from Android still require an explicit phone target.

## Verification and deployment

- Targeted control/voice suite: **205 passed** before the final additional cases.
- Full suite after all changes: **1,187 passed and 142 subtests passed**, with two
  existing ONNX CUDA-provider availability warnings; 33.74 seconds.
- Additional coverage includes the next command returning to PC scope after a
  phone turn, nested routing, structured errors, and preservation of unknown state.
- Deployed smoke checks verify default PC rejection/explicit phone acceptance,
  polite commands, prompt rules, and the two-second endpoint default.
- Installed service is active, connected, control-enabled, and exposes 247 tools.
- Live queries through the running voice service's executor returned PC volume
  60%, brightness 1%, and workspace 1, without changing those settings.

Active release:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261102T044534055Z-pc-default-control`.

Rollback target:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261102-080120-9c1f537`.

The new release was copied from the previously installed release and overlays
only `jarvis_voice/config.py`, `jarvis_voice/daemon.py`, `jarvis_control/nlu.py`,
and `jarvis_control/phone_control.py`. Its metadata records patch hashes and the
parent release. Unrelated development edits were not deployed. Protected OMA
audio files, user credentials, memory data, and device pairing were not edited.

## Scope and remaining checks

Automated tests establish the fixed software routing contracts. Live checks
establish PC executor availability; they do not prove every spoken request,
Android gesture, authenticated account operation, or application workflow.
Physical speech recognition and provider tool selection still need ordinary
user conversation checks.

Recent logs also contained a Composio connector ValueError. Connector source can
raise this when account configuration is missing. No credentials or account
connections were changed in this repair; external messaging availability must
be checked independently. Failure must be reported without silently switching
from the PC to the phone.
