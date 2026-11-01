# Integrated JARVIS audit and Omarchy skill update

Date: 31 October 2026, Asia/Kolkata.

## Installed result

The updated voice, memory, control and CLI packages were installed directly into
`~/.local/share/jarvis-voice`. The service was stopped for the copy and started
again afterward. Existing configuration and memory data were preserved. Previous
installed code is backed up under
`deployment_backup/omarchy-audit-20261031-002846`.

Live installed checks returned:

- Service active/running, connected and listening; no current error; zero automatic restarts.
- Memory enabled, control enabled, 41 attached tools, no tool currently in flight.
- Installed dependency/config readiness check passed.
- Installed Omarchy guide search and current system-time query passed.
- Installed `jarvis-control --help` returned exit 0 from outside the repo.
- 70 bundled guide sections were available. Live command discovery found 369 public Omarchy routes and version 4.0.6-1 before deployment.

## Verification

- Full suite: **239 tests and 81 subtests passed in 5.73 seconds**.
- Parsed all 101 active Python source/test files without syntax errors.
- Shell syntax checks and `git diff --check` passed.
- Original JARVIS-OMA voice-lock verification passed for all seven protected files.
- Public page text was retrieved live from example.com and the official Python documentation.
- A further live request demonstrated the hard fetch deadline: a stalled lookup returned a controlled error after 7.01 seconds.

## Fixed and integrated

| Area | Change |
| --- | --- |
| Omarchy guidance | Bundled the local Omarchy skill and six topic guides; added `omarchy_help(topic=skills)` and compact voice routing. The complete guides are loaded on demand. |
| Command discovery | Uses the installed catalogue and exact command details. Read-only help about a gated command no longer requests permission to merely describe it. |
| Web reading | Added bounded public HTML/plain-text retrieval without browser cookies or clipboard changes, with visible-browser fallback. Script/style text is excluded and source URLs retained. |
| Network deadlines | Isolated page fetches in an owned process so DNS and HTTP share a hard seven-second deadline. Size, content-type, credential-URL, redirect/address and connected-peer checks bound direct reads. |
| Retrieval truthfulness | A page/search window opening without readable text now returns a failed result. Public search text may come from a different provider than the visible window; the returned source URL identifies it. |
| Browser reads | Preserved short valid selected text and refreshed window geometry before OCR fallback. |
| Tool lifecycle | Longer browser operations have an appropriate bound, active tools do not trigger the response watchdog, and a dedicated serialized control worker is drained on shutdown. |
| Duplicate effects | Recent provider call IDs return cached results instead of repeating an action. Cache is retained for session resumption and cleared for a fresh session. |
| Confirmation | A held action cannot be confirmed by the model in the same speech turn. The confirmation must match actual user transcription in a later turn. |
| Voice status | An idle connected microphone reports listening. Completion/interruption clears stale delay warnings. Status exposes memory/control availability and in-flight tool count. |
| Config and credentials | Added strict voice option validation, honored the configured API credential environment name, and improved missing-dependency and invalid-CLI checks. |
| Session continuity | Fresh provider sessions explicitly enable resumption updates. Stale timing fields are reset when reconnecting. |
| IPC ownership | Starting another daemon cannot replace the existing live control socket. Non-socket paths, unsafe runtime directories and sockets not owned by the user are rejected. A failed startup cannot unlink another daemon's socket. |
| Installation | Corrected the `jarvis-control` symlink root; installation tests now check control help, guide files and the public-page reader. Uninstall includes the control shortcut. |
| Logging | Conversation text is logged only when transcript logging is requested; continuous memory capture remains separate. |

## Omarchy provenance and boundaries

The source skill is `/home/g0pi/.agents/skills/omarchy/SKILL.md`; the bundled
copy and guides are in `jarvis_control/omarchy_guides`. The routing preserves
`SUPER+H` for dictation, keeps packaged Omarchy files read-only and uses existing
execution policy. No themes, monitor settings, desktop bindings or packaged
Omarchy files were changed by this integration.

## Coverage limits

This audit covers the active voice/control/memory/CLI source and its test suite.
It is not a proof that every hardware path, imported reference snapshot or external
service is defect-free. Camera capture and privileged/destructive actions were not
executed. Physical microphone/speaker quality still needs listening checks.

Public-page retrieval succeeded on live reference pages, but DNS/network stalls
and website verification challenges remain possible. The repair bounds those
failures and reports them honestly. The older search-window test did not complete;
its uniquely identifiable leftover test window was closed and removal verified.
A reliable end-to-end search result is not claimed from that interrupted test.

## Spoken checks

Wait for the greeting, then say one request at a time:

1. “What Omarchy commands can control my audio?”
2. “Find the Omarchy guide for changing themes.”
3. “What Omarchy version is installed?”
4. “Which workspace am I on?”
5. “What time is it, and what is my timezone?”
6. “Open example.com and tell me what it says.”

See [the integration guide](../omarchy-integration.md) for tool mappings and
[the memory voice checks](../voice-test-commands.md) for persistence tests.
