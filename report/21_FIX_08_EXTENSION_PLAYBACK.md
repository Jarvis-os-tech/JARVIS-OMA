# Fix 08: Extension playback contract (E02)

Date: 2026-10-23. Status: implemented and tested. No device streams opened, running daemon restarted, or spoken end-to-end test performed.

## Change and rationale

`audio/extension.py` now captures `active_generation` before running output processors, then passes processed PCM to the existing public `enqueue_playback(..., generation=...)` method. It no longer bypasses the engine by inserting raw bytes directly into its generation-tagged queue. The engine handles slicing, mute gating, generation validation, and speaking state without any locked-file changes.

Capturing generation before processing matters: if processing overlaps a barge-in, the engine rejects old audio rather than tagging it as part of the new generation. Processor-dropped audio still produces no playback.

The wrapper is declared around NativeAudioEngine. This change does not add compatibility with the separate native companion backend, whose API differs.

## Evidence

New tests instantiate the real NativeAudioEngine without starting hardware streams or replacing its methods. Before the fix, three tests failed: queue format/slicing, mute gating, and stale-generation rejection. Processor-drop behavior already passed.

After repair, new playback tests plus existing voice-lock/extension tests: 13 passed. The pre-existing unlocked composition test now asserts the public API contract. All seven locked voice files verified intact. Codebase reference regenerated.

VERDICT: PASS

## How to check

Restart JARVIS normally to load the changed module. You can say:

> Jarvis, count slowly from one to ten.

Then interrupt with:

> Jarvis, stop.

This is only a normal voice/playback smoke check. The live runtime does not currently instantiate ExtendedAudioEngine, so normal spoken playback does not exercise this repaired extension method. Do not interpret a successful count or interruption as direct proof of E02.

The direct check is:

```sh
.venv/bin/pytest -q tests/test_audio/test_extension_playback.py
```

Expected: 4 passed. These check actual engine queue semantics without playing sound.

## Scope and policy

Planning: compact; context depth: dependency; verification depth: impact; delegation: none. Scope: unlocked extension, new extension tests, unlocked composition-test assertion, and report artifacts. No monkeypatching or overriding core voice functions. Fixed findings so far: S07, S05, S04, E01, S08, S09, E06, E02. Other findings remain open.
