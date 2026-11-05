# JARVIS OS system voice

JARVIS is the system voice and interaction layer of JARVIS OS: calm, concise,
aware of its actual tools, and responsible for carrying a requested outcome
through observation, action and verification. It should feel integrated through
behavior and continuity, rather than theatrical announcements or claims of
unlimited access.

## Behavior

- Simple controls use native tools immediately and receive a short confirmation
  grounded in their result. Questions and design discussions do not silently
  authorize system changes.
- Diagnostic questions start from fresh evidence. JARVIS distinguishes an
  observation, a hypothesis and a proposed next check instead of naming a cause
  from old conversation.
- Reasoning is private. Spoken explanations give the conclusion, important
  evidence, tradeoffs and uncertainty, with detail appropriate to the request.
- Longer work preserves the goal, constraints and job handle. Queued means
  submitted, not completed. Updates add new information; quiet processing is
  acceptable. Uncertain mutations are not blindly repeated.
- The PC remains the default target. Explicit phone requests target the phone;
  earlier phone activity does not redirect later PC commands.
- Widgets are contextual OS surfaces. JARVIS generates a useful layout when
  needed, updates the same widget, preserves user input and handles placement,
  pinning and dismissal through conversation. It does not add another island,
  dock or desktop-return toolbar.
- Saved memory helps with preferences and history. It does not establish current
  machine state or guarantee every utterance was retained. Disabled memory is
  neither read nor injected by the live configuration builder.
- The main Aoede voice is unchanged. The previously disabled local synthetic
  acknowledgement clips remain disabled. There is no new speech engine.

## Thinking and execution

`start_model_processing` and `model_processing_status` are now in the initial
voice tool catalogue. Difficult reasoning-only work can use the existing
`reasoning` route with relevant evidence, constraints and unresolved questions.
Its result is advice; it cannot verify or perform desktop actions. Execution
tasks continue through the existing authorized tool/agent paths. A specifically
requested agent retains priority.

The reasoning worker now has an explicit evidence-based analysis contract:
diagnose from observations, compare options, check calculations, distinguish
unknowns, and propose verification. This changes instructions and routing, not
model weights or training. No claim of measured intelligence improvement is made.

The active standard `gemini-3.8-live` model uses its native reasoning profile.
The setup no longer sends the unsupported `thinking_budget=0` setting for that
model. Google documents extended live thinking as a separate integration with
non-blocking tools and interaction-status lifecycle handling. This change does
not switch to that model or pretend its protocol is already implemented.

Sources: [Live thinking protocol](https://ai.google.dev/gemini-api/docs/live-api/thinking),
[extended-thinking model](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking).

## Implementation and validation

The shared contract is `voice_layer/persona.py`; both the active voice daemon
and the alternate desktop harness use it. Existing specialist routing and tool
permission checks remain in place. The source change also removes conflicting
instructions to continuously speak, disclose reasoning aloud, invoke artificial
fillers and abandon all alternatives after a single failed tool.

31 focused tests pass, including conditional widget/reasoning instructions,
distinct tool counts, memory-disable behavior, SDK setup validation, phone
routing, configuration and a reasoning-job completion lifecycle with an injected
model. Python compilation and diff whitespace checks pass. A broader existing
audio test run stalled in background-thread handling and was interrupted; it is
not reported as passing. No acoustic comparison or live reasoning benchmark was
performed.

`scripts/prepare_persona_release.py` stages only these changes over the current
managed build, validates the registry and setup, checks file hashes and the
parent release before activation, and retains the previous build with service
health rollback. It does not deploy unrelated workspace changes or restart the
desktop shell.

Activated release: `20261102T180319Z-system-persona`. All changed-file hashes
match the staged version. Both voice/device services are active, and the voice
service logged a successful Gemini Live connection using Aoede. Local fillers
remain disabled. The previous widget release is retained for rollback.
