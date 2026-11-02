# Feature folder guide

The copied code is arranged by feature. Full modules keep their original bytes. When a feature is embedded in a shared class, its folder contains a verbatim `.py.txt` extract and a `FEATURE.md` explaining the shared state and imports it still needs.

```text
Oma Jarvis/
├── voice/
│   ├── capture/                 Microphone capture and upstream delivery extracts
│   ├── turn_detection/          Speech detector and turn gate
│   ├── interruptions/           Spoken interruption, barge-in and stop handlers
│   ├── fast_response/           Scheduling, playback preparation, stall monitoring
│   ├── first_token_processing/  Provider event reception and dispatch extracts
│   ├── first_speech_output/     Downstream router, priming and first-write extracts
│   ├── response_latency/        Metrics and their actual timing boundaries
│   ├── playback/                Playback class and output enqueue extracts
│   ├── echo_cancellation/       Echo cancellation and monitor AEC implementations
│   ├── recovery/                Retry, connection and session identity state
│   ├── standby/                 Standby extension and declarations
│   ├── controls/                Mute/interrupt control extracts and tests
│   ├── greetings/               Greeting behavior and related context
│   ├── session/                 Complete stable and legacy session modules
│   ├── backends/
│   │   ├── native/              Locked engine, native backend and C/C++ sources
│   │   └── pipewire/            PipeWire backend
│   ├── extensions/              Extension interfaces and package markers
│   ├── diagnostics/             Voice and native-backend diagnostic tools
│   ├── integrity/               Original voice lock manifest/verifier/tests
│   └── docs/                    Related source documentation
├── gui_control/
│   ├── accessibility/          Complete GUI controller and registered adapters
│   ├── keyboard_and_mouse/     Exact typing/key operation extracts
│   ├── mouse/                  Click and scroll implementation extracts
│   ├── window_management/      Window/workspace operation extracts
│   ├── window_recovery/        Modal handling and focus recovery
│   ├── action_verification/    Ground-truth observations and verification wrappers
│   ├── browser/                Browser integration and interaction extracts
│   ├── clipboard/              Clipboard read/write extracts
│   └── desktop_awareness/      Awareness manifests and tests
├── vision/                     Camera, screen capture, streaming and native helper
├── desktop_control/            Audio devices, display, network, power, theme and OS controls
├── filesystem/                 File operations, task runner and compatibility
├── memory/                     Storage, retrieval, embeddings, conversation and Obsidian
├── integrations/               Google Workspace, GitHub, phone, search and credential code
├── agents/                     Delegation, execution, model routing and development
├── automation/                 Events, planning, scheduling, policy and verification
├── runtime/                    Entry points, IPC, workers and shared services
├── configuration/              Settings, prompts, security helpers and templates
├── skill_registry/             Registration, validation, dispatch and tiering
├── interface/                  Text input, overlays and Orbit UI
├── deployment/                 Copied launchers, installers and service definitions
├── development/                CI and development/documentation tools
├── shared_tests/               Original shared test fixtures
├── reference/                  Historical, upstream and third-party source
├── project_docs/               Repository-wide documents and source metadata
└── _analysis/                  Maps, provenance, dependency analysis and copy checks
```

Each area's `README.md` lists its complete source files. Feature folders use `FEATURE.md` for navigation and dependency notes. Tests and manifests sit under their related feature wherever possible.

The shared modules are preserved once as canonical files. `.py.txt` extracts intentionally repeat relevant methods for inspection; they are not importable replacements. No code has been moved out of the live project, and the reorganized copy is not yet a runnable package layout.

The first-token folder describes provider event/PCM processing. The original implementation does not supply a standalone text-token-to-audible-speech metric; the latency notes distinguish available measurements from that missing end-to-end measurement.
