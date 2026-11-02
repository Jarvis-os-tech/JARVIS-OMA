# Stop stale processing notices after an answer

The reported document-analysis turn began returning audio at 15:28:51, but
the local `reply_waiting` clip was inserted at 15:29:07. A later response
timeout reset the session. The waiting-notice guard allowed a notice after
answer speech had already started.

The installed repair suppresses local waiting notices once answer audio
starts, including when tasks remain in flight. It also handles the provider's
`generation_complete` signal separately from its delayed `turn_complete`
marker: a finished answer keeps playing without stale waiting, timeout or
offline-failure notices. Tool-result and no-audio cases retain their existing
recovery behavior. New input and reconnect cleanup reset completion state.

The preceding silence was a different concrete failure: JARVIS's virtual AEC
microphone was muted while its physical microphone and capture stream were
unmuted. Unmuting only that virtual source immediately restored accepted
speech and provider replies. Each newly created AEC source now initializes
its mute state from its actual physical input once. No physical mute setting
is changed, and later user mute changes are not continually overridden.

Verification: **135 focused tests passed**. They cover answer/notice timing,
generation completion, real pending work, missing audio, microphone state,
both physical mute values and the existing acknowledgement/daemon behavior.

Installed release: `20261102-153837-answer-feedback-fix`; previous release
retained: `20261102-151803-instant-task-ack`. Only `daemon.py` and `echo.py`
were updated in the runtime. After restart the new AEC input was unmuted,
and the service returned to the user's existing standby state with no error.
Say “Hey Jarvis” to resume voice interaction.
