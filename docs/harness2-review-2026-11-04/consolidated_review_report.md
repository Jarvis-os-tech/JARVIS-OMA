# Harness² whole-OS architecture — final review

Review date: 2026-11-04 (Asia/Kolkata).

**Verdict: ready to start a bounded, read-only evaluation prototype; not ready for autonomous OS repair or production promotion.** The map is a useful inventory and target vision, but lacks the contracts needed to build its central incident-to-tested-release loop. This report supplies the holes, smallest fixes and recommended build order. Fixes below are recommendations, not implemented or approved design decisions.

## Scope and evidence

Target: `/home/g0pi/.gemini/antigravity/brain/7956f3d9-c5f7-44c8-aa5d-8f8222a597ea/system_level_architecture_map.md`, lines 1–207. The user's intended scope is transforming the whole Omarchy desktop into JARVIS OS, including diagnostics and healer playbooks, rather than optimizing only the voice assistant. Parent read the user-authorized Antigravity transcript, notably user step 641, for that intent. Historical assistant claims were treated as claims, not verification.

Fresh EGM reviewers received no forked parent transcript. Comprehension read only the map; design/zoom-out checked repository reuse. Fresh conversation isolation does not prove exclusion of host instruction files. No live fault injection, deployment, audio or cloud inference was performed. No external web claims are needed for the findings below.

## Existing foundation versus missing whole-OS work

| Area | Verified current implementation | Boundary still needed |
|---|---|---|
| Research refinement | `learning/refinement.py:98–151` permits instruction-only AGENTS.md changes; `learning/bundles.py:42–48` accepts research role only | Separate OS change domain, editable surface and evaluator; keep current research safeguards |
| Background evaluation | `learning/jobs.py:197–243` has bounded jobs, leases and explicit cloud/offline distinction | OS incident admission, ownership and actual runtime isolation |
| Candidate selection | `learning/trials.py:35–125` recomputes narrow evidence; 128–158 explicitly selects/rolls back research bundles | OS release artifacts, approval scope, health and recovery |
| Supervision | `orchestration/harness2_adapter.py:1–8` keeps JARVIS supervisor authoritative | Do not turn Harness² into a competing process supervisor |
| Release mechanics | `orchestration/release_manager.py:57,425–485` has locking, pointer switch, behavior gate and recovery | Current service scope restarts voice/device bridge; it cannot be used unchanged for non-voice whole-OS releases under the freeze |
| Diagnostics | Installed `/usr/bin/omarchy-crash-watch` offers a click-to-diagnose notification; healer `playbooks.py:153–201` similarly attaches on-improve to notification clicks | Durable incident-to-evaluation handoff is not established by these launchers |
| Evidence | `learning/evidence.py:83–137` bounds and removes recognized secrets, explicitly not comprehensive DLP | Allowlisted incident export, retention and explicit cloud disclosure |

## Blocking holes and fixes

### F1 — Freeze conflicts with promotion scope

**Blocker.** Target 73–74 and 180–199 sends updates to voice, despite its freeze at 158. The map omits the standalone voice freeze. Lock verification detects changes; it grants no authority to update code, runtime settings or deployed voice services.

**Fix:** remove both voice copies from writable candidate/deployment targets. Reject protected paths before executing candidates and before release. Preserve the observed service/mute state. Test shared-code compatibility without modifying voice. Do not route initial deployment through the existing ReleaseManager unchanged: `_restart_services` at 335–342 explicitly restarts voice.

**Acceptance:** a candidate touching either protected surface is rejected before execution; no voice restart or runtime change is attempted, including when a different component fails.

### F2 — Worktree separation is not runtime isolation

**Blocker.** Target 188/202 calls worktrees sandboxes. `learning/refinement.py:174–181` creates a worktree for a constrained research rollout, not a general safe environment for arbitrary OS code. Healer `playbooks.py:262–273` can issue real systemctl mutations. General candidate tests could reach the host home, session bus, credentials or live databases.

**Fix:** use fixtures and mocked OS adapters for the first evaluation slice. Before running untrusted OS code, specify and demonstrate a disposable runtime boundary. Deny host home, credentials, control sockets, D-Bus/systemd, production databases and network by default. For compositor/system-service behavior, prefer a disposable OS guest with explicit fixture interfaces. No privileged host mounts or shared session sockets. Treat a worktree as source separation only.

**Acceptance:** deliberate attempts to write a host canary, access host session sockets, read a credential canary or control a host service fail; guest state can be discarded. Record this evidence separately from unit-test success.

### F3 — Production approval, health and recovery are undefined

