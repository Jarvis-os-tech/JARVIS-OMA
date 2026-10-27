# Voice OS implementation progress

Started 26 October 2026 against the user's 24 October redesign report,
`output/pdf/voice-os-redesign-report-2026-10-24.pdf`, especially the first
implementation backlog on page 15. This is an implementation record, not a
claim that the complete voice OS has shipped.

## Build order and evidence gates

| Order | Deliverable | State | Gate |
| --- | --- | --- | --- |
| 0 | Current inventory, test baseline, scope and task corpus | Baseline recorded; policy choices remain open | Repeatable checks; unresolved limits named |
| 1 | Truthful window/workspace actions | Implemented and live desktop checked | Exact target readback; failed fallback and missing evidence never become success |
| 2 | Shared action broker and trusted grants | Next | Ordinary voice, typed commands, workflows and delegation share one authority boundary |
| 3 | Durable task/action journal and recovery | Pending | Restart and duplicate-request tests; uncertain effects are never replayed blindly |
| 4 | Versioned UI snapshots/events | Pending | Snapshot/subscription consistency, reconnect and bounded slow clients |
| 5 | Folder grants and recoverable file operations | Pending | Canonical scopes, separate effects, traversal/symlink and recovery checks |
| 6 | Voice supervisor and supported audio composition | Pending | Selected backends, generation fences and privacy boundaries verified |
| 7 | Local command essentials | Pending | Published essential commands work with cloud unavailable |
| 8 | Invocation, activity and privacy views | Partial visual island only | Shared task truth, accessible controls, exact targets and recovery |
| 9 | Data lifecycle controls | Pending | Retention and deletion verified across each enabled store/export |
| 10 | Release package and rollback | Partial desktop installation exists | Versioned install/upgrade/rollback, single instance and resume recovery |

The current island and newer desktop/service work are retained. UI polish does
not establish that the broker, journal, offline speech or privacy controls exist.

## Step 1: exact desktop outcomes

Both `DesktopSkills` adapters now route to the verified implementations in
`skills/system_control.py`. Supported direct voice aliases use that same path.

- A window operation captures the current exact address and PID. Modern
  dispatches include that address; readback checks the same identity rather than
  accepting another window with the same application class.
- Fullscreen/maximize and floating changes compute an explicit target from the
  observed starting state. Close verifies disappearance/unmapping; minimize
  verifies `special:scratchpad`; center verifies geometry on the target monitor.
- Center calculations account for scale, rotation and reserved work area.
- Legacy fallback return codes are checked. Close, float and minimize retain
  address-targeted fallbacks. Active-only legacy fullscreen/maximize/center
  fallbacks are declined because a separate focus check leaves a race.
- Numeric workspace switches verify the exact workspace ID. Relative navigation
  resolves the sorted existing workspace IDs before dispatch, excluding special
  workspaces. Requesting the current workspace is a verified no-op, preventing
  `workspace_back_and_forth` from switching somewhere else.
- Verification allows a bounded compositor update delay without replaying the
  action. A dispatch timeout is reported as uncertain and never retried through
  the fallback. Failed or missing observations do not produce success.
- Tiling aliases without a postcondition verifier report `unverified` after input
  dispatch. Generic user keybindings and other desktop adapters are outside this
  step's verification coverage; they are not certified by these results.

Verified results carry the target and timestamped compositor evidence. Observed
mismatches report `error`; unavailable post-action readback reports `unverified`.
Callers must preserve those statuses rather than converting them to success.

### Verification

Automated regression coverage lives in
`tests/test_skills/test_desktop_action_verification.py`. It exercises both failed
dispatches, exact identities, wrong same-class windows, replaced PIDs, missing or
invalid readback, all six window actions, reserved/scaled/rotated monitor geometry,
relative workspace resolution, no-op switching and timeout non-replay. Adapter
and voice-alias tests prove ordinary dispatch preserves the result.

The final focused run passed **115 tests and 31 subtests**, including all 32
new desktop regression tests. It included the desktop adapters, system-control
tests and the voice-lock tests. Run it with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q \
  tests/test_skills/test_desktop_action_verification.py \
  tests/test_skills/test_system_control.py tests/test_skills/test_skills.py \
  tests/test_audio/test_voice_lock.py
