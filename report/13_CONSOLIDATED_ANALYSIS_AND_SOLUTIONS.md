# Consolidated report analysis and solutions

Date: 2026-10-22
Status: proposed repairs, not implemented fixes.
Sources: extracted reports 00–10, supplemental findings 11, and reproduction checks 12.

## Assessment

The strongest findings concern filesystem data loss, microphone mute semantics, subprocess credential boundaries, and broken runtime contracts. Correct these before broad simplification. Reducing line counts is not an acceptance criterion; preserving behavior, safety, and recovery is.

There are 20 tracked supplemental findings: S01–S09 and E01–E11. Some are reproduced defects, some are established by code inspection, and some describe conditional risks or API limitations. Original audit claims that were not independently validated remain investigation items below.

Reports 01–06 and 09–10 contain completion summaries rather than full audits. Report 00 contains extraction instructions. Reports 07–08 have detailed analyses. This plan does not treat summary claims or estimated performance numbers as measurements.

## Stage 1 — Prevent data loss and unintended microphone activation

### S01: protected-path aliases bypass destructive guards — High, reproduced

**Cause:** lexical path equality misses `..` and parent-directory aliases.

**Solution:** create a shared operation-aware path-validation helper. Resolve existing parent directories, normalize the leaf, and compare the actual target identity against protected paths before any destructive operation. For unlinking a symlink, protect the link's parent/leaf identity without accidentally converting unlink into deletion of its target. For operations that follow symlinks, validate the resolved target as well. Use descriptor-relative operations and no-follow checks where paths can change concurrently; a one-time `resolve()` alone does not eliminate races.

**Acceptance:** direct protected paths, `..` aliases, symlinked parents, and concurrent path replacement cannot delete or replace protected directories. Ordinary symlink removal still works. All destructive fixtures must stay in temporary directories.

### S02: copying into an ancestor deletes the source — High, reproduced for copy

**Cause:** overlap validation checks only one direction.

**Solution:** after canonical identity validation, reject equal paths and ancestor/descendant overlap in either direction for directory-tree replacement in both copy and move. Detect same-object aliases and hard links where relevant. Run all checks before removing or staging anything.

**Acceptance:** source-to-parent, source-to-self, and parent-to-descendant operations fail without changing either tree. Verify copy and move independently; the original reproduction covers copy only.

### S03: failed overwrite destroys the previous destination — High, reproduced for copy

**Cause:** destination deletion precedes successful replacement.

**Solution:** copy files into a uniquely created temporary sibling, preserve required metadata, finish and close the staged copy, then atomically replace the destination. Use a recovery protocol for nonempty directory replacement: retain the prior destination as a backup until installation succeeds, restore it on failure, and recover interrupted swaps at startup. For cross-filesystem moves, stage and verify the destination before removing the source. Do not claim a portable single-step atomic replacement for arbitrary directory trees.

**Acceptance:** injected disk-full, permission, copy, rename, and interruption failures preserve original data. Successful operations preserve documented permissions and symlink behavior. Exercise cross-filesystem behavior separately.

### E05: mute/unmute toggle state — High, reproduced

**Solution:** add an idempotent IPC `set_mute` command with a required boolean state. Wire it through an unlocked runtime callback to the existing engine `set_muted()` method. Map CLI `mute` to true, `unmute` to false, and retain `toggle` for deliberate inversion. Publish the resulting state after success. Read-then-toggle is insufficient because concurrent commands can race.

**Acceptance:** repeated mute stays muted; repeated unmute stays unmuted; concurrent setters have explicit final-state semantics. Verify both supported audio backends. Do not edit the locked engine.

## Stage 2 — Repair credential boundaries and execution contracts

### E03: subprocess paths inherit the parent environment — High, code-inspected

**Solution:** use one shared environment builder across `_run`, `_launch`, desktop controls, and auxiliary runtime launches. Preserve essential desktop variables such as PATH, locale, display, runtime directory, and D-Bus session address while filtering unrelated credentials. Grant connector-specific credentials only to commands that require them. For `systemd-run`, verify the environment of the actual service process as well as the launcher: the user service manager has its own environment.

**Acceptance:** synthetic credentials never reach ordinary child commands or launched applications; desktop commands still work. Use synthetic tokens only in tests. Record explicit credential exceptions rather than passing the entire environment.

