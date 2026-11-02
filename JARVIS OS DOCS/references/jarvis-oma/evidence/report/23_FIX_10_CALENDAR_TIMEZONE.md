# Fix 10: Explicit calendar event timezone (E09)

Date: 2026-10-23. Status: implemented and tested. No live Google request, event creation, service restart, or spoken test performed.

## Change and rationale

Added optional `time_zone` to the calendar creation tool schema, skills adapter, connector dispatcher, and creation function. The connector validates IANA zone names using ZoneInfo before calling the Google API, then uses the selected zone for both event boundaries. Omitted values preserve the existing Asia/Kolkata default. Explicit datetime strings, including their offsets, are forwarded unchanged.

This repairs the inability to choose another event timezone. It does not add automatic calendar/account timezone discovery, local-time conversion, validation of offset/zone contradictions, or DST ambiguity resolution. Callers should provide coherent datetimes and zone names; those broader improvements remain separate.

## Evidence

Calendar timezone and existing Google connector suites: 26 passed. New tests cover explicit Asia/Tokyo through the actual tool schema/adapter/dispatcher, backward-compatible omission, and invalid-zone rejection before any API call. Google API responses are mocked and credentials are not used.

Initial async routing attempts stalled. An independent asyncio.to_thread smoke check also timed out, so new routing tests use an inline worker stub, matching existing connector tests. This verifies routing and request construction, not real worker scheduling or Google acceptance. Interrupted runs are not counted as passing.

Voice lock verified: all seven core files intact. Codebase reference regenerated.

VERDICT: PASS

## Voice check

Restart JARVIS normally. If Google Calendar is connected and you want a real test event, say:

> Jarvis, create an event called Timezone Check on October 26, 2026, from 10:00 to 10:15 in the morning Tokyo time. Use Asia/Tokyo as the event timezone, with no guests. Then read the event back to me in Tokyo time.

Expected: 10:00–10:15 Asia/Tokyo. In a calendar displayed in India time, the same event appears at 06:30–06:45. Inspect the event timezone in Google Calendar to verify it is Asia/Tokyo, not merely an India-zone event at an equivalent instant. Remove the test event manually afterward if desired; this connector currently has no calendar-delete tool.

This voice check creates an actual event. A spoken claim alone is insufficient: verify the returned event or calendar entry. If authorization is missing, connect Google Calendar before trying it.

Planning: compact; context depth: dependency; verification depth: impact; delegation: none. Scope: timezone argument across tool boundaries, validation, dedicated tests, and documentation. No other calendar behavior intentionally changed.
