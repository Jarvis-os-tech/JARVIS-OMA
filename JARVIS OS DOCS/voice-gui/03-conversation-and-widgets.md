# 03 — Conversation and widget model

Status: proposed interaction contract. Related: [architecture](04-architecture-and-contract.md).

## Independent state dimensions

Represent presentation (`compact`, `canvas`), connection (`offline`, `connecting`, `ready`, `degraded`), capture (`active`, `software_muted`, `hardware_muted`, `standby`, `stopped`), turn (`listening`, `processing`, `speaking`, `interrupted`, `waiting_clarification`) and each task's lifecycle separately. Approval is attached to a concrete action. A single state string may provide a display summary but cannot own these dimensions.

Priority for visible attention: lock/privacy restrictions; hardware capture fault; required approval/clarification; user-facing error; foreground turn; background activity. Priority chooses the label, not an implied cancellation of lower-priority work.

## Conversational reference grounding

Each surface has stable `widget_id`, `request_id`, optional `task_id`, data entity IDs, revision and user-readable title. Context may include selected entity IDs, focused card, explicitly referenced item, current app and recent card interactions. Resolve speech in this order:

1. Explicit title/entity (“the memory chart for release B”).
2. Current explicit selection (“these rows”).
3. Focused or recently interacted relevant card (“this chart”).
4. A single recent compatible result (“open that report”).
5. Ask a short clarification when multiple material targets remain.

Hover alone is weak context; a spoken destructive action cannot rely on hover. Pointers, display coordinates and titles are observations with timestamps. The user saying “second one” binds to the displayed order and revision, not the newest reordered dataset.

| Speech | Result |
| --- | --- |
| “Expand this chart” | Open detail view for resolved chart; preserve dataset and selection |
| “Compare these” | Compose a comparison from selected compatible entities |
| “Show sources” | Reveal evidence for current claim/card |
| “Only the local ones” | Apply filter to current research scope; report if “local” is ambiguous |
| “Remove that chart” | Dismiss view; retain task/evidence |
| “Cancel that research” | Cancel resolved research task, not merely its card |
| “Keep this” | Pin instance and context |
| “Save this layout for next time” | Create a reusable-template draft for validation |
| “Go back” | Navigate previous canvas view; desktop return is explicit |
| “Return to desktop” | Dismiss expanded canvas and preserve task/capture state |

Click, voice and text produce the same typed intents. Pointer selection updates conversational context; the UI does not inject whole screen contents or credentials into the model. References to source text remain data, even if the source contains commands.

## Widget anatomy

A standard card has: human-readable title; short state/stage; main data; provenance/freshness; relevant primary action; overflow menu. Task cards add elapsed time and cancellation state. Approval cards show action, exact target, relevant effect, expiry and choices. Empty states explain whether there is no data, no permission, a disconnected provider or a load failure.

Common actions: expand, select, pin/unpin, dismiss, show sources, refresh (where safe), and supported open-in-app. Dismiss never deletes evidence or cancels a task. “Open in app” appears only with a supported resource/capability. Keep primary actions sparse; metadata and diagnostics expand on demand.

## Component catalogue

| Component | Primary content | Interaction/evidence requirements |
| --- | --- | --- |
| TextBlock / KeyValueGrid / StatRow | Brief explanation, structured fields, metrics | Plain text by default; units and unknowns explicit |
| Table / Comparison | Labelled columns and stable row IDs | Sort/filter/select without reordering under a reference |
| Chart | Series, axes, units, observation time | Accessible data table; source IDs; comparable sampling intervals |
| SourceList | Titles, origin, retrieved time, claim links | Safe browser open, blocked/unreadable distinction |
| ImageGrid | Relevant images with captions/source | Approved asset references; accessible descriptions; expand |
| FileResults / DiffBlock | Paths, match snippets or revision-bound diff | Stable file identity; app handoff; truncation labelled |
| Timer / Media | Current native service state | Controls wait for actual acknowledgement |
| TaskProgress | Stage, elapsed, steps, receipts | Numeric progress only with denominator; cancellation separate |
| ChoiceList / Form | Clarification or structured input | Preserve unsaved state; validation; explicit submit |
| Approval | Held action and its scope | Bound to action digest/revision, identity, expiry, single-use decision |
| Recovery | Affected feature and next valid step | Retry only with idempotency/outcome check |
| DeviceStatus / PermissionStatus | Real health and access | Unknown/degraded visible; no invented health score |
| RichViewHost (later) | Isolated specialised interaction | Bounded data/action bridge, independent crash recovery |

