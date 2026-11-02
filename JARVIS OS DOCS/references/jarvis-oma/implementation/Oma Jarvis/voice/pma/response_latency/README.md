# Response Latency

Voice-session trace summary and exact timing excerpts. first_output_audio starts at the latest received input transcript fragment and ends at incoming non-silent PCM; it is not microphone-end-to-audible-speech latency.

Complete source files retain their original bytes. Files ending `.txt` are exact source excerpts with original indentation, not standalone implementations. The manifest records every origin and line range.

| Copy | Original location |
| --- | --- |
| [trace_summary.py](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/response_latency/trace_summary.py) | `tools/trace_summary.py` |
| [code_extracts/live__LiveSession._perf.py.txt](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/response_latency/code_extracts/live__LiveSession._perf.py.txt) | `src/omarchy_voice/live.py:306-308` |
| [code_extracts/playback__LiveSpeaker._report.py.txt](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/response_latency/code_extracts/playback__LiveSpeaker._report.py.txt) | `src/omarchy_voice/playback.py:183-190` |
| [code_extracts/diagnostics__latency.txt](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/response_latency/code_extracts/diagnostics__latency.txt) | `docs/diagnostics.md:43-76` |
