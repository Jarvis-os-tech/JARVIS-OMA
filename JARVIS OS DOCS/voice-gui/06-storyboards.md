# 06 — Storyboards and mockup brief

Status: reviewable design scenes. All measurements, results and durations in illustrations are synthetic examples.

## Central visual rule

The assistant opens the conversation; the content takes over the workspace. The core stays in the header's spatial family as it shrinks. A new spoken turn does not clear the canvas or relocate every existing result. There is no application dock, launcher rail or docked helper mode. A small task is answered through voice/compact activity until the user opens the canvas.

## Five-state board

1. **Compact:** Recognisable app windows and wallpaper. Top-centre frosted pill: cyan 12px core, “Wake-word only”, time, real/fixture-labelled battery. No full-screen overlay or dimming.
2. **Listening:** Explicitly expanded canvas on one monitor. Cyan 96px soft core in upper-centre, transcript below: “Compare the last three releases.” Streaming words differentiated. Return pill top-right. No new task cards until useful content exists; earlier retained cards may remain.
3. **Thinking:** Same canvas/header anchor. Core gathers into a 72px slow flowing shape; final transcript reduces prominence. Stage says “Reading benchmark reports” only if that operation is underway. Prior content remains. No fake percentage.
4. **Executing:** Header compacts, 48px core. Cards show a comparison table, labelled memory chart and source list. One progress card shows “Reading report 2 of 3” only with measured report count. Content has room and consistent alignment.
5. **Speaking:** Same multi-card layout and small workspace core with playback-linked activity. Short response: “Release B used the most idle memory in these measurements.” Stop speaking nearby. Sources, selections and scroll stay intact. Do not enlarge the core enough to move all cards.

This deliberately improves the earlier reference image where core locations drift across states and the table becomes too small to read.

## Main workspace composition

```text
┌─────────────────────────────────────────────────────────────────────┐
│ JARVIS   ◉ Speaking       Research: release memory    Return / Esc  │
│ Brief response with a visible source affordance    Stop speaking    │
├─────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────┐ ┌────────────────────────────────┐ │
│ │ Idle memory comparison       │ │ Evidence                       │ │
│ │ readable chart + units       │ │ Report A · observation time     │ │
│ │ selectable release series    │ │ Report B · observation time     │ │
│ │ illustrative data label      │ │ Report C · observation time     │ │
│ └──────────────────────────────┘ └────────────────────────────────┘ │
│ ┌──────────────────────────────┐ ┌────────────────────────────────┐ │
│ │ Release table                │ │ Selected release B             │ │
│ │ A / B / C; measured values   │ │ relevant result + explanation  │ │
│ │ Chart selected · Expand      │ │ Open report · Pin              │ │
│ └──────────────────────────────┘ └────────────────────────────────┘ │
│ Ask a follow-up…                                            Send   │
└─────────────────────────────────────────────────────────────────────┘
```

The canvas is grouped by request/task, not by an arbitrary permanent dashboard. A new request can add a second group while keeping the first resumable. Background completions do not become the foreground group without user intent.

## Three-tier board

| Scene | Composition | What reviewer should understand |
| --- | --- | --- |
| Standard widget | Voice canvas with a relevant timer card and compact conversation header | Routine controls use the same voice canvas without unrelated UI |
| Composed JIT | Expanded canvas with chart/table/source cards; one stable preparing-view slot | Custom arrangement from current request; progressive results |
| Native handoff | Editor/browser now foreground; same report/diff open; compact island only | Work context crosses the boundary; voice remains available |

Preparing-view state precedes the ready state in the storyboard; do not show a skeleton as proof that code is compiling. Stage text identifies whether data retrieval, view composition or isolated rendering is actually underway.

## End-to-end scenario

| Step | User | JARVIS and canvas |
| --- | --- | --- |
| 1 | “Compare memory use across my last three releases.” | Resolve project/release scope; acknowledge; start real retrieval |
| 2 | Waits | Task stage and elapsed; first sources appear progressively |
| 3 | Receives result | Chart + table + evidence, core shrinks; short spoken summary |
| 4 | Selects A and C, says “chart only these” | Selection IDs bind existing chart filter; preserve source links |
| 5 | “Add the frame-drop data.” | Add a second labelled plot with its own units; avoid misleading dual-axis scales |
| 6 | “Why was B worse?” | Resolve B from retained full dataset, reveal source-backed detail; distinguish correlation from cause |
| 7 | “Keep this comparison.” | Pin instance, choose live versus snapshot if relevant |
| 8 | “Open B's report in the browser.” | Resolve report; verify actual page/window; collapse canvas on success |
| 9 | “Show the comparison again.” | Restore pinned group, position, selection and freshness |

## Additional required scenes

- Muted, hardware-muted, standby, connecting, offline and stale privacy/readiness labels.
- Clarification between two matching cards or projects.
- Approval with exact action/target/effect and expired state.
- Task cancellation with partial completion evidence.
- Rich-view failure with native recovery frame and usable Return button.
- Native app in use: compact status only until the user deliberately opens the voice canvas.
- High contrast, reduced motion and 200% text layout.
- Monitor unplug and locked-session restoration.

## Mockup generation brief

Use-case: high-fidelity UI mockup, not a photograph of a monitor. JARVIS spelling exact. Cyan accent, slate glass, clear white/muted typography, consistent 20px cards, restrained core. Reference display is 16:9; maintain believable desktop proportions. Include a clearly visible Return to desktop / Esc control in expanded views. No application dock, launcher rail, permanent sidebar, attached helper cards or unrelated dashboard widgets. Avoid decorative code, indecipherable tiny tables, invented telemetry, floating approval popups unrelated to the request, or a giant orb that crowds out results.

Generated raster artwork illustrates composition and materials. Exact interaction, accessibility and contract rules come from this package. It is not a running desktop or proof of implementation.
