# Oma Jarvis — working-status check

**Checked:** 30 October 2026. **Conclusion: the complete reorganized application is not working independently yet.** Many copied components pass their tests, but the new folder layout cannot start the main application, and behavioral failures remain in the saved implementation.

No production code, copied source module, or locked voice file was edited during this check. The running service was not restarted, and no live microphone, speaker, camera, GUI action, or connected-account operation was exercised.

## Results

| Check | Result | What it establishes |
|---|---|---|
| Copy integrity | All canonical files still match their saved hashes | The copied code is intact |
| Python syntax | 987 Python files parse successfully | Includes reference source; syntax alone does not establish functionality |
| Original organized layout | 8 of 12 representative startup/import checks fail | Main app and several connected modules still need their package/import paths migrated |
| Copied application tests, reconstructed original layout | **1,164 passed, 12 failed, 2 skipped**; 292 passing subtests | Many behaviors work when the original package structure is restored for testing |
| New supplementary voice regressions | **6 failed** | Additional defects/contract failures not covered by the tests saved in the copy |
| Native audio | Builds and self-tests pass with WebRTC disabled and enabled | Scheduling/buffering/cancellation self-tests and enabled DSP checks pass; real-device operation remains untested |
| Native camera helper | Builds successfully | Camera execution and runtime command correctness remain untested |
| Shell syntax | 10 scripts pass `bash -n` | Syntax only; no launcher or installer was executed |
| Standalone memory package | Six stdio/persistence checks pass directly from its copied package | Initialization, ping, tool discovery, proposal, commit after restart, and persistent search work on a disposable database |
| Voice lock | All seven files pass | Original and copied protected source remains intact |

Across the copied suite and supplementary voice run there are **18 distinct failing tests**. The suite's 12 failures are the same tests that failed in the earlier original-checkout audit; no new failure was introduced by reconstructing the copied source for that run. The six supplementary tests were added to the original project after the copy was created and expose additional behavior in the unchanged copied implementation.

## Why the organized folder cannot launch yet

The copy preserves original code bytes. Its files have been organized into feature folders, but the import statements and path calculations still refer to the old packages.

| Startup/import check from the organized copy | Result |
|---|---|
| `runtime/entrypoints/agent.py --check --no-skills` | Fails: `No module named 'core'` |
| Voice session | Fails: `No module named 'core'` |
| GUI controller class | Imports successfully; this alone does not test the external GUI driver |
| GUI action verification | Fails: `No module named 'skills'` |
| Desktop controls | Fails: `No module named 'core'` |
| File operations | Fails: `No module named 'filesystem.filesystem'` |
| Agent delegation | Fails: `No module named 'core'` |
| Proactive runtime | Fails: `No module named 'core'` |
| Configuration settings | Imports successfully |
| Response timing module | Imports successfully |
| Standalone memory server module | Imports successfully; separately passes real stdio/persistence smoke checks |
| Skill registry | Fails: `No module named 'task_runner'` |

The `.py.txt` files in feature folders are exact reading extracts. They depend on their complete containing classes and are not executable replacement modules. They were checked for exact provenance, not presented as runnable feature packages.

## Six additional voice failures

These checks use mocks and deterministic input frames. They establish the observed branches below; they do not measure real-world acoustic quality or latency.

| Area | Observed failure | Copied implementation |
|---|---|---|
| Rate-limit recovery | A repeated resumed-connection failure returns an immediate fresh-session retry, bypassing the expected 60-second cooldown | [ConnectionRecovery.decide](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py:41) |
| Network setup recovery | Repeated setup timeouts discard resumable-session context instead of retaining it | [ConnectionRecovery.decide](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py:41) |
| Error after a session opens | A 400 error with an already-open resumed session is handled as a resume rejection and requests a fresh session, rather than the fatal result expected by the regression | [ConnectionRecovery.decide](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py:41) |
| Speech detector input continuity | Quiet frames between speech frames do not reach the detector | [SpeechTurnGate.process](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py:78) |
| Interruption detector input continuity | The low-volume early return skips quiet frames before updating the detector | [SpokenInterruption.process](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py:67) |
| Cancelled playback generation | A drain timeout after generation cancellation raises `PlaybackBacklogError` and ends the playback worker, instead of discarding the stale generation | [Playback.run](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:180) |

The existing voice tests passed, but these six newer cases did not. Voice reliability therefore should not be declared complete based only on the older suite.

## Twelve failures in the saved suite

| Failure group | Count | Required resolution |
|---|---:|---|
| Agent delegation `cost_profile` schema mismatch | 1 | Make public schema and supported handler options agree |
| Budget/configured default description mismatch | 1 | Choose and consistently document the intended default |
| Cached executable path after replacement | 1 | Re-resolve a removed/replaced executable |
| Harness2 absence assumption | 1 | Isolate command discovery in the test instead of assuming the installed host lacks Harness2 |
| Calendar declarations and capability prompt expectations | 2 | Reconcile older flat-tool expectations with the intended domain-discovery contract |
| Dynamic action routing and verified window/workspace outcomes | 3 | Supply deterministic observations and verify the current action-validation contract |
| Search fallback after quota errors | 2 | Resolve the expected key/model fallback policy and test it consistently |
| Microphone rejection wording | 1 | Preserve the rejection and align the assertion with the actual error contract |

