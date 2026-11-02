# Protected speech turns — 28 October 2026

**VERIFIED:** The user reported repeated unsolicited speech, self-interruptions and connection failures after restoring the GitHub voice baseline. The baseline alone did not resolve those live faults.

## Current behavior

- **VERIFIED:** `core/stable_voice.py` remains the main service's voice runtime. `core/speech_turn.py` adds speech admission using the already-installed local Silero VAD from openWakeWord; no new package, model download or service was installed.
- **VERIFIED:** A sustained local speech detection opens one reply permission. Unsolicited provider audio cannot enter playback, and completion consumes that permission. Quiet/noise frames alone do not open another reply.
- **VERIFIED:** Cloud-bound microphone audio is silenced during playback and for a 450 ms tail afterward to prevent speaker echo becoming a new request. Short leading speech is buffered locally so detection does not discard the start of the request.
- **VERIFIED:** Automatic spoken barge-in is disabled in this reliability mode. Wait for the reply to finish, or use the panel's Stop speaking control. This is a deliberate temporary interaction limit, not full-duplex acoustic parity.
- **VERIFIED:** A request without response progress times out after 20 seconds and discards the stale session handle without replaying the request.
- **VERIFIED:** `core/stable_recovery.py` retries transient network/provider failures with capped backoff rather than exiting merely because five attempts failed. Failed resumptions can fall back to a fresh session. Authentication/configuration failures remain explicit. Logs record error class, numeric code and resume state without exception payloads or credentials.

## Verification

| Label | Evidence |
|---|---|
| VERIFIED | Three lower-cost `gpt-6-luna` agents prepared recovery and regression-test work; the parent reviewed, integrated and corrected it. Agents were closed after completion. |
| VERIFIED | Combined selected regression suite: **78 passed**. Includes unsolicited-output rejection, reply-permission consumption, speech preroll/tail behavior, mute/privacy, manual stop, failed-resume recovery, retries beyond the former exit limit and stalled-request recovery. |
| VERIFIED | Real installed Silero detector: maximum silence probability approximately 0.034 over 100 zero-input frames; measured inference p95 0.624 ms in this short local probe. These are not conversational-latency measurements. |
| VERIFIED | A generated spoken question sent through the real local speech detector and Gemini admitted **one speech turn**, produced **one reply** (87,840 audio bytes), recorded **zero interruptions**, and consumed its reply permission. This test buffered output rather than playing it audibly. |
| VERIFIED | Deployed, unmuted quiet-room observation: **30 seconds, zero admitted speech turns, zero recognized-input events, zero reply bytes, zero provider interruptions**. Main status was idle. |
| VERIFIED | User listening/conversation feedback after deployment: **“Answered once and stopped.”** |
| VERIFIED | A short silence-only PipeWire comparison added zero physical microphone/speaker errors at both automatic and forced-1024 periods. It did not establish an improvement, so the clock was restored to automatic (`0`); no persistent graph-period change was made. |
| VERIFIED | All seven protected voice files remain intact. Automatic graphical-login startup remains enabled. |

## Preserved scope

**VERIFIED:** Pre-fix runtime files are archived under `issus voice/2026-10-28-before-turn-protection/` with checksums. The saved JARVIS-OMA (Copy) folder is unchanged. The main JARVIS service owns the status socket and voice controls; OS tools, memory and camera integrations remain paused for speech-only recovery.

**UNVERIFIED:** Long sessions under changing network/load conditions and full-duplex interruption quality still require separate evaluation. The successful quiet-room and user checks do not prove every future session will be error-free.

## Follow-up: input remained closed

- **VERIFIED:** A manual stop during an active request could leave `response_drop_pending` suppressing subsequent input if the provider never completed the discarded turn. Manual stop now requests a fresh session, and pending-turn flags are cleared before input is rearmed.
- **NEW:** Local admission now accepts two consecutive 20 ms frames at speech probability ≥0.5, improving admission of shorter phrases while retaining the silence floor, output-feedback mask and one-reply permission.
- **VERIFIED:** Status now exposes input-gate activity, reply/drop flags, speech probability and remaining input hold time for diagnosis.
- **VERIFIED:** Updated selected regression suite: **80 passed**; all seven protected audio files remained intact before activation.
- **VERIFIED:** After deployment, the user tested two consecutive questions and confirmed **“Both questions answered.”**
- **VERIFIED:** The previous profile is preserved under `issus voice/2026-10-28-before-input-rearm/` with checksums.
