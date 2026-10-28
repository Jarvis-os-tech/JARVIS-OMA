# JARVIS Voice-First OS Project Docs

This folder is the organized documentation home for building JARVIS into a personal voice-first intelligent operating system.

Current runtime: protected speech turns inside the main JARVIS service, with the JARVIS capability prompt, desktop tool registry, persistent memory, typed input, and authorized background job processing restored. Local speech admission, echo holdoff and panel controls remain active. Super+H remains the existing dictation shortcut.

## Active documents

- [Capability restoration — current runtime](CAPABILITY_RESTORE_2026-10-28.md): main project activation, restored tools/memory, tests, and remaining limitations.
- [Parallel speech streaming](PARALLEL_SPEECH_STREAMING_2026-10-28.md): independent capture/send tasks, opening-word upload, warm playback, first-chunk output and verification limits.
- [Intermittent speech detection fix](SPEECH_DETECTION_FIX_2026-10-28.md): corrected detector window, noisy-phrase continuation and measured limits.
- [Protected speech turns — audio baseline](VOICE_TURN_PROTECTION_2026-10-28.md): self-talk protection, reconnect recovery, measured quiet-room check and user-confirmed behavior.
- [GitHub voice restoration — baseline](GITHUB_VOICE_RESTORE_2026-10-28.md): restored source revision and earlier baseline; superseded behavior is explained in the protected-turn notes.
- [Earlier speech-only recovery](SPEECH_ONLY_RECOVERY_2026-10-28.md): historical reference comparison and temporary copy-launcher details; superseded by the GitHub restoration.
- [Practical build roadmap — current audit and next steps](JARVIS_OS_PRACTICAL_BUILD_ROADMAP.md): fresh test results, verified hardware, scoped solo-development estimates and week-one plan. Current execution priority takes precedence over the broader research roadmap.
- [Research and redesign roadmap — start here](JARVIS_OS_REDESIGN_ROADMAP.md): research conclusions, architecture, phased migration, dependencies, acceptance scenarios, backlog and open decisions.
- [JARVIS Personal Voice-First OS Master Specification](JARVIS_PERSONAL_VOICE_OS_MASTER.md)

The master specification contains the consolidated vision, architecture, current implementation status, security model, audio requirements, event model, autonomy policy, IoT plan, memory model, roadmap, backlog, and definition of done.

## Historical source material

The previous design documents and audit reports are preserved under [archive](archive/). They are no longer separate active specifications. The archive is retained so no research context or implementation evidence is lost.

## Scope boundary

This folder contains design and audit material, including preserved supporting report artifacts. The roadmap is not authorization to change the running desktop. The reverted integration experiment is recorded in the master; its test counts are historical.

## Working rule

Update the master whenever a roadmap item changes from planned to implemented, partial, verified, blocked, or deferred. A feature is not complete until its tests, recovery behavior, permission boundary, and evidence are recorded.
