# PMA voice copy verification — 2026-10-30

Copy verification passed: **7 automated checks passed**. The JARVIS voice-lock verifier also confirmed all **7 locked core files** remain intact.

| Check | Result |
| --- | --- |
| Complete files | 30 copies match their original bytes, permissions and recorded SHA-256 hashes; no hardlinks to sources |
| Feature excerpts | 47 excerpts match their recorded original line ranges exactly and are labelled non-executable `.txt` files |
| Python syntax | All 15 complete Python files compile in memory, without imports or execution |
| Shell syntax | All 7 copied command wrappers pass `bash -n`; no command was executed |
| Indicator metadata | Both JSON manifests parse and their QML entry files exist |
| Selection and dependencies | Every one of the 106 inventoried PMA files is accounted for as a complete copy or an omitted full file; shared dependencies are disclosed |
| Preservation | All 106 inventoried PMA files and 2,490 pre-existing JARVIS files/entries retain their recorded contents or symlink targets and permissions; both Git status snapshots are unchanged |
| Documentation | Generated feature/source links checked; verification report added after checks |

The preservation comparison includes the pre-existing `Oma Jarvis` collection. The only project additions made for this task are under `Oma Jarvis/voice/pma/`. Helper scripts and baseline evidence are outside both source projects, under the Codex visualization workspace.

## What this establishes

The selected source files were copied without rewriting, and the feature excerpts preserve the original lines. Existing uncommitted source changes were retained. No old copy, running-project source, package reference, service, environment or device configuration was changed.

This collection is **not independently runnable**: its folder layout differs from the original package, and shared/nonvoice modules were intentionally left out. No imports were rewritten and no compatibility shims were added. See [dependency map](DEPENDENCY_MAP.md).

The six copied upstream regression-test files were preserved but **not run**. The seven passing checks are copy-integrity, syntax, selection, preservation and documentation checks—not a claim that the voice engines function end to end. QML rendering, systemd service behavior, API access, microphones, audio playback and latency were not exercised. The paid protocol probe was copied but not executed.

## Evidence

- [Validation results](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/copy_validation.xml)
- [Copy manifest and exclusions](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/copy_manifest.json)
- [File and excerpt source map](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/SOURCE_MAP.csv)
- [Python import inventory](../../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/import_dependencies.json)
- Validation script: `/home/g0pi/.codex/visualizations/2026/10/28/01a18322-bb73-7152-b6ff-08dbb72b478b/pma-voice-copy-check/test_copy_integrity.py`
- Preservation evidence: `/home/g0pi/.codex/visualizations/2026/10/28/01a18322-bb73-7152-b6ff-08dbb72b478b/pma-voice-copy-check/preservation.json`

Checks used the existing JARVIS `.venv/bin/pytest` with application plugins/cache disabled and an isolated test root; `python3 -B scripts/verify_voice_lock.py` ran from JARVIS. No application code was executed. The generated source/dependency maps are local to this new collection; the running project's reference generator was not run because it would modify the original documentation.
