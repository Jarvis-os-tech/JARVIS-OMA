# Phase 1 implementation: OS contract foundation

The Phase 1 boundary and contract checker is implemented in `learning/os_contracts.py`, with dedicated tests in `tests/test_learning/test_os_contracts.py`. It uses only the Python standard library and does not import the voice runtime, optional Harness² optimizer or cloud SDKs. Existing research call sites, tool manifests and service configuration are unchanged.

Attribution: CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M. Adamek (Impact Brussels ASBL). Content CC-BY-4.0; code Apache-2.0.

## Implemented behavior

- Accept at most 64 KiB of UTF-8 JSON; reject duplicate keys, unknown/missing fields, invalid Unicode, non-finite values and malformed nesting.
- Admit only fixture-producer, fixture-user-service incidents. Validate typed observation enums, unique observation identities, incident/observation freshness against an explicit clock, and state consistency. No logs, command fields or arbitrary diagnostic text.
- Require an independently supplied baseline hash and bind revisions to the entire validated incident. Evaluation keys also bind evaluator and fixture identities. Snapshot bytes are immutable; exporting a document returns a fresh copy.
- Validate data-only diagnostic proposals against the same incident revision, baseline, advisory action enums and supporting observations. Require synthetic/no-root-cause limitations, distinguish absent/conflicting evidence, and refuse unsupported diagnoses. This is contract conformance, not an independent quality benchmark.
- Screen repository-relative changed file paths against PC manifest roots/individual legacy files, the entire standalone voice tree, the verifier and new contract/evaluator surface. Reject traversal, absolute paths, directory targets, symlinks and existing hardlinks. Missing/invalid manifests fail closed. Passing returns execution_allowed=false and activation_allowed=false.
- Supply read-only CLI commands for policy, incident validation, proposal validation and path screening. Rejected input is not echoed. Incident-file reads are bounded and reject final-component symlinks and nonregular files, including FIFOs.

## Commands

Run from the repository root:

```bash
python -m learning.os_contracts policy
python -m learning.os_contracts check-paths learning/future_os_adapter.py
python -m learning.os_contracts check-paths voice_layer/daemon.py
```

The second command is a path-screening success, not permission to apply a change. The third exits 1 because voice is protected.

Validate a prepared fixture incident by piping its JSON to stdin:

```bash
python -m learning.os_contracts validate-incident --baseline TRUSTED_SHA256 < incident.json
python -m learning.os_contracts validate-proposal --baseline TRUSTED_SHA256 --incident incident.json < proposal.json
```

Replace TRUSTED_SHA256 with a trusted 64-character lowercase SHA-256, not a hash accepted solely from the imported incident. CLI timestamps use actual current UTC; API tests inject a fixed timezone-aware clock. There is no stale-input bypass flag. The CLI writes its small result to stdout and creates no state/job files. See the architecture's exact field contract and the test fixture for input construction.

Programmatic API: `parse_incident(raw_bytes, baseline_sha256=trusted_hash, now=trusted_clock)` returns an immutable canonical snapshot with key/revision/evidence hashes. `parse_proposal(raw_bytes, incident=validated_incident)` returns a checked advisory data object. `incident.evaluation_key(evaluator_sha256, fixtures_sha256)` binds a future evaluation identity. Validate bytes at every later external ingress; do not treat a manually constructed Incident instance as trusted input.

## Verification

The complete learning suite, including the new contract tests, is run with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_learning --junitxml=docs/harness2-review-2026-11-04/phase1-tests.xml
```

Result: **120 passed in 10.40 seconds**, including **58 new contract checks**, with zero skips. The adjacent JUnit file records this build's result. System-Python CLI smoke checks passed for policy and an unprotected path, and correctly rejected a voice path. Both voice baseline verifiers are checked before and after development. No voice settings or services are touched by these commands.

## Remaining phase boundaries

This module performs validation only. No worker, durable job store, real healer exporter, candidate execution, network operation, VM, deployment or rollback is installed. Future worker quotas are policy targets explicitly marked enforced=false. A path check is a point-in-time filter, not a filesystem sandbox; future writers must revalidate and avoid link/race attacks at the actual mutation boundary. The existing voice-lock verifiers remain responsible for baseline-integrity checks; this path screen does not replace them.

No runtime approval is produced. No model-quality or hardware acceptance is established. Phase 2 must implement and test real occurrence identity, consistent read-only database ingestion and missing-evidence handling before enabling real producers. Phase 3 must add an independent evaluator and durable reporting rather than treating proposal validation as proof of diagnosis quality.

Closing checks: both PC and standalone voice verifiers passed after the final code changes. Python syntax and whitespace checks passed. No dependencies were added, and no existing research/voice entry point was modified.
