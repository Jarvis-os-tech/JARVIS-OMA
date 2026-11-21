# Project lessons

## 2026-11-04 — Keep memory layers and vault organization distinct from inferred knowledge

Outcome: installed a six-layer memory manager, typed user memories, scoped recall/replacement/forgetting, dated event and procedure records, and a separate organized Obsidian vault. Preserved 2,530 conversation messages and 334 historical agent notes. Removed 2,184 generated topic notes from the active vault by replacing the legacy export with six numbered sections; a repeat sync created no changes and all managed links resolved. Previous vault folders and generated clutter were moved to Trash, with database/configuration backups retained.

Lesson: conversation history, user instructions, current facts, procedures and shared-agent proposals need separate authority and lifecycle rules. Do not fabricate personal facts to fill empty folders or claim user-described procedures are verified. Keep ephemeral working context out of the vault. Fix the exporter as well as the files so cleanup persists. Preserve a deliberately stopped voice service during an offline-certified release update.

Sources: `docs/organized-memory-system.md`, `jarvis_memory/manager.py`, `jarvis_memory/categories.py`, `jarvis_memory/vault_layout.py`, `tests/test_memory/test_organized_memory.py`. Installed checks: 172 memory tests plus 81 subtests and 167 required behavior checks. Voice endpoint/microphone acceptance remains unclaimed while the service is stopped.

## 2026-11-04 — Evaluate memory ranking without confusing fixtures with model quality

Outcome: built an isolated synthetic evaluation of lexical, vector, weighted and RRF retrieval with 16 query probes and nine passing lifecycle checks. Fixed-vector hybrid and RRF rankings tied; project-scoped entries could enter general recall, and no-answer probes returned topical passages. Read-only runtime status showed lexical retrieval active, semantic embeddings disabled, structured capture enabled and model extraction stopped. No live memories, retrieval configuration or UI were changed.

Lesson: evaluate answerable recall, forbidden-state leakage and answerability separately. A nonempty related passage is not evidence of an answer. Report fixed-vector experiments as ranking/integration probes, not embedding-model accuracy. Freeze a compatible baseline that records existing failures and detects new regressions; do not promote RRF merely because it is fashionable.

Sources: `docs/memory-quality-evaluation.md`, `jarvis_memory/evaluation.py`, `tests/fixtures/memory_quality/cases.json`, `JARVIS OS DOCS/MEMORY-QUALITY-EVIDENCE-2026-11-04.json`, `JARVIS OS DOCS/MEMORY-QUALITY-RUNTIME-STATUS-2026-11-04.json`.

## 2026-11-04 — Keep provider failures visible but silent

Outcome: journal correlation showed that the apparent second voice during Gemini failures was JARVIS's cached `reply_unavailable.pcm` fallback, not the system healer. Seven fallback clips were queued between 08:59:41 and 09:02:42 while the live session repeatedly failed its opening handshake. The shared reply-notice gate now suppresses both waiting and unavailable recordings while retaining `last_error`, status and journal evidence. Forty focused voice checks passed, and the restarted service reconnected to Gemini with microphone input available.

Lesson: failure reporting should not introduce a second voice that can overlap a recovering live provider. Keep transport failures observable in the UI and logs; reserve speech for the authoritative conversational response.

Sources: `voice_layer/daemon.py`, `tests/test_reply_guard.py`, user journal for `jarvis-voice.service` on 2026-11-04 08:59–09:09 IST.

## 2026-11-04 — Verify floating task cards through the compositor

Outcome: deployed the task-event release after 148 installed-environment checks. The shell required a restart to load the changed plugin after rescans kept serving its prior handler. A live temporary-file task produced a verified completed card, and the compositor reported visible floating widget layers. The test card and file were removed; the voice connection and previous system microphone mute were verified.

Lesson: a hidden main canvas does not mean floating cards are absent. Check the actual presentation surface, and wait for the replacement audio source before restoring its mute setting after a voice restart.

Sources: `scripts/prepare_task_events_release.py`, `scripts/deploy_task_events_release.py`, `JARVIS OS DOCS/TASK-EVENTS-DEPLOYMENT-2026-11-04.json`, `JARVIS OS DOCS/TASK-EVENTS-LIVE-CHECK-2026-11-04.json`.

## 2026-11-03 — Verify convergence reports against authoritative source paths

Outcome: review of the supplied dual-codebase report found current-source mismatches: the active JARVIS OS checkout already has the Island UI and PipeWire WebRTC AEC; OMA's native WebRTC wrapper enables gain while explicitly disabling AEC; current memory fusion uses a weighted blend; model-backed fact extraction already exists.

Lesson: before planning a package import or framework replacement, inspect the current entry point, implementation and configuration path. Track source presence, configured use, tested behavior and installed readiness separately. Compare improvements on the same held-out task set.

Sources: `ui/omarchy-jarvis-island/Island.qml`, `bin/jarvis-voice`, `voice_layer/echo.py`, `jarvis_memory/hybrid.py`, `jarvis_memory/extractor.py`, `jarvis_memory/bridge.py`; `/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native/webrtc_gain.cpp`; [analysis](../JARVIS%20OS%20DOCS/INSTAGRAM-CAPABILITY-SYNTHESIS-2026-11-03.md).

Capture note: the requested `capture-learning` skill was not found in the available skill catalog or searched project paths. This dated, sourced entry records the outcome directly; no runtime learning rules were activated.

## 2026-11-03 — Select upstream mechanisms against existing capabilities

Outcome: the OpenVoiceOS/Huw Prosser review selected standalone number/date parsing and Fury's separated UI/tool/transcript, interruption and session concepts. Existing Vosk and Spotify connector references mean those upstream wrappers need a specific demonstrated gap. The old OVOS Piper plugin redirects to a successor; jarvis-mlx declares itself outdated and Apple-specific. Fury and Spotify CLI root listings did not establish a reuse license.

Lesson: check the current upstream README, dependency overlap, platform fit and licensing before importing an appealing assistant stack. Preserve source links and distinguish interface concepts from code approved for reuse.

