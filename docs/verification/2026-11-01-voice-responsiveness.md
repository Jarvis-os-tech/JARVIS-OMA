# Voice responsiveness repair

Observed: accepted speech could remain silent, including a logged 36-second
response timeout. Task calls sometimes completed without audible follow-up.

Confirmed causes:
- Local filler playback set `_reply_started`, so a function-call boundary
  revoked authorization before the real provider answer arrived.
- The provider receive loop awaited desktop actions, preventing it from
  processing audio, interruptions and session updates until those actions ended.

Repair in `jarvis_voice/daemon.py`: distinguish filler from answer audio;
preserve intermediate tool boundaries; run actions sequentially in a bounded
worker alongside reception. Queued actions retain their original speech turn
and playback generation, and stale actions receive `not_run`. Session shutdown
cancels and awaits both workers. The response watchdog excludes queued work.

Verification:
- The three initial regression probes failed before the fix.
- Final focused voice checks: **138 passed** (including five new regression
  tests in `tests/test_voice_responsiveness.py`).
- Full suite with importlib collection: **1089 passed, 3 failed**, plus 142
  passing subtests. Failures concern a memory-recording mock signature, a test
  launcher shebang containing a space, and divergent phone manifest mirrors.
  These files were not changed for this repair. The full run preceded the fifth
  regression test; that test passed in the final focused run.
- Live installed-service check at 22:08 IST: local filler and
  `get_assistant_status` completed; the real spoken answer followed, producing
  64,802 provider PCM bytes and returning to idle/listening. First PCM chunk
  reached playback in 41 ms. This was a text-driven provider/tool/playback
  check, not an end-to-end microphone recognition measurement.

Installed release: `20261101-220719-voice-responsiveness`.
Previous release retained: `20261101-215843-release-stability`.
Only the installed daemon source changed; companion memory and device changes
already present were preserved. The existing checkout edit boundary was
preserved; this investigation acquired no boundary ownership token.

Provider connection handshakes also timed out intermittently before and after
the repair. The service recovered and connected, but this patch cannot
guarantee cloud/network latency or eliminate every possible pause.

## Spoken reply guard

Further optimization installed as `20261101-222210-spoken-reply-guard`:

- After five seconds without progress, play one cached spoken waiting notice
  per request. It does not mark the request answered or reset its watchdog.
- When a turn finishes without speech, request one spoken summary using the
  existing conversation and tool results. Tool execution is denied during
  recovery, so this cannot repeat a task. A spoken preamble before a tool call
  does not count as its final result.
- If that recovery also finishes empty, speak a local failure notice and
  return to listening. When an active request loses its connection, play the
  local failure notice after session workers stop, then reconnect normally.
- Mute, standby and active user speech suppress these notices. A new speech
  turn supersedes any recovery waiting for the send lock.
- Bound connection setup to 12 seconds and typed/greeting/wake sends to three
  seconds. Established conversations have no connection-setup deadline.

The two PCM assets are short, pre-rendered Aoede notices: mono PCM16 at 24 kHz.
They need neither a cloud call nor a new speech package at playback time.

Final focused verification: **150 passed**. This includes 12 reply-guard tests
covering empty results, recovery limits, no repeated actions, new-input races,
privacy, local playback, audio assets and connection setup deadlines.

Full suite: **1109 passed, 1 failed**, plus 142 passing subtests. The remaining
failure is the existing launcher fixture's shebang containing a space. The
suite needed the orchestration test-helper directory on PYTHONPATH because a
new orchestration test imports its helper by basename.

Live installed-service status lookup returned spoken audio. A separate probe
using the installed code deliberately dropped its first cloud answer, then
recovered **37,922 bytes of new provider audio**, completed the turn and had
no tools available. Its first connection attempt timed out; one retry
succeeded. This verifies real cloud recovery but is not a microphone test or
a guarantee against provider outages. Source and installed-daemon hashes match.

## Existing conversational fillers

The existing filler hook referenced external recordings that were absent on
this installation; its fallback was a procedural 180 Hz tone. The active voice
daemon now has bundled, preloaded Aoede recordings for “Hmm”, “Ah”, “Sure” and
“On it”. Explicit configured recordings retain priority.

The five-second waiting guard uses this same hook. A request gets at most one
short filler; a new user turn resets that budget. If an early filler already
played, the waiting guard can instead use the longer status notice. Failure
feedback remains explicit. Muting, standby, active speech and the existing
disable-fillers preference suppress short fillers. Filler playback never marks
the provider answer started. The active daemon no longer constructs the old
DownstreamRouter or generates a placeholder tone to play a filler.

Verification: **72 passed** across spoken-filler, reply-guard, daemon,
responsiveness and crossfade checks. This includes real PCM asset validation
and tests for each context, per-turn limits, alternate thinking sounds and
privacy/preferences. Only the daemon and bundled audio are installed; previous
runtime state and device/memory code are preserved.

## Automatic acknowledgement trigger repair

The first filler deployment still depended on a provider tool call or the
five-second delay warning. A normal reply could therefore produce no filler
at all. The new regression probe (a closed request waiting 800 ms with no
cloud tool call) failed before this repair and passes afterward.

Installed release `20261101-224343-automatic-filler-ack` arms a local 650 ms
timer when microphone ActivityEnd is sent, or when a text request is
dispatched. The 250 ms monitor triggers the cached filler independently of
the cloud. Actual answers, active speech, mute, standby, interrupted turns,
greetings, wake acknowledgements and background announcements suppress early
fillers. One filler remains the per-request maximum. Runtime status includes
the cumulative filler count and last context for direct verification.

Verification: **81 passed**, including the failed-before/passing-after trigger
probe, microphone upload-boundary arming and seven early-ack suppression
cases. Real speaker-monitor capture confirmed the explicitly requested
“On it” clip (normalized correlation **0.995**). After installing the trigger
repair, a normal request that explicitly prohibited cloud tool calls played
the local “Hmm” clip at **724 ms** after dispatch. Speaker capture matched
that recording at **0.997**; runtime reported exactly one local filler and
the provider answer followed. This validates speaker output and automatic
request dispatch; physical microphone recognition was not part of that live
probe. Previous release retained for rollback.
