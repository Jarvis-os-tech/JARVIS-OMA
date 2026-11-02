# Verified source copy

This records the copy-integrity checks performed on 29 October. The later [working-status check on 30 October](WORKING_STATUS_2026-10-30.md) tests imports and behavior and identifies unresolved application and voice failures.

- **14 automated integrity tests passed**, with zero failures or errors.
- **1427 original entries** copied: 1426 regular files and 1 internal relative symlink.
- Every canonical copy matches the captured source checksum. Copies are separate files, not hard links.
- Every original source still matches its captured checksum. Git status outside `Oma Jarvis` matches the pre-copy state, including all pre-existing edits.
- The only new working-tree area is `Oma Jarvis/`. No service, audio device, application entry point or installer was run.
- **All seven locked voice files passed the original integrity verifier**, and their copied bytes match the lock manifest.
- **987 Python source copies parsed** without errors; they were not imported or executed.
- **269 feature extracts** match their recorded source slices exactly. They are non-executable `.py.txt` reading aids.
- **189 bundled tools** resolve to copied handlers, including compatibility aliases.
- Tracked source coverage, copy path uniqueness, local symlinks, dependency targets and generated navigation links were checked.

## Validation scope

These checks verify the organized copy, provenance, classification coverage and preservation of the original project. They do not certify an independently runnable refactor: imports and resource paths deliberately remain unchanged. The original application test suite was not rerun for this copy-only task; existing application defects were not changed.

## Re-run the copy checks

From the original project root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q -p no:cacheprovider -c /dev/null --confcutdir='Oma Jarvis/_analysis/tests' 'Oma Jarvis/_analysis/tests/test_organized_copy.py'
python3 scripts/verify_voice_lock.py
```

If a source file changes later, the original-snapshot check will report it. That is expected for an actively developed project; it is not a reason to overwrite either version automatically.

Machine-readable evidence: `validation.xml`, `verification.json`, `copy_manifest.json`, and the before/after Git status files in this folder.
