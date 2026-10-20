# JARVIS OS Capability Map

This is the planning catalog. Status values are:

- **Existing**: present in the current repository or manifests.
- **Strengthen**: present but needs a shared model, better verification, or persistence.
- **Planned**: a future capability.

## Conversation and input

| Area | Capabilities | Status |
|---|---|---|
| Voice | Full-duplex speech, interruption, greetings, configurable voice/model | Existing |
| Text | Multimodal input bar, typed prompts, file attachments | Existing |
| Vision | Screen streaming, camera frames, screen inspection, OCR | Existing |
| Context | Conversation history, session recording, transcripts | Existing |
| Interaction | Unified voice, text, visual, and notification responses | Strengthen |

## Desktop awareness and GUI control

| Area | Capabilities | Status |
|---|---|---|
| Windows | List, focus, close, minimize, maximize, float, center, fullscreen | Existing |
| Workspaces | List and switch workspaces | Existing |
| Applications | Discover and launch applications | Existing |
| Screen | Screenshot, OCR, active-window inspection | Existing |
| Direct GUI | Observe desktop, click, scroll, type, send keys | Existing |
| Semantic GUI | Accessibility-tree discovery and element targeting | Planned |
| Reliable GUI | Action verification, retry, stale-frame protection, undo | Strengthen |
| GUI workflows | Saved routines such as coding, meeting, research, and media modes | Planned |

## System control

| Area | Capabilities | Status |
|---|---|---|
| Audio | Volume, mute, microphone, PipeWire echo cancellation | Existing |
| Display | Brightness and screenshots | Existing |
| Power | Lock, sleep, hibernate | Existing |
| Network | Wi-Fi and Bluetooth control | Existing |
| Resources | CPU, memory, disk, and process monitoring | Existing |
| Services | Inspect, start, stop, restart, and diagnose services | Planned |
| Hardware | Devices, sensors, battery, monitors, cameras, audio nodes | Strengthen |
| Recovery | Safe mode, emergency stop, rollback, health checks | Planned |

## Files and projects

| Area | Capabilities | Status |
|---|---|---|
| Filesystem | List, read, write, edit, copy, move, trash, delete, search | Existing |
| Tasks | Multi-step filesystem jobs with progress and cancellation | Existing |
| Projects | Project discovery, metadata, active project context | Strengthen |
| Development | Capability proposals, isolated checkouts, tests, review | Existing |
| Verification | Hash checks, test results, diffs, artifact checks | Existing |
| Project memory | Decisions, requirements, open questions, history | Strengthen |

## Multi-agent work

| Area | Capabilities | Status |
|---|---|---|
| Discovery | Detect installed coding agents | Existing |
| Delegation | Run visible or background agents | Existing |
| Monitoring | Status, output, cancellation, timeout | Existing |
| Coordination | Supervisor, roles, dependencies, shared task graph | Planned |
| Isolation | Worktrees, workspace ownership, resource limits | Strengthen |
| Review | Independent review and acceptance criteria | Strengthen |
| Recovery | Resume after restart, retry, reassign, escalate | Planned |

## Memory and personalization

| Area | Capabilities | Status |
|---|---|---|
| Facts | Remember, recall, correct, forget | Existing |
| Profiles | SOUL, MEMORY, USER profiles | Existing |
| Documents | Index and retrieve documents | Existing |
| Semantic retrieval | Local vector cache and semantic ranking | Existing |
| Vault | Obsidian synchronization | Existing |
| Memory governance | Provenance, trust, revisions, injection filtering | Existing |
| Long-term goals | Goals, habits, project continuity, recurring routines | Planned |

## External services

| Area | Capabilities | Status |
|---|---|---|
| Google | Gmail, Calendar, Tasks, Drive, Docs, Sheets | Existing |
| GitHub | Repositories, files, issues, pull requests, analysis | Existing |
| Web | Search and page extraction | Existing |
| Browser | Open websites and future browser automation | Strengthen |
| Messaging | Drafting and sending with explicit approval | Planned |

## Proactive operation

| Area | Capabilities | Status |
|---|---|---|
| Events | Persistent events and activity ledger | Existing |
| Planning | Bounded proactive planning and routing | Existing |
| Monitoring | Reminders, todos, jobs, verification | Existing |
| Controls | Pause, resume, stop all work | Existing |
| Autonomy levels | Configurable autonomy by action risk and context | Planned |
| Notifications | Meaningful-change notifications without noise | Strengthen |
