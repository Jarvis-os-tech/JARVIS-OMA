# Control and retrieval live checks

Date: 30 October 2026, Asia/Kolkata.

- Full native suite: 212 tests and 81 subtests passed in 6.10 seconds.
- Read-only live system time, OS, memory and disk queries passed through the control adapter using the voice configuration.
- Switched to unused workspace 90, verified its active state, and restored the original workspace. Both transitions passed.
- Found and fixed an integration failure: the voice config lacked the control policy defaults (`deny_patterns`, `confirm_patterns`). The adapter now builds a complete control config and maps only the voice-exposed control switches. A regression test exercises the voice config, live time query, held-action gate, and cancellation without executing the held action.
- The installed adapter was backed up, updated and the voice service restarted.
- Public page opening and search-window creation worked, but both page text reads failed with `no readable text in that region`. Both newly created test windows were closed and removal verified. These checks are failures for information retrieval, not successful lookups.
- Further diagnosis: the primary selection contained rich data and the reader correctly declined to replace it; the OCR fallback returned no text. A screenshot of only the public example.com test region showed a blue/blank region rather than the expected page. The exact rendering/capture cause remains unconfirmed. No clipboard contents were retained.
- Two isolated natural-language provider-to-control tests timed out during connection setup, before a tool ran. This run does not claim a verified new voice-provider tool roundtrip. Direct native control and retrieval checks are separate evidence.

Evidence: [control live results](control-live-results.json), [retrieval live results](retrieval-live-results.json).

Safe spoken checks after the greeting finishes:

1. “What time is it, and what is my timezone?”
2. “How much memory is available right now?”
3. “How much disk space is free?”
4. “Which workspace am I on?”
5. “Switch to workspace 90.” Then “Switch back to workspace [your original workspace number].”

Web search is not yet a reliable spoken-answer test: opening results does not prove their contents were read.