```

A controlled live check passed 11 operations on an owned temporary Foot window:
floating off/on, center, fullscreen on/off, maximize on/off, minimize, close, an
empty numeric workspace switch and restoration. Every operation had fresh
compositor evidence, and original workspace restoration was verified. This did
not test speech recognition, legacy compositor versions, Bluetooth, a microphone,
cloud inference or an end-to-end spoken request. No voice daemon restart was
performed; an already-running daemon retains its imported code until restart.

## Baseline and inventory

Base revision: `17bec36`, with user/sibling changes already present. That revision
alone does not identify the entire tested working tree.

| Inventory | Observed |
| --- | --- |
| Canonical manifests (`skill_manifests/`) | 27 files, 203 unique declared tools |
| Mirror manifests (`skills/manifests/`) | 23 files, 188 unique declared tools |
| Locked voice files | All seven pass the integrity verifier |
| Full suite | 1,176 passed, 2 failed, 2 skipped; 332 passed subtests; 88.37 seconds |
| Opt-in real sandbox checks | Skipped; no sandbox isolation claim |

The full suite was run with local socket access. The initial restricted run
encountered socket-related failures and stalled during async teardown; it was
interrupted and is not the baseline used above. The completed run used:

```bash
timeout -k 5 180 env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  .venv/bin/pytest -q -o faulthandler_timeout=30 \
  --junitxml=output/test-results/voice-os-step-01-2026-10-26.xml
```

The completed suite collected the regression file before its last four edge
cases were added. The final focused run covers those additions separately.

Two unresolved full-suite results block a green release baseline:

1. `CLIAnythingIntegrationTests.test_info_shows_harness_details` timed out in the
   installed `cli-hub search gimp --json` call. External dependency readiness is
   not established by this test run.
2. `SystemInformationWiringTests.test_manifest_parameters_match_handlers_and_mirrors`
   found four canonical manifests absent from the mirror: `personal-agents.json`,
   `harness-local.json`, `research-learning.json`, `harness-refinement.json`.
   Consolidate or synchronize the trees without overwriting ongoing capability work.

## Initial daily task corpus

These are acceptance targets, not claims that all ten workflows work today.

| Task | Required observable outcome |
| --- | --- |
| Switch to a numbered workspace | Exact requested workspace ID is active |
| Next/previous workspace | Exact pre-resolved existing ID, including wraparound |
| Float or fullscreen the current window | Same address/PID reaches requested state |
| Close or minimize the current window | Exact target disappears or enters the scratchpad |
| Focus one of two similar application windows | Explicit selection and exact focus readback |
| Launch an application | Correct application appears; process launch alone is insufficient |
| Adjust volume/brightness | Fresh device setting matches the requested value |
| Organize a granted test folder | Preview, scoped operations, content verification and recovery manifest |
| Run an owned coding task and stop it | Durable ownership, observed cancellation and independent acceptance |
| Handle network loss during a command | Draft preserved; local essentials only; no stale instruction replay |

## Scope and privacy contract for subsequent steps

Linux, Omarchy and ordinary applications stay in place. The seven locked voice
files remain byte-for-byte protected. Extensions belong in unlocked adapters.

Existing preferences are not silently reset. Existing explicit authorization
must become a trusted stored grant in the broker, rather than a model-supplied
approval argument. A missing grant requires a concrete target/effect decision;
valid authorization should not cause repeated prompting.

The redesigned mode selector, local speech lane, true capture release,
private-session retention controls and exporter-wide deletion are pending.
Do not label today's software mute as releasing the microphone, local wake as
general offline operation, or fact forgetting as transcript/export deletion.
No new capture, transcript retention, model downloads or cloud upload were
enabled for this implementation step.

Supported offline commands/languages, transcript retention periods, granted
folders/accounts and stop/undo semantics still require explicit configuration
as their dependent phases are implemented. Until then, preserve current
configuration and identify these as open decisions.

## Next implementation

Build backlog item 2 around the existing `DesktopSkills.execute` choke point.
Reuse proactive effect classification and policy primitives, but keep trusted
user authorization outside model arguments. Define action identity and the UI
event contract early so the subsequent durable journal becomes the single
source of task truth.
