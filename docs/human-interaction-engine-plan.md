# JARVIS human interaction engine — six-stage V1

Implemented in the source checkout on 2026-11-04. This builds on the existing voice layer and execution system. The initial build did not restart the running voice service. The reviewed stale-progress fix was subsequently certified and deployed to the active checkout-based service on 2026-11-04; see the deployment note below. The Memory Engine remains separate. Automated checks establish software behavior, not audible quality or real-room acoustic performance.

## 1. Listening, thinking pauses and interruption

`voice_layer/config.py` and the example now default to 60 silent 20 ms frames (1.2 seconds). Shorter breathing/thinking pauses remain in the current turn. Existing explicit configuration values take precedence. This is bounded pause tolerance, not semantic end-of-turn understanding; longer thinking pauses can still close a turn. The longer default adds up to 800 ms compared with the previous 400 ms setting.

`voice_layer/daemon.py` no longer discards the first 350 ms of potential barge-in during playback. The existing speech and playback-reference echo evidence gates still decide whether to admit an interruption. Stopping speech fences old audio; it does not automatically cancel committed task effects. Existing correction and task-cancellation rules continue to apply. Automatic interruption requires `barge_in = true`; a deliberately configured half-duplex profile is respected.

## 2. Contextual acknowledgements

Admitted tool and local-command work uses its existing contextual cached phrase: for example, search uses “I'll look that up.” Generic waiting and model-requested fillers use short neutral clips; transcript wording alone cannot produce an action-specific claim. Deferred acknowledgements snapshot the action arguments and replay only for current-turn work still in flight. Getters and invalid control names do not announce a setting change.

There is one acknowledgement budget per user turn. A fast answer, an already-spoken acknowledgement, rejected work, user speech, mute or standby suppresses another acknowledgement. If a generic acknowledgement has already played before tool admission, the system preserves that budget instead of speaking twice. Missing contextual recordings use the existing bounded fallback. The existing answer path supersedes queued filler.

## 3. Truthful progress communication

`voice_layer/background.py` polls the existing task presentation journal through `voice_layer/progress.py`. Reads run outside the audio event loop. The existing event validator checks snapshots; fixed spoken wording describes running work, measured completed steps, or a confirmation blocker. Task title/result prose cannot instruct the voice through this path.

Updates coalesce per task, reject older revisions/generations, clear on completion or disappearance, and have a global 20-second delivery cooldown. Mute, standby, disconnection, active user speech, foreground replies/tools, greetings and wake transitions suppress progress speech. Existing terminal-result notices retain priority and acknowledgement ownership. This handles background task progress; it does not interrupt an outstanding foreground tool call with synthetic progress turns. Delivery state is bounded and local to the voice process.

## 4. Natural delivery, context and emotional care

The instruction used by the native audio model now explicitly guides meaningful rhythm, variable sentence length and pauses, concise task results, and proportionate technical explanations. It retains one JARVIS identity and suppresses duplicate acknowledgements. Existing context resolution and focused clarification rules remain active.

Explicit expressions of distress receive gentle attention. Pitch, loudness, accent or speaking rate are not treated as evidence of an emotional diagnosis. Expressive delivery uses the existing native voice path; no separate emotion classifier or additional TTS model was added. Instruction tests cannot establish that the provider audibly follows these directions.

## 5. Sparse listening backchannels

`voice_layer/interaction.py` proposes the existing short “Hmm” listening cue only for a long first-person English narrative with an available transcript, at least eight seconds of speaking, a safe pause, and enough time for the complete clip before the turn closes. Requests, questions, negation, uncertain/no transcript, task activity, previous task acknowledgement and private states remain silent. The policy allows one cue per turn with at least 20 seconds between cues. The existing `fillers.enable_local_fillers` preference controls this audio too.

Automatic cues additionally require the session's echo cancellation to be active. The first 80 ms of microphone input during a cue is held for reference comparison: matched echo is replaced by silence, while distinct resumed speech is replayed without losing its PCM or turn boundaries. Speech resumption or a real answer stops the cue. `voice_layer/playback.py` uses an independent playback epoch to cancel the cue without invalidating queued microphone frames. Backchannels use the same output queue as responses.

The narrative rule is a conservative English heuristic, not a semantic or emotional model. The system prefers silence when eligibility is uncertain. Real acoustics, transcript timing and whether this cached voice sounds consistent still need listening tests.

## 6. Integration and acceptance

