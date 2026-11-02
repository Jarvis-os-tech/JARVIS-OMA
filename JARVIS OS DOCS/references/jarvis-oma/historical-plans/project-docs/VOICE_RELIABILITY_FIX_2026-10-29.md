# Missed speech and cut replies — 2026-10-29

## Reproduced causes

1. **Capture backlog during idle/network stalls.** The explicit-activity runtime still sent zero PCM at 50 Hz while idle or muted. A one-second queue could overflow on a short stall, renewing the voice session and losing input.
2. **Playback overflow during fast generation.** Provider audio generated faster than physical playback could exceed the old ten-second backlog, cutting the reply and renewing the whole connection.
3. **Thinking-only interruption acknowledgement.** Continued speech after a pause could be treated as an interruption while the previous answer was still thinking. The code waited for completion of an audio generation that had not started and discarded the new response as stale. The live reproduction recorded 93,120 discarded bytes with no recognized reply.

The running service had zero systemd restarts. The recorded failures were repeated internal voice-session reconnections, including buffer overflows, transport timeouts, and provider connection errors.

## Changes

- Idle/muted PCM is captured locally for metering but is not sent or queued outside an explicit speech activity. Activity boundaries and voiced PCM remain ordered; interrupted capture emits an end marker.
- Active capture queue is bounded to four seconds, allowing the existing three-second send deadline to recover before the old one-second capacity is exhausted.
- Playback is bounded by both PCM bytes (60 seconds/2.88 MB) and item count. Playback still starts with the first chunk; increased capacity adds no mandatory startup wait. Over-cap rejection is atomic and stop clears queued bytes immediately.
- Distinct microphone/playback backlog errors aid diagnosis. Overruns are recoverable and start a fresh cloud session rather than replaying a truncated turn or eventually killing the daemon.
- Tool-result transport has a five-second timeout rather than holding the send lock indefinitely.
- Interruption waits for old-response acknowledgement only when old model output had actually started. Thinking-only continuation accepts the new reply without waiting for a nonexistent old-audio completion.
- Existing barge-in, echo guards, tool permissions, memory, camera defaults and locked audio core are preserved.

## Verification

- **129 targeted automated tests pass.** All seven protected voice-core files pass integrity verification.
- New regressions cover five seconds of idle/muted capture, a two-second active-speech send stall, a fast 12-second reply, bounded output memory, fresh-session overrun recovery, and the thinking-only acknowledgement bug.
- Live generated-speech check: eight seconds of idle with zero uploaded PCM frames, then three consecutive answered questions, three recognized inputs, three admitted turns and zero response timeouts. Replies returned 101,280, 82,562 and 74,882 bytes respectively. This check buffered output without physical speaker playback and excluded microphone audio and saved memory.
- A diagnostic connection reset also occurred before the successful run. These changes address reproduced local failures; provider/network outages can still interrupt a session.
- An earlier synthetic timeout test was stopped after its obsolete fixture spun; the fixture now distinguishes real model output from thinking-only state. The final full targeted run passes.
- Physical microphone and acoustic playback still require user confirmation after activation; no claim of perfect reliability is made.

## Files and rollback context

- Runtime: `core/stable_voice.py`, `core/stable_recovery.py`.
- New tests: `tests/test_core/test_voice_reliability.py`; existing voice/streaming/mute/interruption tests adjusted for no idle upload and accurate response-state fixtures.
- Snapshot before these changes: `issus voice/2026-10-29-before-reliability-fix/`.
- Other existing uncommitted work, including spoken-interruption support, was preserved.
