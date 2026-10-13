# Capability development

JARVIS can develop changes to its own Python code or another trusted Python
repository. A goal launches fresh researcher, implementer, and reviewer sessions
through the installed coding-agent CLI. Each role runs sequentially in one private
checkout; separate JARVIS agent jobs can still run in unrelated workspaces.

This improves the assistant's software and tools. It does not train model weights,
grant new OS permissions, or prove that a requested feature works just because an
agent says it does.

## Use

Restart the voice assistant after loading this code, then say something like:

> Develop a capability that lists my audio devices. Use Codex in
> /home/g0pi/Projects/JARVIS-OMA, add tests, and prepare the change for review.

The voice model calls `start_development` with the goal and absolute repository
path. Ask for `development_status`, `list_development_jobs`, or
`cancel_development` using the returned job ID. The standard manifest directory is
`skills/manifests`; the legacy `skill_manifests` copy also includes these tools.
Custom manifest directories must include `development.json` to expose them.

Without starting audio or the cloud voice connection:

```sh
.venv/bin/python scripts/develop.py start \
  "Add an audio-device listing capability with tests" \
  --workspace /home/g0pi/Projects/JARVIS-OMA --agent codex
.venv/bin/python scripts/develop.py list
.venv/bin/python scripts/develop.py status JOB_ID
```

`start` stays in the foreground, prints its ID immediately, and prints final
evidence on completion. Ctrl+C or SIGTERM cancels that job and keeps its checkout.
Voice jobs live in the assistant process. The CLI list/status commands only read
saved evidence; they do not take ownership of, interrupt, or resume active jobs.
There is no cross-process CLI cancel command: stop a foreground job with Ctrl+C
and a voice-owned job with `cancel_development`.

Requirements: Git, Linux bubblewrap (`bwrap`), a Python environment containing the
target project's test dependencies, and an installed/authenticated agent
(`codex`, `claude`, `opencode`, `gemini`, `hermes`, or `omp`). Discovery checks
installation, not login status or quota. No packages or accounts are provisioned
automatically. Internet research depends on the selected CLI's available tools;
the research prompt asks for official sources and disclosure of unavailable
research, but does not guarantee web access.

## Execution and evidence

1. Validate the goal, agent, autonomy controls and repository path. One development
   job runs at a time, with an exclusive manager lock across processes.
2. Require a clean Git source tree, including untracked files. Clone without hard
   links, pin the exact source commit, and remove the origin remote. Ignored files,
   local `.env`, virtual environments and uncommitted edits are not copied. Tracked
   `.env` files are rejected; `.env.example`, `.env.sample` and `.env.template` are
   allowed. Git history is copied, so only use trusted repositories without
   committed secrets.
3. Run the unchanged baseline tests. Failure stops work before any paid agent
   session. The runner is fixed to `python -m unittest discover -s tests` and
   requires a nonzero reported test count.
4. Run research, retain its notes, and pass them to a new implementation session
   as reference data. Research that changes checkout files fails the job.
5. Capture the implementation diff, including new files, and run the test suite.
   Missing tests, zero tests, a failing exit code, timeout, or files changed during
   testing prevent a ready result.
6. Run a fresh reviewer session against the tested tree and actual test result.
   A Git tree fingerprint detects reviewer edits. Review text is explicitly
   untrusted evidence; a zero reviewer exit code is not semantic approval.
7. Save `ready_for_review` only after these checks. It means the proposal is
   available for inspection, not that review approved it or the feature is live.

Private records live under `$XDG_STATE_HOME/jarvis-oma/evolution`, defaulting to
`~/.local/state/jarvis-oma/evolution`. Each job contains its exact source commit,
checkout path, phase IDs, exit codes, bounded logs/diff, test results, tested tree
ID and review output. Diff/log truncation is reported; the full proposed files
remain in the checkout. Interrupted jobs are marked `interrupted` on manager
restart and never blindly resumed. Start a new job to retry a goal. Retained
checkouts are not automatically deleted; manage their disk usage after review.

Each agent phase has a 15-minute wall-clock limit; each test pass has five minutes.
There are no automatic repair loops. These are time/concurrency bounds, not token
or billing limits. `pause_jarvis` and `stop_all_jarvis_work` cancel voice-owned
development and reject new starts until resumed. Shutdown cancels development
before closing the shared agent pool. For a separately running CLI, changes to the
shared control latch are checked at stage/command boundaries.

## Isolation and activation boundary

The test runner requires bubblewrap: private process/network namespaces, a cleared
environment, temporary home, read-only system/Python runtime, and only the proposal
checkout writable. It fails closed if the sandbox cannot start. There is no
fallback that executes generated tests directly on the host. The kernel must
permit the required namespaces. Tests that need a real desktop, audio server,
network or host services need a separately designed integration test environment.

The coding workers themselves use the existing agent CLI permissions and
authentication. Their separate checkout prevents ordinary edits from modifying
the source, but is **not a security sandbox**: those CLIs may still access host
files or network within their configured permissions. Process-group cancellation
also does not guarantee containment of a hostile worker that detaches. Tests and
agent reports remain fallible and can be gamed; inspect changed tests and the
review report. This version is for trusted repositories and installed agents.

There is deliberately no automatic apply, hot reload, restart, push or deployment
stage. Review the retained checkout against its recorded `source_head`, integrate
the chosen changes using your normal Git workflow, run integration tests, then
restart JARVIS. The running assistant remains on its current code until that
separate release step. Automated activation, canary checks and rollback need a
release manager before unattended live self-updates are appropriate.

## Design references

The staged workflow and preserved evidence follow the emphasis on incremental
work and verification in [Anthropic's long-running agent harness research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
and [OpenAI's harness engineering report](https://openai.com/index/harness-engineering/).
The local architecture audit motivated explicit code gates and the distinction
between process completion, test evidence, review and deployment.

## Verification

```sh
.venv/bin/python -m unittest tests.test_orchestration.test_evolution tests.test_skills.test_development -v
JARVIS_TEST_SANDBOX=1 .venv/bin/python -m unittest tests.test_orchestration.test_evolution.SandboxIntegrationTests -v
```

The ordinary tests use trusted local fake agents and temporary repositories, with
no cloud calls. The opt-in sandbox check runs real bubblewrap and verifies access
boundaries. No successful paid/cloud-agent run is implied by these tests.
