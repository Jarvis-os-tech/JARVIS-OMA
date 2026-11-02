# Voice repair — 28 October 2026

- **VERIFIED:** The startup greeting crashed because `LiveVoice.greet` passed a boot ID to `GreetingMemory.prepare` and `sent`, whose APIs do not accept it. Repaired the callers in `core/agent.py`.
- **VERIFIED:** `jarvisctl mute/unmute` sent `set_mute`, which the IPC server did not implement. Added an explicit boolean setter, rejection of invalid values, unavailable-callback errors, and CLI failure reporting. Repeating the current mute setting now preserves playback rather than flushing it again.
- **VERIFIED:** Repairs were developed and tested in the existing isolated worktree, then installed in the main project for the running service. Rollback copies of the original deployed files/config are in `/tmp/jarvis-voice-repair-20261028` (temporary storage).
- **VERIFIED:** The user explicitly authorized live microphone transmission to Gemini. Local configuration now uses `start_muted = false`; the existing service remains enabled for graphical-session login startup.
- **NEW:** Increased the configured native playback cushion from 80 to 240 ms to provide more tolerance for network delivery pauses. This adds buffering delay; it is not a measured universal cure for distortion.
- **VERIFIED:** Voice/greeting/IPC/CLI/native/extension regression suite: **101 passed, 5 subtests passed**. All seven protected voice files remain intact.
- **VERIFIED:** Local native acceptance: 30 short/long turns, 20 interruptions, owned-helper recovery, and a 10-second paced stream passed; zero starvation samples during the paced run. These tests use silence and do not establish acoustic speech quality.
- **VERIFIED:** A separate generated speech test had zero clipped samples and rendered all 129,120 expected samples with zero starvation and zero callback errors.
- **VERIFIED:** After resuming the service with the larger cushion, a live status snapshot showed 228,960 provider audio bytes, 114,720 rendered playback samples, zero starvation, zero rebuffers, zero output callback errors, zero provider interruptions, and microphone unmuted.
- **VERIFIED:** The user confirmed the fully buffered speaker-test phrase sounded "Clear and continuous."
- **UNVERIFIED:** Long live conversations, noise, double-talk, and prolonged network jitter remain outside these short checks. The speaker-test feedback does not establish quality across all live conditions.
- **VERIFIED:** No protected audio implementation was modified. Super+H dictation was not changed.

## Follow-up: recognition and repeated reply cancellation

- **VERIFIED:** The user reported continuing silence and chopping after the buffered test. That test did not establish live conversation reliability.
- **VERIFIED:** The physical microphone was at 39%; after raising it to 85%, a short physical-source reading contained usable audio (RMS approximately 0.027). The temporary sample was deleted after calculating levels.
- **VERIFIED:** With sensitive speech detection, live recognition began, but four provider interruptions occurred with zero native starvation samples. These interruptions cancel playback; the figures alone do not distinguish real user interruptions from speaker feedback.
- **NEW:** Current reliability trial: microphone volume ceiling 85%, additional native WebRTC gain disabled, high start/end speech sensitivity, `NO_INTERRUPTION`, and a 240 ms native cushion. This deliberately disables automatic spoken barge-in; the manual Stop speaking control remains available.
- **VERIFIED:** During this trial, a live snapshot showed two recognized-input events and 147,840 rendered samples with zero provider interruptions and zero starvation. A later snapshot showed 295,200 provider audio bytes, zero pending notices, zero callback errors, and the service enabled and microphone unmuted.
- **VERIFIED:** Configuration tests passed: 21 tests and 52 subtests. Startup validation and all seven voice locks passed.
- **UNVERIFIED:** The user has not yet confirmed acoustic quality in this live reliability trial. Automatic interruption should be reintroduced only after measuring speaker feedback and genuine double-talk separately.