**Blocker.** Target 191–207 gives test success authority to promote and promises stability without defining an owner or a recovery transaction. Existing release primitives are JARVIS-specific; research `activate_trial` selects a bundle for the next startup, not a whole-OS release. `learning/trials.py:148–158` explicitly reports restart required, contradicting any assumption of instantaneous, zero-downtime bundle rollback from earlier discussion.

**Fix:** first version produces a reviewable candidate and report only. Before enabling deployment, specify candidate/base hashes, tests and evaluator identity, allowed files/components, explicit human approval bound to that artifact, serialized activation, service state snapshot, health deadline, rollback trigger and behavior if rollback itself fails. Approval must expire when baseline or artifact changes. Include data/config migration compatibility; reverting source pointers does not undo database or external effects.

**Acceptance:** injected test failure prevents eligibility; stale baseline invalidates approval; failed health returns to the recorded prior version/state; an initially stopped service stays stopped; failed rollback is clearly reported. Replace “guaranteeing OS stability” with “eligible for reviewed deployment within the tested limits.”

### F4 — No OS acceptance benchmark

**Blocker for OS promotion.** `learning/refinement.py:324–334` explicitly states narrow synthetic research checks, no established quality gain and no Live audio coverage. `learning/voice_tests.py:1` is a manual checklist. The passing learning suite cannot certify a healer playbook, desktop operation, rollback or real audio.

**Fix:** create one domain benchmark before broad optimization: synthetic failed-unit incident → allowed diagnostic proposal → observable expected outcome in disposable state. Include normal, malformed, duplicate, stale, permission-denied, timeout, cancellation, crash/recovery and protected-target cases. Keep evaluator code and held-out cases outside candidate edit permissions. Compare against the unchanged baseline; allow an honest no-improvement result.

**Acceptance:** emit reproducible per-case outcomes, failure counts, elapsed time and resource/call budgets; forbid protected side effects regardless of aggregate score. Add desktop/session and real-hardware evaluation only when those domains enter scope; define their thresholds from measurements.

## Major holes and fixes

### F5 — Current state and proposed links are mixed

Target 174–207 depicts a connected, operational loop that the inspected research adapter does not implement. The crash watcher and healer notify first; their diagrams omit the click. Tier6 initial topology also puts benchmarks before worktree separation, opposite the detailed pipeline.

**Fix:** label every component and edge existing, implemented-unverified or proposed; attach source evidence. Correct click-to-launch and pipeline order. Mark service/model/path claims as a machine snapshot until inspected; do not hardcode UID1000 or Wayland display names in reusable contracts. Show the API-agent caller, authorization, execution and result path, or omit that disconnected box from the first slice.

### F6 — Incident-to-candidate contract is missing

No demonstrated code path joins healer incidents/coredumps to the research optimizer and OS deployer. A prompt launch is not a durable workflow.

**Fix:** a read-only exporter produces an allowlisted incident record with schema version, source incident ID, producer, observed timestamp, component, severity, redacted evidence references/hash, current baseline and desired observable outcome. An admitted task owns its candidate/run ID. Record observed, triaged, proposed, evaluated, awaiting-review, rejected or cancelled; add approved/deployed/rolled-back only when those steps exist. Store no raw core dump or unrestricted log transcript in optimizer input.

**Acceptance:** replaying the same incident is idempotent; malformed or incomplete evidence is rejected or explicitly marked incomplete; task restart does not silently repeat side effects.

### F7 — Fleet visibility is mistaken for concurrency control

Target168 claims read-only brain-who prevents collisions. Existing `refinement_lease`, job leases and release locks provide reusable pieces, but do not establish whole-OS incident ownership across separate repositories and daemons.

**Fix:** keep existing supervisor authoritative. First version admits one evaluation job at a time, with durable ownership and stale-job inspection; deduplicate incident identity and cap retries/cooldowns. Observe a repeat failure after intervention before retrying. Keep source locks separate from release activation locks. Do not build a new six-agent coordinator for the first slice.

### F8 — Evidence privacy and authority are underspecified

The blueprint feeds coredumps and incident data into an optimizer. Current `sanitize` removes recognized values/patterns and binary fields; it does not establish that arbitrary prose is free of PII. `Harness2Adapter.record_outcome` also writes task/output excerpts without invoking that sanitizer.

**Fix:** export minimal structured incident fields and bounded redacted excerpts. Treat diagnostics, transcripts, retrieved lessons and model proposals as untrusted data, never permission to execute commands or change the evaluator. Keep cloud inference explicit, show exactly what will leave the machine, record provenance and define retention/deletion. Use synthetic canaries to test leakage; do not claim comprehensive automatic redaction.

