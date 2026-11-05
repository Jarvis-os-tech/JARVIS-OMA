# JARVIS OS build documentation

This is the central documentation home for transforming Omarchy into the JARVIS
voice-first personal AI operating system. It consolidates build material from
`/home/g0pi/JARVIS OS` and `/home/g0pi/Projects/JARVIS-OMA`.

## Start here

- [Final product master](JARVIS_OS_FINAL_MASTER.md): product vision, architecture,
  five core pillars, build sequence, and acceptance gates. This is the active master.
- [Product master PDF](JARVIS_OS_FINAL_MASTER.pdf): existing shareable export.
- [Reference audit](JARVIS_OS_REFERENCE_AUDIT_2026-11-02.md): source context and
  implementation evidence behind the product plan.
- [OpenVoiceOS reference](OPENVOICEOS-REFERENCE.md): upstream components and
  proposed experiments for speech, wake words, skills, and events.
- [Consolidation report and catalogue](CONSOLIDATION-REPORT.md): every retained
  unique reference, cleanup counts, exceptions, and recovery archive location.

## Supporting references

- [API, CLI and connector services](CONNECTOR-SERVICES-2026-11-03.md):
  supervised API execution, CLI-Hub installation, preserved Composio connectors,
  live service readiness and verification evidence.

- [System integration audit and execution evidence](SYSTEM-INTEGRATION-AUDIT-2026-11-03.md):
  real GUI/file checks, guarded spoken results, repaired adapters, deadlines and deployment limits.

- [Complete Voice GUI design](JARVIS_VOICE_GUI_DESIGN.md): one consolidated
  design document, including the no-dock scope, visual system, widgets,
  interaction flows, architecture, delivery plan and Fury source analysis.
- [Voice GUI design package](voice-gui/README.md): supporting split documents for the voice canvas,
  native and JIT widgets, visual/motion system, interaction contracts, desktop
  handoff, storyboards, reference research, and phased acceptance plan.
  Planning/design only; no desktop activation.

- [Voice/control reliability and speed verification](VOICE-CONTROL-RELIABILITY-2026-11-02.md):
  active release, speech-turn fixes, live keyboard/selection repairs, measured timings and limits.

- [PC-default control fix and verification](PC-DEFAULT-CONTROL-FIX-2026-11-02.md):
  device selection, automatic command execution, adapter results, and deployed release.

- [Sentence-pause fix and verification](VOICE-SENTENCE-PAUSES-2026-11-02.md):
  current endpoint setting, regression evidence, and recovery details.

| Collection | Contents |
| --- | --- |
| [JARVIS OS references](references/jarvis-os/) | Voice/control guides, memory, mobile, UI, Hermes, specs, implementation plans, and verification |
| [JARVIS OMA references](references/jarvis-oma/) | Earlier architectures, feature descriptions, research, component guides, reports, and unique exported documentation |

Supporting references are organized as `implementation`, `designs`, `research`,
`evidence`, and `historical-plans`, preserving their original paths within each
source collection. Earlier masters and roadmaps are historical design inputs.
Their implementation claims and dated test results require fresh verification
before being used as current status.

## Maintenance

Keep new build documentation here. Update the final product master when product
direction changes, and link focused implementation/evidence documents from this
index or the catalogue. Keep one authoritative copy of each document.

Agent instructions, attribution, root repository entry points, dependencies,
personal memory, and runtime-consumed documentation/data retain their required
locations. The OMA generated codebase reference uses a compatibility symlink.
The installer reads its port guide from this folder and retains the installed
guide's existing location.

The [migration manifest](CONSOLIDATION-MANIFEST.json) records original source
paths, content hashes, canonical destinations, and duplicate decisions.
