# Wake phrases and shortcut repair

## Findings

The offline listener was running, with an unmuted capture route, but its single
Hey Jarvis model showed low scores during the reported failure. It did not have
an explicit Hello Jarvis recognizer. Separately, the old Super+Shift+J command
called `listen toggle`: in standby it signalled wake and then flipped soft mute
on, leaving the resumed conversation disabled. The standalone Super+1 helper
could leave standby successfully; the two shortcuts had different semantics.

## Repair

- The original Hey Jarvis model remains. A local Vosk decoder also recognizes
  exactly Hey Jarvis and Hello Jarvis using the existing bundled English model
  from the mobile project. The managed build contains its own copy; it does not
  depend on a source checkout or download a model at wake time.
- Both complete and partial recognizer results require the identified greeting
  words and at least 0.80 confidence per word. Competing greetings and unknown
  speech are represented in the grammar. Audio stays local during standby.
- Wake and standby-toggle clear JARVIS soft mute when resuming. The legacy
  `listen toggle` path now prioritizes waking from standby instead of muting it.
- Capture EOF is an error rather than a false successful wake. Entering standby
  no longer silently unmutes the system default microphone.
- Per the user's latest preference, the only JARVIS wake/standby shortcut is
  **Super+Shift+S**. It replaces Google Maps. Super+Shift+J is removed, and
  Super+1 explicitly restores ordinary workspace 1 navigation. Config reload
  reports no errors. The status shortcut Super+Ctrl+J is unchanged.

The model/decoder API follows the upstream
[Vosk grammar example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py).
The dependency is pinned to vosk 0.3.45 in the JARVIS environment and source
requirements. The Aoede voice, synthetic-filler preference, widgets and island
are preserved.

## Evidence and limits

116 focused wake, IPC, speech, persona and intent checks pass, including the
standby-plus-mute regression, both aliases, uncertain/partial phrases, manual
wake races and capture EOF. Initial restricted test execution blocked socket
creation; the same suite passed with local socket access. One warning concerns
the unavailable CUDA provider; CPU execution is available.

Ten local audio fixtures passed: one recorded Hey Jarvis sample, synthetic
Hey/Hello samples, six negative utterances and silence. These were fed to the
decoder in memory, with no test speech played. The installed build also detected
the recorded fixture with its bundled model, and changed-file hashes match.
These samples do not establish recognition for every accent, room or distance.

A live standby/wake cycle executed the shortcut's exact command through the
compositor and reconnected the voice service without soft mute. This verifies
the command path; it is not a physical keyboard press. Final binding inventory
contains Super+Shift+S for JARVIS, Super+1 for workspace 1, and no Super+Shift+J.
Final voice status is connected, out of standby, unmuted, with an unmuted
JARVIS capture source and no reported error. A user-spoken room test remains the
final acoustic check.

Activated build: `20261103T100948083561Z-wake-repair`.
Previous build: `20261103T031451981271Z-system-persona`.
Preparation/activation: `scripts/prepare_wake_release.py` with file-hash checks,
locked parent validation, service health checking and retained rollback.

The original shortcut configuration is saved at
`~/.config/hypr/bindings.lua.before-wake-repair-20261103T101003Z`.
The configuration before the requested S-key change is saved at
`~/.config/hypr/bindings.lua.before-jarvis-shift-s-20261103T101207Z`.
