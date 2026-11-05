# System integration and execution evidence — 3 November 2026

This pass repairs the request → tool → observed state → spoken result path.
It does not certify every application, account or possible command, and it
does not establish a zero-hallucination guarantee for a generative model.

## Critical findings repaired

1. **Unsupported success speech.** For recognized operational requests and
   common live-status questions, provider audio is now withheld until a
   meaningful completed tool receipt exists. Capability discovery alone does
   not unlock speech. Failed, pending and unverified operations receive factual
   local feedback. Unsupported provider assertions are excluded from the saved
   assistant response. Confirmation and authorization requirements remain audible.
2. **Failure flags lost across adapters.** Completion classification now retains
   negative ground-truth/focus flags, SDK `successful=false`, nested execution
   envelopes, stopped/timed-out work, authorization-pending states and legacy
   admission/absent/false receipts. A successful tool receipt is explicitly
   scoped to that tool call, rather than the user's entire goal.
3. **Unusable GUI contracts.** The bridge called a nonexistent `click_window`
   driver action and omitted required process identity on window targets. It
   now uses supported exact PID/window targeting and window-relative input
   coordinates. Native driver IDs are bound to observed compositor identities;
   ambiguous PID/rectangle matches remain unresolved.
4. **Missing foreground backend.** The installed driver explicitly refuses
   some foreground input because its Hyprland plugin is unavailable. An exact,
   focused-window Wayland pointer fallback now handles that admission refusal.
   It checks address, PID, current bounds, focus and pointer position before
   dispatch. Timeouts and uncertain driver outcomes never trigger a second click.
5. **Declared service tools without handlers.** Two Composio search/execution
   registry entries referenced nonexistent methods. Their actual domain handlers
   are now connected and tested through registry execution.

## Other execution repairs

- The voice loop formerly stopped at its sixth call even after five successful
  calls. It now allows a bounded 64-call turn; a nine-step successful workflow
  passes. Exhaustion explicitly reports unfinished work, and repeated rejected
  requests retain their circuit breaker.
- Direct, voice and domain-routed tools share deadline selection. Domain routing
  no longer truncates a slow supported operation at a shorter outer deadline.
- Cancelled desktop/GUI subprocesses are killed and reaped. Shared execution has
  a bounded deadline, records an unknown outcome when appropriate, releases its
  lock and does not replay an uncertain action.
- Cached historical success receipts are reclassified under current result
  rules without repeating their operations.
- A failed or malformed window inventory cannot prove a window closed.
  Ambiguous window targets and failed process inspection cannot prove success.
- Clipboard writes require exact full-content readback, including whitespace;
  matching only the first 50 characters is insufficient.
- Literal native typing uses a stable complete keymap with conventional physical
  keycodes, preserving case and punctuation. Unsupported literal characters use
  the existing clipboard-preserving content-paste path when safe. A real test
  had exposed intermittent incomplete text under the previous injector route.
- Phone adapters require a phone target in the current request. Explicit phone
  pairing/QR requests retain their dedicated intent checks.
- Service discovery cannot execute a tool from a different platform or select
  arbitrarily between multiple matching actions. SDK failures survive transport
  wrappers. Generating an authorization link remains pending until connection
  verification succeeds; a failed browser open is not announced as successful.

The native pointer implementation follows the
[wlr virtual-pointer protocol](https://github.com/swaywm/wlr-protocols/blob/master/unstable/wlr-virtual-pointer-unstable-v1.xml).
Input delivery is always distinguished from proof of its application effect.

## Verification

The [machine-readable evidence](SYSTEM-INTEGRATION-EVIDENCE-2026-11-03.json)
records the final test counts, installed release, module hashes, service health,
capability inventory and actual-effect checks.

Final validation: **1,483 tests and 146 subtests passed**. The optional retrieval
service module was skipped in the main environment and its **three tests passed**
in its separate environment. The installed voice is connected, listening and
control-enabled, with 262 registered tools and 95 in the initial voice catalog.

Installed release: `/home/g0pi/.local/share/jarvis-runtime/releases/20261103T121454952667Z-system-integration`.
Rollback parent: `/home/g0pi/.local/share/jarvis-runtime/releases/20261103T120212700784Z-system-integration`.

Real tests used a dedicated temporary GTK window and owned temporary files:

| Test | Independent observation |
| --- | --- |
| Create directory, write, edit, copy and move | Exact final file contents and disappearance of the moved source |
| Type text, press Enter, select and replace | Full field value and entry activation signal |
| Accessible button click | Test application's click counter incremented |
| Exact-window coordinate click | Click counter incremented through the native fallback |
| Close test window | Successful compositor inventory confirmed its removal |
| Native settings queries | Actual volume, brightness and workspace handlers returned results |
| Unsupported spoken success | Audio withheld; factual local feedback emitted; no model retry |
| Running-service execution socket | Real queries, consistent duplicate receipts and rejection of an invented tool |

The fixture inherited an accessibility-disabled test environment initially.
Accessibility was enabled for the fixture itself, without changing the desktop's
global accessibility settings. All test windows and temporary files were closed
or removed. No external messages, purchases or destructive user-file operations
were used as live tests.

The desktop registry contains 227 entries with callable handlers. Optional
CLI-Hub commands remain unavailable on this machine and are recorded as missing
dependencies. Registration is distinguished from dependency availability and
from successful execution against a live account.

Agent-Reach's health/channel/validation checks run separately in its own FastAPI
environment. The main environment skips that optional service test module;
this is recorded separately from the main regression count.

## Deployment and practical limits

The scoped release is cloned from the installed runtime. Changed definitions
are spliced into modules containing unrelated in-progress work; other installed
behavior is retained. Compilation, registry checks, receipt classification,
nine-step execution and real input effects were checked before activation.
Activation checks service health and preserves the prior mute/standby state.
The release manifest and evidence identify the parent rollback release.

The spoken guard recognizes conservative command/status patterns; it is not a
formal verifier of arbitrary natural-language goals. A successful wrong tool,
an unrecognized phrase, background narration or ambiguous application state can
still require correction. Readback interpretation and complete multi-step goal
coverage still require validation. Login/permission prompts and unsupported app
interfaces remain genuine blockers. Arbitrary authenticated platform operations
were not exhaustively executed during this audit.

The reliable contract is to execute supported, authorized actions, report their
observed results and identify unfinished or unverified work. It would be false
to describe these checks as proof that every action works or that model errors
are impossible.
