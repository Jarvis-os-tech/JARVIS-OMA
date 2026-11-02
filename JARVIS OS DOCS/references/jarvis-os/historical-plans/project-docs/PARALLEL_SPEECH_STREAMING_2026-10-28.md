# Parallel speech streaming — 2026-10-28

Request: process opening words as they arrive and start playback with the first generated reply audio.

## Implemented

- Microphone capture/local detection has its own asynchronous task, separate from network sending, provider reception, playback, HUD updates and tool jobs.
- Capture forwards 20 ms PCM frames through a bounded 50-item FIFO. Opening speech includes the existing pre-roll; upload begins after local speech admission, while the user is still speaking.
- Explicit activity markers preserve order. The local 400 ms pause still closes a user turn; there is no whole-utterance upload buffer. Provider response generation remains controlled by Gemini.
- Capture can continue during an outgoing network delay. Writes have three-second deadlines; a full capture queue fails explicitly instead of growing indefinitely. Reconnection may lose an in-flight turn; actions are not speculatively executed from partial words.
- Generation checks prevent queued pre-stop input from becoming a new activity. Mute, speaker-echo suppression, one-reply authorization and disabled automatic barge-in remain active.
- Playback opens its existing PipeWire player after connection setup, before microphone capture starts. It writes the first received reply chunk without waiting for a sentence or turn-complete event. The existing pacing/cushion is retained for continuous playback.
- Status exposes `speech_pipeline`, `capture_queue_frames`, `first_speech_upload_ms` and `first_audio_chunk_to_write_ms`. Upload timing starts at local speech admission; write timing measures delivery to the playback pipe, not acoustic sound from the speaker.

## Verification

- 94 targeted tests pass, including new tests for upload during ongoing speech, continued capture under network backpressure, warm playback reuse, first-chunk writing before turn completion, and concurrent receipt of later reply chunks.
- All seven protected voice-core files pass integrity checks.
- A generated-speech Gemini Live check using the actual sender and 191-tool configuration returned one recognized input and reply PCM. The first admitted speech upload took 4 ms; first returned PCM arrived 793 ms after the local end marker. These are single synthetic-run observations, not latency guarantees. The diagnostic did not play sound, capture a microphone, or send saved memory.
- Fresh human listening confirmation is still required after activation. Cloud/network latency and provider turn-taking cannot be eliminated by local concurrency.

Changes: `core/stable_voice.py`, `tests/test_core/test_parallel_voice_streaming.py`.
Snapshot before change: `issus voice/2026-10-28-before-parallel-streaming/`.
