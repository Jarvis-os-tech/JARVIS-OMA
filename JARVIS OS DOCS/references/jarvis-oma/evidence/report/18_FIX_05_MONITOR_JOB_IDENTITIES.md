# Fix 05: Monitor job-ID aliases (S08)

Date: 2026-10-23. Status: implemented and tested. No live voice or daemon restart performed.

## Change and rationale

`proactive/monitor.py` uses one ID normalizer before duplicate checking and before every lookup. Tracking, getting, updating, and starting retries now agree about surrounding whitespace. Invalid or blank IDs raise MonitorError. A duplicate alias cannot replace the original job's deadlines, retry configuration, or metadata.

Two new project tests failed before the fix: duplicate aliases were admitted and whitespace lookups failed. After repair, tests cover preservation of the original record, canonical IDs across update/retry, and invalid IDs. The supplemental S08 check now asserts rejection of the duplicate and preservation of original metadata.

## Evidence

Monitor and supplemental checks: 22 passed, 4 subtests passed. All seven locked voice files verified intact. Codebase reference regenerated.

VERDICT: PASS

## How to check

This component API is not exposed as a direct JARVIS voice tool. Ordinary spoken task creation does not reliably exercise whitespace-alias admission and must not be presented as proof of this repair.

Run the focused regression from the project directory:

```sh
.venv/bin/pytest -q tests/test_proactive/test_proactive_monitor.py -k 'whitespace_alias or job_identity'
```

Expected: 2 tests pass, with the original job preserved after a duplicate-ID attempt. Restart JARVIS normally to load updated Python modules if it uses this monitor; no special spoken action is required.

Planning: direct; delegation: none. Scope: monitor ID handling, regression tests, supplemental check, and documentation. Remaining findings unchanged. Fixed so far: S07, S05, S04, E01, S08.
