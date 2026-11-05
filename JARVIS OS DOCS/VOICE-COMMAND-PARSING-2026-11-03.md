# Step 2: voice-command parsing

Implemented a bounded English parsing pilot using the collected OpenVoiceOS
number/date span APIs. The initial build was tested in the checkout; the user
subsequently authorized deployment, completed below.

## Resulting behavior

- Exact PC volume, brightness and workspace commands accept spoken numbers,
  including zero, hundreds and hyphenated numbers. Existing integer ranges
  remain: volume 0–100, brightness 1–100, workspace 1–10.
- A parsed value must cover the entire value phrase. Fractions requiring
  rounding, negative/out-of-range settings, alternatives, extra instructions
  and multiple controls fall back instead of executing locally.
- The voice tool gate compares supported explicit numeric commands with
  model-proposed arguments. It rejects a different value or control, rounding,
  clamping and guessing between alternatives. This covers the pilot's exact
  command grammar; it is not a general proof of arbitrary multi-step commands.
- Values retain their original surface and half-open Unicode character
  offsets. Quoted content, code, URLs, paths and common alphanumeric IDs are
  protected. Phonetic normalization still works outside those protected spans.
- Provider transcription chunks are retained verbatim as user evidence.
  This also protects a quoted string or path split across transcription chunks.
- Quoted standby/pairing text cannot trigger those intent categories or the
  corresponding quoted authorization hints.

Examples of local command parsing:

| Original words | Result |
| --- | --- |
| Set volume to forty five percent | `volume_set`, 45 |
| Could you set brightness to sixty percent? | `brightness_set`, 60 |
| Switch to workspace two | `workspace_switch`, 2 |
| Set volume to thirty or forty | No local execution; numeric tool proposal rejected pending clarification. |
| Set volume to minus five | No local execution or silent conversion to positive five. |
| Type "java forty five" | Quoted text stays unchanged. |

## Date and duration capability

The read-only `parse_command_values` tool is registered in the live tool catalog
and excluded from action-completion evidence. It returns `candidate_only: true`:
parsing does not create a reminder, calendar event or other task.

The tool accepts original text, language, `include_temporal`, an optional ISO
`anchor_datetime` with a UTC offset, and an explicit IANA `time_zone` defaulting
to `Asia/Kolkata`. If the reference time is omitted, the adapter samples the
current time once in the requested zone. Relative dates never depend on the
worker's host-local timezone.

With reference `2026-11-03T23:45:00+05:30`:

| Words | Parsed candidate |
| --- | --- |
| tomorrow at five pm | `2026-11-04T17:00:00+05:30` |
| in thirty minutes | `2026-11-04T00:15:00+05:30`, duration 1800 seconds |
| tomorrow at 17:30 | `2026-11-04T17:30:00+05:30` |
| at five | AM/PM clarification required. |
| on 04/05/2026 | Explicit, unambiguous date/time required. |
| at 5 pm PST | Timezone clarification required; not silently interpreted as IST. |

Contained duplicate date spans with equal values are collapsed. Multiple date
candidates require clarification. Existing calendar validation rejects DST
folds/gaps and explicit offset/zone conflicts. Explicit relative durations
count elapsed seconds across DST, rather than silently adding wall-clock hours.

The tool description tells the model to use temporal parsing before scheduling,
report the resolved timestamp/zone and ask about ambiguity. Existing calendar
creation APIs still require explicit datetimes. This is guidance and a read-only
parsing capability, not universal enforcement that every scheduling path must
have a prior parser receipt.

## Dependencies and execution boundary

Core requirements add `ovos-number-parser==0.24.3a1`, with evaluated
`quebra-frases==0.3.7` and `unicode-rbnf==2.4.1`. Optional temporal requirements are
in `configs/parsing-requirements.txt`, included by development/test requirements.
They pin `ovos-date-parser==0.35.7a1` and selected evaluated temporal dependencies.
This is not a full transitive dependency lock.

Both installed span API modules matched the collected source byte-for-byte:

- Number parser source commit: `8e527673eb0e0aae9776d33e38e05bc32fdd7dbb`.
- Date parser source commit: `2c24a781d1869b05d96c6aca43847a08025f8b59`.

The Apache-2.0 packages are consumed as dependencies; no upstream source was
copied into JARVIS. The typed-slots plugin supplies the span/value design
reference without importing its framework dependencies.

The date package brings additional OVOS/config/calendar libraries. An isolated
experiment resolved 36 total packages. Measured cold imports in that experiment
were approximately 0.43 seconds for numbers and 3.8 seconds for dates; these are
single-machine observations, not latency guarantees. Date imports/scanning run
in a separate process with a temporary HOME/XDG profile, a 10-second deadline,
and bounded input/output. Cancellation and timeout kill and reap the worker.
The real-time audio loop never imports the date parser. Number parsing is lazy
and does have a first-use import cost.

Input is bounded to 512 characters and 64 words. Unsupported language, missing
dependencies, no match, invalid parsing and worker timeout have distinct
statuses. This pilot admits English; existing Hinglish routing remains, without
claiming new Hindi number/date support. Missing optional temporal dependencies
return an explicit diagnostic.

## Verification

- Focused parser/NLU/local voice/catalog/calendar checks: **170 passed, 12 subtests**.
- Required behavior gate: **125 passed across nine contracts**, including the
  original input bar, attachments, vision, cancellation, permissions, evidence
  and rollback cases. Source fingerprint remained unchanged during the run.
- Golden numeric commands are in `tests/behavior/parsing_cases.json`; the new
  `PARSING-1` contract keeps these cases required for future source releases.
- Saved gate evidence: `VOICE-COMMAND-PARSING-EVIDENCE-2026-11-03.json`.

Run from the checkout:

```bash
.venv/bin/python scripts/behavior_gate.py --report /tmp/jarvis-parsing-gate.json
```

Development dependencies were installed only into the checkout's `.venv` and
a temporary evaluation environment. Live speech recognition, provider behavior,
actual control effects and installed-service deployment were not acceptance
tested in this task.

References: [collected source review](upstream-sources/2026-11-03/README.md),
[number parser](https://pypi.org/project/ovos-number-parser/),
[date parser](https://pypi.org/project/ovos-date-parser/).

## Authorized deployment

Deployed release:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261103T165256169577Z-command-parsing`.
Previous release retained:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261103T160238419426Z-input-vision-repair`.

`scripts/prepare_parsing_release.py` overlays reviewed definitions on the
installed runtime, keeping its `jarvis_voice` package layout. It also deploys
the prerequisite binary-audio forwarding fix and source-build gate. Test-only
aliases allow the source tests to exercise that installed package directly.
The first staging attempt was rejected because a test helper was absent; the
helper was added and the second candidate passed all **125 checks** under the
installed Python 3.13 environment before activation.

Installed the evaluated parsing dependencies: 28 added packages, with no
existing package upgrades. Release rollback restores code and service pointers;
the additional shared-environment packages remain installed.

After activation, both `jarvis-voice` and `jarvis-device-bridge` were active.
The running service exposed 97 voice tools (previously 96), including the parser.
Three read-only calls through its control socket verified:

- “set volume to forty five percent” returns 45 without changing the setting.
- “tomorrow at five pm,” anchored at `2026-11-03T23:45:00+05:30`, resolves to
  `2026-11-04T17:00:00+05:30`.
- “at five” requires clarification.

Final service state: standby true, mute false, vision off, local speech ready,
no active tools and no reported error. These preserve the prior settings.
No real volume change, calendar creation, screen capture or spoken ASR test was
performed during verification.

Deployment evidence: `VOICE-COMMAND-PARSING-DEPLOYMENT-2026-11-03.json` and
`VOICE-COMMAND-PARSING-LIVE-CHECKS-2026-11-03.json`. The candidate's full gate
report is retained inside its release as `behavior-gate.json`.
