# JARVIS Voice-First OS Project Docs

This folder is the organized documentation home for building JARVIS into a personal voice-first intelligent operating system.

## Final product direction - 2 November 2026

Start with the [JARVIS OS final master](../../../../JARVIS_OS_FINAL_MASTER.md): the consolidated five-pillar blueprint for transforming normal Omarchy into a voice-first, agent-native personal AI OS. The earlier project folders and plans supply reference material. The [reference audit](../../../../JARVIS_OS_REFERENCE_AUDIT_2026-11-02.md) records the current evidence, conflicting assumptions, and remaining release blockers separately from the product goal.

Latest voice reliability follow-up: [missed speech and cut replies — 2026-10-29](VOICE_RELIABILITY_FIX_2026-10-29.md).

Latest speaker/HUD repair: [speaker continuity and listening indicator — 2026-10-29](AUDIO_OUTPUT_AND_LISTENING_FIX_2026-10-29.md).

Current runtime: protected speech turns inside the main JARVIS service, with the JARVIS capability prompt, desktop tool registry, persistent memory, typed input, and authorized background job processing restored. Local speech admission, echo holdoff and panel controls remain active. Super+H remains the existing dictation shortcut.

## Active documents

- [Verified desktop workflows](VERIFIED_DESKTOP_WORKFLOWS_2026-10-28.md): exact-target focus/workspace checks, file-content readback, bound-tab URL verification and 60 offline acceptance trials; live spoken acceptance remains pending.
- [Desktop action verification](DESKTOP_ACTION_VERIFICATION_2026-10-28.md): truthful input outcomes, clipboard/Return failure handling, startup regression verification and voice-preservation evidence.
- [Capability restoration — current runtime](../../../jarvis-os/historical-plans/project-docs/CAPABILITY_RESTORE_2026-10-28.md): main project activation, restored tools/memory, tests, and remaining limitations.
- [Parallel speech streaming](../../../jarvis-os/historical-plans/project-docs/PARALLEL_SPEECH_STREAMING_2026-10-28.md): independent capture/send tasks, opening-word upload, warm playback, first-chunk output and verification limits.
- [Intermittent speech detection fix](../../../jarvis-os/historical-plans/project-docs/SPEECH_DETECTION_FIX_2026-10-28.md): corrected detector window, noisy-phrase continuation and measured limits.
- [Protected speech turns — audio baseline](../../../jarvis-os/historical-plans/project-docs/VOICE_TURN_PROTECTION_2026-10-28.md): self-talk protection, reconnect recovery, measured quiet-room check and user-confirmed behavior.
- [GitHub voice restoration — baseline](../../../jarvis-os/historical-plans/project-docs/GITHUB_VOICE_RESTORE_2026-10-28.md): restored source revision and earlier baseline; superseded behavior is explained in the protected-turn notes.
- [Earlier speech-only recovery](../../../jarvis-os/historical-plans/project-docs/SPEECH_ONLY_RECOVERY_2026-10-28.md): historical reference comparison and temporary copy-launcher details; superseded by the GitHub restoration.
- [Practical build roadmap — current audit and next steps](JARVIS_OS_PRACTICAL_BUILD_ROADMAP.md): fresh test results, verified hardware, scoped solo-development estimates and week-one plan. Current execution priority takes precedence over the broader research roadmap.
- [Research and redesign roadmap — start here](../../../jarvis-os/historical-plans/project-docs/JARVIS_OS_REDESIGN_ROADMAP.md): research conclusions, architecture, phased migration, dependencies, acceptance scenarios, backlog and open decisions.
- [JARVIS Personal Voice-First OS Master Specification](JARVIS_PERSONAL_VOICE_OS_MASTER.md)

The earlier specification remains a reference for its consolidated requirements and historical implementation state. The final master linked above takes precedence for current product direction; dated verification records establish implementation evidence.

## Historical source material

The previous design documents and audit reports are preserved under [archive](../../../../../../Projects/JARVIS-OMA/project-docs/archive). They are no longer separate active specifications. The archive is retained so no research context or implementation evidence is lost.

## Scope boundary

This folder contains design and audit material, including preserved supporting report artifacts. The roadmap is not authorization to change the running desktop. The reverted integration experiment is recorded in the master; its test counts are historical.

## Working rule

Update the master whenever a roadmap item changes from planned to implemented, partial, verified, blocked, or deferred. A feature is not complete until its tests, recovery behavior, permission boundary, and evidence are recorded.
