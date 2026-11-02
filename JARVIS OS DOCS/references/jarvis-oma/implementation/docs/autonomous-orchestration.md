# Autonomous software goals

Call `start_agent_goal(goal, workspace)` once for an authorized software task.
The default `cost_profile="configured"` preserves existing CLI providers, models,
and Claude Code proxy settings. Codex is temporarily excluded: Claude performs
development and review. The optional `cost_profile="budget"` assigns models through
`orchestration/model_policy.py`. Codex defaults to the locally configured
`gpt-5.6-luna`; Claude uses `haiku` (resolved by the installed provider).
Set `JARVIS_BUDGET_MODEL_HERMES` and `JARVIS_BUDGET_MODEL_OPENCODE` to supported
model IDs for their providers before launching. All four routes can be overridden
using `JARVIS_BUDGET_MODEL_<AGENT>`. Missing budget routes fail before any agent
launches; there is no automatic fallback to a more expensive model. Explicit
`cost_profile="configured"` preserves each CLI's own defaults. Provider pricing
and subscription coverage must be checked separately; this policy selects models
but cannot enforce a dollar spending cap or guarantee provider-side billing.
It returns a team ID without waiting for agent execution. The fixed workflow is
Hermes research/planning → Claude development → OpenCode QA → Claude
review/final testing. Optional agents remain available through explicit team
assignments. Antigravity has a development persona but no verified executor yet.

Each stage receives recent preceding output as untrusted evidence. Failures stop
later launches. `check_agent_team` returns member job IDs; `check_agent_job`
provides their output. `cancel_agent_team` stops current work and prevents later
stages. Completion events enter the existing voice notification queue. A stage
exiting successfully is not independent proof that its deliverables are correct.

“Stop all Jarvis work” immediately blocks new agent jobs and teams, cancels
teams still preparing their terminals, and waits for owned cancellation before
reporting stopped. A cancelled voice request does not abandon an ongoing stop.
“Resume Jarvis” reopens agent admission once cancellation has finished.

Memory context is fetched on the memory worker. This is a bounded snapshot;
full historical memory search from external agents is not implemented yet.

Goal stages run native interactive agent interfaces in four titled panes of one visible
terminal and one team session on the private `jarvis-desktop` tmux server.
All panes are created up front. Native agents report completion through a per-job
JSON handoff file as their final tool action; JARVIS then starts the next stage.
This is agent-reported completion, not process exit or independent verification.
Missing completion reports time out. Completed interactive panes remain available
for inspection and further conversation. Legacy batch mode still uses process exit.
The user-requested
default uses Hermes `--yolo`, Claude `--dangerously-skip-permissions`, and OpenCode
`--auto` (which retains explicit deny rules). Existing provider/model settings are
preserved. This removes per-action permission prompts according to each CLI's
native semantics. It does not remove timeouts or make a zero exit code proof of
correctness. Long-running model turns can still time out.

Teams run asynchronously with conversation. Stages sharing a checkout execute
sequentially. Separate jobs in distinct workspaces can run concurrently (up to
four). Team state currently lives in memory; restart recovery, durable scheduling,
isolated parallel development branches, structured semantic QA gates and Harness²
integration remain future work. This change does not establish the cause of a
live microphone outage; audio and interruption behavior still need a live test.
