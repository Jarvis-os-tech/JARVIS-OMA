# Situation-specific spoken acknowledgements

Replaced the three-word rotation as the normal acknowledgement path with
15 cached phrases selected by the admitted task, validated control arguments,
or explicit intent in the current transcript. Examples include reading a
file, searching online, inspecting the screen, using the terminal, opening
an app and adjusting a specific desktop control. Getters never imply a
setting was changed. Negative or merely quoted/discussed search requests
do not become claims of a search.

Provider instructions allow natural wording based on the actual request,
while the local cached phrases cover provider delay without another model
round trip. Known task admission supplies the strongest context; generic
thinking phrases are used when the task is not yet known. They retain mute,
standby, active-speech, stale-turn and already-started-answer guards and the
one-acknowledgement budget. Repeated still-working recordings remain disabled.

Four phrases were generated in the existing Aoede voice. The speech provider
then returned HTTP 429 for its daily free-tier speech-generation limit of
10 requests. The other 11 phrases use the existing offline eSpeak voice;
they intentionally remain available without waiting for a quota reset or
making a network request during a conversation. The voice difference is
reported to the user. `voice_layer/assets/acknowledgements.json` records
the exact text, voice origin, duration and hash of each recording.

The real local result now uses response-priority playback, replacing queued
acknowledgement audio instead of sitting behind it. Cached phrase selection
is synchronous and does not delay the task's executor admission.

The installed release copies only the voice daemon, acknowledgement selector
and acknowledgement assets, preserving the existing runtime modules and
rollback parent. Its manifest records the exact daemon and asset hashes.

Verification: 156 focused tests passed. Activated release:
`20261102-223701-situational-acknowledgements`; the cloud connection recovered.
The physical Mic1 source was muted at final readback, and the private AEC
source correctly matched it. That user/system mute was preserved.
