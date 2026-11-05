# Voice Separate Voice Disabling Repair — 2026-11-05

## Problem
When operational actions or web/application launch tools (such as `open_website` or `open_application`) returned unverified or failed statuses, `_finish_unverified_action` in `voice_layer/daemon.py` invoked `self.local_router.synthesize(text)`. This dispatched text to `needle_worker` / `offline_speech.py` using `libespeak-ng`, an offline synthetic robotic voice.
As a result, whenever a task failed or could not be verified, users heard a disruptive, robotic "separate voice" saying `"I could not verify that action, so I have not marked it complete."` instead of maintaining voice consistency.

## Repair
Under explicit user authorization (`"fix that its neever use the spearate voice when anythign failed"`):
1. Modified `voice_layer/daemon.py` in `_finish_unverified_action()` to eliminate the call to `self.local_router.synthesize(text)`. When an action is unverified or fails, `pcm` remains empty (`b''`), and `self._play_reply_notice('reply_unavailable')` is executed instead. No secondary offline synthetic voice is ever queued or spoken.
2. The failure or unverified state is still recorded in conversation history and state memory (`self._memory_assistant` and `self._assistant_text`), but no disruptive separate speech is produced.
3. Updated `tests/test_action_speech_evidence.py` to assert that zero bytes of separate offline audio are queued on unverified actions (`assert voice.player.queued_bytes == 0`).
4. Recomputed file checksums and updated `audio/.voice_lock.json` with the new approved baseline and authorized repair record.
5. Preserved file permissions (`chmod 444` on locked files, `chmod 555` on protected directories).

## Validation
* `python3 scripts/verify_voice_lock.py` passes cleanly (approved baseline intact).
* `python3 universal-voice/scripts/verify_voice_lock.py` passes cleanly (independent baseline intact).
* `tests/test_action_speech_evidence.py` passes all 18 test cases.
* `tests/test_voice_lock.py` passes all 5 test cases.
* Existing voice test suites (`test_background.py`, `test_daemon.py`, `test_playback.py`, `test_speech.py`, `test_voice_layer.py`) pass with zero regressions.
