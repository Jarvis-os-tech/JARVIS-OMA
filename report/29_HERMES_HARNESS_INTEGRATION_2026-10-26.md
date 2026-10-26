# Hermes and Harness integration — 26 October 2026

## Team board

All changes preserve the existing dirty checkout and locked voice files. No
repository installation is part of this work. Runtime refinement uses scratch
worktrees; task helpers use fresh owned Hermes sessions.

| Work item | Owner | Scope | State | Gate |
| --- | --- | --- | --- | --- |
| Hermes gateway bridge | hermes_bridge; final hardening by root | New bridge module and protocol tests | Integrated | Real gateway metadata, bounded protocol and lifecycle tests |
| Temporary task agents | dynamic_agents | Supervisor and lifecycle tests | Integrated | Ownership, bounded jobs, cancellation and persistence |
| Feedback-driven Harness | mistake_refinement | Learning runner/CLI and feedback tests | Integrated | Real upstream recursion with selected feedback; independent checks preserved |
| Voice integration | root | Skills, manifests, prompt, docs, readiness | Integrated | Schema validation, runtime tests, voice lock, service inspection |

## Acceptance record

The combined learning, Hermes bridge, task-agent, voice adapters, agent/startup,
configuration, voice orbit, IPC and Groq routing suite passed **238 tests and
52 subtests** in 13.70 seconds after final replay-gap, child-process cancellation,
credential inheritance and shutdown checks. Tests using local sockets and scratch
Git worktrees ran outside the restricted tool environment. The complete learning suite independently passed
96 tests. All seven locked voice files verify intact, and the generated codebase
reference is synchronized.

The existing `jarvis-oma.service` was restarted after verification. Its actual
IPC status reports `learning_enabled`, `personal_agents_enabled` and
`feedback_refinement_enabled` all true, with zero learning capture failures or
drops. The service is idle and remains muted for manual voice acceptance. Local
readiness diagnostics pass for all 15 learning/refinement/helper voice tools.
Manual acoustic and real user-task acceptance remain pending.

Actual gateway discovery reported **65 toolsets and 90 enabled tools**. A fresh
isolated session returned `JARVIS_HERMES_OK`; an explicit second turn in that
session returned the distinct `JARVIS_HERMES_FOLLOWUP_OK`. Both had matching turn
admission identities. The complete TaskAgents supervisor also completed a real
no-tools request, with its private scratch Git worktree and durable journal:
`task-6a55fb755164`. These demonstrate background communication and ownership,
not the accuracy of arbitrary tools or tasks.

Hermes source inspected locally was revision
`bf0203a794a07aac3ff764972ab9087baa4e4f4e`. The bridge uses the existing installed
interpreter receipt and supported authenticated gateway client, avoiding a
launcher bootstrap that could attempt dependency repair. It neither installs
nor updates repositories or starts an absent gateway. Capability discovery is
read-only; only fresh JARVIS-owned sessions receive task prompts.

Temporary agents are role-specific Hermes sessions. They inherit Hermes's
configured harness, provider and tools. Roles are not new executable code or OS
permission boundaries. Sessions use separate private scratch worktrees, three
active-task and 600-second limits, bounded/redacted context and results, explicit
cancellation acknowledgment and private restart-readable journals. Follow-ups
operate only on sessions owned by the current manager. No existing personal
conversation is adopted, and unknown work is not replayed.

Selected feedback now reaches real Harness² instruction proposal stages through
cloud inference. Tests execute the real upstream recursion with a scripted
backend and assert proposer-only notes, secret redaction and artifact identity.
The cloud child receives only its explicitly needed provider key. No paid
Harness model trial was run. Reports retain `feedback_addressed_verified: false`;
the fixed research checks do not establish that the selected complaint is fixed.

Candidates are proposals. Existing independent checks, explicit trial activation,
manual voice acceptance, lesson publication and rollback remain in force.
This does not implement unattended production-code modification, repair model
weights, or demonstrate general self-improvement. The existing engineering route
remains separate. No candidate was activated or lesson published by this build.

Operator steps and voice requests: [personal agents](../docs/personal-agents.md),
[selected feedback refinement](../docs/mistake-refinement.md), and
[trial/rollback administration](../docs/harness-learning.md).
