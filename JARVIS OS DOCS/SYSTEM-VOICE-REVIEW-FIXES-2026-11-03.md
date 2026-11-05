# System voice review fixes

The three findings from the persona review have regression coverage and fixes.

## Reasoning results reach the active voice delivery path

The live `UnifiedSkills` adapter now exposes terminal model-job results through
its existing background-notice interface. It reads job state instead of draining
the queue shared with the alternate task consumer. Completed, failed and
cancelled states retain their actual meaning; job IDs remain internal.

Notices remain pending if voice is busy or delivery is rejected. The existing
delivery loop acknowledges the model notice after accepting an announcement or
local notification. Subsequent polls omit the acknowledged notice. Existing
control-task and Hermes notice acknowledgements continue through their original
paths. Model records remain session-scoped; this does not add a durable job store
or prove that audio was physically heard.

## Updated worker instructions are actually deployed

Preparation now replaces `REASONING_INSTRUCTION` from the current source even
when the installed build already defines it. The update uses Python AST
boundaries, preserves other worker code and handles the older inline-instruction
format. Repeated preparation does not duplicate the definition.

The managed candidate includes the delivery helper, the two updated delivery
methods and the release-manager fixes, while preserving unrelated installed
control changes. Staging validates actual notice creation/acknowledgement as
well as tool registration and Live setup.

## Release switching checks the parent under a shared lock

Prepared files copy into a private temporary directory outside `releases/`.
Copied file hashes are verified. Immediately before promotion, the manager
acquires the common release lock and checks that the active build still matches
the build used to prepare the candidate. If another update changed it, activation
stops without changing pointers or restarting services.

Switching, rollback, recovery and pruning share this lock. Incomplete copies
cannot be pruned as releases. The persona and widget deployment helpers use this
checked installation path. An operation already holding the lock causes another
operation to fail clearly rather than race it. Unrelated tools that bypass the
manager and directly edit links are outside this coordination contract.

## Evidence

- Before implementation, all five original regression cases failed, covering
  missing delivery, failed/cancelled outcomes, stale prompt deployment and an
  active build changing during copying.
- After implementation, 58 focused persona/configuration/release tests pass.
- Another 11 background-delivery checks pass. Three existing thread-dependent
  cases were excluded after the broader run stalled. The separate existing
  Hermes native-delivery test could not collect because its shared
  `test_durable_hermes` fixture module is absent. A focused compatibility test
  verifies control, model and Hermes notices coexist and acknowledge correctly.
- Additional checks cover shared locking across operations, copied-file hash
  rejection, successful installation/rollback pointers and legacy prompt
  migration. Compilation and diff whitespace checks pass.

No synthetic spoken demonstration is used for verification. Aoede and the
disabled local synthetic acknowledgement clips remain user configuration.

Activated build: `20261102T190155784777Z-system-persona`. All changed-file hashes
match the staged candidate. Voice and device services are active, and Gemini
Live connected successfully with Aoede. The previous persona build is retained
for rollback. No desktop-shell restart was required.
