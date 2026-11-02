# Intermittently missed speech — 2026-10-28

The user reports missed speech even after several seconds of silence, rather than only during playback or the echo holdoff.

## Evidence

- Running service was connected and unmuted, with zero queue backlog, zero response timeouts and zero provider interruptions. One prior admitted request had produced 158,880 reply bytes.
- Installed `openwakeword.vad.VAD.predict` recommends 480-sample windows at 16 kHz (30 ms) and notes lower performance with other sizes. The recovered wrapper used 320 samples (20 ms).
- With the same generated phrase, gain and seeded synthetic noise, the old 320-sample model rejected two cases that 480-sample windows detected: gain 0.07/noise RMS 0.01 and gain 0.2/noise RMS 0.025. A still poorer signal remained undetected; this does not eliminate microphone limits.

## Change

- `core/speech_turn.py` now groups incoming 20 ms PCM frames into contiguous, non-overlapping 30 ms detector windows. Transport stays at 20 ms and existing pre-roll preserves the onset.
- A retained score is marked stale while the next window fills. It cannot count as a second independent positive to start a turn. Reset clears both partial samples and retained predictions.
- Start threshold remains 0.5. Once speech starts, continuation threshold is 0.25 instead of 0.35, preventing the recovered noisy phrases from splitting into two turns. True silence still closes a production turn after 400 ms.
- Echo holdoff, mute guards, playback suppression, single-reply authorization and parallel transport remain unchanged.

## Verification and limits

- 98 targeted tests pass; all seven protected voice files pass integrity verification.
- Seeded synthetic silence/noise checks: zero admitted turns in three 20-second cases (silence, RMS 0.01 noise and RMS 0.025 noise). Synthetic noise is not a substitute for real-room validation.
- Full tool-enabled live check with generated noisy speech: one admitted turn, one recognized input, 63,840 response bytes, zero provider interruptions, empty capture queue. No microphone audio or saved memory was included in the cloud diagnostic.
- User hearing/detection reliability after the change still requires confirmation on the physical microphone. This fix addresses a reproduced filter weakness; it does not prove every intermittent miss had that cause.

Regression tests: `tests/test_core/test_speech_turn_gate.py` (sample continuity, reset isolation, independent onset evidence, noisy continuation).
Snapshot: `issus voice/2026-10-28-before-speech-window-fix/`.
