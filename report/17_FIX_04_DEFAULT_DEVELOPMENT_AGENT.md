# Fix 04: Unsupported default development agent (E01)

Status: implemented and tested, 2026-10-22. No running JARVIS restart or live coding-agent invocation was performed.

## What changed and why

Added `codex` to `AGENTS` in `orchestration/agent_orchestrator.py`. Codex already has a command builder, persona, development-tool declarations, and default callers. The missing registry entry prevented discovery and rejected default evolution requests. This localized repair preserves existing intended defaults and uses the same registry for discovery, CLI choices, and admission.

The machine's Codex executable was discovered after the repair. This establishes installation, not login state or live-provider availability. No unrelated registry or permission changes were made.

## Evidence

Before repair: the existing `test_cancel_during_spawn_cleans_up` failed at default `manager.start()` with `EvolutionError: unknown coding agent`.

After repair: evolution, agent-orchestrator, and development-skills suites passed 34 tests; 2 opt-in real-sandbox checks were skipped. Fixtures use local fake agents and temporary Git repositories, not cloud coding sessions. Voice lock verified: all seven core files intact. Codebase reference regenerated.

VERDICT: PASS

## Voice check

Restart JARVIS normally, or run `systemctl --user restart jarvis-oma.service` if using the service.

Say:

> Jarvis, use list_system_agents and tell me whether Codex is available. Do not start a task.

Expected: Codex appears as available on this machine. This verifies discovery of the previously missing registry entry, not authentication or the entire development pipeline.

The default development start path was verified by automated tests. A full voice development trial needs a clean disposable Git repository and authenticated agent, and creates a real proposal job. Do not use the current dirty shared project as its source. Missing authentication, sandbox tooling, or a dirty repository are separate errors, not the repaired unknown-agent bug.

Planning: direct; delegation: none; scope: one registry entry and report artifacts. Remaining unsupported-agent inputs must still be rejected.

Fixed supplemental findings so far: S07, S05, S04, E01.
