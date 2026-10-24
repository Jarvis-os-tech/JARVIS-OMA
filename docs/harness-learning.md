# Harness learning foundation

## Local setup and voice-controlled integration checks

The existing reviewed Harness² package can now be controlled through JARVIS's
voice tools. This setup does not clone or install Agency Agents or any other
repository. The Agency specialist layer remains deferred.

A persistent, private state directory is initialized at `.jarvis-learning/` in
the JARVIS checkout; the directory is Git-ignored. Start one JARVIS instance:

```bash
scripts/start-learning.sh
```

Stop an existing microphone session first. The launcher initializes the curated
research bundle only if none is selected, then calls the normal voice launcher
with the learning directory. It does not restart an already running service.
`JARVIS_LEARNING_DIR` can select another state directory. For setup without
microphone access or cloud connections, use `scripts/start-learning.sh --setup-only`.
This opt-in session captures text and tool results as described below.

Test these voice commands:

1. **“Jarvis, check your Harness integration status.”** Expect the local core
   availability and learning-enabled state. No installation or job starts.
2. **“Jarvis, run an offline Harness integration check.”** Expect a queued job,
   followed by a completion or failure notification. Keep talking while it runs.
3. **“Jarvis, show the latest Harness check result.”** Expect four upstream
   rollouts, three improvement stages and the fixture comparison. An offline
   pass verifies integration plumbing, not smarter behavior or an adopted lesson.
4. **“Jarvis, run another offline Harness check.”** Then **“Jarvis, cancel the
   Harness check.”** Expect cancellation if it is still running, or an honest
   report that it already finished. A fast check may finish before your cancel
   request arrives.

The tool names are `get_harness_status`, `start_harness_check`,
`harness_check_status` and `cancel_harness_check`. Only one check per running
JARVIS service is allowed; the existing state-directory lease also serializes
refinement across processes. Recent job statuses are bounded to ten in memory
and are lost on a voice-process restart; the underlying refinement reports and
worktrees remain in `.jarvis-learning/refinements/`. No automatic retry occurs.

Each check uses a child Python process, a private working directory, the existing
JARVIS source and the reviewed installed Harness² core. The child is explicitly
offline with at most 32 scripted model calls, a 120-second refinement budget and
a 150-second parent deadline. Output is capped at 256 KiB stdout and 8 KiB
stderr. Recognized secret environment variables are filtered from its initial
environment. It does not inherit the repository as its working directory.
This is trusted-local process supervision, not an OS sandbox against another
process with the same user permissions.

Cancellation and shutdown terminate only the process group created for that
check; after three seconds a still-running group is killed. Partial artifacts
remain for inspection. The bounded completion notification summarizes the check
and identifies its local report. If the notification queue is full, the check
status records a dropped notification and preserves the result for explicit
lookup. Neither the voice tools nor launcher activate optimizer candidates or
start paid cloud refinement. All locked voice files remain untouched.

This opt-in foundation adds versioned research instructions to JARVIS's existing
prompt and captures observed task evidence. The optional refinement command now
invokes real Harness² over bounded research fixtures and saves proposed guidance
for review. It does not activate candidates automatically or implement the
separate engineering team.

## Initialize and enable

From the repository root, initialize a private state directory:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state init
```

For persistent use, choose a private directory rather than `/tmp`. Initialization
registers the curated research seed and activates it only when no bundle is
already active. The seed is an original compact adaptation of Agency Agents'
Research Synthesist, with its reviewed source revision recorded in the bundle.

Opt in when starting JARVIS:

```bash
./run.sh --learning-dir /tmp/jarvis-research-state
```

`JARVIS_LEARNING_DIR` is the equivalent environment setting. Without either
setting, the new bundle loading and evidence capture paths are disabled.
The research playbook is conditional guidance for research requests; ordinary
JARVIS tool declarations and fixed runtime rules are preserved. This does not
create a specialist permission boundary for live desktop tools. Bundle files
are trusted local administrative inputs, not safe instructions from arbitrary
web pages or optimizer outputs.

The active bundle is pinned at startup. Administrative changes take effect on
the next JARVIS startup, so a running conversation cannot mix bundle versions.
Evidence records the actual connected model, prompt hash, tool-declaration hash,
and bundle hash. The full prompt/private memory is not copied into the evidence.

## Inspect, activate, restore, and correct

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state status
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state activate /absolute/path/candidate.json
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state restore
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state episodes
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state episode EPISODE_ID
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-state feedback EPISODE_ID "This answer omitted a relevant source."
```

