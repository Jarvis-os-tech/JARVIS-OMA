# Whistle short commands and offline fallback

Enabled for the user's desktop in release
`20261102-164920-whistle-short-commands`. The previous release is retained
for rollback. The existing 400 ms speech pause and spoken acknowledgement
settings are preserved.

## Routing and ownership

The microphone still uses the existing local speech detector and PipeWire
echo cancellation. Short speech is held in a bounded memory buffer while
Whistle checks it. Exact commands cover output mute, volume and brightness,
numbered workspaces, installed application names, stopping speech, and
standby. Installed app names are supplied as recognition hints; ambiguous
names are excluded. Negated, compound, unfamiliar and uncertain commands
never execute through this path.

A confident conversational prefix releases audio to Gemini after about
800 ms of captured speech plus recognition time. Longer speech streams to
Gemini once the 2.5-second local buffer limit is reached. Short unmatched
speech forwards its original audio once. Recognition has a 500 ms deadline;
slow or failed recognition yields to the cloud and its worker is restarted
in the background. This can add recognition time to short unmatched
conversation; it is not a promise that every cloud turn gets faster.

Locally claimed commands never send their audio to the cloud. They use the
same existing skill executor, validation, policy and outcome classification.
An uncertain or failed action is consumed locally and cannot be retried
automatically by Gemini. Turn IDs and playback generations reject stale
recognition; cancellation waits for an already-admitted action to settle.
The global disabled-tools setting also applies to local actions.

## Offline behavior

A local capture worker remains available during cloud setup and retry
delays. Supported desktop commands can run without a cloud reply. Other
requests receive the cached failure response; offline transcription does
not provide offline reasoning, document analysis or speech generation.
Mute and standby prevent local transcription. Standby requests interrupt
the cloud retry delay and enter the existing local wake listener.

## Runtime and configuration

`scripts/install_whistle.py` installs an isolated `cactus-needle==3.2.1`
package, Whistle weights and the 3.3.1 CPU engine under
`~/.local/share/jarvis-runtime/whistle`. Its manifest records asset hashes.
The speech worker has no tools and owns the non-thread-safe model. Audio is
converted from JARVIS's PCM16 to Whistle's float samples in memory. Runtime
paths are explicit, Hugging Face offline mode is enabled, and telemetry is
disabled. There is no model download on the audio path.

The user configuration enables:

```toml
[local_speech]
enabled = true
max_command_seconds = 2.5
decode_timeout = 0.5
minimum_word_probability = 0.5
```

Configuration backup:
`~/.config/jarvis-voice/config.toml.bak.20261102-164920`.
Only daemon, config, speech-frame metadata, local recognition and the private
worker were updated in the installed runtime. Source hashes are recorded in
the release manifest. The runtime keeps its existing `jarvis_voice` package
layout while workspace implementation lives in `voice_layer`.

## Verification

184 focused tests passed, covering command ownership, original-audio
fallback, early conversational streaming, native-worker deadlines, confidence,
negation, ambiguous apps, stale turns, disabled tools, mute, standby,
acknowledgements, playback and existing voice recovery behavior.

On this Intel i5-1235U laptop, 12 warm recognitions of the existing
`ordinary.pcm` fixture took 79–317 ms (median 147 ms). This small sample is
not a general performance guarantee. Separately, a complete synthetic spoken
"volume down" test used the real speech gate and Whistle with a simulated
executor: online and offline each executed exactly once, sent no cloud audio,
and decoded in 190 ms and 320 ms respectively. These are recognition timings;
the 400 ms pause, action execution and speaker buffering are additional.

Generated Aoede phrases exercised vocabulary handling and rejected
"Do not open Firefox." No real desktop setting was changed by those tests.
The installed service reported Whistle ready and Gemini connected after
activation. Physical microphone availability is checked separately.

Official references: [Whistle model](https://huggingface.co/Cactus-Compute/whistle)
and [Cactus runtime](https://github.com/cactus-compute/needle).
