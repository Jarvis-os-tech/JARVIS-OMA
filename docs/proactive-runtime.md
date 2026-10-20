# Proactive Autonomy Runtime

The proactive runtime (`proactive/`) enables JARVIS to observe desktop activity, maintain a chronological event ledger, plan background tasks, and proactively assist the user within strict safety boundaries.

## Architecture

```text
[Desktop Activity / Idle] ──> [Monitor] ──> [Event Bus] ──> [Activity Ledger (SQLite)]
                                                                  │
                                                                  ▼
[Safety Policy & User Control] <──── [Autonomous Planner] <──────┘
             │
             ▼
[Worker Execution / Live Notification]
```

## Core Modules

- **`events.py`**: Pydantic/dataclass data models representing desktop events, activity states, and audit trails.
- **`monitor.py`**: Observes system idle state, resource spikes, and active windows without blocking voice audio.
- **`planner.py`**: Decomposes user goals or detected triggers into atomic, bounded actions.
- **`policy.py`**: Evaluates proposed actions against safety guardrails. Halts execution if user presence or explicit overrides require pause.
- **`runtime.py`**: Proactive daemon coordinator managing background loops, voice alerts, and execution limits.
- **`ledger.py`**: Persistent SQLite activity and execution records.
- **`verification.py`**: Bounded independent checks of exact artifact bytes.

## Proactive daily focus

The live voice observer checks ongoing Omarchy todos every ten seconds and
initiates a daily focus briefing without waiting for a spoken request. It selects
up to three incomplete ongoing tasks, ordered critical, high, medium, then low.
The existing notification sender waits for the current reply and playback to
finish before delivering the briefing. No briefing is created for an empty list.

Briefings are deduplicated in the persistent event database per workspace and
local calendar day, including across restarts. The first scan with eligible tasks
creates the briefing; it is not a fixed morning alarm. Pause and stop suppress
creation and processing. Resuming allows a queued briefing to be processed.
As with other queued notifications, completion records handoff to the voice loop,
not confirmed audible delivery; a crash during handoff may lose a briefing.
Task titles are supplied as untrusted context. Suggestions do not authorize or
launch workers; explicit authorized task requests keep their existing execution
path. This is a daily prioritization foundation, not predictive desktop awareness.

## Google Calendar briefings and reminders

While the live voice session is running, the observer reads the connected Google
account's **primary calendar** once per minute through the existing Workspace
adapter. It requests up to 50 events from today's midnight through ten minutes
after the next midnight. Existing connector expansion includes recurring event
instances. This first version does not scan other calendars or paginate beyond
50 events, and does not run when JARVIS is offline.

Today's timed and all-day events accompany the once-daily task briefing, even
when there are no ongoing todos. The observer uses `memory.obsidian_timezone`
(default `Asia/Kolkata`), matching the existing greeting timezone. Timestamped
events are converted from their UTC offsets; all-day dates remain dates.

Each timed event starting within the next ten minutes creates one read-only
reminder. The minute polling interval means this usually arrives nine to ten
minutes beforehand; starting JARVIS later can produce a shorter warning.
Cancelled events, malformed timestamps, and already-started events do not create
reminders. All-day events do not receive timed alerts. Reminder identity includes
the calendar, event ID, and start instant, allowing a rescheduled start to receive
a new reminder while suppressing repeats across restarts. Schedule changes and
cancellations have up to one minute of observation delay; cancellation of a
previously queued voice notice is not implemented.

Pause and stop prevent reminder creation/processing and hold Calendar voice
reminders. Reminders expire at the event start, including while waiting behind
speech or a pause. Calendar errors leave the task/reminder loop operational and
are retried on the next poll; if the task briefing has already been created during
an outage, the recovered schedule is not added to that day's briefing retroactively.
Notifications have the same handoff/crash limitation described above. Calendar
fields are untrusted context, never authorization to change events, join meetings,
or launch workers. Conflict warnings and change announcements are not included.

## Verified execution foundation

Observed todos and reminders never authorize execution, including high/critical
priority todos. An explicit `proactive_task` request authorizes delegation of
that request. The policy retains the `unknown` effect rather than pretending
delegated work is inherently reversible. The worker's native permission controls
still govern its actions. This is not yet a central broker that intercepts every
worker action; external CLI workers retain their existing OS permissions.

The Python `enqueue` API defaults to `authorized=False` and rejects non-boolean
authorization. Trusted callers with a user request pass `authorized=True`.
Execution records persist the workspace, predeclared acceptance checks, expected
job count, each job's last observed state, and verification evidence. Parent tasks
wait for every required worker; a single completed worker cannot close the parent.
Worker failure prevents success. On restart, missing workers become `interrupted`
and are never automatically retried. Live worker reattachment is not implemented.
Queue event completion means dispatch handled, not task success.

After successful worker execution:

- No acceptance checks: activity becomes `unverified`.
- All specified file checks pass: activity becomes `succeeded`.
- A specified file is missing, inaccessible, unsafe or has different bytes:
  activity becomes `failed`, with check evidence.

`proactive_status` exposes the records and outcomes. The optional voice-tool
`artifact_check` is an object with a workspace-relative `path` and an expected
`sha256` digest established before dispatch. The runtime API supports up to 16
such checks through `verification=[...]`. Do not invent a digest or adopt the
worker's claimed output as the expected result. A digest proves exact bytes only;
it does not prove semantic task correctness, authorship, or that a previously
existing artifact was newly created. Most open-ended tasks should remain
unverified until a suitable semantic checker is implemented.

The Linux verifier rejects symlinks in artifact path components, traversal,
special files and files over 16 MiB, and runs off the voice event loop. It stores
hashes and check results, not file contents. Existing activity databases migrate
transactionally to support `unverified` and `interrupted`, preserving old rows.
Historical `succeeded` rows are not retroactively validated.

Tick calls are serialized. Control revisions are checked before every dispatch;
a partial launch failure attempts to cancel already launched workers and records
cancellation errors. Stopping does not undo completed external effects. A crash
between process launch and saving its identifier is still an uncertain launch;
durable process adoption and action-level cancellation leases remain future work.
Candidate workers must not have write access to the verifier, its state database,
or acceptance criteria for this to be a meaningful trust boundary. Owner-only
SQLite permissions alone do not isolate other processes running as the same user.

Offline checks:

```sh
.venv/bin/python -m unittest discover -s tests/test_proactive -v
.venv/bin/python -m unittest tests.test_skills.test_development -v
```