A candidate JSON document accepts exactly `version` (1), `role` (`research`),
`instructions` (up to 12,000 characters), and `source`. Fields for permissions,
models, tools, adapters, scripts, and guardrails are rejected. Content hashes
identify immutable bundle files; an atomic active pointer preserves one previous
selection. `restore` selects that previous bundle; it does not delete evidence.
Use one administrator at a time; the registry is not a multi-writer deployment
service. Files are integrity checked, but the registry is not a defense against
another process already authorized to write its private state directory.

## Evidence semantics and privacy

`episodes.sqlite3` stores ordered observations: request/transcription fragments,
tool arguments and returned results/errors, assistant output, termination state,
and explicitly attached user corrections. Later requests reference the previous
episode; they are not automatically classified as factual corrections. Causes
remain `unknown`. Delivered output is recorded as `delivered_unverified`.
Tool return, action cancellation, and user-goal verification remain distinct.

Capture runs on a bounded background worker. Queue overflow or storage errors
produce counters, logs, and incomplete-capture records where storage permits.
Truncation and recognized-secret redaction are explicit. A total storage failure
cannot guarantee a durable health record; a process crash can lose queued events.
Episodes lacking an end record or containing pending actions require investigation.
This is a best-effort foundation, not a lossless or tamper-proof audit system.

State uses owner-only files/directories. Capture is opt-in because tool outputs
and transcripts can contain private information. Recognized credential fields,
credential-valued environment variables, and bearer strings are redacted; this
is not comprehensive secret or personal-data detection. No audio/video bytes are
recorded, and no evidence is sent to embeddings, Obsidian, or an optimizer.
Retention/deletion and finer role/privacy filtering remain future work. Do not
enable capture for sensitive workloads without reviewing these limits.

## Run the cloud-free research fixture

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-research-fixture demo
.venv/bin/pytest tests/test_learning -q
```

The demo exercises the real JARVIS prompt builder, `LiveVoice` tool-response
path, corpus-only dispatcher, and durable capture using scripted provider
messages. It makes no network calls, opens no microphone, and does not change
the selected active bundle. Its provider identity is `offline-scripted`.
The corpus permits only exact search/read operations over its supplied mapping;
it rejects arbitrary filesystem paths, other tools, and extra arguments.

The deterministic assessor checks citation quotes against corpus passages and
declared fixture answers. Missing-source cases require an explicit evidence-gap
explanation. It does not establish general semantic entailment, real model
quality, acoustic behavior, or a Harness² improvement. Those need later native
model probes and independent evaluation.

## Manual voice acceptance

Initialize a dedicated state directory and start one JARVIS instance:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-voice-test init
./run.sh --learning-dir /tmp/jarvis-voice-test
```

Avoid running a second instance alongside a service already using the microphone.
Use non-sensitive requests: this opt-in session captures text and tool results.
Print the six spoken requests and expected behavior with `voice-tests`:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-voice-test voice-tests
.venv/bin/python -m learning --state-dir /tmp/jarvis-voice-test voice-report
```

Say each request once, wait for its answer, and perform correction then recall
in the same conversation. Record pass/fail, what JARVIS actually said, and any
audio delay or interruption problem. The report searches the latest 20 episodes
for spoken markers, including fragmented transcriptions. Misheard markers may
not match. Captured output does not prove audible playback, correct answers, or
successful tools. Manual results remain pending until you review them. These
checks do not demonstrate Harness² optimization or persistent learned memory.
The test state is temporary and may be removed by the operating system; review
it before rebooting. It stays outside the source checkout.

Use an episode ID from `voice-report` to attach your own verdict:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-voice-test review EPISODE_ID pass --lag before_answer --note "Correct answer, but a pause before speaking"
```

