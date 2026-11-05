# Phase 2: read-only healer incident ingestion

Built 2026-11-05 (Asia/Kolkata). The local importer is `learning/os_ingestion.py`; tests are `tests/test_learning/test_os_ingestion.py`. It uses the standard library and existing contract/hash/private-directory helpers. No voice tool, daemon, service configuration, cloud SDK or optional optimizer dependency was added.

Attribution: CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M. Adamek (Impact Brussels ASBL). Content CC-BY-4.0; code Apache-2.0.

## What is implemented

Select one occurrence row from an explicitly named healer SQLite database. The reader uses mode=ro, query_only, trusted_schema=OFF and a read transaction. It validates a physical incidents table with integer primary-key occurrence IDs, text domain/timestamp columns, the systemd_service domain and freshness. Source database and WAL files are each limited to 256 MiB; query progress has a cooperative two-second deadline and connection lock timeout. Invalid/missing input never initializes ingestion state. It does not instantiate healer's store, which would initialize schema and journaling.

Only row ID, domain and creation timestamp are selected. Raw trace_json, title, symptom fingerprint, prompts and logs are not selected or exported. The imported contract has producer=healer-metadata, component=unidentified-user-service, state=unknown and empty evidence. This is historical metadata about a reported service-domain incident, not proof that a particular service is currently failed or a cause is known. The reported incident category cannot authorize a repair.

The Phase 1 parser remains fixture-only by default and its CLI/policy remain unchanged in scope. Only a caller explicitly enabling allow_healer_metadata can validate the metadata profile; it cannot attach observations or assert failed state. Real-incident proposal evaluation is explicitly rejected pending Phase 3. The importer always returns execution_allowed=false, activation_allowed=false and disposition=ingestion_only.

## Identity, deduplication and recovery

The operator supplies a stable 32-character lowercase hex source-instance ID and an independently trusted baseline SHA-256. Retain that instance ID across repeated imports from the same source. Do not generate a new one on every import in production.

Occurrence identity binds source-instance plus database occurrence row ID, rather than healer's recurring symptom ID. A separate fingerprint binds selected occurrence metadata. Baseline changes create a new version with the same incident key, without overwriting earlier records. Full incident revisions bind normalized metadata and baseline.

A private local source binding hashes the canonical source path plus device/inode. Replacing the file or reusing the instance against another path is rejected; changing a row's selected metadata under an old occurrence identity is also rejected. A restored/recreated source requires inspection and explicit instance rotation. These checks detect source-binding and selected-metadata changes; they do not prove authenticity or detect alteration confined to intentionally ignored fields.

Ingestion state is a separate dedicated directory, mode 0700, with 0600 files. A nonblocking exclusive file lease serializes writers. Sources and incidents are committed together in one SQLite transaction; errors/interruption roll back local partial records. Reopening the store and re-importing returns duplicate. Corrupted persisted revisions are rejected instead of silently repaired. The source database cannot reside in the ingestion state directory. Protected repository paths, symlinks, hardlinks, unrelated state contents and nonregular source/state files are rejected.

Admission caps persistent incident versions at 100 and checks the 100 MiB state quota, with a SQLite page-count ceiling. At capacity new versions fail; existing duplicates are still recognized unless byte quota is already exhausted. No evidence is pruned automatically. These are ingestion limits, not the future worker/evaluation budget enforcement.

## Usage

From the repository root, substitute the selected occurrence row ID, a retained source-instance ID and a trusted baseline hash:

```bash
python -m learning.os_ingestion \
  --db /home/g0pi/.local/share/omarchy-healer/incidents.db \
  --state-dir /absolute/path/to/dedicated-ingestion-state \
  --row-id ROW_ID \
  --source-instance SOURCE_INSTANCE_HEX \
  --baseline TRUSTED_SHA256
```

Use an ordinary writable private state location outside the source database directory. This command creates only its separate local state and emits bounded metadata JSON to stdout. Save/export that JSON with appropriate privacy permissions if needed. Errors produce a generic rejection without echoing raw database content or paths. No watcher or automatic recurring import has been enabled.

Programmatic entry point: ingest_healer_incident(db, state_dir=..., row_id=..., source_instance=..., baseline_sha256=..., now=timezone_aware_clock). read_healer_incident supplies a nonpersistent read-only source snapshot when needed by future integration. Ingested records are historical and subject to the same 24-hour freshness/5-minute future tolerance; no stale-data bypass was added.

## Verification

All **146 learning tests passed in 8.78 seconds**, with zero skips, including **26 new ingestion checks** alongside 58 Phase 1 contract checks. Evidence: phase2-tests.xml. Cases include repeated symptom IDs with distinct occurrence rows, duplicate detection after reopening, baseline revisions, malformed/stale input, unsupported schema/domain, missing and replaced DBs, changed occurrence metadata, private-log canaries, single-writer contention, atomic rollback, corrupt local data and quotas.

A concurrent WAL writer test changes the selected row after the reader's transaction has established its snapshot; the importer retains the earlier consistent snapshot. The test authorizer denies INSERT/UPDATE/DELETE/schema changes on the source connection. A quiescent-source byte comparison also remains unchanged after imports.

The actual installed healer database was checked using one supported recent occurrence. It returned ingested then duplicate, unknown state and zero observations. The temporary ingestion state was removed afterward. Sanitized evidence: phase2-live-check.json. No source incident/schema mutation or service operation was issued. SQLite may maintain normal WAL shared-memory reader bookkeeping; read-only record access does not promise byte-for-byte immutability of every live sidecar while healer is writing.

The restricted full-suite run stalled during collection and was interrupted. The host-environment rerun completed, then was repeated after the final profile restriction. The live SQLite check likewise required host access for its WAL reader bookkeeping. No checks were weakened or skipped.

## Remaining work

No voice command or background service is wired to this importer. No current unit identity/state is inferred from the incomplete source table. Phase 3 must independently evaluate diagnoses and persist evaluation outcomes; Phase 4 must prove execution containment before testing repairs. No repairs, VM, deployment or rollback mechanism is enabled here. File checks are point-in-time checks within private local state, not a sandbox against the machine owner or a malicious concurrent writer.

Closing verification: both voice baseline verifiers passed after final source changes; syntax/whitespace checks passed and saved JUnit evidence was checked for 146 tests with zero errors, failures or skips.
