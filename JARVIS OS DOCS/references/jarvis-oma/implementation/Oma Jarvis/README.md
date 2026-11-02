# Oma Jarvis — organized source copy

## Connector collection and completeness update — 30 October

Browse [connectors](connectors/README.md) for all connector implementations, adapters, manifests, tools and related tests together. The newer voice regression test, omitted dependency locks, and bundled upstream assets/test resources have also been added. The original domain counts below describe the earlier snapshot; additions and intentional connector duplicates are recorded separately.

- [Current coverage report](../../evidence/Oma%20Jarvis/_analysis/COPY_COVERAGE_2026-10-30.md)
- [Combined source map, including PMA voice](../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/COMPLETE_SOURCE_MAP.csv)
- [PMA voice collection](voice/pma/README.md)

This workspace groups copies of JARVIS-OMA by responsibility and feature. Original source files are byte-for-byte copies. The running project was not moved or rewritten.

**This is an organized source snapshot, not an independently runnable application.** Imports, relative paths, launch scripts and service targets still describe the original layout. No imports or behavior have been rewritten. Do not use the copied installer/launcher as a new deployment.

**Runtime check, 30 October:** the copied suite passes 1,164 tests but fails 12; six supplementary voice regression checks also fail. The organized layout has unresolved imports. See the [working-status report](../../evidence/Oma%20Jarvis/_analysis/WORKING_STATUS_2026-10-30.md) for the tested conditions and remaining work.

## Browse the code

Start with the [feature folder guide](../../evidence/Oma%20Jarvis/_analysis/FEATURE_LAYOUT.md) for the nested voice and GUI structure.

| Folder | Responsibility | Original files copied |
|---|---|---:|
| [voice](voice/README.md) | Voice capture, speech turns, interruptions, response handling, playback, latency, echo cancellation and recovery. | 77 |
| [gui_control](gui_control/README.md) | Accessibility, browser interaction, keyboard/mouse control, window recovery and verified GUI outcomes. | 19 |
| [vision](vision/README.md) | Camera and screen frames, streaming, native camera helpers and visual input. | 9 |
| [desktop_control](desktop_control/README.md) | Operating-system controls, system information, extensions and desktop environment discovery. | 25 |
| [filesystem](filesystem/README.md) | File operations and multi-step file-task execution. | 11 |
| [memory](memory/README.md) | Persistent memory implementation, retrieval, embeddings, session storage, Obsidian and standalone MCP packaging. | 101 |
| [integrations](integrations/README.md) | Google Workspace, GitHub, telephony, search and credential-store implementation (no credentials). | 30 |
| [agents](agents/README.md) | Delegation, execution backends, model routing, development jobs and harness integrations. | 40 |
| [automation](automation/README.md) | Proactive events, scheduling, planning, policy and verification. | 24 |
| [runtime](runtime/README.md) | Application entry points, IPC, workers and cross-domain service coordination. | 15 |
| [configuration](configuration/README.md) | Settings, shared prompts, environment filtering, dependency lists and configuration templates. | 12 |
| [skill_registry](skill_registry/README.md) | Skill registration, validation, dispatch, tool tiering and compatibility package markers. | 12 |
| [interface](interface/README.md) | Text input, overlay client and Orbit UI. | 11 |
| [deployment](deployment/README.md) | Copied launchers, service definitions and installation scripts. | 11 |
| [development](development/README.md) | CI, diagnostics, documentation generators and contributor templates. | 5 |
| [shared_tests](shared_tests/README.md) | Original shared test fixtures and test package markers. | 10 |
| [reference](reference/README.md) | Upstream examples, third-party source, recovery source snapshots and historical reports; not active application ownership. | 981 |
| [project_docs](project_docs/README.md) | Repository-wide design, contribution, license and metadata documents. | 34 |

## Voice features

The `voice` folder has feature folders for capture, turn detection, interruptions, fast response, first token/event processing, first speech output, response latency, playback, echo cancellation, recovery, standby, controls, greetings, diagnostics and backend implementations.

Full files that span multiple features have one canonical copy in `voice/session` or the appropriate shared backend. Feature folders contain exact `.py.txt` code extracts with line locations and dependency notes. These extracts are reading aids, not new Python modules; deliberate extract duplication is distinguished from canonical source copies.

**Timing terminology:** received audio, first write to the speaker process, and actual audible sound are different milestones. `response_first_audio_ms` starts at a recognized-input update; `first_audio_chunk_to_write_ms` measures queue-to-write delay. The code does not establish an end-to-end text-token-to-audible-speech metric.

## Maps and verification

- [Original → organized path map and hashes](../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/SOURCE_MAP.csv)
- [Dependency map and remaining mixed modules](../../evidence/Oma%20Jarvis/_analysis/DEPENDENCY_MAP.md)
- [Tool → feature → handler → system command map](../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/TOOL_OWNERSHIP.csv)
- [All Python symbols and source locations](../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/SYMBOL_INDEX.csv)
- [Feature code-extract provenance](../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_analysis/CODE_EXTRACTS.csv)
- [Copy validation and original-file checks](../../evidence/Oma%20Jarvis/_analysis/VERIFICATION.md)

## Included and excluded

Active code, tests, manifests, source documentation, build files and configuration templates are copied. Versioned third-party Artemis source and curated upstream memory examples are under `reference`; source-only voice recovery snapshots are kept there separately. Duplicate source mirrors are preserved and identified, not silently consolidated.

Live memory data, credentials, private configuration, `.git`, virtual environments, caches, compiled binaries, dependency installations, third-party scratch/traces and local runtime state are excluded. No symlink points back into the running project.

Repository instructions and original documentation are preserved as source metadata. The new source/dependency maps document this copy; the original `CODEBASE_REFERENCE.md` and its generator were not changed or run against the live checkout.

Snapshot captured (UTC): 2026-10-29T17:07:22.004248+00:00. Git HEAD: `14038166b31c6a019b1d79990174262bcd0c2dd2`. Existing uncommitted source changes are included.