Results accept `pass`, `partial`, or `fail`; lag accepts `none`, `before_answer`,
`during_speech`, or `unknown`. Reviews append history with explicit user
attribution. The report displays the latest review for each matching episode;
the newest matching episode determines the test's displayed manual result.
Earlier reviewed episodes do not grant a pass to a newer unreviewed attempt.
Timing includes recorded tool durations and an approximate interval between the
last input event and first output event. Background persistence and provider
transcription timing affect this interval; it is not microphone-to-speaker
latency. Missing or reversed timestamps remain unknown. A lag report does not
identify a cause or automatically rewrite the harness.

## Next integration boundary

### Run the real Harness² integration

The optional dependency pins upstream commit
`1cfe254e8d25b15f37048c3730134686abe60335`. The adapter checks SHA256 identities
of seven reviewed upstream core modules before starting. Install with Python
3.12 or 3.13 in the JARVIS environment:

```bash
uv pip install --python .venv/bin/python -r requirements-harness2.txt
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial refine --offline
```

`--offline` runs the real upstream sequential recursion with scripted model
responses: one baseline, two proposals and their rollouts, composition, and a
final rollout. Three further cases compare the baseline and composed guidance:
an unseen notice, missing evidence, and current/superseded conflicting notices.
The fixture assessor checks exact sentences and quotations independently after
refinement. It is deliberately narrow and does not establish semantic reasoning
quality. Expected offline results are tied checks, not a demonstrated gain.

For an explicit cloud trial, export `GEMINI_API_KEY` privately and supply a
Gemini **text** model available to your account:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial refine --model YOUR_TEXT_MODEL_ID --max-calls 32 --seconds 600
```

This command can incur provider charges. There are no automatic transport
retries; each provider request consumes a reserved call even on failure. Token
usage is recorded when returned; dollar cost is unknown. The model output cap
is 4,096 tokens per request. Executor attempts permit at most four model steps
with at most two corpus operations per step. Proposer evidence is capped at
120,000 characters and rejected rather than silently truncated. Network calls
have timeouts bounded by remaining time (at most 60 seconds). Local Git commands
have separate 15-second timeouts, so the wall-clock deadline is approximate.
Use Ctrl+C to stop. SIGKILL or power loss may leave only `started.json`; inspect
such a run rather than replaying it. A local lock prevents concurrent refinement
commands sharing this state directory; separate directories are separate leases.

Each attempt uses a detached Git worktree from a new **scratch repository**
containing only research instructions. The JARVIS checkout is not copied or
edited by the optimizer. Only `AGENTS.md` text is accepted; it maps to the
existing instruction bundle. The upstream Codex file-layout schema is reused,
but no Codex/OpenCode subprocess is launched. A JARVIS-native tool-free text
proposer converts upstream missions and evidence to bounded instruction JSON.
Malformed native proposals fail closed; upstream retains the previous harness.

The executor reuses JARVIS's `live_config` prompt builder and `LiveVoice` tool
response/dispatch code, with only fixed-corpus search/read skills. It uses
non-Live Gemini text transport, with no microphone, speaker, desktop, network
search tool, shell, or filesystem tools exposed to the model. This validates
the research integration; text-model findings do not establish Live voice-model
quality or acoustic performance. No source text or model output becomes code.

Inspect the printed `run_dir`: `report.json` includes upstream stage outcomes,
retrospective checks, per-call usage, and execution failures. `candidate.json`
contains the proposed bundle. `runs/` retains worktrees, source reads, outputs,
and run identities; `optimizer/context/` contains exactly the task-specific
evidence sent to the proposer. Assessor results and held-out cases are not
provided to the proposer. `interrupted.json` records caught failures; a started
run with neither report nor interruption record requires manual investigation.
Artifacts stay under the private state directory and are not automatically
deleted. This is trusted local isolation, not an OS sandbox against a hostile
process with the same user account.

The command never registers or activates its candidate and never ingests your
private voice episodes. Review `candidate.json`, the stage failures and the
baseline comparison first. The existing `activate`/`restore` commands remain
manual administration, **not quality gates**. Later work must establish broader
native-model gains, review-approved use of real mistake records, validated
experience memory, and production activation criteria. Locked voice files are
neither edited nor overridden.

### Gate a controlled trial and test it by voice

New refinement reports include a SHA256 manifest covering the candidate,
start record and every run's instructions, identity and output. Use the run ID
(the final 32-character directory name) to check a candidate:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial candidate-check RUN_ID
```

