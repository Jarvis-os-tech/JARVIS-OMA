# Startup capability recovery — 27 October 2026

## Debug report

| Field | Result |
| --- | --- |
| Symptom | Supported commands could be rejected at startup. |
| Root cause | Permanent missing-command cache, reduced launcher PATH, early desktop-session probing and stale routing metadata. |
| Fix | Shared command resolution, dependency-only recovery, bounded desktop wait, later session recovery and fresh domain/router metadata. |
| Evidence | 100 focused tests passed; 17 new regression tests passed; the full suite retained exactly its 29 baseline failures. |
| Regression tests | `tests/test_skills/test_capability_startup_recovery.py`; `tests/test_core/test_startup.py`. |
| Related | Existing microphone policy and action verification were preserved; this change does not alter voice-core implementation. |
| Status | DONE_WITH_CONCERNS: startup fixes verified offline; wider suite has existing failures and the daemon is stopped. |

## Symptom and reproduced causes

JARVIS could reject an action immediately after startup even though the necessary
tool was available later in the same session. The investigation reproduced these
specific causes:

1. The command registry cached missing executables indefinitely. Capability
   discovery checked the current PATH separately, so discovery and execution
   could disagree. With `exclude_unavailable = true`, a temporary missing command
   also removed its tools for the entire lifetime of the registry.
2. The service launcher invoked the virtual environment's Python directly without
   adding its command directory to PATH. Project-installed tools such as
   `cli-hub` could therefore be invisible under the service's smaller PATH.
3. The launcher made a single desktop-session check. Wayland and Hyprland sockets
   appearing shortly afterward were not consistently available to GUI commands,
   system controls, and verification helpers.
4. Capability lookup omitted each tool's domain, which is needed for an exact
   `execute_domain_tool` call. The local Groq router also retained its initial
   declaration snapshot after a dependency recovered.

## Changes

- `skills/skills.py` now uses one command resolver for discovery and execution,
  retries missing or invalid executable paths, and restores tools excluded only
  because a dependency was missing. Configuration exclusions remain authoritative.
- Capability inspection, domain discovery and dispatch refresh readiness without
  executing desktop actions. Capability results include the exact domain and
  continue to report `runtime_verified = false` until actual execution verifies it.
- `run.sh` exposes project-installed commands and waits up to five seconds for
  missing desktop identifiers. A slow desktop does not permanently disable tools:
  later capability requests and desktop command environments retry recovery.
- Recovery preserves explicitly configured desktop identifiers and only infers
  missing values when the socket evidence identifies one unambiguous session.
  Shared process identifiers reach independent GUI and verification helpers;
  subprocess environments still filter credentials.
- `core/agent.py` refreshes the local router's declarations before routing a new
  command. Existing domain discovery remains available to the connected voice
  session; recovered domain tools do not require a daemon restart.

The seven locked voice-core files were not modified. Existing microphone policy,
argument-alias, and action-verification edits present before this investigation
were preserved.

## Verification

- Focused startup, recovery, configuration, credential-filtering and voice-lock
  tests: **63 passed, 52 subtests passed**.
- Desktop-session, subprocess-environment, connection, adjustment-routing and
  ground-truth checks: **37 passed, 5 subtests passed**.
- The new recovery module contains 17 regression tests, including late command
  availability, replacement binaries, configuration exclusions, exact domain
  routing, late desktop identifiers and the actual launcher under a reduced PATH.
  Its initial dependency-recovery tests reproduced ten failures before the fix.
- Launcher shell syntax passed. `scripts/verify_voice_lock.py` confirmed all seven
  protected files are intact.
- `run.sh --check` passed with the service-style reduced PATH. This check did not
  open audio or a network connection.
- Full-suite result: **922 passed, 29 failed, 2 skipped, 289 subtests passed**.
  An isolated copy of the earlier production code, preserving the four existing
  user edits and using the same safe audio test fixtures, produced **905 passed,
  29 failed, 2 skipped, 289 subtests passed**. Comparing test identities and
  outcomes found **the same 29 failures, no new failures, no changed outcomes for
  shared tests, and 17 added passing recovery tests**.
  The wider suite therefore remains failing; it is not reported as a clean pass.
  Existing failures cover greeting/vision fixtures, orchestration and cost-policy
  expectations, tool-tier declarations, CLI-hub expectations, phone notices and
  desktop action verification.

To rerun the startup-specific checks:

```sh
.venv/bin/pytest -q tests/test_skills/test_capability_startup_recovery.py \
  tests/test_core/test_startup.py tests/test_core/test_secret_env.py \
  tests/test_core/test_config.py tests/test_audio/test_voice_lock.py
.venv/bin/pytest -q tests/test_core/test_desktop_session.py \
  tests/test_skills/test_subprocess_environment.py tests/test_core/test_connection.py \
  tests/test_skills/test_adjustment_routing.py tests/test_skills/test_ground_truth.py
python3 scripts/verify_voice_lock.py
bash -n run.sh
```

The desktop-session tests bind temporary local sockets and need permission to do
so in a restricted test environment. Test audio engines and providers are mocked;
the native backend readiness ordering is covered without opening a device.

## Operational limits

At the final service check, `jarvis-oma.service` was inactive and no other loaded
`jarvis*.service` was active. The source changes are in the checkout used by that
service and will load on the next start. The stopped service was left stopped.

These changes fix the reproduced startup recovery failures. They cannot guarantee
that every future request succeeds: an absent dependency, disconnected account,
ambiguous desktop session, provider outage or genuinely unsupported action still
requires an accurate error. No live spoken-command or cloud-inference test was
performed during this investigation.
