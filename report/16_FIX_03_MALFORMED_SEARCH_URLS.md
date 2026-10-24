# Fix 03: Malformed search-result URLs (S04)

Status: implemented and tested, 2026-10-22. No service restart or live search was performed.

## Change

`connectors/internet_search.py` now catches URL-parser ValueError exceptions and rejects the malformed item. Valid later search results survive. If every result is invalid, callers receive the existing SearchProviderError instead of an unexpected parser exception. Existing public-link restrictions remain in place.

## Verification

New deterministic tests failed before the repair on malformed URLs. After repair, search-result URL tests plus supplemental checks passed: 14 tests, 8 subtests. Tests cover malformed items followed by valid sources, all-invalid responses, and existing nonpublic/credentialed URL rejection. Network requests were mocked; synthetic credentials only. The supplemental S04 check now asserts the repaired behavior.

See final session output for the existing search-suite result. Voice lock verified; codebase reference regenerated.

Planning: direct; delegation: none; scope: URL validator, dedicated regression tests, and report artifacts. No locked voice changes.

## Voice check and its limits

Restart JARVIS using your normal launcher or `systemctl --user restart jarvis-oma.service`.

Say:

> Jarvis, search the web for Python documentation and tell me which sources you found.

Expected: normal search results and usable source links. This is a smoke check only: a normal provider response does not reproduce the malformed-link case, and JARVIS may use another search provider. The deterministic automated tests establish that a malformed Brave result is skipped and a valid later result is retained. Do not treat a spoken statement of success alone as proof of the parser fix.

Fixed so far: S07, S05, S04. Other findings remain open.

Existing search checks: 7 passed, 30 deselected. Combined verification: 21 tests and 8 subtests passed across the two runs.

VERDICT: PASS
