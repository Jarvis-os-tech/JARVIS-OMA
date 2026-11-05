# Goldfish Annotated Review Report

**Status:** resolved at the documentation level following the user instruction to proceed. Ten proposed textual fixes applied in the workspace replacement architecture.md; zero contested, escalated or declined. The original Antigravity map and production code remain unchanged. Implementation/operational findings remain open.

**Target:** original Antigravity architecture map, full file (1–207). Proposed replacement is `architecture_proposed.md` beside this report. The original is outside the writable workspace; approval can establish this workspace version as the canonical replacement without modifying Antigravity storage.

All ten findings are PROPOSE FIX; no finding is contested, escalated or declined. Approval covers the concrete proposed architecture text and its advisory-first scope/defaults. It does not authorize implementation or deployment, and does not unlock voice.

## F1 — Freeze conflicts with promotion scope — Severity: Blocker
- **Affected scope:** original map; see F1 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Freeze conflicts with promotion scope; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Delete every Harness²-to-voice promotion arrow; replace with immutable exclusions for both manifests and preserve service state.
- **Replacement location:** `Authority and protected boundaries` in `architecture_proposed.md`.

## F2 — Worktrees presented as runtime isolation — Severity: Blocker
- **Affected scope:** original map; see F2 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Worktrees presented as runtime isolation; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Replace sandbox wording with source separation; forbid candidate execution in milestone1; require tested disposable guest before later execution.
- **Replacement location:** `Runtime isolation and later execution` in `architecture_proposed.md`.

## F3 — Undefined production approval and recovery — Severity: Blocker
- **Affected scope:** original map; see F3 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Undefined production approval and recovery; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Replace stability guarantee with disabled deployment and artifact-bound approval, prior-state capture, behavioral health and explicit rollback failure semantics.
- **Replacement location:** `Deployment and recovery contract — future, disabled` in `architecture_proposed.md`.

## F4 — Research checks treated as OS evidence — Severity: Blocker
- **Affected scope:** original map; see F4 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Research checks treated as OS evidence; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Add independent fixture evaluator, forbidden-effect checks and per-case outcomes; explicitly limit synthetic quality claims.
- **Replacement location:** `Proposal and evaluation contract version1` in `architecture_proposed.md`.

## F5 — Current/proposed states mixed — Severity: Major
- **Affected scope:** original map; see F5 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Current/proposed states mixed; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Replace unlabeled topology with evidence table and explicitly proposed flow; correct click-to-launch and portable path assumptions.
- **Replacement location:** `Existing evidence and proposed coverage` in `architecture_proposed.md`.

## F6 — Missing incident handoff — Severity: Major
- **Affected scope:** original map; see F6 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Missing incident handoff; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Add bounded allowlisted incident/proposal/report contracts and revision/idempotency behavior; synthetic input first, tested read-only exporter later.
- **Replacement location:** `Incident contract version1` in `architecture_proposed.md`.

## F7 — Telemetry mistaken for locking — Severity: Major
- **Affected scope:** original map; see F7 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Telemetry mistaken for locking; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Keep supervisor authoritative; add one-writer lease and durable incomplete state without silent replay; remove collision-prevention claim.
- **Replacement location:** `Ownership, restart and limits` in `architecture_proposed.md`.

## F8 — Unspecified evidence privacy — Severity: Major
- **Affected scope:** original map; see F8 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Unspecified evidence privacy; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Reject raw logs/cores/transcripts and executable content; structured minimum fields only, private local storage and no cloud calls.
- **Replacement location:** `Incident contract version1` in `architecture_proposed.md`.

## F9 — Missing optional dependency installation path — Severity: Major
- **Affected scope:** original map; see F9 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Missing optional dependency installation path; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Require trusted origin/pin reconstruction plus a clean disposable install test without upstream skips; do not claim package repair is implemented.
- **Replacement location:** `Acceptance and build dependencies` in `architecture_proposed.md`.

## F10 — Missing scope, alternatives and limits — Severity: Major
- **Affected scope:** original map; see F10 in consolidated_review_report.md for reviewer/source traceability.
- **Discrepancy and rationale:** Missing scope, alternatives and limits; evidence and consequences are recorded in the consolidated review.
- **AI Suggestion:** PROPOSE FIX
- **Proposed Edit:** Add coverage/non-goals, three alternatives, explicit proposed quotas and staged acceptance; keep architecture approval pending.
- **Replacement location:** `Problem and scope; Alternatives awaiting author decision` in `architecture_proposed.md`.

## Remaining work
Approval settles the written architecture choice, not implementation evidence. Production code, clean-install reproduction, guest containment and release recovery still require separately authorized work. No review convergence or safety guarantee is claimed.

## Resolution handoff

Ten textual fixes accepted/applied to architecture.md; zero contested/escalated/declined. User clarification permits voice inspection/findings only, with both codebases and behavior preserved. Phase ordering places advisory evaluation before guest trials and deployment. No independent re-audit/convergence claimed. F1–F10 require later implementation evidence and are not operationally closed.
