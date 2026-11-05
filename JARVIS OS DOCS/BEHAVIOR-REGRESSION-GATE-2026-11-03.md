# JARVIS behavior regression gate

Step 1 of the upstream adoption plan is implemented in the working checkout.
The gate checks observable JARVIS behavior with synthetic inputs and boundary
stubs, using named contracts inspired by the collected OVOS harness/OvoScope
methodology. No OVOS runtime or upstream code was installed or copied.

## Run

From the project directory, using an environment with both runtime and test
dependencies installed:

```bash
.venv/bin/python scripts/behavior_gate.py --report /tmp/jarvis-behavior-gate.json
```

Exit 0 certifies this deterministic suite; any other exit blocks certification.
The default deadline is 120 seconds. Loopback sockets must be available. The
runner removes inherited credentials, uses a temporary HOME and XDG profile,
and disables automatic third-party pytest plugins. Test data is synthetic;
the suite does not capture the desktop, play audio or call a cloud model.

## Required contracts

| Contract | Observable expectation |
| --- | --- |
| INPUT-1 | Original attachment bar remains the default; closing cleans up both interfaces. |
| ATTACH-1 | Image/audio bytes and metadata reach the fake session, text is preserved, PDF extraction/scanned fallback is honest, unauthorized HTTP input is rejected. |
| VISION-1 | Synthetic frames reach the session, missing camera leaves vision off, failures return an error. |
| CANCEL-1 | Cancellation reaches callbacks and awaits worker/process cleanup. |
| PERMISSION-1 | Destructive commands are denied, held actions need a new confirmation turn, cancellation drops pending work. |
| RESULT-1 | Failed/queued/unverified receipts cannot release success speech; verified results can; duplicate tool IDs execute once. |
| RELEASE-1 | Failed candidate restart/health restores both release pointers. |
| GATE-1 | Real miniature pytest runs prove skips, xfails/xpasses, missing cases, test/setup/teardown failures and stale reports cannot pass. |

The reviewed case inventory is `tests/behavior/contracts.json`. Every selector
must collect at least one test, and every parameterized instance collected must
pass setup, call and teardown. A skip is a failure for certification, even if a
normal full pytest run would accept it. Changes to these contracts need review
alongside the implementation; changing the case inventory is not evidence that
an old behavior is preserved.

The JSON report records case results, collected node IDs, missing/failed checks,
elapsed time, the case-inventory hash and a source fingerprint. The fingerprint
covers Python/JSON/TOML/QML/HTML/JavaScript in the listed runtime/test directories
and requirements files; it excludes collected upstream references, native
binaries and model weights. A source change during the run fails the gate.

## Integration and scope

- CI runs the gate before the full suite on its configured Python versions and
  uploads a separate result artifact for each version.
- `ReleaseManager.build_release()` runs it against the exported candidate before
  compiling/stripping tests. Missing gate files, missing test dependencies,
  unsuccessful execution or missing fresh evidence stop the build before any
  active release pointer changes. The report remains in the built release.
- The build interpreter needs `requirements-dev.txt` as well as runtime
  dependencies. The gate never installs dependencies implicitly.
- Existing rollback and narrow prepared-release repair paths remain available.
  `install_prepared_release()` and direct activation of an already-built release
  do not rerun this source-test gate. Prepared repairs need their own candidate
  validation; this change is not universal deployment enforcement.
- These are local behavioral checks. They do not certify rendered appearance,
  real microphone/camera devices, model interpretation, live provider media-format
  support, speech recognition accuracy or latency. Those need separate acceptance
  checks with appropriate user authorization.

## Issue found while building the gate

Audio attachments had been decoded as text in `LiveVoice.send_inputs()`. The
source now forwards recognized audio MIME types/extensions as binary audio
parts, preserving bytes and filename. WAV and MP3 cases exercise MIME handling;
images/text and extracted/unreadable PDFs are also covered. Actual provider
acceptance remains unverified. This source change was not deployed to the live
voice service during this task.

## Validation

- Required gate: **49 passed**, eight contracts, approximately four seconds on
  the host with loopback networking available.
- Broader release-manager, switching and CLI-release checks: **20 passed**
  (some overlap the gate's rollback cases).
- An initial restricted run could not complete loopback testing and failed at
  its deadline rather than certifying skipped work.
- Saved report: `BEHAVIOR-REGRESSION-EVIDENCE-2026-11-03.json`.

Methodology sources: collected
[`ovos-test-harness`](upstream-sources/2026-11-03/ovos-test-harness/README.md)
and [`OvoScope`](upstream-sources/2026-11-03/ovoscope/README.md). Their OVOS bus
and full-stack dependencies were not added to JARVIS.
