# Fix 06: Non-finite policy time inputs (S09)

Date: 2026-10-23. Status: implemented and tested. No live daemon restart performed.

## Change and rationale

`proactive/policy.py` now rejects NaN and infinite evaluation timestamps before pause handling or policy-state mutation. Duration configuration must also be numeric and finite; action counts must be integers, excluding booleans. Existing nonnegative-duration and positive-window/count requirements remain enforced. This prevents invalid time entries from becoming permanently unexpired rate-limit records.

Finite backward timestamps are outside this fix's scope; normal callers must continue supplying monotonic time. Invalid caller input is the trigger for S09; ordinary monotonic clocks do not produce NaN.

## Evidence

New tests failed before the repair on accepted NaN/infinite timestamps and invalid configuration. After repair: 69 tests and 48 subtests passed across the proactive suite and supplemental checks. Cases verify that invalid inputs leave normal admission and rate-window expiry working, both before and after a valid event. The supplemental S09 check now asserts rejection and successful later admission. All seven locked voice files verified intact. Codebase reference regenerated.

VERDICT: PASS

## How to check

This is an internal validation fix, not a directly exposed voice action. Normal voice commands cannot deliberately inject these invalid numeric timestamps, so a spoken confirmation would not test it.

Run from the project directory:

```sh
.venv/bin/pytest -q tests/test_proactive/test_proactive_policy.py -k 'invalid_timestamps or limits_reject'
```

Expected: both selected tests pass. Restart JARVIS normally to load the updated module. No rate-limit tuning or extra voice action is required.

Planning: direct; delegation: none; scope: finite policy inputs, relevant tests, and report artifacts. Fixed findings so far: S07, S05, S04, E01, S08, S09. Other findings remain open.