The gated trial route requires a cloud-backed report, the pinned upstream
revision, three successful proposal stages, complete unchanged artifacts, an
unchanged active baseline, and changed candidate instructions. It recomputes
the fixture checks from outputs rather than trusting the report's pass flags.
The candidate must pass all four narrow checks and exceed the baseline's count.
Offline runs and ties are blocked. Reports created before the manifest was
introduced need a new run; they cannot be retroactively treated as bound evidence.
Initialize a baseline in the trial state directory before the refinement run.
Even eligibility is only a prerequisite for a controlled manual trial, not proof
of broad quality or production readiness. A strong baseline may leave no room
for a gain on these narrow checks; do not weaken the gate to force adoption.

After reviewing the eligible bundle and evidence, a trusted local administrator
can explicitly select it:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial trial-activate RUN_ID --note "Reviewed the candidate and evidence for a controlled research trial"
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial trial-voice-tests
./run.sh --learning-dir /tmp/jarvis-harness2-trial
```

Run only one microphone session. Selection affects the next startup; the command
does not restart the service or change an already running conversation. The
voice checklist identifies the selected bundle; recorded episode identities
identify the bundle actually used by the running process. Run the same checklist
on the baseline first and record your manual results. Repeat after selection,
including research sourcing, unknown information, corrections, conversation
recall and interruption. Note whether lag is before the answer or during speech.

If the trial regresses, restore its baseline and restart JARVIS:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial trial-rollback RUN_ID
```

Rollback refuses to change an unrelated active bundle. An intent record is
written before selection; if the process dies in between, inspect `status` and
`trial-intent.json` to determine whether selection occurred. Trial activation is
serialized with refinement commands in the same state directory; legacy raw
`activate`/`restore` remain trusted administrator operations and bypass this gate.
The manifest detects accidental edits against a trusted local report. It is not
a signature or protection against someone authorized to rewrite both the report
and its artifacts. No candidate is selected by the build or offline tests.

### Scoped experience memory and voice feedback

Research experiences now reuse the existing `jarvis_memory.knowledge.KnowledgeStore`
revision ledger in a private, separate `research-experience.sqlite3` under the
learning state directory. They do not enter ordinary user-fact retrieval,
embeddings or Obsidian automatically. This avoids treating an observation or
voice correction as a standing instruction.

