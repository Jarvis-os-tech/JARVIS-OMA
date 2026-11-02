# Voice foundation

Reference: `/home/g0pi/Projects/JARVIS-OMA/Oma Jarvis/voice`.
The reference contains both complete modules and code extracts; extracts are not
standalone runtime modules. The active implementation lives in `jarvis_voice`.

| Audio stage | Local runtime | Organized OMA reference |
| --- | --- | --- |
| Microphone and transport | `daemon.py`: `_capture_audio`, `_send_frames` | `capture`, `session` |
| Turn detection | `speech.py`: `SpeechTurnGate`, `SileroSpeechDetector` | `turn_detection` |
| First audio and continuity | `playback.py`: `prepare`, `_prime`, `run` | `first_speech_output`, `playback` |
| Interruption | `speech.py`: `SpokenInterruption`; playback generation fence | `interruptions` |
| Failure recovery | `daemon.py`: `supervise`; `recovery.py` | `recovery`, `fast_response` |
| Response timing | `daemon.py`: `status`; `playback.py` | `response_latency` |

## Behavior

Capture and sending run concurrently. Microphone EOF, detector failures, and a
full four-second capture queue fail the session rather than silently losing
speech or its activity boundaries. Session workers are cancelled and awaited
before reconnecting. Audio processes and turn state are cleared before backoff.
The startup greeting shares that session lifetime.

The default endpoint requires 15 quiet capture frames (300 ms). Playback primes
up to 80 ms of PCM, waiting at most 40 ms for short provider gaps. It requests
an 80 ms PipeWire buffer and feeds audio up to 120 ms ahead to tolerate brief
scheduling delays. These are continuity safeguards, not a guarantee against
provider or hardware artifacts. The default speaker echo holdoff is 350 ms, with turn-gate
suppression after blocked audio. This is a half-duplex clarity safeguard, not
acoustic echo cancellation. Automatic interruption stays opt-in.

Status timings separate provider response delay after detected turn close from
local playback startup delay. They exclude the 300 ms endpoint window and do not
measure the physical speaker. Compare several real conversations before tuning
endpoint or buffering; slower speech and room echo need listening checks.

## Validation

Run `.venv/bin/pytest tests/ --ignore=tests/test_memory -q` for the voice suites,
then `.venv/bin/python -m jarvis_voice --check` for local readiness.
Unix socket tests need access to the user session. A real microphone/speaker
conversation is still needed to assess perceived clarity and conversational pace.
The original seven locked JARVIS-OMA audio files must remain unchanged.

`latency.activity_end_to_first_audio_ms` measures provider delay after the actual
activity-end send. `speech_active`, `speech_probability`, and
`capture_queue_frames` expose endpoint detection and upload backlog separately.

Live sessions explicitly use `thinking_budget=0`, verified against the configured
provider in an isolated test. This favors quick conversational responses. The
probe measured 801 ms with the default setting and 701 ms with budget zero for
a one-word text request; these single samples do not establish microphone
conversation latency.
