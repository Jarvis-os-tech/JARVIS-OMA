# Acknowledgements for replies that take time

The voice controller now waits 1.2 seconds for an ordinary answer before
adding a short thinking acknowledgement. When an action is still running,
it uses the earlier 650 ms threshold: browser/system work gets “On it”,
agent work gets “Sure”, and file inspection or thinking gets “Hmm”/“Ah”.
Fast answers and spoken preambles suppress additional short fillers.

A request can play one short acknowledgement and one longer waiting notice.
The waiting notice is spaced five seconds after the last spoken feedback,
so silent tool-progress events cannot postpone it indefinitely. Neither
notice resets the provider response watchdog. Mute, active speech, standby,
greetings, wake confirmations and interruption handling retain their guards.
Missing or disabled short fillers cannot starve the longer waiting notice.

The model prompt no longer forces a filler tool call as its first output;
it can answer fast questions directly and leave delay feedback to the local
controller. Configured filler recordings and the existing tool remain valid.

Validation: **93 tests passed** across acknowledgement timing, filler playback,
reply recovery, daemon behavior, parallel reception and crossfade handling.
Scenarios cover fast answers, contextual work acknowledgements, recent
speech, repeated silent task progress, unavailable/disabled short clips and
duplicate acknowledgement suppression.

Installed release: `20261102-073832-ack-cadence`. Its previous release remains
available for rollback. Only the installed daemon changed; its audio assets,
device code and memory code were retained.

Speaker-monitor verification using the installed code and simulated continuing
work confirmed exactly one “On it” acknowledgement followed by one spaced
waiting notice. The captured clips matched their bundled recordings at
normalized correlations **0.995** and **0.986**. No real web/task action was
executed. The low-latency recorder captured the complete waiting phrase; the
first capture used its default buffer and truncated that phrase's end.
The running service is connected, unmuted and has no reported error.
