# Immediate task acknowledgements

Longer-work acknowledgements now enter the local audio queue immediately at
authorized task admission, before skill execution is awaited. This path has no
650 ms or 1.2-second timer. Cached clips are already in memory; playback does
not require cloud speech generation or delay the task while the clip finishes.

Browser/network work uses “On it”, agent/delegation work uses “Sure”, and file
inspection uses “Hmm”. Quick status lookups keep their direct answer. Cached
tool results, denied actions and repeated requests do not produce duplicate
acknowledgements. Existing mute, standby and already-speaking guards remain.
If a task starts while the user is speaking, its acknowledgement is deferred
until ActivityEnd and only plays if that task/turn is still active.

The existing fallback timers remain for thinking latency or tools without a
task-admission acknowledgement. This does not predict whether an arbitrary
question will need future reasoning time. The physical audio device still has
its normal buffering; “immediate” means no deliberate task-ack timer.

## References

[NVIDIA PersonaPlex model card](https://huggingface.co/nvidia/personaplex-7b-v1)
describes concurrent audio understanding and generation, including rapid
turn-taking and interruption handling. The timing principle informed the local
cached-feedback path; no PersonaPlex model replacement was performed.

The user also supplied [Block Dessa](https://block.xyz/dessa). The web reader
could not retrieve that page. A direct public-page fetch did not execute
because automatic approval review timed out, so this change makes no new
technical claim about Dessa.

## Verification

- **102 focused tests passed**, including acknowledgement-before-execution,
  duplicate/cached tool calls, action rejection, pending speech boundaries,
  standby, mute, new turns and short status requests.
- An installed-code speaker-monitor test used a simulated authorized web task
  with no external action. Its acknowledgement queued **12.03 ms** after
  dispatch and the first PCM write occurred at **12.52 ms**. Captured output
  matched the bundled “On it” clip at normalized correlation **0.995**.
- Exactly one acknowledgement played. No timer/response monitor was running
  in that probe, demonstrating that task admission itself triggered playback.
- Installed release: `20261102-151803-instant-task-ack`. Previous release:
  `20261102-131733-mode-stability`. Source and installed daemon hashes match.
  Existing runtime modules and microphone settings were preserved.
