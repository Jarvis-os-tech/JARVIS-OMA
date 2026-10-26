# Supplemental code audit findings

Date: 2026-10-22
Scope: targeted review of current repository code and the extracted reports. This is not an exhaustive security or performance audit. No application fixes were made.

## New findings from the latest investigation

### S01 — High: protected-directory checks can be bypassed with `..`

Location: `filesystem/filesystem.py`, `path_for()` (line 32), and destructive-operation guards (`delete_path`, `move_path`, `copy_path`, `trash_path`).

`path_for()` uses `Path.absolute()`, which does not normalize `..`. Guards compare the resulting path lexically against `CRITICAL_PATHS`. A protected directory supplied as `protected/../protected` passes the equality guard and reaches deletion. Automated reproduction used a temporary protected directory and patched critical-path set; no real system directory was touched.

Recommendation: normalize path identity before protection checks, explicitly handle symlinks, and guard ancestor replacement. Retain descriptor-based checks where concurrent path changes matter. Do not blindly resolve a final symlink when the operation intends to act on the link itself.

### S02 — High: copying into an ancestor deletes the source

Location: `filesystem/filesystem.py`, `copy_path()` (line 262); analogous ancestor-check omission exists in `move_path()` (line 237).

The guard rejects a destination inside the source but does not reject a destination that contains the source. With `source=/temporary/parent/source` and `destination=/temporary/parent`, `overwrite=True` removes the destination tree, including the source, before copying. A temporary-directory test reproduced loss of both the source and destination. The move variant was inspected but not independently reproduced.

Recommendation: reject overlapping source/destination trees in both directions before any mutation, including normalized aliases.

### S03 — High: failed overwrite-copy destroys the previous destination

Location: `filesystem/filesystem.py`, `copy_path()` (line 262); `move_path()` also removes the destination before attempting the move.

Existing destinations are deleted before the replacement operation succeeds. A test injected an ENOSPC error into `copy2`; the operation raised an error and the original destination was gone. Real causes include disk exhaustion or read/permission failures.

Recommendation: stage the replacement beside the destination and replace only after successful completion; use an explicit recovery strategy for directories and cross-filesystem moves. Keep the previous destination recoverable on failure.

### S04 — Medium: malformed search-result URLs abort result processing

Location: `connectors/internet_search.py`, `_public_url()` (line 71) and `brave_search()`.

`urlsplit()` raises `ValueError` for malformed bracketed hosts such as `https://[invalid`. `_public_url()` does not catch it, and the result loop does not isolate this validation error. One malformed provider result therefore raises from the search function instead of being skipped. Reproduced locally without network access.

Recommendation: catch parsing errors and return False; test a malformed result followed by a usable result.

## Earlier findings consolidated here

