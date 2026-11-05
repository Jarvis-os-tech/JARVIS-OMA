# PC audit fixes — 2026-11-04

Scope: PC code from the Ponytail audit. Android/mobile source changes were excluded.
Three `gpt-6-luna` workers implemented independent fixes. The parent reviewed their
changes, corrected edge cases, and obtained a fourth independent review.

| Audit issue | Fix |
| --- | --- |
| 1: Protected path aliases | Normalize parent aliases and `..` for destructive operations while preserving final symlink entry semantics. |
| 2: Destructive overwrites | Reject ancestor destinations, stage replacements, restore old entries on failure, and report recoverable backup paths when cleanup fails. |
| 3: Restricted shared memories | Exclude restricted records from shared search/read/history, including earlier snapshots of a subsequently restricted record. |
| 4: PC network bridge | Default to loopback. Non-loopback plaintext requires explicit unsafe opt-in; TLS requires both key and certificate. PC-generated pairing defaults match the local bridge. |
| 5: Installation | Include learning/contracts/configs, align the payload and service path, validate dependencies and metadata before publishing `current`, preserve existing releases, and support relative installation roots. |
| 6: SQLite snapshots | Use SQLite's backup API with private temporary files and collision-safe names. Backup failure stops activation. |
| 7: Late queued commands | Reject unrelated work immediately while busy. Return a bounded running receipt for admitted work, retain its execution slot, and preserve durable request deduplication. |
| 9: Duplicate memory metadata | Distinguish omitted expiry from explicit clearing, preserve stronger user evidence/authority, and retain restrictive sensitivity. |
| 10: Integration tests | Verify current task-event identifiers with isolated presentation storage. Check deployment paths against the supported development/production mode. |

Parent review corrected weaker-authority expiry changes, restricted historical
snapshots, replacement rollback collisions, misleading pending receipts, installer
virtual-environment fixtures, missing dependency checks, and relative symlink roots.

## Verification

- Full regression suite: 1,722 passed, 1 skipped; 149 passing subtests.
- Final installer/admission checks after independent review: 9 passed.
- Required behavior gate against final source: 167 passed, source unchanged during certification.
- Focused memory suite: 179 passed; 84 passing subtests.
- Relevant source diff checks and installer shell syntax passed. An unrelated existing
  trailing blank line in `tests/test_nlu.py` was preserved.

The active development-mode PC voice and device-bridge services were reloaded.
Both were active afterwards, Gemini was connected, mute/standby settings were
preserved, and the device bridge listened on `127.0.0.1:8766`.

## Limits

Android's hostname validation issue (audit issue 8) remains deferred as requested.
Direct LAN access now requires TLS or explicit `--allow-lan`; loopback forwarding
remains supported. Existing external-agent memory processes need reconnecting to
load updated modules; the Hermes gateway was not restarted.

The release snapshot API covers databases in its configured runtime data directory.
It is not a claim that all external state directories or all agent data were backed up.
No acoustic hardware acceptance, Android build, or external-agent reconnect was performed.
