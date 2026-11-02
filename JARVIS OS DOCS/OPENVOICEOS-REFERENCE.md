# OpenVoiceOS reference for JARVIS OS

Reviewed: 2 November 2026. Scope: official organization overview, technical
manual, and the component READMEs linked below. This is an architecture review;
no OVOS packages have been installed or tested with JARVIS.

## Role in the product plan

The [OpenVoiceOS link](https://github.com/OpenVoiceOS) points to an organization
containing a collection of related projects. Its
[technical manual](https://openvoiceos.github.io/ovos-technical-manual/)
describes a modular voice platform that can be adopted component by component.
This makes it a useful upstream reference for our Omarchy transformation.

The following adoption decisions are JARVIS design proposals inferred from
the upstream documentation. They are not claims of existing interoperability.

## Component map

| Upstream component | Documented responsibility | Proposed JARVIS use |
| --- | --- | --- |
| [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager) | Plugin discovery, base classes, configuration, and loading through Python entry points; STT, TTS, wake word and VAD plugin interfaces | Evaluate a narrow adapter for optional local speech providers |
| [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) | Microphone input, wake word, VAD, STT, and transcription events | Study its listening states and endpoint settings alongside our existing voice loop |
| [ovos-audio](https://github.com/OpenVoiceOS/ovos-audio) | TTS synthesis and audio playback as a bus-connected service | Reference for local speech output and fallback-provider configuration |
| [ovos-core](https://github.com/OpenVoiceOS/ovos-core) | Intent processing, skills, and optional LLM/persona fallback | Reference for routing routine commands before open-ended reasoning |
| [ovos-messagebus](https://github.com/OpenVoiceOS/ovos-messagebus) | WebSocket event exchange among services | Evaluate an isolated compatibility bridge if a selected OVOS skill needs it |

## 1. Speech provider interfaces

Our current foundation uses Gemini Live for bidirectional audio. A local speech
path would typically require separate recognition, command processing, and
synthesis stages. These paths have different timing and cancellation semantics.

Proposed JARVIS interfaces should expose provider availability, start/stop,
streaming support, language, sample format, deadline, and cancellation. Reuse of
an OVOS provider depends on its specific implementation and dependencies. A
plugin being discoverable does not establish offline operation or streaming.

Keep provider configuration explicit: local-only, cloud-enabled, or hybrid.
Automatic fallback should respect the selected mode; local-only must never send
audio to a cloud provider during an outage.

## 2. Listening and conversation state

The Dinkum listener documents configurable microphone, wake-word, VAD, and STT
modules, speech/silence timeouts, and experimental continuous and hybrid
listening. Its continuous-listening documentation warns that output speech can
be heard as new input. See the
[listener configuration](https://github.com/OpenVoiceOS/ovos-dinkum-listener#configuration).

For JARVIS, evaluate wake word → active conversation → follow-up window → standby.
Measure false wakes, missed wakes, clipped words, slow speech, and interruptions
with real speakers in the target room. Echo suppression, acoustic echo
cancellation, and barge-in require distinct checks. VAD alone cannot establish
that captured speech came from the user.

## 3. Deterministic command routing

OVOS core documents skills and a persona/solver fallback for requests that skills
do not handle. See [core and persona support](https://github.com/OpenVoiceOS/ovos-core).

Proposed JARVIS routing: cancellation and mute first, then explicit supported
desktop commands, then contextual workflows and general reasoning. Reuse our
typed control tools and result verification for each desktop operation.

A local command path should make a small documented set of actions available
without the conversational provider. This requires local recognition and
response output as well as local execution; a local actuator alone does not make
the spoken workflow offline-capable.

## 4. Events and trust boundaries

The OVOS message bus broadcasts each message to all connected clients and ships
with a loopback host default. This is an event distribution mechanism; the
documented broadcast behavior is not per-client authorization. See the
[bus README](https://github.com/OpenVoiceOS/ovos-messagebus).

Proposed JARVIS event fields: event type, schema version, request ID, turn ID,
execution generation, producer, timestamp, and bounded payload. Define events
for listening, transcript readiness, action request/result, speech completion,
interruption, and task completion.

If an OVOS bridge is implemented, validate incoming messages, map selected events
to typed requests, and apply JARVIS policy before execution. A bus message must
not become a user confirmation. Restrict which transcript, memory, and credential
data can enter the shared event stream.

## 5. Audio output and voice personality

OVOS audio separates synthesis and playback and documents configurable TTS
fallback and dialog transformers. Its README also describes a transition from
legacy audio/OCP toward ovos-media; verify the chosen release before depending
on those media APIs. See [ovos-audio](https://github.com/OpenVoiceOS/ovos-audio).

For JARVIS, define one output owner per session so a fallback TTS engine cannot
speak over live-model output. A cancelled turn must cancel synthesis and discard
queued audio. Persona styling should preserve verified facts, failures,
confirmation wording, and numeric results.

## Proposed evaluation sequence

1. Inventory the existing JARVIS voice interfaces and choose one local STT and
   one local TTS candidate from the plugin ecosystem after examining their own
   documentation, model requirements, and licenses.
2. Build an isolated provider experiment using recorded, consented test speech.
   Record pinned versions and hardware requirements.
3. Compare recognition accuracy, time to first audible response, interruption
   behavior, CPU/RAM use, and operation with networking disabled.
4. Connect one harmless read-only request through the existing JARVIS router.
   Then evaluate one reversible action with observed-state verification.
5. Consider selected OVOS skills through a restricted adapter if they provide
   a clear capability benefit. Examine each skill's code and dependencies.

Acceptance: one owner for microphone/playback; no duplicated action on reconnect;
working cancellation; observable provider selection; an honest unavailable
response; no network access in local-only mode; and results reproducible on the
target Omarchy machine.

## Adoption status

Approved by this document for architectural study: modular speech providers,
explicit listening states, command-first routing, and event schemas.
Implementation remains proposed. No claim is made that the OVOS installer
supports our exact Omarchy setup or that existing OVOS skills work unmodified
inside JARVIS. Review component, plugin, and model licenses individually before
redistribution.
