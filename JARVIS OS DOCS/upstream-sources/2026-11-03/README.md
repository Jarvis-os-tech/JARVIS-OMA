# Collected upstream references for JARVIS

Collected and reviewed: 3 November 2026.

Screened the public repository inventories for **391 OpenVoiceOS repositories and 40 Huw Prosser repositories**. Downloaded **12 selected OVOS source checkouts**, retaining Git commit identities, original licenses, documentation and tests. The collection occupies approximately **29 MB** including inventories and Git data at collection time.

This is a source collection and adoption review. Metadata screening of 431 repositories is not a line-by-line audit of all their code. Source review focused on selected READMEs, dependency declarations, interfaces and critical implementation paths. Nothing here was installed into JARVIS, enabled as a service, or exercised with the microphone. No model weights were downloaded.

## What we should use

| Source collected | Useful contribution | Decision for JARVIS |
|---|---|---|
| [ovos-number-parser](ovos-number-parser/) | Spoken values, fractions, numeric spans and pronunciation | First candidate for a narrowly scoped parsing adapter. Preserve raw utterances, quoted text, IDs and paths. |
| [ovos-date-parser](ovos-date-parser/) | Dates, durations, spans and spoken time | Candidate for calendar/task input parsing after dependency isolation and timezone tests. |
| [ovos-color-parser](ovos-color-parser/) | Color names, values and spans | Optional addition for theme/widget commands; also a dependency of the typed-slots wrapper. |
| [ovos-typed-slots-transformer](ovos-typed-slots-transformer/) | Extract typed values with original text offsets rather than rewriting the utterance | Adopt the span/value contract in a JARVIS adapter; evaluate direct parser calls before importing the whole OVOS wrapper. Current source also supports language spans. |
| [ovos-plugin-manager](ovos-plugin-manager/) | Speech-provider and transformer interfaces | Reference for optional provider adapters; adding the entire plugin ecosystem is conditional. |
| [ovos-pydantic-models](ovos-pydantic-models/) | Typed event models and validation | Reference for event validation; direct dependency only for actual OVOS interoperability. |
| [ovos-dinkum-listener](ovos-dinkum-listener/) | Listening state transitions, verifier gates, endpoint policy and diagnostics | Compare individual mechanisms with current `voice_layer`; do not launch a competing capture daemon. |
| [ovoscope](ovoscope/) | Fake-bus, ordered event assertions, multi-turn and voice-loop harnesses | Reuse test methodology for JARVIS action/voice evidence; direct installation brings OVOS Core and a pytest plugin. |
| [ovos-test-harness](ovos-test-harness/) | Cross-repository conformance and compatibility testing | Reference for a JARVIS contract matrix and pinned stack verification. It tests OVOS, not JARVIS unchanged. |
| [ovos-utterance-corrections-plugin](ovos-utterance-corrections-plugin/) | Configurable name/word corrections | Candidate for explicit, scoped corrections. Whole-utterance fuzzy substitution and unrestricted regexes need changes before adoption. |
| [ovos-eot-plugin-cuelight](ovos-eot-plugin-cuelight/) | Model-based turn-end decisions | Experiment only: English-only, external model package, and an interface mismatch in this collected stack. |
| [ovos-a2a-agent-plugin](ovos-a2a-agent-plugin/) | Agent-card discovery, session/task association and remote error handling | Reference if current orchestration gains an A2A adapter. No requirement to replace Hermes or the task supervisor. |

Every collected repository contains an Apache-2.0 LICENSE at the recorded commit. Keep its license, attribution, file notices and any applicable NOTICE information with redistributed material. Dependency and model licensing remains separate.

## Findings that change the earlier shortlist

### 1. Date parsing has a material dependency footprint

The current date-parser manifest includes `ovos-config`, `ovos-spec-tools` and `chronologia`, as well as number parsing, dateparser, dateutil and sentence splitting. Its package initializer imports OVOS configuration/utilities and calendar machinery. It can be called outside the OVOS daemon, but that does not make it free of OVOS library dependencies. Evaluate in an isolated environment before adding it to JARVIS requirements.

The number parser declares its dependencies dynamically from `requirements.txt`: `quebra_frases` and `unicode-rbnf`. An empty `declared_dependencies` array in our manifest therefore does not mean it has no dependencies. The color parser likewise declares `ovos-utils` and `rapidfuzz` through its requirements file.

### 2. Typed spans are more useful than global transcript replacement

The transformer returns values alongside `[start, end]` offsets and the original surface text. This lets JARVIS parse “forty percent” for a control field while preserving exactly what the user asked. Its source distinguishes five types, including language; its README/description still lists four in places. It does not yet compute location/timezone slots. Missing results can also mean a missing or failed parser, so JARVIS should retain that diagnostic distinction in its own adapter.

