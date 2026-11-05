# Hermes as a directly callable Jarvis tool

Updated 2 November 2026. Hermes remains the main orchestrator. Jarvis can also orchestrate independently and invoke Hermes as a tool.

## What changed

Jarvis now exposes `call_hermes_api(operation, arguments, request_key)`. This is a private local integration with the installed Hermes runtime. It uses API Anything's operation-catalog, JSON Schema and `ok`/`data` conventions. Jarvis's existing API Anything tools also accept `site="hermes"`; requests stay on this machine. No browser capture, gateway-token export or public-registry publication is involved. The upstream API Anything repository was inspected, not modified.

```
Jarvis voice / desktop / mobile
  → existing UnifiedSkills registry
  → call_hermes_api (or API Anything's private hermes site)
      → cron / Kanban: installed Hermes native handlers and existing stores
      → tasks / workflows: authenticated gateway admissions + durable receipts
Hermes → existing Jarvis MCP bridge → Jarvis tools and local worker agents
```

The API adds no replacement scheduler, board, memory database or agent execution engine. General-purpose tool execution continues inside Hermes, where its approvals and provider configuration apply.

## Operations

Call `operations.list` first. Schemas are read from the installed Hermes version rather than inferred from voice commands. Availability is checked against the active gateway profile.

| Operation | Behavior |
|---|---|
| `operations.list` | Native schemas plus task/workflow operations |
| `cron.list` | Real schedules; accepts `include_disabled` |
| `cron.create` | Native schedule parsing, registration, prompt checks and delivery configuration |
| `cron.update` | Modify an existing native job |
| `cron.pause`, `cron.resume`, `cron.remove` | Native lifecycle, using discovered job identity |
| `kanban.list`, `kanban.show`, `kanban.attachments` | Native board and card reads |
| `kanban.create`, `kanban.comment`, `kanban.link` | Native cards, comments and dependencies |
| `kanban.complete`, `kanban.block`, `kanban.schedule` | Native lifecycle and goal checks |
| `kanban.request_review`, `kanban.request_changes`, `kanban.unblock` | Native review and routing |
| `features.list` | Live Hermes feature discovery |
| `tasks.start` | Any user-authorized task supported by Hermes's enabled features |
| `tasks.list`, `tasks.status` | Persisted names, state and results |
| `workflow.start` | One durable Hermes assignment containing named steps, dependencies and optional worker choices |

Immediate cron execution and Kanban file/URL attachments are deliberately left to `tasks.start` and Hermes's normal tools. Other existing Jarvis tools still expose artifact reads, cancellation, follow-up, approval responses, event replay and ownership handoff.

## Examples for Jarvis

These are natural requests; Jarvis selects the operation and keeps transport IDs internal.

- “Jarvis, show my Hermes scheduled jobs, including paused ones.”
- “Jarvis, create a Hermes reminder in ten minutes to take a break.”
- “Jarvis, schedule a daily project briefing at 9 am using Hermes, and notify me here.”
- “Jarvis, pause the daily project briefing.”
- “Jarvis, show my Hermes Kanban board.”
- “Jarvis, create a research card and a review card, with review dependent on research.”
- “Jarvis, use Hermes to ask Codex to inspect the backend and OMP to inspect the frontend in parallel, then combine their findings.”
- “Jarvis, ask Hermes which skills and tools are available.”
- “Jarvis, show the progress of my research workflow.”

Scheduling must preserve the user's timezone and delivery requirements. Native natural-language schedules use Hermes's configured timezone. Default direct-API delivery is `local`: Hermes stores results, and Jarvis's existing outbox reports completion. A saved schedule or completion notice does **not** prove that the full result was spoken. Explicit external delivery targets still require the user's request.

## API examples

```json
{"operation":"cron.create","arguments":{"name":"Daily project briefing","schedule":"every day at 9am","prompt":"Review the authorized project and summarize changes and blockers.","deliver":"local"},"request_key":"daily-project-briefing-v1"}
```

```json
{"operation":"workflow.start","arguments":{"goal":"Inspect the project and produce a reviewed report","tasks":[{"name":"Backend inspection","instruction":"Inspect the backend; report evidence without editing files.","agent":"codex"},{"name":"Frontend inspection","instruction":"Inspect the frontend; report evidence without editing files.","agent":"omp"},{"name":"Combined review","instruction":"Compare the evidence and produce one report.","depends_on":["Backend inspection","Frontend inspection"]}],"timeout_seconds":1800},"request_key":"project-inspection-v1"}
```

Existing API Anything adapter:

```json
{"site":"hermes","op":"cron.list","args":{"include_disabled":true}}
```

For writes through that adapter, put `request_key` inside `args`; it is removed before native schema validation.

## Reliability and limits

- Mutations require a stable request key. Same key and arguments return the stored receipt. Changed arguments with the same key are rejected.
- The adapter records intent before sending a native write. A lost response remains unknown; it is not sent again automatically. Inspect the native resource before deliberately creating a new request.
- Goals are durably queued instead of rejected after two active assignments. Two supervised goals execute at once, with a bound of 32 pending assignments. Deadlines include time in the queue.
- Unresolved old receipts are quarantined and remain visible. They are never replayed. Their native terminal receipts can be recovered read-only. Quarantined work may still exist in Hermes independently; the concurrency bound applies to supervised goals.
- Parallel parent delegates receive distinct native Git snapshots, including tracked edits and explicitly approved inputs. Their artifacts are reviewed and consolidated explicitly; competing writers are never placed in one workspace.
- A failed required worker prevents parent success unless an independently successful replacement has the same exact assignment.
- Workflow dependencies are validated for duplicate/missing names and cycles. Hermes owns actual step execution, worker choice, concurrency and review; this is not a second deterministic workflow scheduler.
- A command returning a native send/prefill/skill directive now becomes a durable Hermes assignment. Dispatch alone is no longer treated as execution.
- Voice disconnects do not cancel admitted goals. Native errors and unavailable providers must remain visible.
- Stable operator configuration separates task/worker state from release directories. Imported older tasks retain their original workspace and are not resubmitted or moved while running.
- Cron and Kanban management calls use native state-management handlers. Arbitrary terminal/browser/network tools are not exposed as an unrestricted direct execution endpoint.

## Verification and deployment

The active Jarvis release receives an overlay of integration files, preserving voice/device changes. `scripts/install-hermes-api.py` prepares the overlay, checks that the API is in the live tool catalog, snapshots state, and uses the existing release manager's health check and rollback. `--activate` switches releases. It never restarts Hermes or prunes previous releases.

Live evidence is recorded in `hermes-api-live-verification.json`: real cron create, duplicate suppression, update, pause, resume, list and removal. Only temporary local test jobs were used and removed. One interrupted update correctly remained unknown rather than being repeated. An uninterrupted update returned the changed native prompt preview.

The final installed-service check passed: Jarvis accepted the workflow through its private control API, Hermes delegated to Codex and OMP in distinct snapshot workspaces, both workers returned their exact expected answers with exit code zero, and Hermes completed one review continuation. Neither worker changed files. **110 regression tests passed.**

Regression checks cover write deduplication across clients, concurrent identical writes, uncertain outcomes, schema validation, workflow validation, queue order, releasing a slot, command directives, API Anything routing and read-only result recovery. Broader checks cover existing orchestration and voice-tool behavior.

Provider availability remains separate from integration readiness. Prior bounded probes verified Codex, OpenCode, OMP and Crush. Claude and Gemini probes timed out; Pi needs the user's specific local provider/model. No provider settings were changed by this work. Antigravity and unavailable external services cannot be promised merely because Hermes can discover a feature.