### E04: credential-name filtering has gaps — Medium, code-inspected

**Solution:** expand targeted name detection for standalone KEY segments, private/signing/encryption keys, and authorization/bearer variables. Inspect credential-bearing connection URLs rather than deleting every variable ending in URL. Apply updates before final filtering, or restrict privileged updates, so overrides cannot silently reintroduce secret variables. Keep any required credential forwarding explicit.

**Acceptance:** a table of known secret and legitimate environment names verifies filtering without breaking unrelated URL configuration. Include mixed-case names and override behavior.

### E06: explicit empty environment is ignored — High, reproduced

**Solution:** replace truthiness fallback with `_desktop_env() if env is None else env`. Preserve caller-supplied dictionaries, including an empty one.

**Acceptance:** `env={}` produces an empty environment, `env=None` uses the intended filtered default, and an explicit minimal dictionary is preserved exactly.

### E01: evolution defaults to an unsupported agent — High, existing test fails

**Solution:** define one authoritative supported-agent registry and default resolver shared by evolution, skills, CLI tools, discovery, and command construction. Choose a configured supported installed agent. If Codex is intended to be supported, complete its registration and discovery integration rather than changing only one tuple. Return a clear unavailable-agent error when no valid choice exists.

**Acceptance:** default start succeeds with a supported fixture agent; unsupported and missing agents fail before creating a job. Run the existing evolution suite and discovery/command tests.

### E02: audio extension violates playback queue format — High, code-inspected

**Solution:** change only `audio/extension.py`: submit processed PCM through the existing public `enqueue_output(generation, frame)` or `enqueue_playback(pcm, generation)` API instead of writing directly into `c_output_queue`. Capture and preserve the generation associated with the frame before processor work so a barge-in during processing does not retag stale audio as current. Use the arbitrary-buffer API when frame sizing is not guaranteed.

**Acceptance:** processed playback works, dropped processor output is ignored, stale generations are rejected, mute is respected, frame slicing works, and barge-in cannot replay stale data. Place new checks in a new unlocked extension test file. Never edit or monkeypatch locked voice functions.

## Stage 3 — Correct filesystem task results and text reading

### S05: empty-file tasks falsely fail — Medium, reproduced

**Solution:** remove the blanket nonzero-size requirement. Verify exact requested write content, including empty bytes, and allow edits/appends that legitimately leave the file empty. Distinguish operation success from verification failure in job results to prevent accidental duplicate execution.

**Acceptance:** empty write, empty append, and edit-to-empty succeed when their requested result is achieved; missing files still fail.

### S06: unchanged files can pass task verification — Medium, fault-injected reproduction

**Solution:** establish an explicit executor contract and reject error-valued results as well as exceptions. Capture bounded preconditions and expected postconditions before execution: write content/digest, append prior content plus suffix, edit expected replacement, move source absence plus destination identity, and trash source absence plus returned trash artifact. Check cancellation states without claiming unverified steps succeeded. Account for concurrent file changes explicitly rather than overwriting them silently.

**Acceptance:** an executor returning an error or performing no write cannot yield completed status. Wrong nonempty content fails. Valid writes pass. This is a contract gap; current filesystem adapters normally raise their errors, so the fault-injected error shape is not claimed as normal production behavior.

### S07: character offsets are treated as byte offsets — Medium, reproduced

**Solution:** retain the advertised character-offset contract: read and discard characters in bounded chunks until the offset, then read at most `max_chars + 1`. Do not use byte seek with a character count. If huge-file performance requires continuation tokens later, introduce them as an explicit API change rather than silently changing units.

**Acceptance:** pagination reconstructs ASCII, accented, Indic, and emoji text exactly; offsets at and past EOF behave predictably; memory use stays bounded.

## Stage 4 — Bound background work and handle invalid inputs

### E07: IPC subscriber buffers are unbounded — Medium, code-inspected risk

**Solution:** maintain bounded per-client delivery queues with one asynchronous writer task per subscriber and a drain deadline. State updates may be coalesced to the latest state. Disconnect consistently slow clients, cancel their writer tasks on shutdown, and keep broadcast publication nonblocking. Add bounded request-read deadlines separately.

