# Direct conversation with JARVIS OS

The immediate priority is natural communication between the user and their
computer. This pass changes the existing voice session and tool routing; it
does not introduce another assistant, shell, dock or speech engine.

## Interaction

- Wake from standby with “Hey Jarvis.” Once conversation is active, follow-ups
  do not need a repeated wake phrase or command prefix.
- Speak ordinary requests. JARVIS uses the attached OS tools when a request is
  clear and reports their actual result in a short, direct reply.
- Follow-ups such as “no, make it thirty,” “a little lower,” or “the other
  window” retain the relevant context. Unclear targets require one focused
  question. Earlier effects are not silently undone or replayed.
- Questions and ordinary conversation receive a spoken answer. They do not
  automatically launch tools, widgets or a background agent.
- Stopping the current answer keeps conversation available. Explicit standby
  pauses conversation until recalled. Neither action cancels background work.
- Wake acknowledgement is brief and natural; it does not recite a system report
  or servile roleplay.

The shared persona supplies these rules to both voice configuration builders.
Superseded blanket standby rules were removed from the daemon and alternate
harness. The standby tool description now matches the shared policy. The local
intent gate accepts explicit natural requests such as “don't speak until I call
you”; it continues to reject standby for “stop talking” and brief corrections.

These are instruction and routing improvements, not a guarantee of perfect
speech recognition, reference resolution or acoustic interruption. Existing
turn timing, Aoede, barge-in configuration and disabled synthetic fillers are
preserved.

## Verification

103 focused persona, intent, phone-target, configuration and release checks pass.
Another 16 selected daemon and speech checks pass. The broader daemon run stalled
after 38 checks in this environment and was interrupted; it is not reported as a
passing full suite. Preparation compiles Python, loads the installed manifests,
validates the voice SDK setup, and verifies model-result notice delivery.
The deployment regression also checks that wake behavior and old standby rules
are refreshed while unrelated installed code is retained.

Before activation the existing voice service was connected with automatic
barge-in enabled, but its JARVIS audio source was system-muted. Restarting the
service recreated that virtual input unmuted; its original muted state was
restored on the new JARVIS virtual source. The physical source was not changed.
Mute persistence when the virtual source is recreated remains a separate runtime
limitation. An unmuted input is needed for the following physical conversation check.

An isolated five-turn Gemini Live session passed with synthetic controls and
discarded audio: ordinary conversation used no tools; explicit volume 35,
“no, make it thirty,” and “a little lower” produced fixture values 35, 30 and
25 with a spoken reply after each result. “Don't speak until I call you” invoked
standby and produced a brief wake reminder. No real desktop actions were run.
The fixture inputs, tool calls and reply transcripts are saved in
[the provider check](DIRECT-CONVERSATION-PROVIDER-CHECK-2026-11-03.jsonl).

Activated build: `20261103T031451981271Z-system-persona`. Changed-file hashes
match the staged candidate. Both operational services are active, and the voice
session connected with Aoede and automatic barge-in enabled. Local synthetic
fillers remain disabled. The previous build is retained for rollback.

## Physical acceptance session still required

| User interaction | Expected behavior |
| --- | --- |
| Wake once, then ask a second question | Conversation continues without repeating the wake phrase |
| “Set speaker volume to thirty-five percent”; “no, thirty”; “a little lower” | Same target, revised values, short replies grounded in tool results |
| “Move that window” with more than one plausible target | One question identifying the missing target |
| Interrupt an explanation with “wait, make it shorter” | Previous audio stops; the revised answer follows |
| “Stop talking” | Current answer ends; conversation remains available |
| “Don't speak until I call you” | Standby; existing background tasks remain independent |
| Ask about a current system problem | Fresh observations, a clear explanation, no invented diagnosis |

Synthetic provider checks do not establish microphone recognition, echo
rejection, physical speaker output or the quality of conversation in the room.
