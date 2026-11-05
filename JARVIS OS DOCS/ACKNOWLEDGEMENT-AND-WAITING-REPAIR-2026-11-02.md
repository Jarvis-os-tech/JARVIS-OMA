# Restore acknowledgement variety and remove repeated waiting speech

The later voice build made acknowledgement helpers no-ops and removed the
fallback timer. Restored acknowledgement at admitted task start, at local
Whistle command execution, and after a 150 ms direct-answer grace. General
turns cycle through Hmm, On it and Sure; known tool contexts choose an
appropriate clip. Mute, standby, user speech, already-started answers and
the one-acknowledgement-per-turn budget remain enforced. A default-speaker
playback check exercised all three different cached clips successfully.

The `reply_waiting` recording is now rejected at its playback entry point,
even if an older caller asks for it. No repeated synthetic progress turns
were restored. Provider instructions and one-shot empty-answer recovery
require actual results, concrete findings or a clear failure, rather than
generic still-working/processing sentences or claims of stale pending work.
Model-generated language is guided by those instructions; it is distinct
from the local recording, which is disabled deterministically.

136 focused tests passed, covering acknowledgement rotation, task admission,
Whistle commands, one-shot playback, disabled waiting recordings, playback,
answer completion and the daemon. Only the voice daemon is replaced in the
runtime release, preserving existing Needle, Whistle, standby and desktop
integration modules. The release manifest records its exact daemon hash and
rollback parent.
