# Fix 01: Unicode character offsets (S07)

Status: implemented and tested, 2026-10-22. A running daemon must restart to load it; no service restart or spoken end-to-end test was performed here.

## What changed and why

`filesystem/filesystem.py` now skips decoded characters in chunks of at most 8192 instead of seeking to a UTF-8 byte offset. This matches the existing `read_file` schema's character-offset contract and avoids allocating the full skipped prefix. Large offsets require reading the prefix, so time remains proportional to the prefix length. Offsets count Unicode code points, not grapheme clusters.

`tests/test_filesystem/test_filesystem.py` covers accented text, Devanagari, emoji, pagination, EOF, beyond EOF, and an offset across multiple chunks. The S07 characterization test in report 12 now asserts correct behavior. Other reproduction tests still characterize unresolved bugs.

## Evidence

Before the fix, the new integration test failed with decoding errors and incorrect slices. After the fix: 24 tests passed and 10 subtests passed across filesystem, task-runner, and supplemental checks. The actual `DesktopSkills.execute('read_file', ...)` call on the voice fixture returned `VOICE CHECK PASSED`. All seven locked voice files passed verification. Codebase reference regenerated.

VERDICT: PASS

## Check through JARVIS voice

Restart JARVIS once using your normal launcher. If it runs as the user service, the terminal command is:

```sh
systemctl --user restart jarvis-oma.service
```

Say:

> Jarvis, use the read_file tool to read /home/g0pi/Projects/JARVIS-OMA/report/voice_read_check.txt with offset one and max_chars one hundred. Read the returned text aloud.

Expected result: `VOICE CHECK PASSED`, with no leading accented character and no decoding error. The fixture starts with one accented character, so offset zero would not exercise the fix. Ask for the exact offset if the model ignores that parameter. A spoken assertion without a tool call is not proof of success.

Only S07 was repaired in this change. Remaining findings stay open.