| ID | Priority | Finding | Evidence / qualification |
|---|---|---|---|
| E01 | High | Evolution defaults to unsupported `codex` | `orchestration/evolution.py:179` vs `orchestration/agent_orchestrator.py:17`. Existing evolution test failed with `EvolutionError: unknown coding agent`. |
| E02 | High | Extension playback queue contract mismatch | `audio/extension.py:220` queues bytes; locked `audio/engine.py:536` unpacks `(generation, candidate)`. Code inspection; repair must remain in the unlocked extension. |
| E03 | High | Desktop subprocess paths inherit full parent environment | `skills/skills.py:733` and `_launch`; `skills/system_control.py:39`. Existing sanitizer is omitted. Exposure to child processes is established; external exfiltration is not claimed. |
| E04 | Medium | Sanitizer misses credential-name patterns | `core/secret_env.py:7` does not match names such as `OPENAI_KEY`, `PRIVATE_KEY`, or `AUTH_BEARER`. Avoid indiscriminately removing every URL variable. |
| E05 | High | Explicit mute/unmute commands toggle instead of setting state | `scripts/jarvisctl:128`. Automated reproduction: two `mute` commands leave the state unmuted. Both aliases share the toggle request. |
| E06 | High | Explicit empty subprocess environment is discarded | `skills/system_control.py:54`, `env=env or _desktop_env()`. Automated test confirmed a synthetic parent variable is inherited with `env={}`. Use an explicit None check. |
| E07 | Medium | IPC broadcasts have no subscriber backpressure bound | `core/ipc.py:118`, `broadcast_state()`. No drain, buffer cap, or slow-client eviction. Code inspection only; growth rate was not measured. |
| E08 | Medium | Vision upload can block audio transmission on the shared lock | `core/agent.py:500` and audio sender around line 685. Vision holds `send_lock` through a network await with a two-second timeout. Structural contention confirmed; audible delay not measured. |
| E09 | Medium | Calendar event timezone is fixed | `connectors/google_workspace.py:480` always sets `Asia/Kolkata`, with no timezone parameter. Limitation for events requiring another timezone; not a failure for every offset-aware datetime. |
| E10 | Medium | Tests select a different adapter implementation | `skills/skills.py:1653` and `1667` inspect mock `call_count` and change volume/brightness behavior. This undermines test representativeness. |
| E11 | Low | Greeting records have no retention bound | `core/greeting.py:41` inserts indefinitely; recent retrieval uses LIMIT 8. Disk growth confirmed structurally, practical volume not measured. |

## Validation

- `.venv/bin/pytest -q report/12_audit_reproductions.py`: **6 passed**. These are characterization/reproduction checks that assert the current faulty behavior. Passing means the issue was reproduced, not fixed. They must change to desired-behavior assertions when fixes land.
- Four new checks cover S01–S04. Two earlier checks cover E05 and E06.
- Earlier focused existing-suite run: **2 passed, 1 failed**, stopping at the evolution unsupported-agent failure.
- Earlier IPC + Google connector run: **23 passed, 9 failed**. All nine IPC failures occurred during socket bind with `PermissionError: Operation not permitted` in the restricted execution environment; they do not establish IPC implementation failures.
- `python3 scripts/verify_voice_lock.py`: all seven locked voice files intact, verified again after this supplemental review.
- No live provider calls, microphone tuning measurements, destructive system operations, or application fixes were performed.

## Report-quality cautions

`00_MASTER_IMPROVEMENT_REPORT.md` contains extraction instructions rather than a master audit. Reports 01–06 and 09–10 are completion summaries. Reports 07–08 contain detailed audits. Recovering their original full messages remains useful.

Do not treat all original suggestions as confirmed defects: tool responses have a cleanup path, camera teardown exists, wake-word performance figures lack local measurements, and blanket deletion of safety checks or database migrations is not justified by line-count reduction.

## Suggested repair sequence

1. Fix S01–S03 with isolated filesystem regression tests to prevent data loss.
2. Fix E05 and environment handling (E03, E04, E06).
3. Fix E01 and E02 without modifying any locked voice file.
4. Add bounded IPC delivery, address malformed search URLs, and measure vision/audio contention.
5. Address timezone configuration, test-specific production branches, and retention policy.

## Follow-up investigation: five additional reproduced findings

### S05 — Medium: valid empty-file tasks are reported as failures

Location: `filesystem/task_runner.py`, `_verify_step_ground_truth()`.

The filesystem write API accepts empty content, but task verification rejects every zero-byte file. A one-step task successfully created the requested empty file and was then marked failed with a ground-truth error. Empty-file writes and edits that intentionally remove all content are legitimate operations.

Recommendation: verify requested postconditions, allowing empty content when requested. Keep execution failure distinct from verification failure so callers do not blindly repeat an already-applied operation.

### S06 — Medium: task verification can report success despite an unsuccessful write

Location: `filesystem/task_runner.py`, `_run()` and `_verify_step_ground_truth()`.

