# Main JARVIS capability restoration — 2026-10-28

User request: enable JARVIS's existing capabilities and restart it, preserving working speech.

## VERIFIED

- Main service working directory: `/home/g0pi/Projects/JARVIS-OMA`; not the saved Copy project.
- Recovery launcher previously forced `--no-skills` true. This is now an explicit opt-out; the runtime reads the existing configuration.
- Skills, memory and proactive configuration enabled. Service reports `skills_enabled: true`, `memory_enabled: true`, and 191 registered tools.
- Shared JARVIS identity and tiered tool prompt reused from `core/harness_config.py`. A missing `get_assistant_status` manifest was added to both manifest directories, reusing its existing adapter.
- Existing task/delegation, filesystem, desktop, search and connector tools are exposed through their registry, including domain discovery. Each adapter still enforces its own availability and argument checks.
- Memory startup/context lookup uses the existing bounded worker. Authorized conversation exchanges are recorded; configured Obsidian synchronization runs separately from audio.
- Existing proactive runtime advances queued jobs. Typed input and attachments from the existing input bar can request a protected reply. Requested visual tool results can forward a bounded frame to Live.
- Existing tool identity cache prevents action replay after reconnection; uncertain prior actions are reported rather than repeated.
- 88 targeted automated tests pass. All seven locked voice-core files pass integrity verification.
- A separate read-only Gemini Live check called `get_assistant_status`, returned one tool result, and generated 176,640 bytes of buffered audio. Its transcript was: “I am Jarvis, and my desktop tools are fully connected.” This diagnostic did not play audio or capture a microphone. Its shell exposed 182 tools because nine CLI-hub tools were not on that shell's PATH; the running service exposes 191.
- Main user service remains enabled for graphical login.

## LIMITS / UNVERIFIED

- Registration is not an end-to-end pass for every tool. External accounts, hardware, agent CLIs and network providers still need their own working dependencies and credentials.
- Continuous screen/camera streaming remains unavailable in this recovery runtime and fails explicitly. On-demand visual tools are available; no camera starts automatically.
- Spoken background notifications, automatic greetings, automatic barge-in, telephony event streaming and standby lifecycle are not restored here. Status tools provide background progress; no unprompted spoken notices are introduced.
- No fresh human listening assessment was obtained after enabling capabilities. The last human-confirmed two-question test preceded this restoration.
- No broad provider failover or new agent framework was added. Existing model-processing and delegation tools remain available through their adapters.

## Files

- `core/stable_voice.py`: recovered audio transport plus shared capability configuration, tools, typed input and memory exchange hooks.
- `core/stable_capabilities.py`: optional memory/background lifecycle and bounded visual reads.
- `config.toml`: skills, memory and proactive enable flags.
- `skill_manifests/assistant-status.json`, `skills/manifests/assistant-status.json`: existing status adapter declaration.
- `tests/test_core/test_stable_capabilities.py`: integration and regression checks.

Pre-change runtime/config snapshots: `issus voice/2026-10-28-before-capability-restore/`.

## Reply-delay follow-up

- User confirmed a clear live reply after reporting no response. Service counters confirmed one recognized input and 79,200 returned audio bytes, with no provider interruption.
- Generated-speech comparison: existing automatic detection returned first audio after 1,342 and 1,083 ms from the test waveform end; explicit local turn boundaries with a 400 ms local pause returned after 906 and 1,108 ms. This is a small two-sample comparison, not a microphone latency guarantee.
- Recovery runtime now sends explicit activity start/end events and disables duplicate provider activity detection. Local end-of-turn silence is 400 ms; echo holdoff and no automatic barge-in remain enabled.
- HUD status now uses the startup tool-count snapshot instead of refreshing registry dependencies every 100 ms. Previous median status time was only 0.148 ms, so this was not demonstrated to be the main delay source.
- Added content-free `last_reply_after_local_end_ms` and `response_timeouts` status fields. The latency field starts at the local end marker; it excludes the pause used to detect that end and does not measure acoustic speaker output.
- 91 targeted automated tests pass; all seven protected voice files retain their integrity.
- Updated actual sender plus full 191-tool configuration produced a generated-speech reply, with one recognized input and no provider interruption. Saved memory and microphone audio were excluded from cloud diagnostics.
- User-perceived response speed after this change still needs a fresh spoken check.
