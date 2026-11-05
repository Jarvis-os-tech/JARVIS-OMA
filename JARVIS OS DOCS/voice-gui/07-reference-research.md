# 07 — Reference research

Checked 2 November 2026. Reference scope: design and architecture preparation only; no repository was cloned, installed or executed.

## User-selected visual references

The two supplied JARVIS boards establish cyan core, dark glass cards, state storyboard, compact privacy labels and persistent desktop exit. The requested improvements are stable core placement, larger readable data, purposeful card actions and dynamic composition rather than fixed dashboard furniture.

The user identified Huw Prosser's Rose reels as the intended interaction reference:

- [Initial Rose demo](https://www.instagram.com/reel/DfGOQ5pIZqy/)
- [Rose research demo](https://www.instagram.com/reel/DfIDY9mo5Bn/)
- [Creator's repositories](https://github.com/huwprosser?tab=repositories)

Browser playback frames observed during this conversation showed a dark central Rose core and, in the research demo, a canvas with charts, text and images with a smaller corner assistant. Audio was not transcribed, exact complete timing was not measured, and the videos do not establish whether panels are generated code, composed templates or prebuilt widgets. Treat voice-driven reshaping and deep integration as the user's desired JARVIS requirements, not verified internals of Rose.

## Relevant public repositories

| Reference | Verified from public documentation | Use for JARVIS |
| --- | --- | --- |
| [jarvis-mlx README](https://github.com/huwprosser/jarvis-mlx/blob/main/README.md) | README warns that the project is outdated; describes an Apple Silicon/MLX voice stack | Historical context only; not the current Rose GUI or a Linux replacement |
| [fury-sdk README](https://github.com/huwprosser/fury-sdk/blob/main/README.md) | Python agent library with streaming, interruption, tools, and tool-emitted UI events separate from transcript deltas | Study event separation; no need to replace existing JARVIS orchestration merely to adopt the pattern |
| [fury-sdk session documentation](https://github.com/huwprosser/fury-sdk/blob/main/docs/sessions.md) | Optional session persistence separates durable messages from UI output and calls out recovery limits | Reinforces separate workspace persistence; ephemeral UI events alone cannot restore a canvas |
| [fury-sdk-js README](https://github.com/huwprosser/fury-sdk-js/blob/main/README.md) | JS/TS counterpart exposes streaming tool UI and transcript events | Optional reference for future renderer bridge; not evidence of Rose's frontend stack |

The inspected profile/listing and documents did not establish a public current Rose GUI repository. A GitHub repository search for `user:huwprosser rose` also returned no matches during this review. This is a limited finding, not a claim that none exists under another name or account. Do not label Fury as Rose's confirmed backend without direct creator documentation. Source reuse needs license verification for the exact files/revision; public visibility alone is not a reuse license. This package reuses concepts, not upstream code.

## Transferable pattern

Fury documents a tool-side emission callback with a dedicated UI event field and separate history deltas. The relevant inference for JARVIS is that tools can publish structured progress/presentation events while durable tool outcomes remain authoritative. This does not imply that the UI stream itself is permissioned, replayable, crash-safe or sufficient for generated-widget isolation. JARVIS needs its own admission, revision, evidence, persistence and capability contract.

## Official platform references

- [Quickshell PanelWindow](https://quickshell.org/docs/v0.3.0/types/Quickshell/PanelWindow/): panel anchors, focus and reserved space. Bind exact APIs to the installed version.
- [Quickshell WlrLayershell](https://quickshell.org/docs/v0.2.0/types/Quickshell.Wayland/WlrLayershell/): layer/focus identity; cited version may differ from installed runtime.
- [Qt shared security model](https://doc.qt.io/qt-6/shared-security-model.html): untrusted QML is outside the trusted application-code assumption.
- [Qt handling untrusted data](https://doc.qt.io/qt-6/untrusteddata.html): generated/network data requires validation; QML does not create separate privacy domains.
- [Hyprland dispatchers](https://wiki.hypr.land/Configuring/Basics/Dispatchers/): compositor operations are version-dependent; current docs must not be copied over an older installation untested.

## Evidence gaps to resolve during implementation

Actual deployed shell/version/config and supported assistive stack; measured playback envelope source; stream/snapshot atomicity; safe standalone preview and return path; task IDs/receipts available from existing services; native app resource readback; compositor blur/placement support; reviewed rich-renderer confinement; hardware performance budgets.

The repository's older island bridge contains checkout-specific paths and placeholder approval/agent content. Existing audio state files and legacy overlay paths differ. None should be presented as production-ready GUI integration without verification.
