# Real-time assistant behavior

JARVIS keeps microphone capture, provider reception, desktop tools and device
playback running concurrently. Routine replies should be brief; substantial
work uses the existing background task and agent tools so conversation can
continue. Completed and failed tasks already produce a queued result notice.
The locked voice core remains unchanged.

## Useful proactive alerts

The default `[proactive]` settings implement useful alerts and task progress
without interrupting conversations:

- Check every 30 seconds while the voice session is active. Pause and stop-all
  controls prevent observations and new proactive work. The observer belongs to
  the assistant process and keeps running across provider reconnects and voice
  standby; delivery waits for a connected, unmuted and quiet conversation.
- Refresh an already-connected primary Calendar every 120 seconds. Re-evaluate
  its cached events at every observation, so meetings enter the ten-minute
  reminder window even when no new request is made. Refresh across local-day
  boundaries. Cancelled or rescheduled queued notices are discarded after the
  next successful refresh; data older than two refresh intervals is suppressed.
- Announce native Omarchy reminders within one minute of their scheduled time.
  Reading a future timer never authorizes starting a task or delegating work.
- Report critical local conditions: battery at or below 15% while not charging,
  storage at or below 5% free, and available memory at or below 5% for two
  consecutive observations. Unknown sensor values remain unknown. Recovery
  hysteresis prevents repeated alerts; recovered queued alerts are discarded.
- Wait for user speech, tool execution and local playback to finish, then allow
  two seconds of quiet before an unsolicited notice. Space notices by at least
  30 seconds. Mute and standby suppress delivery. Expired alerts are dropped.
- Daily focus suggestions are disabled by default. Observations do not grant
  permission to send messages, change settings, run suggested tasks or modify
  Calendar events.

The event ledger provides persistent calendar reminder deduplication. Local
health episodes and notice admission use bounded in-process state. A service
restart may report a still-critical health condition again. A calendar change
made after the last refresh cannot be known until another successful refresh.

Change the observation cadence, quiet interval, cooldown, or individual feature
toggles in `config.toml`; examples are in `config.toml.example`.
`proactive.enabled = false` disables automatic observations. Explicitly queued
authorized work and existing task-result notifications remain independent.

## Memory and status

Saved memory context is loaded on its existing bounded worker before the first
provider connection, with a one-second startup budget. Unavailable memory does
not prevent voice startup. Full memory tools remain available after connection.

Ask “What is your voice status?” to invoke `get_assistant_status`, or “What can
you do?” to invoke `list_capabilities`. Status reports mute/standby, pending
notices, observation checks, context availability and response timing metadata.
It does not return speech text or credentials. Reading proactive status does
not resume paused work.

Response timing measures the latest recognized-input update or typed request
observed by the client to the first following provider PCM. It excludes
microphone endpointing and speaker buffering. Provider transcriptions can
arrive out of order, so these samples are observations, not acoustic latency
or a count of user turns. Unknown timing is `null`; sample history is bounded.

## Transport and verified actions

Native PipeWire capture and playback use a C companion with preallocated
lock-free rings. Microphone writes take priority over tool results; optional
vision never waits behind either. A capture backlog or microphone writer p95
above 20 ms suppresses video. Interruption advances a generation fence so stale
screenshots cannot enter the new turn. Cancelling a video write already in
flight reconnects the transport because its delivery is uncertain.

The initial Live session exposes 35 essential and domain-routing tools, while
the full registry remains available through validated on-demand domain calls.
Desktop mutations bind and check the target window before input. Clicks and
scrolls require observable accessibility changes within 300 ms; missing evidence
returns `unverified_effect` with an accessibility/CLI fallback. Surface changes
alone do not establish that the user's intended goal succeeded.

Tool call identities and ready responses survive session resumption. Interrupted
actions with uncertain outcomes are reported explicitly and never replayed
automatically. Fresh sessions receive a fresh identity namespace. Connection
state and revision are published together so the Island clears stale speech
indicators during reconnects.

Background code-change announcements require stable SHA-256 evidence, repository
status checks and isolated syntax smoke tests. These establish structural
validity, not functional correctness. Model replies without verified changes
are announced as responses received rather than verified work completion.

## Verification coverage

Tests cover cached calendar events entering the reminder window, refresh
invalidation, pause/disable behavior, ongoing observation, native timers,
resource recovery, quiet/cooldown delivery, first-session memory, status tool
wiring, and response observations. Existing scheduling, desktop skill and
proactive runtime tests remain part of the verification.

Architectural regression tests also cover video backpressure and generation
fences, native ring scheduling, focus theft and unchanged GUI surfaces,
domain schema validation, reconnect duplicate-call suppression, Island state
clearing, and independent background workspace evidence. The complete offline
suite on 2026-10-27 passed 1,300 tests and 385 subtests; two opt-in sandbox tests
were skipped. Native C self-tests cover adaptive jitter buffering and 100
cancellations. These results do not measure audible response latency or
double-talk quality.

The same-day silent PipeWire device check passed 30 turns, 20 interruptions and
30 seconds of paced jitter playback with zero starvation or dropped capture
frames. Maximum render interruption acknowledgement was 11.6 ms; owned-helper
recovery took 109 ms. These are local transport observations, not microphone to
spoken-answer latency. The primary service was restored with its prior mute
setting.