**Acceptance:** a subscribed client that stops reading cannot cause unbounded buffer growth or delay a healthy client. Assert queue/transport bounds under sustained updates. Socket tests require an environment that permits local UNIX sockets.

### E08: vision contends with microphone sending — Medium, structural risk

**Solution:** instrument send-lock wait time and audio delivery delay first. Keep only the newest pending vision frame, limit resolution/bytes, and drop stale frames under congestion. Schedule audio before optional video. Use a serialized outbound sender if the SDK requires it. Merely assigning separate locks is unsafe without confirming SDK concurrency support and does not remove an in-flight network send. Evaluate transport/provider changes only if measured limits cannot meet audio requirements.

**Acceptance:** under delayed video sends, audio delay and dropped-frame counts remain within a documented measured budget. Test cancellation, standby, and reconnect behavior. No local latency budget has yet been measured.

### S04: malformed search URLs abort processing — Medium, reproduced

**Solution:** handle `ValueError` from URL parsing/hostname validation and reject only the invalid item. Keep result validation isolated so valid later results survive. Return the normal provider error if none remain.

**Acceptance:** malformed bracketed hosts, unsupported schemes, credentialed URLs, and malformed values are skipped; a subsequent valid result is returned. No live search calls are necessary for unit tests.

### S08: job-ID aliases overwrite monitor state — Medium, reproduced component defect

**Solution:** either reject surrounding whitespace or normalize it once before duplicate checking, then apply the same identity rule to every public monitor method. Reject a duplicate without mutating the original job.

**Acceptance:** `job` and ` job ` cannot replace each other; original deadlines, retries, and metadata remain intact. External reachability is not yet established.

### S09: non-finite timestamps poison rate limits — Medium, reproduced component defect

**Solution:** validate timestamps with `math.isfinite()` before any state mutation. Validate all duration configuration as finite and range-correct, rejecting booleans and invalid counts. Define a backward-clock policy, preferably rejecting decreasing monotonic timestamps.

**Acceptance:** NaN and infinities fail without altering dedupe or rate queues; valid entries expire normally afterward. Normal monotonic clocks do not generate NaN, so exposure depends on invalid caller input.

## Stage 5 — Configuration, representative tests, and bounded history

### E09: fixed calendar timezone — Medium, API limitation

**Solution:** add an optional IANA timezone argument, defaulting to a configured user/calendar timezone. Validate it with `zoneinfo.ZoneInfo`. Preserve explicit offsets and reject contradictory or ambiguous naive times according to a documented policy, including DST transitions. Update the tool schema when the argument is exposed.

**Acceptance:** existing Asia/Kolkata usage is preserved, another timezone works, offset-aware values stay correct, invalid zones fail clearly, and DST edge cases are explicit.

### E10: mock detection changes production adapter behavior — Medium, code-inspected

**Solution:** remove `call_count` inspection and keep one implementation path for volume and brightness. Inject command runners normally; assert their arguments and returned state. Adapt old tests to the real shared adapter contract.

**Acceptance:** the same code path runs under tests and real execution; failure propagation, mute, and valid/invalid adjustment ranges remain covered.

### E11: greeting history grows indefinitely — Low, code-inspected

**Solution:** introduce a bounded retention policy within the existing database transaction. Preserve any context-key history required to suppress repeated reminders, either in a separately bounded suppression table or with a documented time horizon. Avoid deleting all older keys merely because only eight greeting texts are shown.

**Acceptance:** repeated inserts remain within the retention policy, restart persistence works, recent-context suppression remains correct, and migration preserves existing usable records. Changing SQLite to JSON is not necessary for this fix.

## Original reports: additional proposals requiring investigation