Some failures demonstrate implementation defects; others demonstrate test/behavior disagreement or host dependence. They should not all be “fixed” by weakening safety checks or changing assertions blindly. Exact names and error messages are in [failures.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/failures.json).

## Saved-suite results by feature area

These are test-case counts, excluding the 292 subtests and the six supplementary voice tests. Areas follow the folder that owns each copied test; they are not coverage percentages or proofs that all code in that area works.

| Area | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Voice | 334 | 0 | 0 |
| GUI control | 155 | 0 | 0 |
| Desktop control | 127 | 0 | 0 |
| Memory | 116 | 0 | 0 |
| Agents | 110 | 3 | 2 |
| Integrations | 89 | 1 | 0 |
| Automation | 58 | 0 | 0 |
| Runtime | 51 | 0 | 0 |
| Skill registry | 49 | 8 | 0 |
| Configuration | 26 | 0 | 0 |
| Filesystem | 18 | 0 | 0 |
| Vision | 18 | 0 | 0 |
| Deployment | 7 | 0 | 0 |
| Interface | 6 | 0 | 0 |

In particular, filesystem tests passing does not disprove the destructive-path risks found in the earlier audit; the existing tests do not cover every known problem. Similarly, compiling the camera helper does not resolve its previously identified command-construction or output-format issues.

## How the behavioral tests were isolated

1. Reconstructed 607 project entries from the **copies**, using their original relative paths, in a separate staging folder outside the running project. No source file was taken from the live implementation for this reconstruction.
2. Used the existing `.venv/bin/python` and pytest installation as test dependencies. A Python execution audit hook in the pytest process rejected attempts to execute original project source outside that dependency environment. The guard reported **zero violations**; 222 staged module files were loaded in the saved-suite run. Child test commands inherited the staged working directory and Python path; the audit hook itself is process-local.
3. Used temporary settings/state locations, removed credential variables, and excluded live desktop/agent markers. The normal copied pytest credential-isolation fixture was retained.
4. Ran the copied offline suite with a 180-second limit; it completed in 59.61 seconds. Two opt-in real isolation tests were skipped.
5. Added the one newer regression-test file only to the staging area, then ran those six tests against the same copied implementation. The organized copy and original source were not rewritten.
6. Built native code in separate build directories. Audio self-tests exit before device initialization. The camera binary was compiled but not used to capture anything.
7. Tested the standalone memory package through its actual stdio entry point using a new disposable SQLite database and a synthetic record. No user memory store was used.

## Snapshot freshness and preservation

The re-run of the original 14 copy-integrity checks reports **13 passed and 1 failed**. The failed check compares historical Git status with today's status: `tests/test_core/test_voice_regression_review.py` was added after the snapshot. It is a freshness difference, not copy corruption. That new test file is the source of the supplementary six checks above.

All canonical copied files still match the snapshot hashes, and the corresponding original file contents remain identical to the saved snapshot. The original project's Git status did not change during this validation. The protected voice manifest passed again. Historical validation records from 29 October have been retained.

## What is still unverified

- Real microphone/speaker behavior, echo cancellation in the room, interruption reliability on real speech, and acoustic first-token/first-speech latency.
- Live GUI actions through Cua Driver/Hyprland, actual camera capture, telephony, and authenticated Google/GitHub/provider operations.
- Standalone compilation/execution of the archived Artemis UI/mobile application, Rust reference bundle, and historical recovery snapshots. Their Python files passed syntax parsing where applicable; they were not installed or launched as independent products.
- A complete coverage percentage or exhaustive proof of all code paths. Available tests and the additional regressions establish the specific results above.

## Work needed for an independently working copy

First migrate imports, package entry points, resource/configuration paths and deployment targets inside `Oma Jarvis`, and turn selected feature extracts into actual interfaces while preserving shared state correctly. Fix the six voice regressions and resolve the twelve saved-suite failures against explicit behavior contracts. Retain the voice lock and use extensions where required. Then perform isolated device/provider integration checks with the intended installation.

No such implementation changes were made in this verification task.

## Evidence

- [Organized-layout smoke results](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/organized_layout_smoke.json)
- [Copied-suite JUnit results](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/copied_suite.xml) and [failure log](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/copied_suite.log)
- [Supplementary voice results](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/supplementary_voice.xml) and [failure details](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/supplementary_failures.json)
- [Native build/self-test and shell results](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/native_and_shell.json)
- [Standalone memory results](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/standalone_memory.json)
- [Import provenance](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/import_provenance.json) and [preservation check](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/runtime_check_2026-10-30/preservation.json)
