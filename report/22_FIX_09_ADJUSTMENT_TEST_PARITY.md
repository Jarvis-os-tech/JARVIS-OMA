# Fix 09: Volume/brightness test parity (E10)

Date: 2026-10-23. Status: implemented and tested. No live volume/brightness changes or daemon restart performed.

## Change and rationale

Removed `_run.call_count` inspection from the legacy volume and brightness adapters in `skills/skills.py`. They now always delegate through `_adapter_set_volume` and `_adapter_set_brightness`, the production control paths. Test mocks no longer select a different command implementation that can hide real errors. Existing mute-toggle translation is preserved. The default manifest's compatibility aliases may already route voice calls directly to the set adapters; this change repairs legacy/custom adapter testing rather than claiming new hardware capabilities.

New regression tests use a mocked runner and require delegation to the actual control API, including propagated error results. They failed before repair and pass afterward. The existing dynamic-manifest brightness test was updated to verify the shared contract instead of expecting the removed mock-only command path.

## Evidence

Adjustment routing and dynamic skills suites: 42 tests and 16 subtests passed. All seven locked voice files verified intact. Codebase reference regenerated. No hardware state changed in these tests.

VERDICT: PASS

## Voice commands

Restart JARVIS normally to load changes. Say:

1. “Jarvis, tell me the current speaker volume and screen brightness percentages.” Record the original values.
2. “Jarvis, increase speaker volume by five percentage points and tell me the actual volume afterward.”
3. “Jarvis, increase screen brightness by five percentage points and tell me the actual brightness afterward.”
4. “Jarvis, restore speaker volume to [original volume] percent and screen brightness to [original brightness] percent.”

Expected: settings change using available desktop controls and JARVIS reports observed values. At maximum settings increases may clamp; brightness hardware can round values. Unsupported hardware or missing commands must yield an error rather than fabricated success.

These commands smoke-test the shared control path. Automated routing tests establish the particular fix: tests no longer bypass that path when mocks are present. Spoken success alone cannot prove test parity.

Planning: direct; delegation: none; scope: remove mock-only branches, adjust existing test contract, add routing regressions and report artifacts. Fixed so far: S07, S05, S04, E01, S08, S09, E06, E02, E10.
