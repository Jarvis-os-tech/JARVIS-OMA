# Desktop action verification — 28 October 2026

Scope: continue the reliability roadmap while leaving voice and audio code unchanged.

## Changes

- The shared desktop-input boundary no longer upgrades a command's `success`
  response to `verified: true` merely because the same foreground window remains
  active. Focus evidence identifies the target; it does not prove that an
  application accepted text or performed the requested click or shortcut.
- Without an explicit verified effect observation, input results are returned as
  `unverified_effect`, with `verified: false` and the existing accessibility/CLI
  fallback. An adapter's explicit negative verification is not overwritten.
- A clipboard copy that exits unsuccessfully stops multiline input before any
  paste or Return key is sent, avoiding accidental pasting of the old clipboard.
- Both typing paths check the Return key command's exit status. If text input
  completes but Return fails, the result reports an error and partial execution.
  The input is not automatically replayed.
- Verified window close/minimize results retain their separate exact-target
  readback contract; they do not require a closed or minimized window to remain
  the foreground window.

The restored startup capability fixes were already present at the beginning of
this implementation pass. Their 17 regression tests passed in the combined run.
No further startup or voice changes were needed for this work package.

## Tests and evidence

The new `tests/test_skills/test_action_outcomes.py` reproduced 14 failing cases
before the fixes, with six existing-behavior guard cases passing. After the
changes, all 20 cases passed.

Combined startup recovery, desktop/system controls, modal handling, plugin
readback, GUI control and ground-truth tests: **146 passed, 8 subtests passed**.
Commands, windows and subprocess responses in the new tests are mocked. No real
typing, clipboard modification, mouse action, audio capture or cloud call was
used for these regression checks.

Full-suite result: **1,027 passed, 27 failed, 2 skipped, 289 subtests passed**.
An isolated unchanged `1403816` baseline produced **1,003 passed, 31 failed,
2 skipped, 289 subtests passed**. Comparing test identities found no introduced
failures and 20 new passing tests. Of the four baseline failures that passed in
the working checkout, two are the typing-result failures fixed here; the other
two are vision tests whose isolated baseline lacks the installed, untracked
`vision_ctrl` binary. Those environment differences are not claimed as fixes.
All 27 remaining failures also failed in the unchanged baseline.

The remaining failures include older CLI/declaration expectations, orchestration,
phone notices, desktop fixtures and vision-stream/entrypoint behavior. They are
not evidence that the entire release is ready; voice-related failures are outside
this change's permitted scope.

| Verification | Result |
| --- | --- |
| Python syntax/build check | All four changed/new Python files parsed successfully. |
| Type and lint tools | `pyright` and `ruff` are not installed in the project environment; not run. |
| Coverage | Not measured; `pytest_cov` is not installed. |
| Focused tests | 146 passed; 8 subtests passed. |
| Full tests | 1,027 passed; 27 baseline failures remain; no introduced failure identities. |
| Scoped security review | No new credentials, shell evaluation, permissions or external actions; failed clipboard copy cannot paste old content. |
| Voice boundary | All 44 snapshotted files unchanged; all seven protected files intact. |
| Release status | This desktop work package is tested; the broader release remains blocked by its existing gates. |

```sh
.venv/bin/pytest -q tests/test_skills/test_action_outcomes.py \
  tests/test_skills/test_capability_startup_recovery.py \
  tests/test_skills/test_system_control.py tests/test_skills/test_modal_healing.py \
  tests/test_skills/test_plugin_control_reliability.py \
  tests/test_skills/test_gui_control.py tests/test_skills/test_ground_truth.py
python3 scripts/verify_voice_lock.py
```

## Voice preservation

Before making changes, hashes were recorded for 44 tracked voice, audio, runtime,
launcher and configuration files. Comparison after implementation found no
changes. The seven protected voice-core files also passed their integrity check.
No service restart or microphone configuration change is part of this package.

## Remaining work

This closes the two known registry typing-result failures in the practical
roadmap. It does not complete its verified OS-control phase. An unverified input
still needs an application-specific readback, accessibility observation or user
check before claiming its intended effect or retrying it.

The planned 20 intents × 3 live trials, zero wrong-target writes, crash-safe task
recovery and long-duration reliability gates remain open. Voice performance and
interruption work are outside this user-authorized scope.