Sources: [selection record](../JARVIS%20OS%20DOCS/SELECTIVE-UPSTREAM-REUSE-2026-11-03.md), [Piper migration](https://github.com/OpenVoiceOS/ovos-tts-plugin-piper), [Fury sessions](https://github.com/huwprosser/fury-sdk/blob/main/docs/sessions.md), [jarvis-mlx](https://github.com/huwprosser/jarvis-mlx).

## 2026-11-03 — Verify interfaces and dependency declarations after collection

Outcome: screened 431 repository entries and collected 12 licensed OVOS references. Static inspection found that the CueLight wrapper imports an EOT template absent from the collected plugin-manager source despite apparently sufficient version constraints. The date parser imports additional OVOS/calendar dependencies. The corrections plugin catches timeout exceptions without passing a timeout to its substitution call.

Lesson: a compatible-looking version number, standalone README description, or mocked timeout test is insufficient evidence for production adoption. Check actual imported symbols, dynamic dependency files and where execution is bounded. Keep experiments out of the live voice path until their specific contracts are demonstrated.

Source: [collection review and pinned evidence](../JARVIS%20OS%20DOCS/upstream-sources/2026-11-03/README.md). Verification checked source integrity and syntax only; no upstream runtime was installed or tested.

## 2026-11-03 — Preserve multimodal input when adding optional widgets

Outcome: restored the original JARVIS attachment bar after an optional text-only canvas field had taken over its adapter. Fixed close cleanup, missing voice-vision imports and missing-input error reporting; retained the prior installed release. Focused tests passed and the original 600 × 50 input window was verified through the running service. A user-approved screen-vision check produced fresh frames and restored off mode.

Lesson: an optional UI extension must preserve the existing entry point's capabilities, including attachments and cleanup. Test both the preferred and fallback paths, and distinguish local preview capture from cloud interpretation. Preserve standby/mute settings during deployment. Verify hardware through a host-visible channel; restricted `/dev` visibility is not proof that a webcam is absent.

Source: [repair and verification record](../JARVIS%20OS%20DOCS/INPUT-BAR-AND-VISION-REPAIR-2026-11-03.md), `skills/skills.py`, `voice_layer/daemon.py`, `voice_layer/ipc.py`, `tests/test_widget_canvas.py`, `tests/test_vision_runtime.py`.

## 2026-11-03 — Make behavior certification stricter than ordinary test success

Outcome: built eight named behavior contracts with 49 passing checks, required in CI and standard source-release builds. Seeded failures, skips, expected failures, missing cases and cleanup errors were rejected. The attachment contracts exposed binary audio being decoded as text; the source now forwards audio bytes with their media type. Twenty broader release checks also passed, with overlap in rollback coverage.

Lesson: a zero test-runner exit code alone is insufficient evidence that all required behaviors ran. Require complete per-case execution, fresh result evidence and a source fingerprint. Keep deterministic contracts separate from live device/provider acceptance, and state which release paths actually enforce the gate.

Sources: `scripts/behavior_gate.py`, `tests/behavior/contracts.json`, `tests/behavior/test_gate_enforcement.py`, `tests/behavior/test_multimodal_contracts.py`; [implementation and evidence](../JARVIS%20OS%20DOCS/BEHAVIOR-REGRESSION-GATE-2026-11-03.md). No live runtime release was changed during this outcome.

## 2026-11-03 — Treat parser output as evidence that needs domain validation

Outcome: integrated OVOS number/date spans into a bounded English pilot. Experiments found that number spans omit a spoken minus sign, date parsing guesses bare AM/PM, and relative-hour arithmetic can count wall time across DST. JARVIS now preserves signed source evidence, rejects ambiguous numeric controls and conflicting model arguments, flags unclear dates/zones, and resolves explicit durations as elapsed time. Temporal parsing runs in a cancellable process outside the audio loop.

Lesson: validate the entire typed phrase and its domain bounds, not just the first numeric result. Keep original transcript offsets, protect quoted/code/path data, require explicit timezone anchors, and measure cold imports before placing a parser on a voice path. A parsed scheduling candidate is not an executed task or universal scheduling authorization.

Sources: `jarvis_control/command_values.py`, `jarvis_control/parsing_service.py`, `voice_layer/local_speech.py`, `tests/behavior/test_command_parsing.py`; [implementation and saved evidence](../JARVIS%20OS%20DOCS/VOICE-COMMAND-PARSING-2026-11-03.md). Focused checks: 170 passed plus 12 subtests; expanded behavior gate: 125 passed. Source/dev environment changed; installed voice release was not deployed.

## 2026-11-03 — Certify the actual installed layout before activation

Outcome: after explicit deployment authorization, staged parsing over the existing `jarvis_voice` runtime, installed 28 additional dependency packages without upgrades, and passed 125 behavior checks under the installed Python 3.13 environment. The first candidate correctly failed for a missing test helper. The corrected candidate was activated atomically; three read-only running-service parser checks passed and standby/mute/vision settings were preserved.

Lesson: checkout tests and installed-runtime certification are distinct evidence. Preserve the installed package layout and unrelated release content, include test support needed for certification, and retain an expected-parent rollback target. State that additive shared dependencies remain after code rollback.

Source: `scripts/prepare_parsing_release.py`; [deployment and live evidence](../JARVIS%20OS%20DOCS/VOICE-COMMAND-PARSING-2026-11-03.md#authorized-deployment). Active release: `20261103T165256169577Z-command-parsing`; prior input/vision repair retained.

## 2026-11-03 — Present task state from a shared journal rather than result prose

Outcome: built a canonical schema and bounded persistent task presentation journal shared by filesystem receipts, UI snapshots and terminal notices. Model/worker responses remain unverified, cancellation requests remain nonterminal until confirmed, and delayed updates/acknowledgements cannot overwrite a newer result. Generic widgets cannot forge task-owned cards. A presentation failure leaves an admitted task admitted rather than encouraging resubmission.

Lesson: keep execution authority, transcript, presentation and notification acknowledgement distinct. Persist stream/revision/generation identity, retain pending outcomes under backpressure, and resync from current snapshots when replay history is bounded. Use an exclusive presenter lease before inferring that an in-memory task vanished after restart. Progress is measured data, never decorative percentages.

Sources: `contracts/task-event-v1.json`, `orchestration/task_events.py`, `orchestration/task_presentation.py`, `ui/jarvis_widgets/TaskEvents.js`; [implementation and evidence](../JARVIS%20OS%20DOCS/CONSISTENT-TASK-UI-EVENTS-2026-11-03.md). Final gate: 148 passed; broader existing checks: 86 passed plus 10 subtests; Qt suite: 16 passed. Built in source; installed runtime and shell were not changed.


## 2026-11-04 — Admit early interruptions through evidence gates

Outcome: removed the voice capture loop's unconditional first-350-ms playback interruption exclusion. Existing speech/VAD and playback-reference correlation checks still govern admission. Added synthetic startup acceptance, echo rejection and missing-reference scenarios; updated the obsolete holdoff assertion. Parent validation passed 59 focused voice checks and 7 selected daemon checks. A broader daemon run stalled and was stopped; installed runtime and hardware were not changed.

Lesson: a fixed startup blackout can discard a short correction even when the interruption detector has enough evidence. Preserve minimum evidence and echo rejection when removing a timing exclusion, and distinguish synthetic correlation tests from acoustic verification. Pause timing and semantic turn completion remain separate unfinished work.

Sources: `voice_layer/daemon.py`, `voice_layer/speech.py`, `tests/test_hie_startup_interruption.py`, `tests/test_interruptions.py`, `docs/human-interaction-engine-plan.md`. The requested capture-learning skill is absent from the available catalog and project search; this sourced append records the result directly.

## 2026-11-04 — Review agent fixes against lifecycle and deployment contracts

Outcome: lower-cost agents implemented the PC audit repairs; parent review corrected
expiry authority, historical sensitivity, overwrite rollback, pending receipt semantics,
and installer validation. The full suite passed 1,722 checks plus 149 subtests;
the final behavior gate passed 167 checks. Reloaded PC voice/bridge services were
active, Gemini reconnected, privacy settings were preserved, and the bridge bound
to loopback. Android code and the Hermes gateway were not restarted or changed by this repair.

Lesson: review full lifecycle behavior after a narrow fix. Restricted classification
must cover old snapshots, admitted execution can outlive a response deadline, and
installer success requires a complete importable payload before publishing its pointer.
A checkout-based service can be valid development mode; validate the configured mode
instead of treating all checkout paths as deployment failures.

Sources: `docs/pc-audit-fixes-2026-11-04.md`, `tests/test_filesystem_audit_regressions.py`,
`tests/test_memory/test_audit_memory_regressions.py`, `tests/test_device_execution_admission.py`,
`tests/test_device_bridge_security.py`, `tests/test_installation.py`.


## 2026-11-04 — Keep human interaction presentation grounded and preserve microphone identity

Outcome: built the six-stage HIE V1 in the source checkout: 1.2-second default pause tolerance, early interruption evidence gates, contextual admitted-work acknowledgements with copied deferred arguments, idle event-grounded progress, native delivery guidance and sparse narrative listening cues. Buffered the first 80 ms of listening-cue microphone input for echo comparison; matched echo becomes silence and distinct speech is replayed with turn flags preserved. An independent playback epoch cancels listening audio without invalidating microphone generations. Final checks: 258 focused voice tests passed with no failures/skips; the existing required behavior gate passed 201 checks with an unchanged-source fingerprint. CLI dependency/config check passed. No installed release, service or existing profile was changed.

Lesson: action-specific acknowledgement needs execution admission, not transcript hints; deferred presentation must carry arguments and turn identity. Listening feedback must share output priority while preserving input PCM and boundaries through cancellation. Read progress snapshots off the audio loop, suppress stale/absent task updates and keep foreground tool calls free of synthetic conversation turns. A longer fixed pause is not semantic understanding; prompt coverage is not audible expressive-speech acceptance.

Sources: `voice_layer/daemon.py`, `voice_layer/playback.py`, `voice_layer/interaction.py`, `voice_layer/progress.py`, `voice_layer/persona.py`, `tests/test_hie_pipeline.py`, `tests/test_hie_playback_fence.py`, `tests/behavior/contracts.json`, `JARVIS OS DOCS/HIE-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/HIE-VERIFICATION-2026-11-04.json`, `docs/human-interaction-engine-plan.md`. The capture-learning skill is absent from the available catalog/project paths; this sourced append records the actual outcome directly.


## 2026-11-04 — Revalidate progress after waiting for the voice transport

Outcome: read-only HIE review reran 82 focused checks successfully and reproduced a stale-progress race with the real LiveVoice send lock. A running snapshot was selected, the task changed to completed while delivery waited for the lock, and the eventual provider payload still said background work was underway. No application fix was made in this review. No confirmed new buffer-loss or playback-epoch defect was found; a speculative stale acoustic-reference concern was withdrawn because retained reference also covers legitimate room echo tails.

Lesson: privacy checks under a transport lock do not refresh task facts selected before that lock. Bind a progress delivery to task identity/revision and revalidate its state immediately before dispatch. Ordinary passing tests do not prove this wait-window behavior.

Sources: `voice_layer/progress.py:124`, `voice_layer/daemon.py:858`, real-lock synthetic provider reproduction during this review; `tests/test_hie_progress.py`, `tests/test_hie_pipeline.py`, `tests/test_hie_playback_fence.py`. Live audio and the full repository suite were not verified. The capture-learning skill remains absent from the available catalog; this append records the sourced outcome directly.


## 2026-11-04 — Fence task progress at dispatch and verify interrupted deployments

Outcome: fixed the reviewed progress race by carrying immutable task identity/revision into the locked delivery path and re-reading its current journal snapshot before speech authorization. Revision-only changes refresh waiting tokens without repeating delivered notices. The regression first failed five stale cases; final checks passed 49 focused tests and 209 required gate checks with certified source intact. Deployed through the existing checkout-mode voice service restart. An interrupted deployment command omitted its report; read-only verification confirmed new PID 53309, active service, current source, Gemini connection, control and AEC. The helper had exited. The replacement AEC inherited the physical microphone mute; no unmute, UI restart, bridge restart or release-pointer switch was performed.

Lesson: a revision fence must refresh undelivered tokens even when the spoken state is unchanged. After an interrupted deployment, inspect actual process identity and service state before repeating a mutation. Preserve physical privacy signals rather than assuming an old virtual microphone's mute flag represents the underlying device.

Sources: `voice_layer/progress.py`, `voice_layer/daemon.py`, `tests/test_hie_progress.py`, `JARVIS OS DOCS/HIE-FIX-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/HIE-FIX-DEPLOYMENT-2026-11-04.json`; systemd/voice IPC/PipeWire/journal verification after the 2026-11-04 18:14 IST restart. Live acoustic behavior was not tested. Capture-learning remains unavailable; this dated source-backed append records the observed outcome.


## 2026-11-04 — Check physical and virtual microphone mute independently

Outcome: user reported no voice response after deployment. Live status showed Gemini connected but JARVIS's AEC source remained muted; the physical default microphone was already unmuted. Unmuted only the active JARVIS AEC source, then confirmed its mute was false, listening was true, four user turns were admitted and provider audio bytes increased from 162240 to 201120. No application source, physical microphone setting or service restart was needed. Speaker audibility was not verified.

Lesson: a virtual AEC source can retain a mute inherited at creation after the physical microphone is later unmuted. Diagnose both layers; a connected cloud session does not establish working microphone input. Do not automatically synchronize mute states without a defined privacy policy.

Sources: voice IPC status and PipeWire mute probes for `jarvis_aec_6c22a21f` during this repair. Capture-learning is unavailable; this append records the observed outcome.


## 2026-11-04 — Verify active timing overrides before claiming listening cues work

Outcome: user reported listening cues absent. Active config retained400ms turn closure while the cue needed400ms quiet +670ms audio +100ms margin, making it unreachable. Backed up and corrected the active profile to1.2s; reduced only the cue's quiet tail to460ms with a20ms fade and validated cache integrity. Small acknowledgement and native delivery refinements passed120 focused checks and209 required gate checks. Reload preserved standby via a temporarily muted startup; final read-only status later showed connected/listening, AEC unmuted, original autostart/greeting restored and1.2s configured. Audible cue occurrence remains unverified until a new narrative test.

Lesson: source defaults and synthetic timing tests do not establish the active profile's feasibility. Compare minimum quiet time, complete clip duration and safety margin against the actual endpoint. Preserve standby during deployment rather than waiting forever for a standby profile to report idle. Prefer removing empty audio tail and redundant promises over adding speech models or relaxing echo evidence thresholds.

Sources: `voice_layer/daemon.py`, `voice_layer/acknowledgements.py`, `voice_layer/persona.py`, `voice_layer/assets/ack_short_hmm.pcm`, `voice_layer/assets/acknowledgements.json`, `tests/test_situational_acknowledgements.py`, `JARVIS OS DOCS/VOICE-POLISH-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/LISTENING-CUE-PROFILE-FIX-2026-11-04.json`. Capture-learning remains unavailable; this append records the observed outcome.


## 2026-11-04 — Freeze the approved PC voice baseline without disturbing runtime

Outcome: at the user's request, froze 122 PC voice source/test/asset/entry-point paths and compatibility links with a hash manifest and local read-only permissions. Five source directories are non-writable; generated bytecode caches remain writable. The verifier preserves the existing internal compatibility asset link but rejects unexpected redirects, changes, additions and removals. Root CLAUDE.md and its AGENTS.md mirror require explicit user authorization for voice changes; CI and the existing evolution manifest guard use the recorded boundary. Five focused lock tests and 214 required behavior checks passed. CLI dependency/config validation passed. No service restart, runtime profile change or microphone change occurred.

Lesson: reuse the existing voice-lock manifest interface, protect real source plus compatibility paths, and pin legitimate internal links instead of rejecting or copying them. Keep mutable caches and shared application code out of a source freeze. Read-only modes protect local accidental writes; hashes and policy carry the baseline across Git clones, which do not preserve those permission bits. An owner-reversible lock is not a security boundary against the machine owner.

Sources: `audio/.voice_lock.json`, `scripts/verify_voice_lock.py`, `tests/test_voice_lock.py`, `AGENTS.md`, `CLAUDE.md`, `.github/workflows/ci.yml`, `JARVIS OS DOCS/VOICE-LOCK-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/VOICE-SUBSYSTEM-LOCK-2026-11-04.json`. Capture-learning is unavailable; this append records the actual sourced outcome.

## 2026-11-04 — Extract voice without carrying the application or bypassing its freeze

Outcome: explicitly requested standalone copy created under `universal-voice/` while preserving the locked PC baseline. Reused voice streaming, speech gating, interruption, playback, acknowledgement assets, wake listening and event-progress presentation; removed mandatory memory/desktop/vision/task dependencies and rejected unattached tool calls. Configuration, IPC, greeting markers and service name are independent; removed legacy socket-link creation. Built a wheel and source archive with attribution. 68 source checks and 68 checks against an isolated wheel passed; local dependency/VAD and shell preflights passed. Original voice-lock verification passed before and after. No service, microphone or original profile changed.

Lesson: portability requires tracing runtime paths and startup imports, not only copying source. A compatibility socket alias can silently interfere with the original even after renaming the package. Separate Linux distribution compatibility by prerequisites from tested distro/hardware support; an isolated wheel test does not establish a fresh dependency installation or live audio quality.

Sources: `universal-voice/README.md`, `universal-voice/VERIFICATION.json`, `universal-voice/tests/test_portable.py`, `universal-voice/ORIGIN.json`, `universal-voice/dist/SHA256SUMS`. Cross-distribution VMs and live cloud/audio remain untested. Capture-learning is unavailable; this append records the sourced outcome directly.

## 2026-11-04 — Lock both voice copies while preserving the selected system default

Outcome: user explicitly selected keeping the current full JARVIS system voice and locking both copies. Original baseline verifier passed; froze 77 standalone source, asset, test, packaging and distribution files with an independent checksum manifest, verifier and read-only permissions. Added matching agent freeze rules to both instruction mirrors. Both verifiers and source permission checks passed; 68 standalone regressions passed after locking. Existing full voice service was active and cloud connected; its system microphone was muted and was left unchanged. No voice service replacement, restart or audio setting change was performed.

Lesson: a standalone voice extraction does not carry the full assistant's desktop tools. Confirm which runtime should remain the default before substituting one for the other. A code freeze should preserve privacy state and maintain separate manifests rather than regenerating an already approved baseline.

Sources: `universal-voice/.voice_lock.json`, `universal-voice/scripts/verify_voice_lock.py`, `AGENTS.md`, `CLAUDE.md`, existing voice IPC and systemd inspection during this task. Capture-learning remains unavailable; this sourced append records the outcome. Live acoustic behavior was not tested; owner-reversible permissions are an accidental-edit guard.

## 2026-11-04 — Default to EGM for its supported design/document workflows

Outcome: installed egm@egm 0.1.0 and read its bundled Codex integration, execution constraints and skill descriptions. At the user's request, saved global and matching project instruction routing for brainstorming, design drafting, document review, resolution, documentation bootstrap and drift reporting. Ordinary implementation and small bug fixes retain the normal workflow. Both voice baseline checks passed; protected files and runtime settings were untouched.

Lesson: a design plugin is not an inference model or a universal coding mode. Persist task-specific routing, resolve installed skill paths dynamically, preserve real approval/isolation requirements and do not claim workflow execution merely from installation. A fresh session is recommended by the plugin for skill discovery.

Sources: installed `egm` bundle `docs/codex.md`, `resources/execution_instructions.md`, `skills/*/SKILL.md`; global Codex AGENTS.md and project CLAUDE.md/AGENTS.md. End-to-end Goldfish reviews were not run. Capture-learning remains unavailable; this dated append records the sourced outcome.

## 2026-11-04 — Test both frozen voice copies and distinguish distribution locks from local locks

Outcome: read-only audit using EGM drift-report plus existing executable tests passed 501 system voice tests, 214 overlapping required behavior-gate checks and 68 standalone checks. Both source-lock verifiers, source/archive byte comparisons, distribution hashes and dependency/VAD preflights passed. Restricted-environment runs stalled or timed out; host reruns completed without test edits. Runtime initially showed a provider handshake retry, then a connected provider with AEC active; the system microphone remained muted. No source, profile, service or mute changes were made.

Lesson: a local freeze created after packaging does not travel with the older archive/wheel. The downloadable standalone source matches the protected code, but its archive omits the later manifest/verifier/instruction files. Record that distribution gap instead of claiming extracted copies are locked. Automated tests and provider connection do not establish real-room listening cues, barge-in latency or voice quality.

Sources: `docs/voice-audit-2026-11-04/VOICE-TEST-REPORT.md`, `docs/voice-audit-2026-11-04/2026-11-04_DRIFT_REPORT.md`, saved JUnit and gate evidence in that directory; read-only service snapshots. Fresh installations, distro VMs and live audio remain untested. Capture-learning is unavailable; this append records the sourced outcome.

## 2026-11-04 — Mirror physical microphone mute transitions to the owned AEC source

Outcome: user authorized a specific unmute repair. Live state reproduced physical default input unmuted while JARVIS's AEC input remained muted despite a connected provider. Added transition-based synchronization to the existing microphone monitor, scoped to its echo owner's resolved physical source and private AEC. Independent AEC mutes persist when physical mute is unchanged; invalid/unknown state does not unmute. Fifteen new regressions, 516 full voice checks and 229 required gate checks passed. Restarted only the existing voice service; it reconnected with private input unmuted and no input error. Physical settings and saved config were unchanged. Authorized source hashes were recorded and read-only locks restored; standalone copy unchanged.

Lesson: initialization-only mute propagation is insufficient after a physical mute/unmute cycle. Follow observed physical transitions rather than continuously forcing virtual input to match, and preserve the last observation until a write succeeds. Track the actual source, not whatever later becomes the system default. Software regression and ready microphone state still do not prove audible conversation.

Sources: `docs/voice-unmute-repair-2026-11-04.md`, its source patch, `tests/test_microphone_mute_sync.py`, `JARVIS OS DOCS/VOICE-UNMUTE-BEHAVIOR-2026-11-04.json`, `JARVIS OS DOCS/VOICE-UNMUTE-DEPLOYMENT-2026-11-04.json`. Capture-learning remains unavailable; this append records the sourced outcome.

## 2026-11-04 — Separate whole-OS Harness² intent from research-only implementation

Outcome: reviewed the Antigravity system architecture map with fresh-context EGM zoom-out, comprehension, design, structural, style and intermediate zoom-out reviewers. Found open gaps in protected voice exclusions, runtime isolation, release authority/recovery, OS benchmarks, incident contracts and privacy. Existing learning suite passed 62 tests; both voice locks passed before/after. No deployment or source repair performed.

Lesson: Git worktrees isolate source trees, not host service effects. A research-instruction evaluator and successful fixtures do not certify whole-OS self-repair. Start with one sanitized incident producing an evaluated advisory proposal; define separate non-research candidate and recovery contracts before production mutation. Installed crash/healer notifications offer click-to-launch flows, not proof of an automatic evaluation pipeline.

Sources: `docs/harness2-review-2026-11-04/consolidated_review_report.md` and adjacent reviewer reports; `learning/refinement.py`, `learning/trials.py`, `learning/evidence.py`, `orchestration/release_manager.py`; installed `/usr/bin/omarchy-crash-watch` and external healer notification/playbook source. The capture-learning skill is absent in this checkout; this append records the sourced outcome. No implementation plan existed, so EGM Stage9 was explicitly not run; no convergence or runtime safety claim.

## 2026-11-04 — Establish Harness² contracts before live OS integration

Outcome: after the user instructed proceeding through the six-phase sequence, established the workspace architecture baseline with protected voice observation-only access, typed incident/proposal contracts, full-revision idempotency, single-owner job states and phase-specific acceptance obligations. Applied ten review fixes at the documentation level; production and Antigravity source artifacts unchanged.

Lesson: healer symptom IDs are fingerprint-derived and may recur; use occurrence identity for incident ingestion. Its incidents table does not expose direct structured service observations, so do not invent state from status/title or copy raw trace_json. An exporter must avoid MemoryStore initialization because it creates/configures database state. Written boundaries do not close runtime isolation, clean-install or recovery findings.

Sources: `docs/harness2-review-2026-11-04/architecture.md`, `goldfish_review_report.md`; read-only `/home/g0pi/Projects/omarchy-healer/src/omarchy_healer/models.py`, `memory.py`, `probes.py`. Capture-learning skill absent; this append records the sourced outcome.

## 2026-11-04 — Build OS contracts without importing the live voice runtime

Outcome: implemented learning/os_contracts.py as an independent standard-library validation CLI/API. It enforces fixture-only typed incidents, baseline/time checks, immutable revisions, evaluator-bound identities, evidence-supported advisory proposals and protected-path screening. Added 58 contract checks; all 120 learning tests passed with zero skips. Both voice locks passed before/after; no existing runtime entry point, service or dependency changed.

Lesson: canonical incident revisions must include baseline and timestamps, while run reuse must additionally bind evaluator/fixture identities. Reject nested duplicate keys and numeric overflow before hashing JSON. Path screening must reject symlinks, hardlinks and directory scopes; it is still only a point-in-time check and cannot replace enforcement at a future writer. Future limits should be explicitly marked unenforced until a worker actually exists.

Sources: learning/os_contracts.py; tests/test_learning/test_os_contracts.py; docs/harness2-review-2026-11-04/phase1-build.md and phase1-tests.xml. Real incident ingestion, job durability, VM containment and deployment/recovery remain later work. Capture-learning skill absent; this append records the sourced outcome.

## 2026-11-05 — Import healer occurrences as historical metadata without inventing observations

Outcome: built learning/os_ingestion.py for explicit one-occurrence read-only SQLite imports into private separate state. Real metadata has unknown service identity/state and empty evidence; Phase 1 parsing stays fixture-only unless the importer explicitly enables the profile. Source-instance/path/device/inode and row-metadata binding prevent silent replacement/reuse; baseline revisions and reopen duplicates are persisted atomically under one writer lease. All 146 learning tests passed (26 new ingestion checks), both voice locks passed, and a real recent healer occurrence returned ingested then duplicate using temporary state. No incident/schema mutation, voice repair or service operation was issued.

Lesson: use an explicit read transaction to retain one WAL snapshot across schema and occurrence reads. Read-only SQLite may still maintain WAL shared-memory bookkeeping and require host filesystem access; do not claim every live sidecar byte is unchanged. The source's recurring symptom ID and raw trace are not an occurrence identity or reliable structured current-state evidence. Keep typed historical metadata separate from fixture evaluation and disable real-record proposal verdicts until independently implemented.

Sources: learning/os_ingestion.py; learning/os_contracts.py; tests/test_learning/test_os_ingestion.py; docs/harness2-review-2026-11-04/phase2-build.md, phase2-tests.xml, phase2-live-check.json; read-only external healer memory.py schema inspection. Restricted full-suite collection stalled and was interrupted; final host rerun passed 146 tests in 8.78 seconds. Capture-learning skill absent; this append records the sourced outcome. Automatic polling, voice wiring, current-service probes, execution isolation and deployment/recovery remain unimplemented.

## 2026-11-15 — Verify retry and repeat-run behavior before enabling memory maintenance

Outcome: reviewed the local JARVIS OS changes against the recorded upstream commit `4713691`. Temporary-vault checks showed that repeat compaction removed substantive details from the active daily note and that a failed note append still advanced the sync cursor. A temporary voice configuration also reproduced a startup error when the new decision settings were present.

Lesson: make compaction idempotent, advance a persistence cursor only after the corresponding write succeeds, and load new configuration sections through the same typed path as existing settings. Exercise these paths with disposable data before enabling scheduled maintenance.

Sources: `scripts/midnight_summary_sync.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, `departments/memory/department.py`, `voice_layer/config.py` and temporary-data review checks. The capture-learning skill was unavailable in the installed and repository skill paths, so this entry records the findings directly.

## 2026-11-15 — Give memory maintenance a single owner for each file

Outcome: repaired the Memory Department's rollover, session sync, scoped recall integration, and pruning. The agent's notes now live under `Memory Department/Conversations`. The existing exporter retains its own files. Recorded history sync writes the note and its progress marker together, including when the first run occurs after midnight. Temporary-vault checks confirmed retry, repeat compaction, transcript retention, and alternate-vault isolation.

Lesson: keep a durable progress marker in the same atomic write as the content it represents. Apply scope and deletion through one memory store, and keep transcript maintenance from re-promoting historical text into remembered facts.

Sources: `departments/memory/department.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, `departments/memory/tests/test_memory_department.py`, `scripts/midnight_summary_sync.py`, and isolated alternate-vault verification. The capture-learning skill was unavailable, so this entry records the result directly.

## 2026-11-15 — Validate memory stability through retries and worker shutdown

Outcome: hardened the six Memory Department agents and the legacy memory adapter. The graph filters expired and superseded nodes, consolidation regenerates agent-owned fact notes after a failed write, reflection deduplicates its rules, and diagnostic capture redacts credential fields. The legacy adapter now uses the shared bounded worker. Isolated checks exercised tool routing, worker shutdown, and repeat midnight sync against an alternate vault.

Lesson: preserve a stable initial sync cutoff across retries, derive file projections from committed records, and exercise the real worker lifecycle alongside unit tests. Generated rules and agent notes need stable identities and their own write boundaries.

Sources: `departments/memory/tests/test_memory_department.py`, `departments/memory/db.py`, `jarvis_memory/skills.py`, `tests/test_memory/test_memory_worker.py`, and the disposable DesktopSkills and midnight-sync check. The capture-learning skill was unavailable, so this entry records the result directly.

## 2026-11-15 — Verify outcomes at the action boundary

Outcome: buffered voice classifications now reach the Live tool path, and classified confirmation requests block tool execution for the initial turn. Close App reports the window or tab operation's result. Package removal aggregates results across managers. Review cards expose the working Diff action, and widget expiry preserves milliseconds.

Lesson: a classification or dispatch acknowledgment does not establish that a tool ran. Test the actual handoff and retain failures when multiple backends contribute to one result.

Sources: `voice_layer/daemon.py`, `tests/test_gemini_decisions.py`, `tests/test_control/test_privileged_and_security.py`, and the WidgetModel expiry assertions. The capture-learning skill was unavailable.

## 2026-11-15 — Retry desktop submissions before execution starts

Outcome: the control worker now retries only rejected submissions, and shutdown drains active work before releasing the owned camera. In an isolated checkout with local sockets, the behavior gate passed 224 checks and the full suite passed 2,160 tests with 15 skips and 149 subtests. That full run preceded the final camera shutdown change, which passed 15 focused control and concurrency tests. The synthetic memory evaluation reported no baseline regressions and still failed the false-recall check.

Lesson: an admitted tool can change the desktop before raising an error. Retry only when submission itself fails. Drain the worker pool before closing resources an active operation can reopen.

Sources: `jarvis_control/skills.py`, `tests/test_control/test_skills.py`, and the isolated test runs. The capture-learning skill was unavailable.

## 2026-11-16 — Verify desktop repairs at their runtime boundaries

Outcome: repaired desktop voice confirmation and offline classification, file-write conflict handling and Trash recovery, memory sync cursors and evidence filtering, package removal outcomes, release readiness and source fingerprints, evolution cards, stale voice status, and installer packaging. Lower-cost independent reviewers checked the file, release, and memory changes. The final isolated suite passed 2,170 tests and 149 subtests with 15 skips. The behavior gate passed 224 checks when run on its own. The synthetic memory benchmark passed with zero baseline regressions. Phone and mobile work was deferred.

Lesson: verify failure paths through the real local entry point. Keep a file conflict check close to replacement and record which writers honor its lock. Run the required behavior gate separately when a concurrent run fails to produce evidence.

Sources: `tests/test_control/test_voice_control_boundary.py`, `tests/test_filesystem_and_task_runner.py`, `tests/test_release_switching.py`, `departments/memory/tests/test_memory_department.py`, `scripts/behavior_gate.py`, and disposable checkout test results. The capture-learning skill was unavailable.

## 2026-11-16 — Preserve entry and socket ownership during desktop recovery

Outcome: a lower-cost agent review found that an existing daily memory note did not repair its stale rollover marker, and task verification followed symlink targets instead of checking the operated-on entry. Fixed both, including dangling-link verification. Desktop control servers now refuse to replace live listeners or ordinary files, bind before handing sockets to asyncio, and compare device/inode ownership before cleanup. The independent runtime reviewer identified the replacement-path shutdown case; it was fixed and covered for core, voice control, and speak sockets. The final disposable desktop suite passed 2,105 tests and 150 subtests, with 15 optional/runtime skips and 91 phone/mobile-related tests deselected.

Lesson: a pathname is not an ownership identity. Verify the entry an action actually changed, and never let startup or cleanup remove another server's socket. Recover persistent progress markers even when their corresponding output already exists. Preserve repository symlinks when building isolated test snapshots.

Sources: `core/ipc.py`, `voice_layer/ipc.py`, `filesystem/task_runner.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, their regression tests, and `/tmp/jarvis-desktop-audit-ujyf8b0h/.review/suite-final.log`. Phone/mobile code and deployment were excluded; optional integrations and live desktop/cloud behavior remain unverified. The capture-learning skill was unavailable, so this entry records the sourced outcome directly.

## 2026-11-16 — Verify optional desktop connectors without claiming a live connection

Outcome: continued desktop validation after additional YouTube Brain integration changes appeared. A lower-cost reviewer repaired its hardcoded home path, SQLite URI escaping, bus error propagation, missing-note handling, bounded results/content, and bus setup deadline. The parent removed duplicate unconditional connection claims and required observed status before reporting availability. Integration tests now use a temporary SQLite database and the real asynchronous connector rather than personal notes. The final current-source desktop suite passed 2,116 tests and 150 subtests, with 15 optional/runtime skips and 91 phone/mobile-related tests deselected.

Lesson: a declared tool or readable archive does not prove that a live worker or capture pipeline is connected. Keep test fixtures isolated while exercising the real asynchronous boundary, and preserve unsuccessful connector responses instead of turning missing content into success.

Sources: `connectors/yt_brain.py`, `voice_layer/persona.py`, `voice_layer/daemon.py`, `tests/test_yt_brain.py`, `tests/test_yt_brain_persona.py`, and the disposable desktop verification run. Upstream worker response shape was checked read-only in `/home/g0pi/jarvis-yt-brain/yt_brain/jarvis_yt_brain_worker.py`. No phone/mobile modifications or deployment. Capture-learning remains unavailable; this append records the sourced outcome.

Final gate evidence for this continuation: the unchanged final source snapshot passed all 224 required behavior checks (`passed=true`, `source_unchanged=true`). These deterministic checks do not establish live microphone, cloud-provider, desktop-display, or external YouTube worker acceptance.

## 2026-11-16 — Use one desktop-entry inventory across launch routes

Outcome: fixed a case-sensitive legacy app lookup and made DesktopSkills consume the existing XDG desktop_paths/read_desktop discovery helpers. Nested desktop entries are now included and a hidden user override cannot be resurrected by a system entry. Regression coverage includes Antigravity capitalization, separation from Antigravity IDE, nested entries, hidden overrides, failure-loop limits, and worker timing. Isolated focused verification passed 56 tests and 11 subtests.

Lesson: multiple launch routes must agree on entry identity and precedence. A working executable does not make every spoken spelling a valid desktop ID. Bound failed retries and measure queue and handler time without logging file contents.

Sources: `skills/skills.py`, `jarvis_control/tools.py`, `tests/test_antigravity_launch.py`, `tests/test_desktop_tool_failure_loop.py`. The earlier file-action delay remains unattributed; no live action was replayed. Capture-learning is unavailable, so this append records the outcome directly.

## 2026-11-16 — Ground agent inventory in system discovery

Outcome: the live tool catalog now exposes system agent discovery directly, and the voice prompt routes agent inventory questions to it. The orchestration selector recognizes plural “agents.” Focused orchestration and persona checks passed.

Lesson: an inventory question needs the current agent catalog. A list of jobs answers a different question, and an installed command provides no evidence of sign-in.

Sources: `orchestration/tool_tiers.py`, `voice_layer/persona.py`, and `tests/test_orchestration.py`. The capture-learning skill was unavailable. The installed runtime and live microphone were unverified.

## 2026-11-16 — Include native departments in agent discovery

Outcome: the agent lookup now includes the LinkedIn and Memory rosters alongside local command availability. Focused orchestration and persona tests verified 12 LinkedIn agents and six Memory agents.

Lesson: agent inventory should account for internal specialists as well as external delegates. A roster alone does not establish runtime readiness.

Sources: `skills/domains/orchestration.py`, `voice_layer/persona.py`, and `tests/test_orchestration.py`. The capture-learning skill was unavailable. Deployment and live voice were unverified.

## 2026-11-16 — Register teams in the JARVIS agent catalog

Outcome: JARVIS returns one agent list with department membership on native and pipeline entries. The list includes 12 LinkedIn, six Memory, five YouTube Brain, and eight local command entries. Focused routing and catalog tests passed.

Lesson: use department membership as catalog metadata and keep execution behind the owning workflow. Recording a pipeline stage in the inventory leaves its health unverified.

Sources: `skills/domains/orchestration.py`, `skills/domains/yt_brain.py`, `tests/test_orchestration.py`, and the five stages in the adjacent YouTube Brain project's `yt_brain/main.py`. The capture-learning skill was unavailable.

## 2026-11-17 — Keep voice responsive while department work runs

Outcome: synchronous LinkedIn operations now use a dedicated worker. Voice requests for drafts, sprint plans, and profile audits return a tracked background task receipt, and the main voice can give one factual status reply when an action lacks completion evidence. A regression test held a synchronous draft open while a second voice turn completed. The focused voice, interruption, background delivery, and task suites passed 125 tests.

Lesson: moving execution off the audio event loop keeps capture alive, while returning a task receipt releases the conversational turn. Reuse the task runner for status and idle delivery, and keep confirmation-bound actions out of automatic background admission.

Sources: `voice_layer/daemon.py`, `jarvis_control/skills.py`, `skills/domains/linkedin.py`, `filesystem/task_runner.py`, `tests/test_daemon.py`, and the JARVIS Voice service journal. Capture-learning was unavailable. Live microphone conversation and NVIDIA authentication were not exercised.

## 2026-11-17 — Recover missing voice replies without speculative acknowledgements

Outcome: the voice journal showed local “okay,” “sure,” and “hmm” clips followed by new speech turns before reply audio, and a provider reply that recovered only after an empty turn boundary. Ordinary turns now wait for actual reply audio or admitted work. A transcribed turn that stalls can request one spoken answer without replaying tools. All 154 focused checks passed. After restart, the journal recorded two microphone turns with provider audio beginning in roughly one second. Live stall recovery was not induced.

Lesson: a local acknowledgement does not establish that a reply reached playback. Check upload, provider audio, and turn transitions separately. Bound recovery to one attempt per recognized turn and keep it clear of tools in flight.

Sources: JARVIS Voice service journal, `voice_layer/daemon.py`, `tests/test_daemon.py`, `tests/test_gemini_decisions.py`, and `tests/test_spoken_fillers.py`. The capture-learning skill was unavailable.

## 2026-11-17 — Verify low-cost LinkedIn drafts against source facts

The live LinkedIn drafting workflow reached the review queue using the configured primary NVIDIA model alone after agents were fixed to honor their supplied client configuration. The draft invented activity counts, which were removed in review. An authenticity check does not verify factual claims. Sources: the department regression tests and review card `post_20261117_085823_f7`.

## 2026-11-17 — Publish approved images through the LinkedIn department

The Content Scheduler now hands an approved image to the LinkedIn publishing tool as a structured upload, and the department records the returned post ID. The department regression test confirms that approving a published draft again does not trigger another upload or post.

## 2026-11-17 — Route LinkedIn work through the department

The voice persona routes LinkedIn work through the department even when Hermes is absent. The tool catalog exposes post lookup through the department using the connector's `post_id` argument. Sources: `voice_layer/persona.py`, `skill_manifests/linkedin-department.json`, and the focused routing tests.

## 2026-11-17 — Use API Anything for other online services

Voice routing now selects mapped API Anything operations for non-LinkedIn online services. Removing the competing generic platform action instruction keeps the selected route consistent with the existing authorization flow. Sources: `voice_layer/persona.py`, `voice_layer/daemon.py`, and `tests/test_system_persona.py`.

## 2026-11-17 — Preserve sync checkpoints during vault maintenance

The vault pruner now preserves notes that carry session sync checkpoints and keeps index prose intact when cleaning standalone links. The legacy conversations folder also rejects symlinks. The Memory suite passed 198 tests and 87 subtests. A disposable DesktopSkills run verified session sync, replay protection, prune preview, remember, and recall. Sources: `departments/memory/tests/test_memory_department.py` and the disposable DesktopSkills check.

## 2026-11-17 — Keep simultaneous YouTube Brain requests on the live worker

Six parallel reads produced one live reply before the connector assigned unique broker client IDs. After the change, all six used the worker, and live note retrieval passed. A readable SQLite archive now has its own status. Sources: `connectors/yt_brain.py`, `tests/test_yt_brain.py`, and the live read-only smoke check.

## 2026-11-17 — Bound Google Workspace agents by service

The Google Workspace department now owns six agents for Gmail, Calendar, Tasks, Drive, Docs, and Sheets. Every existing Google tool has exactly one service owner or belongs to the department control plane, and off-service dispatch is rejected before the connector runs. JARVIS agent discovery and voice routing now identify Google Workspace as a native department. Forty-one focused offline checks passed, and the local connection check reported Gmail, Calendar, Tasks, and read-only Drive, Docs, and Sheets authorization.

Lesson: reuse the connector as the transport boundary and enforce service ownership above it with immutable allowlists. Capability isolation over one shared OAuth grant is not separate credential isolation.

Sources: `departments/google_workspace/`, `skills/domains/workspace.py`, `skills/domains/orchestration.py`, `voice_layer/persona.py`, and `tests/test_google_workspace_department.py`. No live Google content was read or changed.

## 2026-11-17 — Deploy agent catalogs before testing voice answers

The voice journal showed `list_system_agents` executing successfully while the active service still ran the November 5 managed release, which only returned local command agents. The tested department catalog had remained in the workspace. A prepared release now installs the catalog and Google department through the atomic runtime switch. The restarted voice service connected successfully, and its active package reports 38 registered agents: 12 LinkedIn, six Memory, five YouTube Brain, six Google Workspace, one Update agent, and eight local agents.

Lesson: a passing workspace test does not establish live voice behavior when systemd starts an installed release. Verify the active release path and execute the catalog from that package after activation.

Sources: the JARVIS Voice journal, `systemd/jarvis-voice.service`, `scripts/prepare_google_workspace_release.py`, and the post-activation `list_system_agents` check.

Live acceptance: a typed request was sent through the running voice session. JARVIS invoked `list_system_agents`, began response audio in about 1.5 seconds, and answered that 38 agents are registered with the correct department counts, including six Google Workspace agents. No runtime error appeared during the inventory call.

## 2026-11-20 — Standardize JARVIS Prompting Style into Cross-Runtime Skill

Standardized the Omarchy-derived prompt design invariants into a dedicated, cross-runtime skill `jarvis-prompt-style` located at `~/.agents/skills/jarvis-prompt-style/SKILL.md`. Symlinked the skill across Antigravity (`~/.gemini/config/skills/`), Claude Code (`~/.claude/skills/`), and the JARVIS workspace (`skills/jarvis-prompt-style`).

The skill provides 6 production prompt templates (Crash Forensics, Safe Customization, Zero-Polling Components, Native App Scaffolding, Idempotent Migrations, and Zero-Filler Voice Persona) and enforces the negative constraints matrix prohibiting affirmative filler, unverified root cause speculation, polling loops, raw numeric animation durations, and direct modifications to `/usr/share/omarchy`.

Verified that Claude's dynamic skill selector hook (`~/.claude/hooks/dynamic_skill_selector.py`) and Antigravity discover and select `jarvis-prompt-style` automatically.

Sources: `~/.agents/skills/jarvis-prompt-style/SKILL.md`, `knowledge-base/OMARCHY-PROMPT-STYLE-GUIDE.md`.

