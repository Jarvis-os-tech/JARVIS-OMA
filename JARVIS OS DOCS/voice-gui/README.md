# JARVIS Voice GUI — design package

Prepared: 2 November 2026 · Status: proposed design, ready for review.

**Product intent:** speak a goal, watch the workspace take shape, refine it through conversation, and move naturally between visual tools and native applications.

This package prepares the Voice GUI described in the [product master](../JARVIS_OS_FINAL_MASTER.md), especially sections 5, 6, 8, 9 and 18–21. It records the user's Rose-inspired interaction direction. It is documentation and visual design only. It does not install a shell, change bindings, launch an overlay, modify audio, or authorize implementation/deployment.

Start with the [complete single-file design](../JARVIS_VOICE_GUI_DESIGN.md). It consolidates all eight documents below and includes the user's latest no-dock correction and Fury source analysis. Treat the consolidated file as the review baseline; these split files are supporting authoring references.

## Read the package

| Document | What it settles |
| --- | --- |
| [01 — Product and experience](01-product-and-experience.md) | Scope, modes, surface routing, controls, example journeys and first-release boundary |
| [02 — Visual and motion system](02-visual-and-motion.md) | Palette, typography, geometry, responsive layout, core behaviour, accessibility and motion |
| [03 — Conversation and widget model](03-conversation-and-widgets.md) | Spoken references, selection, widget library, lifecycle, pinning, state ownership and failures |
| [04 — Architecture and UI contract](04-architecture-and-contract.md) | Integration map, proposed events, JSON examples, validation, transport, isolation and handoff |
| [05 — Delivery and acceptance](05-delivery-and-acceptance.md) | Sequenced build packets, acceptance scenarios, performance targets and rollout/return path |
| [06 — Storyboards and mockup brief](06-storyboards.md) | Reviewable screen compositions and an end-to-end research flow |
| [07 — Reference research](07-reference-research.md) | Rose reels, Huw Prosser's public projects, verified facts and unresolved details |
| [08 — Fury source analysis](08-fury-analysis.md) | Runtime/tool code, streaming UI events, interruption, persistence and JARVIS implications |

## Decisions carried forward

1. Wayland + Hyprland are the target desktop foundation; Quickshell/QML is the proposed native presentation layer.
2. Two presentation modes: compact presence and expanded voice canvas. Modes are independent of listening/thinking/executing/speaking. Per the user's correction: no application dock, launcher rail, permanent helper sidebar or docked-assistance mode.
3. Three surface tiers: standard native widgets, schema-composed JIT views, native applications. Isolated rich web views are a later optional JIT capability.
4. The canvas changes with the task. The core becomes smaller when content needs room. Follow-up speech edits existing cards rather than spawning duplicates.
5. Voice, clicks and typed requests use the same context and action authority.
6. “Return to desktop” and Escape dismiss the expanded interface. They do not cancel work or mute capture. Capture state remains visible in compact form.
7. Mute, stop speaking, cancel task, pause automation, standby and stop JARVIS are distinct controls.
8. Compact face stays battery-first: time, actual battery/charging, assistant/privacy state; no weather or microphone button. Volume/brightness sliders remain outside the expanded conversation surface.
9. Standard QML components render validated data. Generated QML never executes inside the trusted shell. A Loader is not a security boundary.
10. Pinning retains an instance. Saving a reusable widget is a separate validated operation.

## What is prepared versus what exists

The existing repository contains a voice daemon, local IPC commands, status reporting, desktop adapters, task systems, a Quickshell shell and legacy island/orbit views. Those are reuse candidates, not proof of a unified Voice GUI. This package proposes missing contracts and integration work explicitly. All timings are targets until measured.

The inspiration reels establish a desired experience. They do not prove the creator's implementation, runtime generation mechanism, microphone handling, permissions or operating-system integration. See the reference research for the limits of observation.

## Review order

Start with the storyboards, then review the experience and visual rules. Use the technical contract and acceptance plan when moving toward implementation. The detailed markdown specifications govern exact behaviour; concept artwork is illustrative, and all sample data in mockups is synthetic.