Volume and brightness controls may exist in detailed system settings/standard OS control panels. Preserve their removal from the expanded assistant conversation surface. Voice commands remain available.

## Lifecycle

`requested → preparing → visible → updated → retained or eligible_for_expiry → dismissed/expired → archived`

An update preserves the identity of a card unless its purpose changes. A result replacement can reuse a slot with a new ID and explicit transition. Source-backed claims remain linked to the evidence version that produced them.

| Category | Policy |
| --- | --- |
| Brief informational chip | Eligible after 15 seconds idle; pause expiry during interaction; retained in recent activity |
| System control feedback | 5–8 seconds after acknowledged result; errors remain accessible |
| Research/chart/file result | Retain for conversation; archive after conversation ends, unless pinned/active |
| Active task | Persist until terminal outcome; dismissed view stays recoverable through activity |
| Approval or clarification | Persist until resolution/explicit expiry; expired approval becomes non-actionable |
| Unsaved form or local edits | No auto-expiry; warn on explicit discard |
| Pinned card | Survive canvas dismissal and restart within retention policy; freshness still enforced |

Interaction restarts eligible inactivity timers. Pinning does not freeze a live dataset silently: offer “Keep live” versus “Save snapshot” when that distinction matters. A snapshot stores its observation time. An offline/restored live card clearly marks its last-known data.

End-of-conversation cleanup archives eligible transient views. It never erases unsaved input, pending actions, task receipts or pinned evidence. Conversation and widget retention settings are reviewable and support deletion/export. Do not retain raw microphone audio by default.

## Ownership

| State | Owner | Restart behaviour |
| --- | --- | --- |
| Task lifecycle and effects | Task/action service | Durable recovery; never replay effects because a view reopens |
| Evidence, source records | Result/evidence store | Restore references and freshness |
| Capture and playback | Voice/audio service | Re-query actual state; never infer from old UI |
| Card specification and revision | GUI gateway/workspace store | Rebuild from validated snapshot |
| Selection, scroll and draft input | Per-widget view state | Preserve locally; persist eligible drafts under retention policy |
| Placement and pinning | Workspace manager | Restore within available monitor bounds |
| Reusable template definition | Versioned template registry | Review compatibility/capabilities before reuse |

Widgets are declarative but not literally stateless: view state must survive useful interaction. A form needs local draft state. The renderer cannot become a second owner of execution or task completion.

## Standard, composed and rich preparation

Standard widgets use known templates and actual service data. Composed JIT views select bounded components and bind them to retrieved data. The model proposes composition; the gateway validates types, assets, capabilities and size before rendering. Unsupported blocks produce a useful native fallback rather than crashing the scene.

Rich code generation is a later path. Show “Preparing custom view” only when actual preparation is running. Keep prior results visible while the new view stages. A generated component passing syntax validation is not proof of safety or correctness. Untrusted QML does not enter the main shell.

“Pin” stores the instance. “Save as reusable widget” creates a versioned draft containing schema, bindings, allowed actions, compatible data types, preview and provenance. Validate it before registration. Reuse never carries an old approval or silently grants new capabilities.

## Failure and concurrency behaviour

Network loss: local mute, exit and available task controls remain functional; provider-dependent controls identify the limitation. Duplicate events: deduplicate by event ID. Out-of-order events: revision checks and resnapshot. GUI reload: restore without replaying tool effects. Rich-renderer crash: keep native chrome and recovery control. Unsupported chart data: display a table and explanation.

The user may keep talking while tools run. Background results land in their owning task group without stealing focus or interrupting a newer request. User keyboard/pointer intervention pauses conflicting desktop automation and requires fresh observation before continuing. A valid completed result remains visible after speech interruption.