### 3. The turn detector is not compatible with the collected manager as-is

`ovos-eot-plugin-cuelight` imports `EndOfTurnEngine` and `EndOfTurnDecision` from `ovos_plugin_manager.templates.eot`. That module is absent from the collected plugin-manager commit, although its declared version is 3.1.0a1 and the plugin only asks for >=3.0.0a1. This is a concrete source-level compatibility gap; package version constraints alone do not establish a working combination.

The detector also loads external CueLight weights and its documentation describes English-only support. Its quoted size and CPU timings are upstream claims, not JARVIS measurements. Retain it for an isolated recorded-audio experiment after resolving its required interface; do not wire it into the active voice loop now.

### 4. Corrections need bounded execution and scope

The corrections implementation catches `TimeoutError`, but the inspected regex substitution call does not supply a timeout. Its timeout test mocks an exception during compilation; it does not demonstrate a bound on a pathological substitution. Whole-utterance fuzzy replacements can substantially change intent. For JARVIS, prefer explicit vocabulary corrections, preserve the original transcript and correction provenance, exclude quoted payloads, and impose a real execution bound on any regex path.

### 5. Evaluation tools are useful references, not drop-in JARVIS tests

OvoScope loads OVOS Core and auto-registers a pytest plugin. The conformance harness assembles an OVOS stack. Keep their useful event-sequence, fake transport, cancellation and compatibility checks, while implementing corresponding assertions around JARVIS's own contracts.

The broader inventory also exposed [ovos-plugin-arena](https://github.com/OpenVoiceOS/ovos-plugin-arena). Its README explicitly labels leaderboard/rating/vote data as placeholders while the platform is in development. Its benchmark organization is a reference; its rankings are not evidence for selecting our providers.

## Huw Prosser: retained references

Fury remains valuable for separating tool lifecycle/UI updates from model-visible history, explicitly choosing partial-turn behavior, and separating persistence from context trimming. Existing local detail is in [the Fury analysis](../../voice-gui/08-fury-analysis.md). The pinned upstream references are recorded in [huw-reference-pins.json](huw-reference-pins.json).

- [Fury Python](https://github.com/huwprosser/fury-sdk): independently implement the event and session concepts against existing JARVIS components. Its inspected root/package metadata did not establish a reuse license.
- [Fury JS/TS](https://github.com/huwprosser/fury-sdk-js): conditional reference if a web renderer needs an agent client; not a current requirement for Quickshell.
- [Spotify CLI](https://github.com/huwprosser/spotify-cli): existing JARVIS Composio Spotify coverage must be compared first. OAuth and reuse licensing remain open. No CLI was installed.
- [jarvis-mlx](https://github.com/huwprosser/jarvis-mlx): outdated Apple Silicon example, excluded from Linux runtime adoption.

Other projects and forks were screened for relevance in the inventory. No public current Rose GUI source was established by this review. No unrelated face-recognition, Unity, WebXR, clap-detection or alternative model-training stacks were imported.

## Collection records and verification

- [manifest.json](manifest.json): exact source commits, license hashes, dependencies and aggregate tracked-content hashes.
- [repository-screening.json](repository-screening.json): a decision and rationale for every one of the 431 repository inventory entries. These decisions are metadata triage; unselected implementations were not all audited.
- [inventory/](inventory/): original public GitHub API responses, including archive flags, detected licenses and default branches.
- [verify_collection.py](verify_collection.py): read-only verifier. Checks the 12 exact commits, clean source trees, license presence, inventory counts, hashes and Python syntax without importing upstream packages.

Initial verification passed for **12 source trees, 1,648 tracked files and 863 Python files parsed**. This establishes collection integrity and syntax on the reviewing interpreter, not runtime behavior, compatibility, acoustic performance or security certification.

The source repositories are intentionally ignored by the parent Git repository to avoid accidentally staging embedded repositories. They remain available locally in this folder. The manifest, review and inventory can be versioned separately; the SHA pins identify what to retrieve on another machine. This is not a complete offline dependency bundle.

## Adoption sequence

1. Add an isolated parser experiment using the pinned number/date sources; test exact values, ambiguity, multiple values, unsupported languages, quotes/paths, and timezone anchors against current JARVIS behavior.
2. Apply the typed-value/provenance contract to a bounded JARVIS adapter where it improves actual commands.
3. Extend current contract tests with ordered tool/UI/transcript events, interruption, cancellation, restart and worker failure using the collected evaluation patterns.
4. Add a reviewed corrections configuration only where actual recordings establish repeatable recognition errors.
5. Resolve and benchmark endpoint/provider experiments separately. Add A2A only for a concrete worker integration.

Collection is complete; runtime adoption remains a separate implementation step with focused acceptance evidence.