### F9 — Fresh-install reproduction is incomplete

`learning/refinement.py:36–45` and test skip messages tell users to install `requirements-harness2.txt`, but that file is absent in this checkout. Current environment tests passed because dependencies are already installed; that does not prove a clean install.

**Fix:** restore one documented pinned optional installation path matching `UPSTREAM_REVISION` and the reviewed hashes; ensure install/status errors point to a real file or command. CI must distinguish required upstream tests from optional dependency skips. Verify in a disposable fresh environment before promising portability.

### F10 — Scope, alternatives and operating limits are missing

“Whole OS” is a destination, not an executable first milestone. Architectural tiers and repair risk tiers share names. Repair permissions must come from the actual catalog/policy, not the map's broad examples such as “non-destructive clear cache.”

**Fix:** add goals/non-goals and a per-component capability table (observe, evaluate, propose, deploy). Compare advisory-only first with immediate controlled promotion; choose advisory-only to validate evidence before granting mutation. Name repair risk classes separately from architecture layers. Bound disk usage, worker count, model calls, timeouts, retry/cooldown and report retention. Stop evaluation from starving the live desktop. Do not duplicate existing monitor/healer responsibilities.

## Smallest recommended build sequence

1. **Correct the map and write the short boundary spec:** current/proposed labels, protected surfaces, component coverage, advisory-only first milestone, incident schema, owner, budgets and acceptance cases. This is the upstream gap; no production integration should precede it.
2. **Read-only incident ingestion:** use existing healer/crash evidence through a minimal exporter; fixture-backed tests first, no host repairs, no automatic agent launch from arbitrary raw logs.
3. **One non-voice domain evaluator:** start with failed user-service diagnostics in disposable state. Reuse existing job leases, budget and provenance patterns; keep OS change artifacts distinct from research-only HarnessBundle. No autonomous code execution on the host.
4. **Candidate/report generation:** bind baseline, candidate and evaluator identities; return a concrete diff, case outcomes and limits. Human reviews it. This is the first complete useful milestone.
5. **Disposable-runtime trials:** prove containment and failure recovery before any real service mutation. Add one healer playbook proposal only after its effects can be verified independently.
6. **Separately approved deployment:** extend applicable existing release primitives for a single non-voice component, preserving initial service/data state. Prove rollback, stale approval rejection and health failure handling before broader OS coverage.

Do not start by rebuilding voice, adding a parallel supervisor, replacing all monitors, importing every agent, or enabling unattended production promotion. Expand domain coverage only after one complete incident → evaluated proposal path works.

## Validation performed

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_learning`: **62 passed in 5.10 seconds**. System Python initially lacked pytest; project environment succeeded. No historical test claim substituted for this run.
- Both PC and standalone voice baseline verifiers passed before review; final checks recorded in the closing validation note.
- Read-only source inspection: learning/refinement, bundles, trials, jobs, evidence, service, voice checklist; Harness² adapter and release manager; installed crash watcher and healer playbook notification/execution paths.
- Source checkout already contains extensive unrelated changes. They were neither reverted nor included in a release. This report assesses the working tree, not a clean commit or current deployed binaries.

## Traceability

| Consolidated fix | Reviewer findings / parent verification |
|---|---|
| F1 | Z1, C2, D1, S3, Y2 |
| F2 | Z3, D2, S4, Y3; parent source inspection |
| F3 | Z3, C3, D3, S2, Y1; parent trials/release inspection |
| F4 | D5/S2 acceptance gaps; parent fixture/checklist inspection |
| F5 | Z2, C1/C7/C8, D4, S4, Y6; installed watcher/healer inspection |
| F6 | C5, D4; parent handoff searches |
| F7 | Z4, C6, D5, Y5 |
| F8 | I2; parent evidence sanitizer and adapter inspection |
| F9 | Parent missing-install-file check and successful environment-specific tests |
| F10 | S1/S3, C4, D5, Y4, I3/I4 |

## Review execution limits

Stages5–7 used actual fresh-context reviewers; reports are adjacent. Stage8 independently rechecks the unchanged map against accumulated findings. No “fixed” or convergence claim is made. Stage9 implementation-plan review is not applicable because the target has no implementation plan; a separate readiness gap assessment cannot certify an unwritten plan. The EGM automated resolution loop was not run because the user requested review/fixes, not approved edits to the source document. This is a final review of this snapshot, not proof that the design has passed all EGM gates.

Closing validation: both voice baseline verifiers passed again after review. No source document, production code, protected assets, services or runtime settings were changed. Only review artifacts and this sourced knowledge-base lesson were written.