The runner does not examine an executor's error-valued return before marking the step completed. Its write verification checks only whether a nonempty file exists, not whether the requested content was written. A fault-injected executor returned `{'status': 'error'}` without changing an existing file; the job still became completed. This establishes a verification-contract gap under that executor result, not evidence that the current filesystem adapter routinely returns this shape (its normal errors are raised).

Recommendation: define and enforce the executor success/error contract, then check tool-specific postconditions. For writes compare requested bytes or their digest; use corresponding append/edit verification rather than file existence alone.

### S07 — Medium: advertised character offsets are interpreted as byte offsets

Location: `filesystem/filesystem.py`, `read_text()`; contract in `skill_manifests/filesystem.json`, `read_file` description.

The manifest promises a character offset, but `TextIOWrapper.seek(offset)` seeks to a byte position. Reading the UTF-8 text `éB` at character offset 1 should yield `B`; the implementation seeks into the middle of `é` and raises a decoding error. This affects non-ASCII text, including many user languages.

Recommendation: implement bounded character-based skipping, or explicitly redesign the public contract around byte offsets and decoder-safe continuation positions. Preserve the offset unit consistently with `chars_read`.

### S08 — Medium: whitespace job-ID aliases overwrite tracked jobs

Location: `proactive/monitor.py`, `ProactiveMonitor.track()`.

Duplicate detection checks the untrimmed incoming ID, but storage uses `job_id.strip()`. Tracking `job` and then ` job ` bypasses duplicate detection and replaces the running job's record, losing its timeout/retry metadata. Reproduced through the public monitor methods. Reachability from external callers was not separately established; this is a component API defect.

Recommendation: normalize the ID before checking existence and use the same identity policy across track, get, update, and retry operations.

### S09 — Medium: NaN timestamps poison policy rate-window expiry

Location: `proactive/policy.py`, `ProactivePolicy.evaluate()` and `_trim_rate_window()`.

The policy accepts float timestamps without a finite-value check. A safe action evaluated at `float('nan')` is accepted and appends NaN to the rate queue. Because comparisons with NaN are false, that queue entry never expires. With a limit of one action, a later action at time 1,000,000 is still rate-limited despite a one-second window. Reproduced through public policy methods. Normal monotonic clocks are finite; impact depends on a caller supplying an invalid timestamp.

Recommendation: reject non-finite timestamps and non-finite duration configuration before mutating policy state; consider guarding backward time as well.

### Follow-up validation

- `.venv/bin/pytest -q report/12_audit_reproductions.py`: **11 passed** (six earlier reproductions plus five new ones). These tests characterize defects; they do not demonstrate fixes.
- Existing filesystem, task-runner, proactive-monitor, and proactive-policy suites: **24 passed, 9 subtests passed**. This shows the reproduced edge cases are missing from the current checks.
- Voice lock rechecked after writing this report: all seven locked files intact.
- The follow-up changed only supplemental report/test artifacts. No application fixes were made.

## Repair status update — Fix 01

S07 is now implemented and verified. Unicode character offsets use bounded decoded reads; the supplemental S07 test now asserts correct behavior. See `14_FIX_01_UNICODE_READ.md` for evidence and voice-check instructions. The other findings remain open. Historical reproduction counts above describe the state at audit time.

## Repair status update — Fix 02

S05 is now implemented and tested: empty-file writes, appends, and edits complete successfully; missing-file verification still fails. See `15_FIX_02_EMPTY_FILE_TASKS.md` for voice-check instructions and evidence. S06 exact-content verification remains open. Fixed findings so far: S07 and S05.

## Repair status update — Fix 03

S04 is now repaired: malformed search-result URLs are skipped without discarding valid later results. Tests cover mixed valid/invalid results and all-invalid responses. See `16_FIX_03_MALFORMED_SEARCH_URLS.md`. Fixed findings so far: S07, S05, S04.

## Repair status update — Fix 04

