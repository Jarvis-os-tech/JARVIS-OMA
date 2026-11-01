# Use Hermes native features through Jarvis

Jarvis connects to the existing Hermes gateway. Hermes remains the main orchestrator; Jarvis is also a primary orchestrator. This integration reuses Hermes's board, scheduler, skills, memory and other native capabilities. It does not create replacement implementations or copy their state into another scheduler/board.

## Voice commands

| Say to Jarvis | Path used |
|---|---|
| “Show the features available in Hermes.” | Live native toolset and command discovery |
| “Show my Hermes Kanban board.” | Native `/kanban list` handler |
| “Show my Hermes scheduled jobs.” | Native `/cron list` handler |
| “Ask Hermes to add a Kanban card called Review the mobile voice interface. Leave it unstarted.” | Hermes interprets the request and uses its native Kanban tools |
| “Ask Hermes to schedule a project summary every weekday at seven AM, Asia/Kolkata. Tell me where the result will be delivered.” | Hermes native cron tool; verify the resulting schedule and delivery target |
| “Ask Hermes to pause the project-summary schedule.” | Hermes native cron tool, using the existing job |
| “Ask Hermes to list its skills for browser automation.” | Hermes native skill discovery |
| “Ask Hermes to research this topic using its web tools.” | Hermes native web tools |
| “Ask Hermes which image-generation provider is ready.” | Hermes inspects its configured provider before any generation |

These are examples for future user requests. No example card, recurring job, notification, message or media generation was created during connection testing.

## Direct connection tools

`get_hermes_features` fetches Hermes's `tools.list` and `commands.catalog` over its authenticated local gateway. The catalog comes from the running installation; it is not a hand-maintained list of cloned capabilities.

`run_hermes_command` forwards one discovered slash-command name and its arguments to Hermes's `command.dispatch`. Hermes's command policy, permissions, installed plugins and refusal rules remain authoritative. Arguments are not passed to a shell by Jarvis. A native `send`, `prefill` or `skill` directive is an instruction for the Hermes agent path, not evidence the requested action has finished. Jarvis sends that work through `start_hermes_goal` when needed.

Natural-language requests use the same existing Hermes agent/harness and native tools. The result must establish the actual action, task name, verification and delivery target. A timed-out mutation must be inspected in Hermes before retrying; the bridge does not replay it automatically.

Scheduled work remains in Hermes's scheduler. Results may be saved locally or sent to a configured Hermes destination. Jarvis voice delivery of every future cron result is not established by creating a schedule; verify its delivery target. There is no second Jarvis cron scheduler introduced here.

## Live verification

- Native Kanban toolset enabled: 15 tools.
- Native cron toolset enabled: `cronjob_manage`.
- Direct `/kanban list` returned the existing Hermes board.
- Direct `/cron list` returned no scheduled jobs.
- Existing cards, jobs, memory and active Hermes work were preserved.

## Enabled native feature groups

This is an inventory snapshot, not proof that every external account/provider is authenticated or that every feature has been executed. GUI-only, optional, unconfigured and permission-restricted features retain Hermes's own requirements. Ask Jarvis to check a feature's current readiness before using it.

| Native group | Description | Tools |
|---|---|---|
| a2a | Plugin toolset: a2a | 5 |
| browser | Browser automation for web interaction (navigate, click, type, scroll, iframes, hold-click) | 14 |
| clarify | Ask the user clarifying questions (multiple-choice or open-ended) | 1 |
| code_execution | Run Python scripts that call tools programmatically (reduces LLM round trips) | 1 |
| computer_use | Background desktop control via cua-driver (macOS/Windows/Linux) — screenshots, mouse, keyboard, scroll, drag. Does NOT steal the user's cursor or keyboard focus. Works with any tool-capable model. | 1 |
| connections | Remote connector discovery, execution, and account authorization | 1 |
| cronjob | Cronjob management tool - create, list, update, pause, resume, remove, and trigger scheduled tasks | 1 |
| delegation | Spawn subagents with isolated context for complex subtasks | 1 |
| file | File manipulation tools: read, write, patch (with fuzzy matching), and search (content + files) | 4 |
| homeassistant | Plugin toolset: homeassistant | 4 |
| image_gen | Creative generation tools (images) | 1 |
| jarvis_orchestrator | MCP server 'jarvis_orchestrator' tools | 12 |
| kanban | Kanban multi-agent coordination — only active when the agent is spawned by the kanban dispatcher (HERMES_KANBAN_TASK env set). The dispatcher runs inside the gateway by default; see `kanban.dispatch_in_gateway` in config.yaml. Lets workers mark tasks done with structured handoffs, enter first-class review (request_review — not a block), return review changes, block for human input, heartbeat during long ops, comment on threads, attach files, and (for orchestrators) list, unblock, and fan out tasks. | 15 |
| memory | Persistent memory across sessions (personal notes + user profile) | 1 |
| omh | Plugin toolset: omh | 16 |
| project | Desktop Projects — create/switch named workspaces (GUI sessions only) | 1 |
| session_search | Search and recall past conversations with summarization | 1 |
| skills | Access, create, edit, and manage skill documents with specialized instructions and knowledge | 3 |
| spotify | Plugin toolset: spotify | 7 |
| terminal | Terminal/command execution and process management tools | 2 |
| todo | Task planning and tracking for multi-step work | 1 |
| tts | Text-to-speech: convert text to audio with Edge TTS (free), ElevenLabs, OpenAI, or xAI | 1 |
| video | Video analysis and understanding tools (opt-in, not in default toolset) | 1 |
| video_gen | Video generation tools. Single ``video_generate`` tool covers text-to-video (prompt only) and image-to-video (prompt + image_url), plus reference-to-video. Provider-specific edit/extend workflows may appear as separate tools. Configure via ``hermes tools`` → Video Generation. | 3 |
| vision | Image analysis and vision tools | 1 |
| web | Web research and content extraction tools | 2 |
| x_search | Search X (Twitter) posts and threads via xAI's built-in x_search Responses tool. Read-only public X discovery; use the xurl skill for authenticated X API reads and account actions. Available when xAI credentials are configured (SuperGrok OAuth or XAI_API_KEY). Off by default; enable in `hermes tools` → X (Twitter) Search. | 1 |

## Native feature references

- [Hermes Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
- [Hermes scheduled tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
- [Hermes slash commands](https://hermes-agent.nousresearch.com/docs/reference/slash-commands)