Restart one JARVIS instance with learning enabled to test the new voice tools:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-voice-test init
./run.sh --learning-dir /tmp/jarvis-voice-test
```

Say these in order:

1. **“Jarvis, check your research learning status.”** It should report enabled,
   the applicable lesson count and pending feedback. Zero validated lessons is
   expected until a real trial has been reviewed and published.
2. **“Jarvis, record research feedback: there was a pause before your last
   answer.”** It should save an **unverified feedback note**, with an unknown
   cause. This does not claim the delay was fixed.
3. **“Jarvis, check your research learning status again.”** Pending feedback
   should increase by one; the validated lesson count should stay unchanged.
4. **“Jarvis, list your validated research lessons.”** It should list only
   applicable reviewed lessons, or honestly report none.
5. **“Jarvis, has recording that feedback already fixed the delay?”** It should
   explain that recording feedback alone does not implement or verify a fix.

The tool names are `get_learning_status`, `list_research_lessons` and
`record_research_feedback`. The status tool also works when learning is disabled
and reports that fact. Recording/listing requires `--learning-dir`; `--no-skills`
disables these voice tools with the other skills. The tools cannot publish a
lesson, select a bundle or start an optimizer. They perform local database work
through the existing bounded file worker, outside the audio callbacks. This does
not establish a latency improvement. Feedback is a model-mediated note, not
proof of the user's exact words; it is attributed to the voice tool and remains
unverified. The preceding episode is linked when available, without claiming
that link establishes the cause of a mistake. Pending counts are scoped to the
current project, bundle and voice model.

To archive a trial candidate as a **pending** research procedure, use its run ID,
a short applicability cue, and the actual running Live model from status:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial lesson-propose RUN_ID --cue "Research notices and missing sources" --voice-model ACTUAL_LIVE_MODEL_ID
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial lesson-list
```

The archived procedure is exactly the candidate instruction bundle, not an
arbitrary new lesson written after its tests. Publication requires an eligible
trial that remains selected, a matching activation intent, and six distinct
captured checklist episodes. Run the original `voice-tests` checklist with all
six “voice check …” markers after selecting the candidate. Review every episode
with the existing `review EPISODE_ID pass` command only after checking its actual
behavior. Then publish the proposal:

```bash
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial lesson-publish PROPOSAL_ID --episodes HELLO_ID RESEARCH_ID UNCERTAINTY_ID CORRECTION_ID RECALL_ID INTERRUPTION_ID
.venv/bin/python -m learning --state-dir /tmp/jarvis-harness2-trial lesson-revoke LESSON_ID --reason "Regression observed in later use"
```

Each reviewed episode must match the candidate bundle, research role and named
voice model, contain captured input/output and an end record, and have an
explicit user pass review. Missing, duplicate, truncated, redacted or incomplete
evidence is rejected. Only the interruption case may end interrupted. These are
manual acceptance observations, not independent proof of broad model quality.
The existing narrow text checks are also recomputed before publication. No real
lesson is automatically published by this build or by the offline test fixtures.

Keys include project, model, bundle, trial and cue identities, avoiding the
memory ledger's globally unique active-key collision across scopes. Retrieval
checks project, research role, model, current bundle, content hash and expiry.
The archive retains the full procedure, cue, proposal, trial reference, separate
text/voice model identities and reviewed episode references. Voice listings are
bounded to five excerpts of 500 characters; they remain procedural references
and do not grant permissions or override fixed rules. A changed model or bundle
requires new matching evidence. Published entries are retained for audit when
revoked; rollback suppresses recall from the candidate bundle. An already-built
optimizer context is a snapshot and is not rewritten by later revocation.

Subsequent refinement runs can provide up to three published procedures (24,000
characters total) to the upstream experience context, matching project, text
model and baseline bundle. Feedback, proposals, transcripts and retrospective
check outcomes are not exported with them. Publication explicitly authorizes
this scoped reuse of the reviewed guidance. The 1,000-entry local ledger cap
stops new feedback, proposals and publication; revocation remains available at
the cap. The feature does not automatically delete older data.
Recognized credential redaction applies to feedback but is not comprehensive
personal-data detection. Keep sensitive material out of manual test requests.

Validation for this change includes the new foundation tests and existing core
agent/startup/orbit tests. Neighboring vision checks pass with temporary local
socket access, except `test_stream_vision_timeout_resilience`, whose existing
teardown stalls and was excluded after a bounded diagnostic run. No live cloud,
microphone, desktop-action, or model-quality validation has been performed.
