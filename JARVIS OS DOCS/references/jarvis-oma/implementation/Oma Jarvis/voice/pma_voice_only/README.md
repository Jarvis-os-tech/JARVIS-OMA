# PMA voice-only runtime

A runnable derivative of the collected PMA voice code. Audio playback, PCM metering, process cleanup and the private control socket are reused from PMA. The new Gemini session contains no tool registry/executor, browser, desktop discovery, planner, task workers, camera, screen capture or connector integrations.

Original PMA files, the organized voice source copy and locked JARVIS audio files remain unchanged. This derivative keeps the upstream MIT license and records reused source ranges in `PROVENANCE.json`.

## System use

Installed runtime: `~/.local/share/pma-voice-only/`.
Service: `omarchy-voice.service`.
Voice preferences: `~/.config/pma-voice-only/config.toml`.
Existing Gemini credentials: `~/.config/omarchy-voice/env` (not copied into this source folder).

Commands:

```sh
omarchy-voice status --json
omarchy-voice listen toggle
omarchy-voice listen stop
omarchy-voice listen start
omarchy-voice listen cancel
systemctl --user stop omarchy-voice.service
systemctl --user disable --now omarchy-voice.service
```

`Super+Shift+V` is the desktop listening toggle when its binding is installed. The service starts listening when `autostart_listening = true`; muting closes the microphone, stops playback and closes the provider connection. Turning listening on establishes a fresh voice session. Muted sessions do not retain cloud conversation history. Playback cancellation also reconnects the voice session so late audio cannot resume the cancelled reply.

The default speaker setting is `barge_in = false`: incoming microphone samples are replaced with silence during playback and its echo tail. Manual cancellation remains available. Spoken barge-in requires headphones or correctly configured echo cancellation before enabling that setting.

The only provider used is the existing Gemini voice configuration. Live microphone audio is sent to that provider while listening. Transcripts and raw audio are not saved by this runtime; status files contain state/counters only. The selected model may have ordinary conversational capabilities, but the local service exposes no actions or other tools, and rejects unsolicited tool calls.

## Verification

- 12 automated checks passed: no action imports/tool schema, refusal of unsolicited tool requests, PCM output, muted-output discard, interruption handling, malformed-audio rejection, microphone shutdown, setup-before-capture ordering, safe mute lifecycle, key redaction and voice-only controls/status.
- A bounded live Gemini probe accepted the setup and returned 80,642 bytes of audio without opening the microphone or speaker.
- The implementation follows the provider's [Live WebSocket protocol](https://ai.google.dev/api/live), including waiting for setup acknowledgement before sending microphone audio.

Live installation checks also passed: microphone data streamed, muting closed capture and the cloud connection without restarting the service, resuming reconnected, and a short spoken response reached the running PCM playback process. The desktop hotkey is present. The service is enabled at login and was left connected/listening. JARVIS remains inactive and masked. See [live checks](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma_voice_only/live-checks.json) and [automated test results](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma_voice_only/test-results.xml).

The collected 30 PMA source files and 47 excerpts remain byte-for-byte unchanged; the seven JARVIS locked voice files also passed their integrity verifier. The copied PMA speaker implementation retains its existing behavior; this task does not claim to repair all historic voice/audio issues.

## Disconnect this voice service

Run `systemctl --user disable --now omarchy-voice.service` to stop it and disable login startup while retaining the code. `deployment_backup/manifest.json` records the prior installed service, launcher, voice-only configuration and hotkey-file states; any pre-existing files were backed up before installation. The original full PMA application was not reinstalled. This service uses only the isolated runtime.
