# 01 — Product and experience

Status: proposed, 2 November 2026. Parent: [product master](../JARVIS_OS_FINAL_MASTER.md).

## Product promise

JARVIS turns a spoken goal into a visible, useful workspace. The interface chooses when a sentence is enough, when a control or card would help, and when a full application is appropriate. The user can keep speaking while work continues, interrupt the response, manipulate a result with the pointer, and return to the desktop immediately.

Success means finishing a real work session mainly through conversation while understanding the computer's actions. A glowing assistant with disconnected decorative panels does not satisfy this promise.

## Presentation modes

| Mode | Entry | Layout | Focus and background | Exit |
| --- | --- | --- | --- | --- |
| Compact presence | Login, explicit collapse, app handoff | Top-centre pill | No dimming; no keyboard grab; applications remain interactive | Explicit expand |
| Expanded voice canvas | Deliberate island activation, chosen shortcut or “open voice workspace” | Core/conversation header and adaptive cards | Dim only the chosen monitor; keyboard focus only following explicit activation/interaction | Always-visible Return to desktop, Escape or repeat activation shortcut |

Wake phrase activation starts a conversation in the current presentation mode. It does not automatically cover the screen. A user preference may opt into expansion on wake. A spoken request to show a large comparison may open the canvas without grabbing application keyboard focus; clicking or explicitly activating the canvas grants focus. The visible Return button remains operable in either case.

Escape dismisses a local popup first; the persistent Return control always dismisses the entire expanded canvas in one action. A configured emergency return shortcut bypasses popup and widget focus. No shortcut is installed by this design package. Super+H remains the existing dictation shortcut.

Returning to desktop preserves ongoing task IDs, widget identities, scroll, selections and unsaved input. Compact form accurately indicates whether capture remains active. Returning is not a privacy operation; mute or standby is separately available.

## Surface selection

| Need | Default surface | Escalation |
| --- | --- | --- |
| Simple fact or acknowledgement | Brief speech and optional transcript | Source/result card when useful |
| Recurring control or stable data | Standard native widget | Settings/app for detailed adjustment |
| Comparison, research, file search, task-specific explanation | JIT composition from approved components | Expanded table/chart, then application |
| Sustained editing, large documents, development, media production | Native app | Retain voice context in compact presence; reopen canvas on request |
| Special visual interaction absent from approved library | Explain/offer available representation first | Later isolated rich renderer, or native app |

The router considers explicit user choice first, then active app/context, task shape, interaction depth, available components and display room. It selects a meaningful surface rather than scoring “lightness” by appearance alone. A visible action does not gain additional execution permissions. The voice canvas contains only relevant conversation, task widgets and necessary controls. Application launchers, a desktop dock, fixed helper sidebars and unrelated dashboard widgets are excluded.

## The core's role

The core is the conversation's anchor. At rest it fits in the compact island. During a focused exchange it expands into the upper-centre header. When research and tools fill the canvas, it shrinks into a fixed header position while cards receive the space. It does not jump to a different location every time speech starts.

Listening, thinking, executing, verifying and speaking can overlap. The voice core shows the current audio/turn state. Task cards show independent execution state. A “Speaking” core can coexist with a “Researching” task card; the system does not pretend that all work has stopped.

## Always-understandable controls

| Control | Effect | Confirmation shown |
| --- | --- | --- |
| Return to desktop | Hide expanded canvas, preserve work and capture state | Compact presence with accurate privacy label |
| Stop speaking | Flush current playback; invalidate old queued narration | “Speech stopped”; task remains visible |
| Cancel this task | Request cancellation of that task and owned workers | “Cancelling”, then cancelled/partial/failed-to-stop receipt |
| Pause automation | Pause conflicting desktop automation at a safe boundary | “Automation paused”; resume after fresh observation |
| Mute microphone | Stop configured capture/transmission | Wait for acknowledged actual state; recover by pointer/keyboard |
| Standby | End active provider session as configured; keep local wake detection if enabled | “Wake-word only” only when confirmed |
| Stop JARVIS | Stop the defined JARVIS service scope | Explicit service and continuing-task information |

The legacy `listen cancel` command may combine speech interruption and cancellation. It must not back a control labelled only “Stop speaking”. See integration gaps.

## Core journeys

### Research workspace

“Compare the last three releases using their memory measurements.” JARVIS resolves the project/release scope and shows a stage only when work starts. As verified data arrives, a comparison table and chart appear with units, dates and sources. “Only show idle memory” changes the existing dataset/filter. “Explain the spike in the second release” selects that release, adds evidence and speaks a short explanation. “Open its log” focuses a supported viewer and collapses the canvas after successful handoff.

### Desktop control

“Set a ten-minute timer.” JARVIS confirms the timer through voice. When the canvas is open, the standard timer card appears there; compact mode can show a brief timer activity indicator. “Add two minutes” updates the same timer if it is the unique salient target. With multiple timers, JARVIS names the candidate timers and asks. The timer continues after its card is dismissed and after the GUI reloads.

### Visual follow-up

The user selects rows in a comparison, then says “chart just these.” Selection IDs and widget revision identify exactly those rows. A new chart is bound to the selection and evidence. Pointer edits are acknowledged without speaking every click. If the selection changed during processing, the action is revalidated.

### Native editing

“Open this diff in VS Code.” The broker resolves the retained file/diff identity, current revision, workspace and supported editor capability. It opens/focuses the actual matching window and checks the outcome. On success the canvas collapses. On failure the card stays visible with the error and alternative action.

### Interruption and correction

“Research these options.” While JARVIS answers: “Wait, only the local options.” Old speech stops; new input retains its opening words. Completed retrieval is reused where relevant. A new request generation updates the research scope without silently repeating completed side effects.

## Supporting surfaces

Activity/history lists tasks, conversations, results and continuing work. Settings holds voice selection, activation preferences, privacy, screen-awareness consent, devices, motion, contrast and detailed system controls. A recovery surface identifies affected features and valid next actions. Technical logs stay in diagnostics rather than occupying ordinary cards.

## First release and later depth

First release: reliable compact/canvas mode switching; real state and privacy; text fallback; transcript; standard timer/media/task/file/source widgets; table/chart JIT composition; voice references; selection feedback; pin/dismiss/restore; verified browser/editor/file-manager handoff; reconnect and local controls.

Later: isolated custom web tools, reviewed reusable templates, complex workflow builders, richer screen-context placement, cross-device canvas continuation and additional languages. Native applications remain available throughout.

All features require support discovery. A requested custom view can fail gracefully into an approved table, report or app. The UI does not advertise capabilities just because a mockup includes them.
