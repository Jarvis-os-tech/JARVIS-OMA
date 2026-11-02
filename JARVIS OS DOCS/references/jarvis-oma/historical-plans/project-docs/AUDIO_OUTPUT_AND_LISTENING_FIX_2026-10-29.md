# Speaker continuity and listening indicator — 2026-10-29

## Reproduced failures

- The status state machine assigned `thinking` before `listening`. Accepting speech set the pending-reply flag immediately, making the listening tag disappear while the user was still speaking.
- Local speaker-loopback comparison using the same three-second generated tone found 20 missing interior 20 ms windows through the old echo-canceller playback sink (about 0.4 seconds of gaps). Direct physical-speaker playback had zero missing interior windows.
- A native monitor-mode echo canceller was then tested with microphone capture active and speaker playback direct: 149 detected tone windows, zero missing interior windows. These are local instrumental measurements, not a guarantee of acoustic quality under every load.
- A clock-quantum experiment did not establish a useful fix and was reverted. Global forced quantum was restored to zero; microphone mute state was restored after the comparisons.

## Implemented

- `core/monitor_echo.py` owns a native PipeWire echo-cancellation module through a child `pw-cli` process. It reads the physical speaker monitor as the echo reference while playback goes directly to the physical speaker. Microphone echo cancellation remains active. System defaults/configuration are not changed, and no persistent service or framework is added.
- The new module validates its microphone and fails closed if echo cancellation cannot initialize. Module lifetime and cleanup belong to the JARVIS process; child environment excludes credentials.
- `core/stable_voice.py` reports `pipewire-monitor-aec` and prioritizes `listening` over a pending reply while speech is active. The existing desktop bridge already maps that state to its Listening label.
- Playback primes up to 80 ms of usable PCM with a maximum 120 ms startup wait. Completed short replies flush immediately. This smooths small provider arrival gaps without waiting for a whole response.
- Playback pipe writes have a two-second drain deadline. Startup buffering is generation-fenced, so stop/interruption cannot release old queued samples.

PipeWire documents the monitor-reference mode here: <https://pipewire.pages.freedesktop.org/pipewire/page_module_echo_cancel.html>.

## Final verification

- **136 targeted tests pass.** All seven locked voice files pass integrity verification.
- Tests cover module ownership/cleanup, raw-microphone rejection, failed-module behavior, Listening state priority, startup buffering, short-response flush, interruption during priming, blocked playback writes, and existing speech/tool/socket regressions.
- Final service inspection confirms the running main project started after the changed runtime files, reports the new monitor-AEC backend, remains enabled for graphical login and has zero systemd restarts. Recent live logs show speech turns completing with first returned audio roughly 1.0–1.4 seconds after local turn end; this does not measure acoustic onset.
- Earlier buffered/generated-speech tests alone were insufficient to establish physical playback continuity. The loopback comparisons above specifically exercised the actual output route.
- Fresh user confirmation of spoken clarity and the visible listening tag remains required. Cloud/provider stalls and longer arrival gaps can still affect a live reply.

## Files

- Runtime: `core/monitor_echo.py`, `core/stable_voice.py`.
- Tests: `tests/test_core/test_monitor_echo.py`, `tests/test_core/test_playback_continuity.py`, and existing voice reliability/control tests.
- `core/stable_echo_cancel.py` and all locked audio-core files remain unchanged; unrelated existing work is preserved.
