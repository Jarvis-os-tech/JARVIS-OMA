# Voice subsystem test report — 2026-11-04

The existing automated voice checks pass. Live conversation quality is not established, and the published standalone packages do not include the later source-lock protections.

## Executed checks

| Check | Result | Evidence |
| --- | --- | --- |
| System voice source/tests from the lock manifest, daemon, echo, IPC and voice control boundary | 468 passed; zero failed, skipped or errored | [JUnit](system-voice-tests.xml) |
| Additional connection recovery and microphone health cases | 33 passed; zero failed, skipped or errored | [JUnit](recovery-microphone-tests.xml) |
| Required repository behavior gate, including HIE and lock contracts | 214 passed; source fingerprint unchanged | [Gate report](required-behavior.json) |
| Standalone voice copy | 68 passed; zero failed, skipped or errored | [JUnit](standalone-tests.xml) |
| Original and standalone hash-lock verifiers | Passed before and after testing | Existing read-only verifiers |
| Original CLI configuration/dependency preflight | Passed | `bin/jarvis-voice --check` |
| Standalone dependency and local VAD preflight | Passed | Read-only doctor |
| Standalone shell launcher/installer syntax | Passed | `bash -n` |
| Standalone wheel/source archive code comparison | No differences from local standalone package source | Exact byte comparison |
| Published archive/wheel SHA256 checksums | Passed | `universal-voice/dist/SHA256SUMS` |

The 214 behavior-gate cases overlap the larger test run; do not add them to claim a unique total. There are 501 system voice tests across the two JUnit reports, and 68 tests for the standalone copy.

## EGM review

Applied the installed EGM `egm-drift-report` workflow to the current HIE plan, historical consolidation specification and standalone README. Read the bundled Codex integration instructions. Findings are in [the drift report](2026-11-04_DRIFT_REPORT.md). This is a document/source comparison, not the separate five-stage Goldfish review protocol; no independent reviewer consensus is claimed. The review reports discrepancies without changing protected files.

## Runtime observations

The selected full JARVIS system service was enabled and active. The active profile had barge-in enabled and 60 silent frames (1.2 seconds). A first read-only snapshot showed a provider opening-handshake timeout and reconnection. A later snapshot showed the provider connected again with echo cancellation active. The AEC microphone remained system-muted and listening was false, with no accepted speech turns in those snapshots. No unmute, service restart, model change or runtime configuration edit was made.

A connected provider does not prove microphone capture or audible output. The mute currently prevents normal spoken interaction. The handshake timeout was transient in these observations; no persistent network/provider fault is asserted.

## Test-environment limits

Initial runs in the restricted tool environment stalled: the gate timed out after 120 seconds; the isolated daemon run reached its 120-second limit; the broader duplicate run was cancelled. These partial runs are not passes. Re-running the existing system checks with normal host process/socket support completed successfully: the full 468-test run took about 7 seconds and the required gate about 20 seconds. The initial gate timeout is retained in [the failed-attempt evidence](restricted-run-timeout.json). No tests were edited or disabled to obtain the successful result.

Two ONNX warnings reported unavailable CUDA execution provider and CPU fallback during the system test run; tests passed. Standalone VAD preflight may emit a telemetry persistence warning in the restricted environment. Neither warning demonstrates a voice failure.

## Not exercised

Real microphone/speaker acoustics; actual interruption stop latency; listening-cue audibility; response tone; sustained conversations; real tool side effects; a fresh cloud session initiated by this audit; fresh dependency installation; Ubuntu/Mint/Fedora/Arch VM matrix; non-x86_64 hardware. Existing unit/integration tests use synthetic inputs or mocks and cannot replace these acceptance checks.

Both voice baselines remain frozen. Findings require a separate specific repair/unlock instruction before code or packaged deliverables can change.