`tests/test_hie_pipeline.py` covers narrative → pause → cue → resumed speech, matched echo rejection, privacy/readiness suppression, answer priority, and deferred acknowledgement races. Playback race tests cover cancellation during priming, process startup and drain. Six HIE contracts were added to `tests/behavior/contracts.json`, so the existing release gate requires these behaviors and rejects missing/skipped checks.

Verification results and any failed attempts are recorded in `JARVIS OS DOCS/HIE-BEHAVIOR-GATE-2026-11-04.json` and `JARVIS OS DOCS/HIE-VERIFICATION-2026-11-04.json`. No live provider, microphone or speaker acceptance is claimed.

## Later listening test

Use the updated checkout/release with `barge_in = true`, `turn_silence_frames = 60`, and local fillers enabled. Existing installed settings are not overwritten by the new defaults. Run only one voice instance. The existing CLI dependency check is `bin/jarvis-voice --check`; passing it does not start audio or verify the microphone.

| Scenario | Expected behavior |
| --- | --- |
| Speak, pause 0.6–1 second, then continue | One user turn; no premature answer |
| Finish a request and remain quiet | Turn closes after the configured pause |
| Ask for a search or file read | One appropriate acknowledgement if needed |
| Ask an immediate question | Direct answer; no extra acknowledgement after it |
| Tell a long story and briefly pause | At most one listening cue when transcript and AEC are available |
| Resume during the cue | Cue stops and the continued words remain in the same turn |
| Say “wait” just after an answer starts | With barge-in enabled, stop old playback and capture the correction |
| Run a background task | Sparse truthful stage/step updates during idle moments |
| Let a task fail or await confirmation | Preserve the actual failure/blocker; do not claim completion |
| Mute or enter standby | No listening/progress speech |
| Express frustration explicitly | Patient wording without claiming to detect your emotions |
| Ask “open that” with multiple possible targets | Ask one focused clarification |

Attribution: CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M. Adamek (Impact Brussels ASBL). Content CC-BY-4.0; code Apache-2.0. See `ATTRIBUTION.md`.


## Reviewed progress fix and deployment — 2026-11-04

Progress delivery now carries task identity, stream, generation, revision and sequence. After waiting for the voice send lock, it looks up that task again and suppresses obsolete updates before authorizing speech. A revision-only change refreshes a waiting delivery token without repeating an already delivered update. The regression test first demonstrated five stale-message failures; the corrected implementation passes completion, changed progress/revision, replacement, disappearance and privacy cases.

Validation: 49 focused checks and 209 required behavior-gate checks passed. Only the checkout-based voice service was restarted; the installed release pointer, device bridge and UI were untouched. The new process reconnected to Gemini with control and AEC active. Its AEC source inherited the physical microphone mute, which was left intact; microphone input is currently muted. No acoustic acceptance was performed. Evidence: `JARVIS OS DOCS/HIE-FIX-DEPLOYMENT-2026-11-04.json` and `JARVIS OS DOCS/HIE-FIX-BEHAVIOR-GATE-2026-11-04.json`.


## Listening cue profile correction and small refinements — 2026-11-04

A real listening test exposed an active-profile mismatch: the user's explicit 20-frame/400-ms endpoint overrode the new source default. A cue requiring at least 400 ms of quiet plus a 670 ms clip and 100 ms margin was impossible in that profile. The active profile was backed up and changed to 60 frames/1.2 seconds. The original voiced prefix of the Hmm recording was preserved; its low-level trailing tail was shortened with a20ms fade, reducing total length to460ms and widening the safe scheduling window. Its cache manifest hash was updated and verified.

Generic waits now rotate Sure/Okay/Hmm without promising On it before work admission. Their direct-answer grace increased from150ms to350ms; admitted task acknowledgements remain immediate. Native voice instructions refine fluid delivery and direct interruption recovery, including silence after a standalone stop-talking request. Speech evidence and echo calibration thresholds were not changed.

120 focused checks and209 required behavior-gate checks passed. Deployment used a temporarily muted startup to restore existing standby before input could be enabled; the temporary autostart/greeting changes were removed. Subsequent read-only status showed the service awake, connected and listening, with its AEC microphone unmuted and the1.2-second profile in place. Actual cue audibility remains for the next listening test; no claim of semantic turn detection or audible tone compliance is made. Evidence: `JARVIS OS DOCS/LISTENING-CUE-PROFILE-FIX-2026-11-04.json`.
