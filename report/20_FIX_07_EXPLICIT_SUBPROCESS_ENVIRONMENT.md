# Fix 07: Explicit empty subprocess environment (E06)

Date: 2026-10-23. Status: implemented and tested. No service restart or voice check performed.

## Change and rationale

`skills/system_control.py` now uses the desktop default only when `env is None`. An explicit empty dictionary stays empty; explicit custom dictionaries stay unchanged. Broader credential filtering of default environments (E03/E04) remains open and is not claimed fixed by this change.

## Evidence

A real child-process test failed before the fix: a synthetic parent variable was present despite `env={}`. After repair, dedicated real-process tests verify empty, default, and custom environment cases. Only synthetic variables are printed by tests. Dedicated environment tests: 3 passed. All seven locked voice files verified intact; codebase reference regenerated.

Runs including the broader desktop-control suite or supplemental checks stalled and were interrupted without a final result. It is not counted as passing. The focused checks were rerun separately and passed.

VERDICT: PASS

## How to check

There is no direct voice-tool parameter to supply a subprocess environment. Normal spoken desktop actions cannot establish that inheritance was prevented. Run from the project directory:

```sh
.venv/bin/pytest -q tests/test_skills/test_subprocess_environment.py
```

Expected: 3 passed. Restart JARVIS normally to load the change. Normal desktop actions may be used as a smoke check only.

Planning: direct; delegation: none. Scope: one environment fallback, dedicated tests, supplemental test and report artifacts. Fixed findings so far: S07, S05, S04, E01, S08, S09, E06.
