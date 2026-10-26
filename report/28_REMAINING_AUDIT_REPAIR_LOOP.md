# Remaining audit repair loop

Scope: the ten findings previously left open in report 11: S01, S02, S03, S06, E03, E04, E05, E07, E08, E11.

The user requested ten Luna workers and a parent review/repair loop. Workers run in batches within the session's three-worker concurrency limit. Existing unrelated workspace changes are preserved. No commits or live account operations are part of this work.

## Worker assignments

| Worker | Finding | Focus |
|---|---|---|
| luna_01_s01 | S01 | Protected directory identities |
| luna_02_e04 | E04 | Credential-name matching |
| luna_03_e11 | E11 | Greeting record retention |
| luna_04_e03 | E03 | Desktop child environments |
| luna_05_e05 | E05 | Explicit mute/unmute |
| luna_06_s02 | S02 | Source/destination overlap |
| luna_07_s06 | S06 | Executor errors and file contents |
| luna_08_e07 | E07 | Bounded IPC subscribers |
| luna_09_s03 | S03 | Recoverable filesystem replacement |
| luna_10_e08 | E08 | Vision/audio send contention |

## Parent review

Review requested and integrated additional corrections for symlink/parent traversal semantics, protected ancestors, constructor compatibility, explicit executor failures, newline handling, and IPC sender ownership and limits.

The parent also fixed Python 3.13 IPC shutdown ordering and a race with connections accepted immediately before shutdown. Regressions cover subscribers and clients that have not sent a command. Fault injection revealed that rollback after partial backup cleanup could delete the only complete copy; publication is now the commit point, and cleanup failures retain the complete destination and identify residual backup paths.

## Changes and practical limits

| Finding | Result |
|---|---|
| S01 | Destructive guards resolve aliases and protect ancestors containing protected entries; mutation still acts on the original entry. |
| S02 | Copy/move reject overlapping trees in both directions, parent symlink aliases, navigation components, and hardlink aliases. |
| S03 | Copy/move stage complete replacements before publication; publication failures restore old entries or name recovery paths. Cleanup failures retain the committed copy and report residual backups. |
| S06 | Tasks reject explicit executor errors and compare requested UTF-8 contents with the result. Append/edit capture expected state before execution; unverifiable files over 5 MiB are rejected before mutation. |
| E03 | Desktop launches filter inherited credential variables while preserving GUI/runtime environment and explicitly supplied empty environments. |
| E04 | Credential-name filtering includes KEY, BEARER, and AUTHORIZATION tokens, including explicit helper updates. |
| E05 | CLI mute/unmute set a boolean state through IPC; toggle retains its previous behavior. |
| E07 | Subscriber queues, message size, sender count, drain duration, and shutdown cleanup are bounded. |
| E08 | Optional video has a 100 ms lock/send timeout threshold; busy-lock frames are dropped and stalled in-flight sends trigger session renewal. |
| E11 | Greeting history retains at most 1,000 records after each insert, including cleanup of legacy excess rows. |

Filesystem protection remains path based: concurrent malicious path substitution between validation and mutation is not eliminated. Staging moves requires additional temporary disk space and copy work. Directory publication is a sequence of renames with recovery, not a crash-proof transaction; retained cleanup backups may be partial and are explicitly reported. Credential filtering is based on names and does not detect every possible secret embedded in arbitrary values.

The video timeout is a cancellation threshold, not a guaranteed wall-clock ceiling: asyncio waits for cancellation cleanup, and the installed websocket library discourages cancelling a blocked send. A timed-out send therefore renews the session instead of silently reusing that transport. Continuous audio under a failing network and actual device performance remain live acceptance checks.

## Verification

- Integrated filesystem, credential isolation, retention, ground truth, and original audit regressions: **120 passed, 38 subtests passed**.
- IPC, explicit mute, backpressure, shutdown, and CLI suites: **30 passed, 9 subtests passed**.
- Broader skills suite: **365 passed, 1 deselected, 53 subtests passed**. The excluded manifest-mirror consistency check belongs to unrelated pre-existing/concurrent harness work, whose new manifests lack matching mirror entries. Initial runs also exposed two tests with incomplete write arguments; those fixtures now include required content.
- Full core plus CLI suite, including vision/audio contention and IPC: **179 passed, 78 subtests passed**.
- All seven locked voice files verified intact; codebase reference regenerated; whitespace/diff validation passed.

Counts above describe separate runs and overlap; they must not be added as a unique test total. The complete repository suite was not run. Core and skill integration runs required escalation for temporary local sockets/subprocesses; sandbox-only attempts either denied socket binds or stalled in threaded work.

Tests use disposable directories, synthetic credentials, local sockets, SQLite fixtures, and mocked provider sends. No live account changes, real user directory deletion, microphone recording, or daemon restart was performed.

## User checks after restarting JARVIS

These commands create and modify disposable test files. Use a new folder for this check.

1. Say: “Jarvis, create a folder called Jarvis Fix Check in my Documents. Create note.txt inside it containing hello.”
2. Say: “Jarvis, copy note.txt over its containing Jarvis Fix Check folder.” Expected: overlap refusal; note.txt must remain intact. Do not test this on valuable directories.
3. Say: “Jarvis, create another.txt containing old. Copy note.txt over another.txt and replace it. Read another.txt.” Expected: hello, with no nested directory.
4. Say: “Jarvis, start a task to write café to verified.txt in that test folder, then append done. Tell me its status and read the file.” Expected: completed only after the exact contents are verified.
5. Say: “Jarvis, share my screen,” then ask “What time is it in IST?” Expected: ordinary conversation continues with screen sharing. Stop with “Jarvis, stop sharing my screen.” This is a live smoke check; it does not reproduce network backpressure deterministically.

The CLI mute state is separate from spoken standby requests. Test E05 in a terminal with `.venv/bin/python scripts/jarvisctl.py mute` twice, then `status --json`: muted must stay true. Run `unmute` twice: muted must stay false. Repeated spoken “mute” may engage standby and does not directly test this CLI repair. Credential filtering, retention bounds, fault-injected disk failures, and IPC queue limits are directly covered by automated tests rather than ordinary voice commands.