| Report area | Analysis | Solution approach and decision evidence |
|---|---|---|
| 01 Audio/native companion | Queue-contract bug is covered by E02. Polling and Python RMS overhead are unmeasured. | Profile startup and frame processing; optimize only measured bottlenecks in extensions/plugins. Preserve voice locks. |
| 02 Core runtime | Tool responses have a cleanup path; long-session growth remains plausible. Optional-worker failure coupling needs fault tests. | Bound response-cache lifetime while preserving replay/deduplication. Give optional workers their own restart/backoff boundaries if fault injection confirms conversation teardown. |
| 03 Desktop skills | Default loader reads `skill_manifests`; CLI-hub declarations also exist in `skills/manifests`, which can be explicitly configured. Blanket deletion is premature. | Inventory active configuration and external callers; resolve intended exposure, migrate manifests explicitly, and test registry availability. Deduplicate adapters through shared implementations after behavior tests. |
| 03 Shell-backed bindings | A shell is deliberately used to source shell functions; argv-only replacement is not automatically equivalent. | Pass script paths as positional shell arguments and quote expansions; validate the trusted script source. Prefer a structured binding API if available. Do not label every shell invocation an exploit without a controllable input path. |
| 04 IPC/service lifecycle | Backpressure is covered by E07. Final 0600 mode does not prove permissions were restrictive during socket creation. | Bind in a private owner-only directory; establish safe creation permissions before listening without introducing unsafe process-global umask races. Verify peer identity if required. Audit installed unit names and migration before deleting duplicate installers. |
| 05 Memory retrieval/storage | Summary alleges full scans, repeated migrations, vector overhead, and redundant stores. These lack independent confirmation here. | Benchmark realistic corpora. If confirmed, add FTS5 with explicit index maintenance and relevance tests; run migrations once by version; batch/vectorize math only if measured. Keep recall safeguards. Plan backup, migration, and rollback before merging databases. |
| 06 Vision/HUD | Shared-lock risk covered by E08; camera teardown already exists. Claimed RSS and latency numbers are not measurements. | Test camera release on exit/cancel/reconnect. Measure disk writes, CPU, and HUD RSS. Reduce capture rate or use in-memory transport when supported; preserve exposure stability and desktop behavior. |
| 07 Standby/privacy | Environment issues covered by E03/E04/E06. Wake thresholds and synchronous inference need local measurements. | Measure missed wakes, false wakes/hour, and event-loop latency on the actual microphone. If offloading inference, use a bounded dedicated worker with serialized detector ownership and lifecycle cleanup. Do not raise thresholds or remove confirmation logic without data. |
| 08 Orchestration/evolution | Agent mismatch covered by E01. Unused guidance and duplicated return are cleanup candidates; removing persistence/redaction is not a demonstrated repair. | Align documented behavior with the actual proposal pipeline. Prefer supported structured/batch CLI modes where appropriate; retain completion validation, process supervision, work isolation, output redaction, and evidence. Verify installed CLI flags rather than copying unverified options from the audit. |
| 09 Filesystem/proactive | S01–S03/S05–S09 cover verified cases. Proposed database consolidation has migration and recovery implications. | Establish which cross-store actions must be atomic; use transactions or a durable outbox as appropriate. Merge databases only with a concrete consistency requirement and tested migration/recovery plan. |
| 10 Connectors/dependencies | Timezone limitation covered by E09. OAuth scope and dependency suggestions need feature inventories. | Request the smallest scopes required by implemented features; document reauthorization. Make optional heavyweight features installable as extras if packaging supports it. Retain HTTP timeouts, response bounds, and error behavior when changing clients; removing a dependency is not a correctness fix by itself. |

## Delivery order and verification

1. Filesystem guards, overlap rejection, recoverable overwrite, and idempotent mute.
2. Environment boundaries, default-agent registry, and extension playback API.
3. Task verification and Unicode pagination.
4. Bounded IPC, robust search parsing, monitor identity, and policy input validation.
5. Calendar configuration, test-path cleanup, greeting retention, and measured performance work.

Keep changes small enough to review separately. Replace characterization assertions with assertions of desired behavior when each fix lands; do not retain tests that require the bug to persist. Place long-term regressions in their corresponding test suites.

For application changes, run relevant tests with `.venv/bin/pytest` and `python3 scripts/verify_voice_lock.py`. Add new extension tests outside the locked test files. If module maps or file references change, run `python3 scripts/update_codebase_reference.py`. Stage autonomy/evolution execution in isolated checkouts as required by project invariants.

Current evidence: 11 supplemental reproduction checks pass because they confirm existing defects; relevant existing suites previously passed 24 tests and 9 subtests. Existing evolution testing exposed the unsupported default. IPC integration tests could not bind sockets in the restricted environment. These results do not certify any proposed fix.
