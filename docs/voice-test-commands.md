# Voice checks after the foundation fixes

Natural interruption is enabled on this installation with `barge_in = true` in
`~/.config/jarvis-voice/config.toml`. JARVIS should stop its current reply when it
detects your speech, then answer your new request. Speaker echo rejection stays
active. For the basic checks below, speak one line at a time.

To check interruption, say “Explain how a computer works in detail.” While
JARVIS is speaking, say “Stop. Just tell me the current time.” It should stop
the explanation and answer the new request. Also try changing a question while
waiting for its answer. No keyboard shortcut is needed.

| Say this | Expected result |
| --- | --- |
| “Reply with just the word ready.” | A short spoken reply without an unnecessary explanation. |
| “What memory tools can you use now?” | It can describe memory storage, search and status, without claiming unrelated desktop controls. |
| “Remember this exact test fact: my test code is BLUE-MANGO-42.” | The memory tool saves the fact and JARVIS gives a spoken acknowledgement. |
| “Search your saved facts for BLUE-MANGO-42. What is the stored fact?” | It calls memory search and reports the saved test fact. |
| “Tell me your memory status.” | It calls the status tool and reports the current local memory state. |
| “Forget only the saved test fact: my test code is BLUE-MANGO-42.” | It removes that exact active fact, without clearing other memories. If it needs the exact wording, it should search first. |
| “Is BLUE-MANGO-42 still an active saved fact? Check the memory tool.” | It reports whether the active fact remains. Conversation history can still contain our test conversation. |

For a persistence check, save the test fact, run `jarvis restart`, wait for the
greeting, then ask the saved-fact search question again before removing it.
Restart is a terminal command, not an attached voice tool.

## What automated checks cover

- A response arriving after the 15-second warning remains authorized and playable.
- A response stalled beyond 45 seconds requests a fresh connection, with an error
  in status; no automatic replay of potentially mutating tool requests.
- Memory writes execute on one ordered worker and are drained before shutdown.
- The exact distributed config loads with its memory section.
- Production startup attaches memory context, complete tool schemas and tool execution.
- Intermediate provider tool boundaries preserve the following spoken response.
- The real installer exposes all three CLIs; installed shortcuts work outside the repo.
- Synthetic memory persists across separate CLI processes.

## Verification limits

Voice quality, endpoint timing and recognition still depend on room noise,
speakers, microphone, network and provider response time. The rare crackle is
not proven fixed by software tests. Software timings are available through
`jarvis-voice status --json`; they do not measure physical speaker latency.
