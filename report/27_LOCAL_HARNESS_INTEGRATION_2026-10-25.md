# Local Harness² integration — 25 October 2026

## Scope

This integration connects the already installed, reviewed Harness² core to
JARVIS's local research instructions, observed task evidence, offline checks,
controlled candidate trials, and scoped experience memory. No repository is
cloned and no dependency is installed. Agency specialist roles and the separate
engineering team remain deferred.

The local voice route runs an **offline integration check** using scripted
responses and the real upstream refinement loop. Passing establishes working
integration, not improved intelligence. Model-backed research trials are an
explicit separate administration operation. There is no unattended deployment
or automatic rewriting of JARVIS application code, permissions, or voice core.

## Team and integration gates

All implementation stays in the existing checkout to preserve current local
work. Agents have disjoint file ownership; optimizer executions use isolated
scratch worktrees.

| Work item | Owner | Files | Acceptance gate |
| --- | --- | --- | --- |
| Shared headless prompt and tool execution | headless_boundary | core/agent.py and new shared core modules | Existing runtime tests; unchanged live behavior; no locked audio edits |
| Research runner boundary | local_runner | research runtime, fixture, operator guide | Same production prompt and dispatch; headless execution opens no audio subsystem |
| Independent reliability verification | independent_verify | learning tests | Fresh-process no-audio regression, repeated real upstream offline runs, lifecycle tests |
| Local setup and final integration | root | diagnostics, startup, references, report | Local readiness, affected tests, voice lock, running-service status |

## Implemented behavior

- Research instruction bundles have immutable content identities and an explicit
  active/previous selection. The running session pins its bundle at startup.
- Bounded background evidence capture records observations and explicit feedback;
  incomplete capture and unknown causes remain visible.
- Seven voice tools expose learning status, reviewed lesson lookup, unverified
  feedback, and offline Harness check status/start/result/cancel.
- Checks run in owned child process groups with call, time and output limits.
  Private atomic journals preserve terminal results across restarts. Recovery
  does not blindly replay work or signal an unverifiable old process.
- Refinement saves candidate instructions and baseline/held-out evidence. It
  never activates its output. Offline results cannot qualify for a model trial.
- The trial gate recomputes checks and verifies artifact identities, provenance,
  baseline selection and strict improvement before explicit activation. Rollback
  refuses to replace an unrelated selection.
- Experience publication additionally requires six distinct manually reviewed
  voice episodes with matching bundle/model identities. Feedback alone remains
  an observation, never an authoritative lesson. Revocation suppresses reuse.
- Normal startup detects the initialized private project state unless explicitly
  overridden or disabled. Setup-only and `learning doctor` need no microphone
  or model request.

## Verification record

Final verification completed on 26 October 2026. All four work items above are
integrated in the working checkout; no commit or remote publication was made.

- Final combined learning, core agent/startup/config, voice orbit, Groq routing
  and IPC suite: **208 passed, 52 subtests passed** in 16.29 seconds. Local
  socket tests required execution outside the restricted tool environment.
- Neighboring audio extension/native-backend and setup/doctor/launcher checks:
  **36 passed, 12 subtests passed**. All seven locked voice files verify intact.
- **20/20 fresh-process offline refinements** completed after the headless fix.
  An import-blocking regression also completes the real upstream loop while
  forbidding `audio`, `sounddevice` and `core.agent` imports.
- A real background job completed four upstream rollouts and three stages in
  the private project state. A new manager recovered its completed journal.
  Its result explicitly records no verified improvement and no activation.
- Setup-only diagnostics report ready, with the reviewed upstream core, active
  research bundle, database integrity and seven voice adapter bindings verified.
- The existing `jarvis-oma.service` is running and its actual IPC status reports
  `learning_enabled: true`, the selected research bundle, and zero learning
  capture failures/drops. The service already loaded the integration during
  startup; no additional restart was needed. Listening was muted at inspection.
- Independent final review found no material integration blocker.

The earlier intermittent child hangs were reproduced by a standalone
`sounddevice` import. Headless research previously imported the voice runtime
just to use its prompt and tool policy. Those functions now live in shared
audio-independent modules, and both live JARVIS and refinement use them. The
locked audio subsystem was not modified. This removes the observed audio
initialization dependency from refinement; it does not claim to repair native
audio initialization generally.

Manual acoustic acceptance remains pending. No paid/model-backed refinement,
verified model-quality gain, or production lesson publication was performed.
Captured mistakes do not yet automatically become optimizer tasks. The completed
local integration provides the bounded execution, evidence and review paths;
unattended general self-evolution is a later capability.

## Manual voice acceptance

Use the existing JARVIS instance after the integration is loaded:

1. “Jarvis, check your Harness integration status.”
2. “Jarvis, run an offline Harness integration check.”
3. “Jarvis, show the latest Harness check result.”
4. “Jarvis, check your research learning status.”
5. “Jarvis, record research feedback: there was a pause before your last answer.”
6. “Jarvis, list your validated research lessons.”

Report what it said, whether the action succeeded, and whether any lag happened
before the answer or during speech. Zero validated lessons is expected until a
real candidate has met the text and manual voice gates. Recording a delay does
not diagnose or fix it.

The complete administration and rollback commands are in
[the operator guide](../docs/harness-learning.md).
