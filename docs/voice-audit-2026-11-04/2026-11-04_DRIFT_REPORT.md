## docs/human-interaction-engine-plan.md

- No drift detected within the documented six-stage V1 implementation. This finding compares source behavior and tests; the document's explicit limits on semantic turn detection, acoustic acceptance and native voice expressiveness still apply. It is not certification against every aspiration in the original conversation.

## docs/superpowers/specs/2026-11-02-voice-layer-consolidation-design.md

- Low priority, historical documentation: the target diagram places wake model binaries under `voice_layer/assets/`, while `voice_layer/standby.py:117` locates the Hey Jarvis ONNX model in the installed `openwakeword` package. Hello Jarvis uses an optional external Vosk model. Source assets contain PCM acknowledgements, not the promised wake binary.
- Low priority, historical documentation: the removal list includes `audio/plugins/standby.py`, which remains as a compatibility re-export of `voice_layer.standby`. It is not an independent second implementation.
- Low priority, historical documentation: the CLI plan specifies a `jarvis_voice` fallback. `bin/jarvis-voice` directly invokes `voice_layer`; compatibility imports are supplied by the separate `jarvis_voice` alias. No fallback is present in the launcher itself.

## universal-voice/README.md and the later standalone freeze

- Major distribution gap relative to the later freeze, not a code mismatch: the local standalone directory has `.voice_lock.json`, `scripts/verify_voice_lock.py`, and freeze instructions, but the downloadable source archive predates those files and contains none of them. The wheel also has no lock baseline. Extracting/installing these artifacts does not reproduce the local lock enforcement. Package source bytes match the local source and published checksums pass. Explicit permission to update/rebaseline protected packaging would be needed to distribute the newer protections; none was inferred from this testing request.
- Unvalidated compatibility: documentation lists Linux families as intended targets, but no clean dependency installation, distro VM matrix or alternate CPU test exists in the available verification evidence. The README discloses this. It remains an acceptance gap rather than a proven portability defect.
