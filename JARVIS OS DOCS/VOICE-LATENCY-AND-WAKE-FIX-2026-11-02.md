# Faster voice feedback and reliable standby release

The user explicitly chose **400 ms of silence** to finish a speech turn.
The active configuration had retained 100 frames (two seconds). It now uses
20 frames. Explicit longer pause configurations remain supported.

Cached conversational acknowledgement fallback now waits 150 ms after the
uploaded turn instead of 1.2 seconds, with a 50 ms monitor interval instead
of 250 ms. Known long-running tasks retain immediate acknowledgement at
task admission. User speech, mute, standby and already-started answers still
suppress fillers; each turn gets at most one.

Real response audio removes remaining queued filler or waiting-notice
frames, with a 20 ms blend into the answer. It preserves the playback
generation and interruption fences. Already-written device audio is not
retracted. Answer completion and stale-notice safeguards from the preceding
repair remain in place.

Standby now preserves wake requests arriving before its listener starts,
allows manual wake to interrupt the arming delay, and retains early wake
audio buffered by a fresh capture stream. Existing reused-queue stale-frame
draining remains. Wake while already awake cannot cancel the next standby.
The arming delay is 100 ms; recognition confidence thresholds are unchanged.

## Verification

- 154 focused tests passed, including playback, acknowledgement timing,
  answer completion, speech turns, microphone ownership and standby races.
- A real-time synthetic-frame check used the actual speech gate, upload
  loop, response monitor and playback scheduler with an in-memory output:
  activity end at 398 ms, acknowledgement queued and first output write at
  589 ms after the final speech block. This measures local software timing,
  not cloud generation or physical speaker latency.
- The installed wake model recognized the buffered Hey Jarvis fixture with
  the updated controller. Confidence and VAD thresholds were not lowered.
- Two actual user turns after activation queued cached acknowledgement
  177 ms and 160 ms after upload completed. Both then received provider
  answer audio, including a successful application-launch task. The cloud
  answer took 3.71 s and 3.15 s after upload; that remaining provider/task
  time is covered by the prompt local acknowledgement.
- Both operational services were active. The new private microphone was
  unmuted at 100%, with no microphone issue or reported voice error.

## Installed release

`20261102-161900-fast-voice-wake`, preserving the prior release
`20261102-153837-answer-feedback-fix` for rollback. Activation waited for
speech and tasks to finish. JARVIS was left awake and connected.

Configuration backup:
`~/.config/jarvis-voice/config.toml.bak.20261102-161900`.

During this work another workspace change consolidated implementation into
`voice_layer`. The tested implementations of daemon, config, playback,
standby and echo were installed into the existing runtime's `jarvis_voice`
package, retaining its other modules. Exact source hashes are recorded in
the installed `release.json`. No unrelated workspace or runtime changes
were included in this release.
