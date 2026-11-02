# Verified desktop workflows — 28 October 2026

Status: implemented and offline tested; live spoken acceptance remains pending.
Voice and audio code remain frozen under the user's instruction.

## Implemented behavior

- **Application opening:** resolve an exact installed application and observe a
  window with its desktop ID or declared `StartupWMClass`. A process name or
  window title alone cannot prove that the application opened. An uncertain
  launch is reported as unverified and is not automatically repeated. Application
  opening gets a longer, bounded observation window for cold startup than a
  workspace state change; late appearance does not trigger another launch.
- **Window focus:** reject ambiguous class/title matches before dispatch; focus
  one address and read back that same address and its known PID. Two windows of
  the same class do not establish interchangeable identities.
- **Workspaces:** preserve verified absolute/relative switching. Moving the active
  window now binds its address, sends one targeted request, and reads back that
  identity's destination. Already-correct placement is verified without a move.
- **Files:** write/edit readbacks compare exact UTF-8 bytes. Append checks the
  appended bytes at the previous byte offset. Copy and move compare a bounded
  regular-file snapshot, and move additionally checks that the source is absent.
  Evidence includes its source, timestamp, byte offset/count and SHA-256 digest.
  Directory creation checks that the requested directory exists.
- **Browser navigation:** a bound browser target/tab is navigated once, then its
  observed URL is checked. Another tab, a redirect, missing state or a failed
  readback cannot prove the requested page. The general website launcher returns
  `dispatched_unverified`; it does not claim a loaded page without tab evidence.
- **Task sequencing:** an explicitly failed or unverified operation stops later
  file-task steps and retains the result for inspection. It is not retried.

Verification remains separate from authorization. The existing manifests,
permission boundaries and typed command arguments remain in use. No new shell
evaluation, provider, agent framework, voice handler or service was added.

## Acceptance fixtures

The registry's real schema validation, adapters and readback predicates are
exercised; desktop commands/observations are fixtures, and filesystem operations
use real temporary files. These are not spoken or physical-desktop trials.

| Group | Cases | Passing fixture trials |
| --- | --- | --- |
| Application/window targeting | Focus by address, class, title; open exact application | 12/12 |
| Workspace placement | Absolute, next, previous; move window; already-correct placement | 15/15 |
| Window state | Fullscreen, maximize, float | 9/9 |
| Files | Create directory; write, append, edit, copy and move file | 18/18 |
| Browser | HTTPS page and blank page in a bound tab | 6/6 |
| Total | 20 cases × 3 trials | 60/60 |

The workflow module has **84 passing cases** in total. Additional cases inject
ambiguous targets, wrong or missing PIDs, wrong destinations, missing application
windows, unrelated titles, wrong browser tabs/targets, redirects, delayed URL
readback, malformed URLs, no-op file commands, verification-size limits and
unverified task results.

## Verification results

- Combined focused selection: **210 passed, 24 subtests passed**.
- Full suite: **1,112 passed, 26 failed, 2 skipped, 292 subtests passed**.
  Comparison with the preceding desktop-only full run found no new failing test
  identities. Its 27 remaining failures dropped to 26; the exact application
  launch adapter test now accepts the structured result without a false success
  claim. The new workflow cases all passed.
- Older focus and move tests now supply actual target/destination observations
  instead of treating a dispatch acknowledgement as verification.
- Python syntax and whitespace checks passed. `ruff`, `pyright` and coverage
  tooling remain unavailable in the project environment; they were not run.
- A read-only live compositor check successfully read the active workspace,
  active-window identity and two valid client identities. No live window input
  was performed by that probe; window titles were not printed.
- Intermediate boundary checks confirmed all **44 snapshotted voice/audio/runtime/configuration files unchanged**.
  At final review, separate edits appeared in `core/stable_voice.py` and
  `core/vision_stream.py` while the shared checkout continued changing. The first
  added `--config` and `--agent-name` parser options. This workflow implementation
  did not write any `core/` or `audio/` file and left the separate edits untouched.
  All seven protected voice-core files passed integrity verification. The recorded
  regression run predates these concurrent changes and does not certify them;
  a checkout-wide unchanged-runtime claim is therefore not made.
- No service restart, microphone change or configuration migration was performed.
  A running daemon loads the updated adapters on its next normal restart.

## Limits and next gate

Regular-file copy/move content verification is capped at **8 MiB**. Directory,
symlink and larger-copy/move outcomes remain unverified rather than certified by
presence alone. Append evidence covers the appended region, not the entire prior
file. Successful file readback is a point-in-time observation.

App identity can require a correct desktop `StartupWMClass`; unsupported mappings
return unverified. Browser proof requires a bound tab and readable URL; redirects
are reported rather than silently treated as the requested URL. Page URL proof
does not establish page content, form submission or a successful login.

The roadmap's **20 spoken actions × 3 live trials, at least 57/60 verified
outcomes, and zero wrong-target writes** gate is still open. Passing fixtures
does not satisfy that gate. Full-duplex voice, durable restart recovery, broad
browser workflows and the complete shell remain separate work packages.

```sh
.venv/bin/pytest -q tests/test_skills/test_verified_workflows.py \
  tests/test_skills/test_awareness.py tests/test_skills/test_system_control.py \
  tests/test_skills/test_action_outcomes.py tests/test_filesystem \
  tests/test_skills/test_ground_truth.py tests/test_skills/test_gui_control.py \
  tests/test_skills/test_capability_startup_recovery.py
python3 scripts/verify_voice_lock.py
```
