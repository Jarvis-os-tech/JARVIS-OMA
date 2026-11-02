# Calendar follow-up: IST accuracy and missing management tools

Date: 2026-10-23. User preference: always use Indian Standard Time, Asia/Kolkata.
Status: implemented and tested locally; no live Google events created, updated, or deleted, and no running JARVIS restart performed.

## Findings and scope

The original connector accepted datetime strings without checking whether their UTC offset matched the event timezone. Thus an IST wall time accidentally tagged as Z could represent a different instant. This is an established missing validation, not proof that it caused the user's particular past mis-scheduling: no exact spoken/requested versus saved timestamp example was supplied or retrieved.

The task-creation tool had no scheduling parameter and cannot place an exact-hour item. Google Tasks API due values represent dates, not precise scheduled hours. Timed requests must use Calendar. The voice instructions now distinguish these explicitly.

Calendar previously exposed only list, read, create, and list-calendars. Delete and reschedule were missing. Custom recurrence, custom popup reminders, availability, and a fresh clock were also absent. Common management operations are now wired through the actual voice tool registry to the connector.

## IST and time handling

- Default remains Asia/Kolkata; helper accepts IST as an alias. Another zone is used only if explicitly requested.
- `calendar_current_time` supplies a fresh date, weekday, timezone, and offset. Voice instructions require it for today/tomorrow/now/relative requests instead of relying on stale conversation dates.
- Naive local datetimes become explicit offset-aware ISO values without moving their wall time. Example: 15:00 becomes 15:00+05:30 in IST.
- Conflicting offsets are rejected with an actionable error. The tool does not silently reinterpret 15:00Z as 15:00 IST or auto-correct the model's guess.
- End must be after start. Malformed timestamps and ambiguous/nonexistent DST wall times in other zones are rejected rather than guessed.
- Missing duration or ambiguous AM/PM is a clarification, not an invented schedule.
- Creation/update returns the provider's schedule when supplied. `time_verified` distinguishes a provider schedule from request-only fallback metadata. Voice instructions require `calendar_get_event` after writes to read back the saved time.
- Prompt improvements guide model behavior; deterministic tests cannot guarantee every future spoken phrase will be interpreted correctly. A live voice retry remains necessary for the user's actual symptom.

## Supported calendar actions after this change

| Action | Status / interface |
|---|---|
| Read current IST date/time | Added `calendar_current_time` |
| List/search scheduled events | Existing `calendar_list_events`; explicit time bounds permit past searches |
| Read event details and timezone | Existing `calendar_get_event`, richer time/recurrence/reminder results |
| Create timed event | Existing tool with validated IST boundaries |
| Reschedule, rename, change description/location | Added `calendar_update_event`; rescheduling needs both boundaries |
| Delete an identified event | Added `calendar_delete_event`; exact event ID, ambiguous matches require clarification |
| Check busy/free periods | Added `calendar_check_availability`; API failures never mean free |
| Recurring timed events | Optional `recurrence_rule` on create/update; single RRULE; Google validates rule semantics |
| Popup reminders | Optional `reminder_minutes` on create/update; 0 at event start, -1 disables, omit preserves defaults |
| Manage one recurring occurrence or whole series | Instance IDs and recurring master IDs are returned; select scope explicitly before modification |
| Choose an existing calendar | Existing `calendar_list_calendars` and calendar_id arguments |
| Guests | Existing creation attendees; editing guests/RSVP is still absent |

## Remaining gaps found

This is not the entire Google Calendar API. Dedicated all-day creation, access/sharing management, attendee/RSVP edits, Meet-link generation, and moving events between calendars are not exposed. Calendar creation/deletion and event file attachments are now exposed. Multiple complex recurrence/exclusion lines are not supported by the single-rule argument. Google Tasks timed notifications are not added; Calendar is used for exact-hour scheduling.

JARVIS's existing proactive spoken reminders and Google Calendar popup reminders are different features. Setting a popup does not prove a spoken reminder will fire or that the browser/device permits notifications. Live notification delivery was not tested.

## Implementation

- New `connectors/calendar_time.py`: timezone lookup, offset/zone validation, DST-safe localization, and interval ordering.
- `connectors/google_workspace.py`: clock/update/delete/free-busy endpoints; creation options; provider schedule metadata; recurrence master IDs.
- `skills/skills.py` and `skill_manifests/google-workspace.json`: complete declaration/adapter/dispatcher wiring and descriptions for exact-time routing.
- `core/agent.py`: IST clock, clarification, readback, and safe event-selection guidance. No locked voice changes.
- New `tests/test_skills/test_calendar_management.py`: actual declared tool pipeline with mocked API and inline worker, plus real datetime validation.

Planning policy: compact; context depth dependency; verification depth impact; delegation none. Scope is calendar time interpretation and common management operations. No external account mutations authorized by the tests or performed during implementation.

## Verification

- Calendar-management, timezone, and existing Google-connector suites: 38 passed, 12 subtests passed.
- Live configuration/instruction tests: 9 passed, 52 deselected. Google SDK accepts the expanded tool declarations.
- Combined: 47 tests and 12 subtests passed.
- All seven locked voice files verified intact; codebase reference regenerated.
- Tests cover actual schema/adapter/dispatcher wiring, IST normalization, offset conflicts, interval validation, invalid reminder/recurrence formats, rescheduling, reminder/recurrence removal, exact-ID URL escaping, delete errors, free-busy errors, and schedule readback metadata.
- Existing worker-scheduling stalls in the restricted environment are avoided in connector unit tests with an inline worker stub. Real thread scheduling, OAuth authorization, Google persistence, live speech interpretation, and notification delivery were not validated.

VERDICT: PASS

## Voice checks after restarting JARVIS

These commands create/change/delete a real test event. Use an authorized connected Google account.

1. “Jarvis, what is today's date and current time in IST? Use the calendar clock tool.”
2. “Jarvis, create a calendar event called IST Test tomorrow from 3 PM to 3:30 PM IST, with no guests. Read back the saved date and time.”
3. “Jarvis, move only that IST Test event to tomorrow from 4 PM to 4:30 PM IST, and read back the saved time.”
4. “Jarvis, add a popup reminder ten minutes before that IST Test event.”
5. “Jarvis, am I free tomorrow from 5 PM to 5:30 PM IST?”
6. “Jarvis, delete only that IST Test event tomorrow at 4 PM IST, then check that it is gone.”

Expected: clock reports +05:30; event retains requested date and wall time; update preserves unrelated event fields; reminder is stored as a popup override; availability reports actual busy periods or an explicit failure; deletion targets only the selected event and later listing no longer shows it. If multiple events match, JARVIS must ask which one.

Optional recurring check: “Jarvis, create a 15-minute event called Weekly IST Test every Monday at 10 AM IST for two occurrences, starting next Monday, with no guests.” Read back the rule/dates. To remove it, explicitly request the entire Weekly IST Test series. Do not confuse series deletion with deleting one occurrence.

## Reference basis

- Google Events insert: https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
- Google Events patch: https://developers.google.com/workspace/calendar/api/v3/reference/events/patch (unspecified fields are preserved; specified arrays replace existing arrays)
- Google Tasks resource: https://developers.google.com/workspace/tasks/reference/rest/v1/tasks

No live Google API success is inferred from mocked tests.
