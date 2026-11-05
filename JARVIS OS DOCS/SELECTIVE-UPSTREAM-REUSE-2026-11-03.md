# Useful upstream components for JARVIS

Reviewed: 3 November 2026. Scope: select useful capabilities from [OpenVoiceOS](https://github.com/OpenVoiceOS) and [Huw Prosser](https://github.com/huwprosser). These are adoption recommendations based on public documentation and selected source inspection, not verified integrations. No packages, models or services were installed. No upstream implementation was copied.

Follow-up: the user subsequently authorized collection. [The completed collection and source review](upstream-sources/2026-11-03/README.md) screens 431 repository entries and retains 12 licensed OVOS checkouts with exact commit pins. It supersedes the initial dependency assumptions below: current date parsing carries OVOS library dependencies, and the current turn-detector/plugin-manager snapshots have an interface gap. No collected source was activated in JARVIS.

## First selections

| Selection | What to take | JARVIS destination | First proof |
|---|---|---|---|
| [ovos-number-parser](https://github.com/OpenVoiceOS/ovos-number-parser) | Standalone spoken-number extraction and number pronunciation | Narrow optional adapter in `jarvis_control/nlu.py`, or shared text normalization | Correctly interpret volume/brightness values, fractions and multiple-number utterances without rewriting IDs, file paths or quoted text. |
| [ovos-date-parser](https://github.com/OpenVoiceOS/ovos-date-parser) | Date/time/duration extraction and speech formatting | Existing calendar/task interfaces through a shared parsing adapter | Resolve relative dates against an explicit Asia/Kolkata reference time; preserve ambiguity and verify the resolved timestamp before scheduling. Parsing itself does not create a task. |
| [Fury stream event structure](https://github.com/huwprosser/fury-sdk/blob/main/src/fury/types.py) | Separate user-visible text, tool lifecycle, tool UI and transcript records | Existing widget/backend and task event contracts | A running tool updates its card; its completion receipt and transcript retain the same action identity; stale events cannot overwrite a newer turn. Adopt the structure concept without copying source pending license clarification. |
| [Fury interruption](https://github.com/huwprosser/fury-sdk/blob/main/docs/interruption.md) | Explicit distinction between retaining an interrupted partial reply and discarding cancelled text | `voice_layer` turn/session policy | Interruption and cancellation have defined history outcomes; neither silently rolls back a completed tool action. Generated text is not automatically proof of what was audible. |
| [Fury sessions](https://github.com/huwprosser/fury-sdk/blob/main/docs/sessions.md) | Separate append-only conversation records, bounded context and custom UI/application state | Existing memory/session and task records | Restart reconstructs an accurate conversation and separately restores workspace state, without repeating side effects. Keep existing durable storage unless a comparison justifies replacement. |

The two OVOS parsers document standalone use without the assistant daemon. The number-parser README and OVOS plugin-manager/models repository pages identify Apache-2.0 licensing. Check the exact package revision and its notices before code redistribution; review date-parser and model licenses separately.

## Conditional selections

| Candidate | Useful part | Selection condition |
|---|---|---|
| [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager) | Speech-provider discovery and interfaces for STT, TTS, wake words and VAD | Add a narrow adapter only when at least one provider offers a demonstrated benefit over current integrations. Keep explicit provider configuration and cancellation. |
| [ovos-pydantic-models](https://github.com/OpenVoiceOS/ovos-pydantic-models) | Validated OVOS event schemas | Use if exchanging events with an OVOS component; study the typed-event approach for JARVIS. Do not impose the entire OVOS event vocabulary on unrelated components. |
| [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) | Wake/follow-up listening states, VAD thresholds, false-wake verification and diagnostic recordings | Study individual mechanisms; preserve one owner of the microphone. Its continuous/hybrid modes are documented as experimental. |
| [ovos-stt-plugin-vosk](https://github.com/OpenVoiceOS/ovos-stt-plugin-vosk) | Local batch and streaming recognition adapter | JARVIS already pins Vosk in `requirements.txt`; use only if the OVOS wrapper adds a measurable requirement. Test existing Vosk first. Preload local models before an offline test. |
| [spotify-cli](https://github.com/huwprosser/spotify-cli) | Search, playback commands and player status | JARVIS already names Spotify in Composio. Compare existing coverage first. The CLI requires a developer app and OAuth; license clearance and command-result verification remain open. |
| [fury-sdk-js](https://github.com/huwprosser/fury-sdk-js) | JS/TS counterpart to Fury's event interfaces | Reconsider if a web renderer needs it; current Quickshell/Python components do not establish a need for another agent runtime. This review did not freshly audit its implementation. |

## Exclude from the initial adoption set

- **The full OVOS runtime, installer, core and message bus:** these duplicate responsibilities already present in JARVIS. Revisit a compatibility bridge only for a specifically selected OVOS skill.
- **The old [OVOS Piper plugin](https://github.com/OpenVoiceOS/ovos-tts-plugin-piper):** its README says it is archived and redirects to [phoonnx](https://github.com/TigreGotico/phoonnx). That successor is outside the two requested accounts and was not assessed here. This is a migration note, not approval to install it.
- **[jarvis-mlx](https://github.com/huwprosser/jarvis-mlx):** the README calls it outdated and targets Apple Silicon/MLX. It is historical interaction/architecture reference, not a direct Linux runtime candidate.
- **Clap detection, face recognition, image clustering, browser Whisper demos and unrelated forks:** no current JARVIS gap in this request justifies importing them. Current voice/VAD/vision paths should be measured first.
- **A supposed public Rose GUI:** the inspected profile and repository listing do not establish its source location or confirm Fury as its backend. Do not describe Fury as that implementation.

## License and implementation status

The inspected Fury repository root listing has no LICENSE file, and its `pyproject.toml` has no license declaration. The inspected Spotify CLI root listing also has no LICENSE file. This is an unresolved reuse permission question, not a legal determination about every file or distribution. Retain links and independently express the interface ideas; do not vendor these implementations on the assumption that public GitHub access grants a reuse license.

Fury's own session documentation identifies useful limits: one writer per session, unfinished tool-call/result pairs need application recovery, successful JSONL writes are not fsynced, and uncertain writes should not be retried blindly. Its example storage should not replace JARVIS's existing ledger merely for feature parity.

Recommended sequence: validate the number/date parsers against current behavior; tighten existing UI/tool/transcript event contracts using Fury's separation; then evaluate one specific missing speech provider. Spotify remains a bounded media extension if current connector coverage is insufficient.

## Existing local references

- [OpenVoiceOS architecture review](OPENVOICEOS-REFERENCE.md)
- [Fury source analysis](voice-gui/08-fury-analysis.md)
- [Rose/Huw reference research](voice-gui/07-reference-research.md)
- [20-post capability synthesis](INSTAGRAM-CAPABILITY-SYNTHESIS-2026-11-03.md)

## Inspection sources

Reviewed the profile listings, selected repository READMEs, Fury `src/fury/types.py`, `docs/interruption.md`, `docs/sessions.md`, `pyproject.toml`, and root contents for Fury and Spotify CLI. README branches were `dev` for the inspected OVOS projects and `main` for Huw's projects. Mutable branch URLs identify the review sources but are not reproducible dependency pins. Pin commits and inspect dependencies before implementation.
