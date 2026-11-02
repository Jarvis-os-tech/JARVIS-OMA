# JARVIS OMA Verification Matrix

Date: 2026-10-18

This report is based on source inspection, the current repository tests, and four independent focused audits. A capability is marked **verified** only when implementation evidence and executable test evidence agree. Mocked subprocess tests prove wiring and guards, not live desktop success.

## Repository test baseline

| Check | Result | Meaning |
|---|---|---|
| System Python pytest | Failed before tests | `pytest` is not installed in `/usr/bin/python3`. |
| Project pytest collection | Failed | Running `./.venv/bin/python -m pytest -q` produced 66 collection errors, including missing `openjarvis`, missing `click`, and test-package import conflicts. |
| Project tests with `PYTHONPATH=.` | Incomplete | Tests started and reached failures, then stalled in a live-style test run. It was stopped after the run stopped producing output. |
| Focused memory/proactive audit | 128 tests passed | These areas have strong unit-level evidence. Two integration modules could not import because `numpy` and `httpx` were unavailable. |
| Focused GUI/system audit | Unit-level tests passed | Guards, schemas, dispatch, stale-frame checks, and result handling are covered. Live desktop effects were not proven. |
| Focused orchestration audit | Partial | Local orchestration code is implemented; some skill tests could not import because `httpx` is missing. |

## Verified or mostly verified capabilities

| Capability | Status | Evidence | Important limit |
|---|---|---|---|
| Skill manifest discovery and schema validation | Verified at unit level | Registry and skill tests | Does not prove every optional runtime dependency is available. |
| Filesystem operations | Verified at unit level | Filesystem and task-runner tests | Integration test collection is affected by missing dependencies. |
| Memory facts, profiles, recall, correction, and forgetting | Working with integration gaps | 128 focused memory/proactive tests passed; source inspection | Session wiring depends on configuration; SQLite cleanup warnings need follow-up. |
| Proactive events, ledger, policy, pause, resume, and stop | Working with recovery risks | Focused proactive tests passed | Processing events may be stranded across a crash. |
| System-control command wiring | Working at adapter level | Tests cover lock, screenshots, windows, power, network, clipboard, typing, brightness, audio, and workspace dispatch | Most tests mock external commands; live compositor, hardware, and session state are unverified. |
| GUI safety guards | Working at adapter level | Tests cover fresh observations, tokens, bounds, stale frames, and recovery | Live Cua/Hyprland input was not exercised. |
| Browser-control safeguards | Working at adapter level | Tests cover binding, URL constraints, routes, and dispatch | Real browser connection and post-action page changes are unverified. |
| Background agent supervisor | Working with limits | Source inspection shows four active-job limit, workspace reservation, cancellation, timeout, output bounds, and sanitized environment | Installed CLI does not prove authentication or task correctness. |
| Visible Codex/Claude execution | Partial | Tests cover terminal launch and prompt submission guards | Actual tmux, terminal, and agent interaction was not verified. |
| Capability development workflow | Partial | Source includes isolated checkout, stages, diff, review, and retained evidence | Real `bwrap` sandbox and authenticated agent stages were not verified. |
| Agent Orchestrator app integration | Partial | Manifest, adapters, and mock tests exist | Required dependency and live daemon behavior were not verified. |

## Not yet proven

- Live microphone and speaker streaming through PipeWire
- Live Gemini session and tool-call round trips
- Live screen/camera frames reaching the model
- Live GUI clicks, scrolling, typing, and keypress effects
- Live browser tab binding and navigation
- Live system power, network, audio, and brightness changes
- Authentication and quota for any coding agent
- Recovery after JARVIS process crash and restart
- Full end-to-end voice-to-action-to-verification workflows
- Correct installation and importability of the bundled legacy memory-system tests

## Findings that should become engineering tasks

1. Define one supported test command and fix collection/import configuration.
2. Install or declare the missing project test dependencies through the project’s normal dependency process; do not silently rely on host packages.
3. Split offline unit tests from live desktop smoke tests so the offline suite cannot hang.
4. Add a capability health command that reports dependency, session, binary, and authentication readiness.
5. Add controlled live smoke tests for GUI, system adapters, and agent delegation.
6. Close SQLite connections deterministically in retrieval paths.
7. Reclaim or reconcile proactive events that remain processing after a crash.
8. Persist agent jobs and recovery state across JARVIS restarts.
9. Change capability status in the master blueprint only from evidence in this matrix.

## Status vocabulary

- **Verified:** implementation and relevant automated tests agree.
- **Working at adapter level:** code and mocked/unit tests work, but live external behavior is unproven.
- **Working with integration gaps:** core tests pass, but wiring or environment gaps remain.
- **Partial:** meaningful implementation exists, but important paths or dependencies are not proven.
- **Unverified:** claimed or present in code, but no reliable executable evidence yet.