E01 is repaired by admitting the already implemented Codex adapter into the shared supported-agent registry. The previously failing default-start test and relevant suites pass (34 passed, 2 opt-in checks skipped). Codex discovery reports available locally; login and live execution were not tested. See `17_FIX_04_DEFAULT_DEVELOPMENT_AGENT.md`. Fixed so far: S07, S05, S04, E01.

## Repair status update — Fix 05

S08 is repaired: monitor IDs are normalized before admission and lookup, duplicate aliases are rejected, and existing records stay intact. See `18_FIX_05_MONITOR_JOB_IDENTITIES.md`. Fixed so far: S07, S05, S04, E01, S08.

## Repair status update — Fix 06

S09 is repaired: non-finite evaluation timestamps and duration settings are rejected before state changes; rate-limit counts require integers. The proactive suite and supplemental checks passed 69 tests and 48 subtests. See `19_FIX_06_POLICY_FINITE_TIMESTAMPS.md`. Fixed so far: S07, S05, S04, E01, S08, S09.

## Repair status update — Fix 07

E06 is repaired: explicit empty and custom subprocess environments are preserved; only None selects the desktop default. Dedicated real-child-process tests passed (3 tests). Runs including broader desktop-control or supplemental checks stalled and were interrupted. E03/E04 remain open. See `20_FIX_07_EXPLICIT_SUBPROCESS_ENVIRONMENT.md`. Fixed so far: S07, S05, S04, E01, S08, S09, E06.

## Repair status update — Fix 08

E02 is repaired in the unlocked audio extension: processed PCM uses the engine's public generation-safe playback API, with generation captured before processor work. Actual-engine tests cover slicing, mute, barge-in during processing, and dropped frames. 13 tests passed; all voice locks intact. Normal voice commands do not directly exercise this currently unused wrapper. See `21_FIX_08_EXTENSION_PLAYBACK.md`. Fixed so far: S07, S05, S04, E01, S08, S09, E06, E02.

## Repair status update — Fix 09

E10 is repaired: volume/brightness adapters no longer inspect mocks to change behavior. Dedicated routing/error tests and the dynamic skills suite passed 42 tests and 16 subtests. Voice smoke checks and expected measured values are documented in `22_FIX_09_ADJUSTMENT_TEST_PARITY.md`. Fixed so far: S07, S05, S04, E01, S08, S09, E06, E02, E10.

## Repair status update — Fix 10

E09 is repaired with an optional validated IANA `time_zone` parameter across the tool schema, skills adapter, dispatcher, and connector. Existing omission defaults remain Asia/Kolkata. 26 connector/timezone tests passed using mocked API and inline worker execution; live Google acceptance and worker scheduling were not verified. See `23_FIX_10_CALENDAR_TIMEZONE.md` for a Tokyo-time voice check. Fixed so far: S07, S05, S04, E01, S08, S09, E06, E02, E10, E09.

## Calendar follow-up — IST and management

Extended E09's repair with explicit IST datetime normalization, conflict rejection, a fresh clock, saved-time readback metadata, delete/reschedule, availability, recurrence, and popup reminders. The user's exact past mis-scheduling cause remains unconfirmed without the original timestamps. 47 tests and 12 subtests passed; no live calendar changes performed. Remaining calendar API gaps and voice checks are in `24_CALENDAR_IST_AND_MANAGEMENT.md`.

## Repair status update — Remaining ten findings

The user requested ten Luna workers and a parent review/repair loop. S01, S02, S03, S06, E03, E04, E05, E07, E08, and E11 now have implementations and regression coverage. Original reproduction assertions in report 12 now assert corrected behavior. This addresses all 20 individually tracked findings; it is not an exhaustive claim that the application has no remaining defects.

See `28_REMAINING_AUDIT_REPAIR_LOOP.md` for worker assignments, parent review corrections, test evidence, voice/CLI checks, and practical limits including path-race exposure, staged replacement disk overhead, and live transport behavior. Existing unrelated changes from other sessions were preserved. No live account operations or daemon restart were performed during this repair pass.
