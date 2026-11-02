# Sentence pause handling — 2 November 2026

## Report and cause

The user clarified that JARVIS replies before they finish their sentence.
The installed configuration used 50 capture frames (one second) of silence to
close the user's turn. The default-less LiveVoice construction also retained an
older 15-frame (300 ms) fallback. Both could split a sentence containing a longer
breathing or thinking pause.

## Change

- Set the source default and distributed configuration example to 100 frames,
  equivalent to two seconds of silence at 20 ms/frame.
- Make LiveVoice use the Config default when no explicit value is supplied.
- Back up the installed user configuration, change its explicit setting from
  50 to 100, and restart `jarvis-voice.service`.
- Keep the existing barge-in configuration enabled.

Only the supported configuration setting was deployed to the installed release.
Source default/fallback changes and the new regression test remain in the
development checkout for the next release. Protected OMA voice files were not
edited.

## Verification

A capture-path regression feeds one utterance containing 1.2- and 1.8-second
pauses, followed by two seconds of final silence. Before the fix, both default
construction paths admitted three turns; afterward, both admit one turn and
close it only at the final pause.

Focused tests: **88 passed** across interruptions, speech detection,
configuration, playback, responsiveness, voice lifecycle, acknowledgements,
and reply guarding. Configuration readiness and Git whitespace checks passed.

After restart, the installed service reported active/running, connected to its
voice provider, no microphone issue, and no status error. These are software
checks; the user should assess the pause handling in a real conversation.

The tradeoff is an additional second of waiting after the user finishes speaking.
Pauses of two seconds or longer can still close a turn; this is a silence-based
endpoint, not semantic detection that guarantees a sentence is complete.

## Recovery

Previous user configuration:
`/home/g0pi/.config/jarvis-voice/config.toml.before-sentence-pause-20261102`.
Restoring its prior pause value and restarting the voice service reverses the
installed setting change.
