# Visible desktop delegation

Claude Code uses the existing OmniRoute connection with an explicit model:
`task_type: coding` (default) selects `auto/best-coding`, `reasoning` selects
`auto/best-reasoning`, and `fast` selects `auto/best-fast`. JARVIS should choose
the task type when delegating: implementation and fixes are coding, analysis and
planning are reasoning, and simple greetings or short responses are fast.
The selected model is included in job status. Existing open sessions retain
their model; this selection applies to newly delegated sessions.

JARVIS's `delegate_agent` voice skill now uses a visible terminal session for
Codex and Claude Code. `tmux` and `xdg-terminal-exec` must be installed in the
graphical session. Each job gets an isolated pane on the `jarvis-desktop` tmux
socket and starts in the requested workspace. JARVIS waits for the interactive
composer, inserts the task using bracketed paste, and sends Enter. It captures
the pane every half second for `check_agent_job`, applying the existing secret
redaction and output bounds.

Codex uses its installed `--approve-for-me` automatic review mode with the
workspace-write sandbox; Claude uses `--permission-mode auto`. These are native
approval decisions, not unconditional clicks on every confirmation. Login,
workspace trust, unsupported approval prompts, and quota failures may require
the user to interact in the visible terminal. JARVIS does not infer permission
from arbitrary text printed by an agent.

An interactive agent may stay open after answering. `running` means the session
is alive, not that the task is verified or still processing. `submission_state`
distinguishes waiting for the composer from a submitted task. Process exit is
reported through the existing completion event queue. Cancellation and timeout
kill only the owned session; file changes remain. Completed sessions remain
visible so their output can be reviewed.

OpenCode, Gemini, Hermes, and OMP use the existing supervised CLI runner. Their
jobs run in the background with bounded output, cancellation, timeouts, and
process completion events. Each CLI applies its own native permissions. Discovery
reports `visible_supported` and `background_supported` for each agent; only
installed commands can be delegated. Native desktop application input remains
unimplemented. The standalone HTML dashboard is unrelated to this execution path.
