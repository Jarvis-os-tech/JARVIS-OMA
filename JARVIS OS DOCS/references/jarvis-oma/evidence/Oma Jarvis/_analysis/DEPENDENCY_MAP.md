# Dependency map and remaining shared code

This map describes existing dependencies, not a completed runtime refactor. Imports inside copied code still use original module names.

## Main flow

Original launchers → runtime entry point → voice session → speech/audio backends and skills registry. The registry routes to GUI, desktop, files, memory, integrations, agents and automation. IPC and interface observe/control the runtime. Configuration and workers are shared infrastructure.

## Voice feature boundaries

| Feature | Code ownership / remaining dependency |
|---|---|
| Capture | Session capture/send methods plus native callback; shares queue, turn gate and session state |
| Interruptions | SpokenInterruption plus session/native interruption methods; shares playback generations and echo reference |
| First token/event processing | LiveVoice.handle/receive; provider-event dispatch and PCM reception are inside the shared session class |
| First speech output | DownstreamRouter and playback prepare/prime/write; the native callback is a separate output path |
| Fast response | Scheduling and warmed playback; active versus legacy caller relationships must be preserved |
| Response latency | Different observation boundaries: recognized input → received audio; opened speech → upload; queued chunk → write |
| Recovery | Connection/cache state and retry decisions; shared session lifecycle controls resume versus fresh connections |

## Modules that remain mixed

| Canonical source | Why it remains intact | Next boundary to extract in a future runnable refactor |
|---|---|---|
| `core/stable_voice.py` | Capture, playback, interruption, provider event dispatch and session lifecycle share class state | Capture source, playback sink, interruption controller, provider transport and session coordinator |
| `core/agent.py` | Legacy voice path also coordinates memory, phone, proactive work and tool services | Keep an explicit runtime parity checklist before retiring or splitting it |
| `audio/engine.py` | Locked capture/output/AEC/VAD/barge-in engine | Extensions/composition only; do not modify the protected source |
| `skills/skills.py` | Registry, schema validation and many domain handlers share state | Separate registry/policy from domain adapters using TOOL_OWNERSHIP.csv |
| `skills/system_control.py` | GUI/window/input actions and OS/device controls share helpers | Window/input service, clipboard service, audio/display/network device services |
| `core/stable_capabilities.py` | Cross-domain service startup and visual results used by voice | Capability service coordinator with explicit dependencies |
| Mixed manifests | Several manifests declare tools from more than one domain | Keep originals intact now; split declarations when the loader can consume the new schema layout |

## Cross-domain import edges

| Consumer | Dependency | Distinct file pairs |
|---|---|---|
| agents | automation | 1 |
| agents | configuration | 4 |
| agents | integrations | 1 |
| agents | memory | 1 |
| agents | runtime | 1 |
| agents | skill_registry | 3 |
| automation | runtime | 1 |
| configuration | agents | 1 |
| desktop_control | configuration | 1 |
| desktop_control | gui_control | 2 |
| desktop_control | skill_registry | 1 |
| gui_control | configuration | 2 |
| gui_control | desktop_control | 3 |
| gui_control | skill_registry | 3 |
| integrations | gui_control | 3 |
| integrations | skill_registry | 2 |
| interface | runtime | 1 |
| memory | configuration | 4 |
| runtime | configuration | 1 |
| runtime | deployment | 1 |
| runtime | skill_registry | 1 |
| runtime | voice | 3 |
| skill_registry | agents | 4 |
| skill_registry | automation | 1 |
| skill_registry | configuration | 2 |
| skill_registry | deployment | 1 |
| skill_registry | desktop_control | 5 |
| skill_registry | filesystem | 2 |
| skill_registry | gui_control | 3 |
| skill_registry | integrations | 7 |
| skill_registry | interface | 3 |
| skill_registry | memory | 2 |
| skill_registry | runtime | 1 |
| vision | voice | 1 |
| voice | agents | 1 |
| voice | automation | 2 |
| voice | configuration | 8 |
| voice | runtime | 4 |
| voice | skill_registry | 3 |
| voice | vision | 1 |

## Evidence and limitations

- SOURCE_MAP.csv maps every included source and its checksum to its canonical copy.
- IMPORT_DEPENDENCIES.json / .csv records static imports including lazy and optional imports; relative imports and known source package roots are resolved where possible.
- TOOL_OWNERSHIP.csv maps bundled declarations to registered handler names, source locations, feature owners and declared system commands. String-dispatched handlers are not mistaken for dead code.
- SYMBOL_INDEX.csv lists classes/functions/methods, original line ranges and canonical destination.
- CODE_EXTRACTS.json identifies deliberate feature extracts and their exact provenance. They are excluded from runnable source counts.
- External/stdlib/unresolved imports are labelled together rather than falsely labelled missing dependencies. Runtime reflection, subprocess command construction, callbacks and filesystem path assumptions need separate integration work.
- C/C++ and QML source/build definitions are retained. Their compilation and QML runtime import graph are not inferred from Python AST imports.
- Python import cycles in this map do not prove runtime cycles: optional/local imports and compatibility shims are included.
- Curated reference material, third-party source and recovery snapshots are not application architecture targets; their source and provenance stay under reference.

## Future independent execution checklist

Rewrite imports and package metadata inside this copy only; replace original layout-dependent resource paths; choose one entry point and service; externalize runtime data/configuration; preserve the voice lock; test feature contracts and cross-domain integration. No live service or original source needs to change to perform that later work.
