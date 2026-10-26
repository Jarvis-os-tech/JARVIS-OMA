# JARVIS, Hermes and Harness²

JARVIS remains the voice interface. Temporary task agents use the already
installed Hermes gateway, configured provider, harness and skills in the
background. They are task-specific sessions, not newly installed agents or
new model weights. No copy of Hermes or its skill library is maintained here.

Use `get_hermes_status` before relying on the connection. `create_task_agent`
returns a queued job immediately. `task_agent_status` reads progress and bounded
output; `list_task_agents` lists JARVIS-owned jobs. `followup_task_agent` creates
another turn in the same owned helper session after its prior turn ends.
`cancel_task_agent` reports the cancellation acknowledgement and any uncertainty.
Do not assume cancellation undoes tools or external changes.

Limits are three active helpers, 600 seconds per task and 50 retained job
journals. Inputs and results are bounded and recognized credentials are
redacted, with redaction/truncation flags visible in job status. This is not
comprehensive personal-data filtering. Completed results survive restart;
follow-ups are permitted only for sessions owned by the current manager.
Interrupted work is not replayed. Unknown remote execution blocks new work
until inspected; a local restart cannot establish that remote tools stopped.

For a no-model connection check from the project root:

```bash
.venv/bin/python scripts/check-personal-agents.py
```

Add `--smoke` to explicitly send one harmless no-tools request through the
configured Hermes provider. No installer or gateway bootstrap is invoked.

Only the relevant task and explicit context are sent. Personal Hermes chats
are not resumed by default. Helper results are untrusted observations. A model's
claim that it changed something still needs an appropriate independent check.

Hermes retains its configured permissions. A role prompt, working directory,
deadline or private job journal is not an OS security boundary. JARVIS must
preserve the user's authorization when delegating, including explicit approval
for messages to others and consequential external actions. Simple helpers
should produce drafts, analysis and proposals; code-changing engineering work
belongs in the existing isolated-worktree development route.

Try these voice requests:

1. “Jarvis, check the Hermes background connection.”
2. “Create a temporary planning agent through Hermes to draft a three-item
   morning checklist. Do not use tools or change anything.”
3. “Show the latest task agent result.”
4. “Ask that agent to shorten the checklist to two items.”
5. “List your temporary task agents.”

Harness² improves proposed research instructions using cloud inference, not
model weights. Record a research correction, then list feedback to select its
identity. `start_harness_refinement` submits those selected sanitized notes as
unverified evidence. Use `JARVIS_HARNESS_MODEL` to override the existing background
text-model route. The Live audio model is not implicitly used as the text model.

Refinement still uses independent fixed and held-out checks. It creates a
candidate and evidence, not an automatic production fix. Existing trial,
rollback and reviewed experience-publication gates remain in force. A failure
such as audio latency may be outside the research harness's editable surface;
recording it or generating instructions does not establish a repair.

For details, see [the learning guide](harness-learning.md) and
[feedback-driven refinement](mistake-refinement.md).
