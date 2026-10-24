# Ponytail Systems Audit: Multi-Agent Orchestration & Self-Evolution Subsystem

**Auditor:** Ponytail Senior Systems Auditor (Investigator Agent 8)  
**Target Subsystem:** JARVIS-OMA Multi-Agent Orchestration & Self-Evolution Subsystem  
**Key Files Analyzed:**
- [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py)
- [`orchestration/desktop_execution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py)
- [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py)
- [`agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent_orchestrator.py)
- [`orchestration/harness2_adapter.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/harness2_adapter.py)
- [`orchestration/personas.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/personas.py)
- [`scripts/test_agent_delegation.py`](file:///home/g0pi/Projects/JARVIS-OMA/scripts/test_agent_delegation.py)
- [`scripts/develop.py`](file:///home/g0pi/Projects/JARVIS-OMA/scripts/develop.py)

---

## 1. Executive Summary

The JARVIS-OMA Multi-Agent Orchestration and Evolution subsystem provides an asynchronous, process-supervised bridge between the Gemini Live voice agent and local coding CLI agents (`claude`, `opencode`, `hermes`, `omp`, `pi`, `crush`, and historically `codex`).

### Key Audit Findings:
1. **The Evolution Engine Reality Check (Myth vs Code):**
   External documentation and prompts describe the evolution engine as featuring *"failure diagnostics, AST analysis, automated fix synthesis, test execution gates, and rollback mechanisms"*. In actual code, **there is zero AST analysis, zero automated fix synthesis algorithms, and zero rollback logic**. `orchestration/evolution.py` does not import `ast`. Instead, it is a sequential 3-stage agent delegator (`researcher` -> `implementer` -> `reviewer`) operating strictly inside an isolated local git clone (`git clone --local --no-checkout`) and verifying test output using `bubblewrap` (`bwrap`). Because the main repository is never touched, no rollback mechanism is needed or implemented.
2. **Critical Agent Mismatch Bug:**
   `orchestration/agent_orchestrator.py` defines `AGENTS = ('claude', 'opencode', 'gemini', 'hermes', 'omp', 'pi', 'crush')`, deliberately omitting `codex`. However, `orchestration/evolution.py` ([`start`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L179-L188)), `skills/skills.py` ([`_adapter_start_development`](file:///home/g0pi/Projects/JARVIS-OMA/skills/skills.py#L970)), and `scripts/develop.py` ([`main`](file:///home/g0pi/Projects/JARVIS-OMA/scripts/develop.py#L56)) hardcode default `agent='codex'`. Calling `evolution.start()` with default arguments immediately raises `EvolutionError('unknown coding agent')`.
3. **Speculative Abstraction Bloat (`Harness2Adapter`):**
   [`orchestration/harness2_adapter.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/harness2_adapter.py) (98 lines) is a speculative stub for an uninstalled "Harness²" framework. Its `_load_guidance()` method is never invoked, contains accidental duplicate lines (`return out` twice on lines 68-69), and merely appends JSON lines to a file nobody reads.
4. **Desktop Screen-Scraping vs Batch Execution:**
   [`orchestration/desktop_execution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py) introduces high fragility by screen-scraping tmux terminal output every 500ms using regex prompt markers and hardcoded Claude trust dialog keystrokes (`Down`, `Enter`), plus requiring agents to write JSON handoff files to `/tmp`. Meanwhile, the simpler `visible_batch_command` path runs agents non-interactively with exact exit codes and zero terminal scraping.
5. **Robust POSIX & Process Hygiene:**
   The process supervisor in [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py) implements exemplary POSIX process group management (`start_new_session=True`, `os.killpg(SIGTERM)` -> 2s timeout -> `os.killpg(SIGKILL)`), directory descriptor checks (`dir_fd`, `O_NOFOLLOW`), non-overlapping workspace reservation, and strict voice file immutability locking.

---

## 2. Orchestration & Evolution Architecture Breakdown

### 2.1 Agent Discovery & Multi-Agent Delegation Pipeline
- **Discovery (`discover`):** Inspects the host `PATH` via [`shutil.which`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L103) for installed agent binaries.
- **Task Brief Cleansing (`clear_task_brief`):** Parses JSON envelopes from voice routing and formats human-readable briefs with `Task`, `Context`, `Expected result`, and `Constraints` ([`agent_orchestrator.py` L37-74](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L37-L74)).
- **Command Synthesis (`command_for`):** Formats non-shell argument lists for each agent CLI. Enforces strict flag ordering and avoids shell invocation (`shlex`/`exec` style).
- **Concurrency & Workspace Isolation:**
  - Hard limit of 4 concurrent active agent jobs ([`agent_orchestrator.py` L168](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L168)).
  - Non-overlapping directory hierarchy check: prevents two jobs from sharing the same directory or nesting inside one another ([`agent_orchestrator.py` L170-173](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L170-L173)).
  - Job retention cap: keeps the latest 50 completed/terminal jobs in memory ([`agent_orchestrator.py` L181-183](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L181-L183)).
- **Team Execution (`delegate_team` & `_run_team`):**
  - Bounded pipeline of 1 to 6 sequential tasks ([`agent_orchestrator.py` L310](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L310)).
  - Passes untrusted tail output (up to 3000 chars) from previous stages into the next specialist's prompt context ([`agent_orchestrator.py` L371-381](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L371-L381)).
  - Any failure halts the entire team immediately.

### 2.2 Desktop & Tmux Supervision (`DesktopAgentOrchestrator`)
- **Isolation:** Spawns sessions strictly on a private tmux socket: `tmux -L jarvis-desktop` ([`desktop_execution.py` L258](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L258)). This ensures user tmux sessions are untouched.
- **Visible Desktop Window:** Launches `xdg-terminal-exec tmux -L jarvis-desktop attach-session -t <session>` on Wayland/Hyprland desktop ([`desktop_execution.py` L380, L450](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L380)).
- **Multi-Pane Layout for Teams:** Creates a single window with tiled panes (`split-window`, `remain-on-exit on`, `@jarvis_role` borders) and zooms active panes with `select-pane -Z` ([`desktop_execution.py` L361-377, L561](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L361-L377)).
- **Interactive Control Mechanics (Fragility Hotspot):**
  - Detects prompt readiness by polling `capture-pane` every 500ms for markers (`PROMPT_MARKERS`: `›`, `❯`, `>`, `Ask anything`).
  - Sends text via bracketed paste escapes `\x1b[200~` ... `\x1b[201~`.
  - Handoff file protocol: Requires agent to write JSON to a private temp directory `result.json` to signal completion ([`desktop_execution.py` L144-148](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L144-L148)).
  - Process retirement: Replaces finished TUI with `respawn-pane -k -t <target> printf ...` to leave an inspectable dead pane without leaving running processes ([`desktop_execution.py` L196-200](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L196-L200)).

### 2.3 Evolution Subsystem Reality Check
| Claimed / Speculative Feature | Actual Implementation in [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py) |
|---|---|
| **AST Analysis** | **NON-EXISTENT.** `ast` module is not imported. No syntax tree inspection, validation, or transformation exists. |
| **Failure Diagnostics** | **PROMPT CONCATENATION ONLY.** Simply dumps the last 5,000 characters of the researcher/test runner output into the implementer's prompt ([`L344`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L344)). |
| **Automated Fix Synthesis** | **DELEGATED TO EXTERNAL CLI.** No algorithmic synthesis or automated refactoring. Fixes rely 100% on prompting external agent CLIs (`codex`/`claude`). |
| **Rollback Mechanisms** | **NOT NEEDED / NOT IMPLEMENTED.** Edits never touch the main repository. Work happens in `~/.local/state/jarvis-oma/evolution/<id>/checkout` created via `git clone --local --no-checkout`. |
| **Verification Gates** | **REAL & RIGOROUS.** Uses `bwrap` (Bubblewrap) with `--unshare-all`, `--clearenv`, read-only mounts, and dedicated `/tmp/home` to run `unittest discover -s tests`. Checks for non-zero test execution. |
| **Tree Integrity & Voice Lock** | **REAL & RIGOROUS.** Computes `git write-tree` SHA before and after researcher and reviewer stages ([`L444, L456, L459`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L444)). Verifies diff against `LOCKED_VOICE_PATHS` and `audio/.voice_lock.json` ([`L423-437`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L423-L437)). |

---

## 3. Safety, Concurrency & Rollback Integrity Analysis

### 3.1 Workspace Isolation & Concurrency
- `AgentOrchestrator` uses canonical path resolution (`Path(workspace).expanduser().resolve(strict=True)`) and verifies that no active job's root is identical or an ancestor/descendant of the requested root.
- Concurrency limit is locked at 4 jobs. Stop intent is latched via `stop_admission()` before cancellation tasks are scheduled.
- Cleanups on cancel are protected by `asyncio.shield()` so that voice timeouts or parent task cancellations cannot leave detached subprocesses.

### 3.2 Process Termination & POSIX Group Signaling
- `asyncio.create_subprocess_exec` is called with `start_new_session=True`.
- In `_stop_process(process)`:
  1. `os.killpg(process.pid, signal.SIGTERM)` signals the entire process group.
  2. Awaits `process.wait()` with a 1-2 second deadline.
  3. Escalates to `os.killpg(process.pid, signal.SIGKILL)` if any helpers remain alive.
  4. Handles `ProcessLookupError` defensively.

### 3.3 Sandbox Boundaries & Credential Sanitization
- Subprocess environment is passed through `sanitized_subprocess_env()` ([`core/secret_env.py`](file:///home/g0pi/Projects/JARVIS-OMA/core/secret_env.py)), filtering out any environment variables matching `API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`, etc.
- In `EvolutionManager._verify`:
  - `bwrap` creates an unshared namespace (`--unshare-all`, `--clearenv`), isolates the network, mounts `/workspace` read-write, sets `HOME=/tmp/home`, and mounts runtime Python paths as read-only.
- In `DesktopAgentOrchestrator._read_completion_report`:
  - Uses `os.open` with `O_NOFOLLOW` and `dir_fd` ([`desktop_execution.py` L156](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L156)) to prevent symlink traversal attacks on temporary report files.

### 3.4 Cryptographically Locked Voice Invariants
- `orchestration/evolution.py` includes `_check_voice_lock(job)` ([`evolution.py` L423-437](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L423-L437)), which checks `git diff --name-only` against `LOCKED_VOICE_PATHS` (`audio/engine.py`, `audio/downstream.py`, `audio/echo_cancel.py`, `audio/__init__.py`, `echo_cancel.py`, `tests/test_audio/*`) and `audio/.voice_lock.json`. Any mutation immediately aborts evolution.
- In team delegator prompts ([`personas.py` L29, L37](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/personas.py#L29)), the invariant is explicitly injected.

---

## 4. Ponytail Over-Engineering Audit

| Tag | File & Lines | Description | Ponytail Rationale & Replacement |
|---|---|---|---|
| `delete:` | [`orchestration/harness2_adapter.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/harness2_adapter.py#L1-L98) | `Harness2Adapter` class (98 lines), `_load_guidance` dead code, duplicate `return out` (L68-69), unread `lessons.jsonl` writer. | **Speculative complexity.** Harness2 is not installed. Discards structured task fields for hardcoded text. **Replacement:** Delete file completely; inline prompt template in orchestrator. |
| `delete:` | [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L128-L148) | `EvolutionManager._load()` scanning 32-hex directories, loading every historical job into memory on startup. | **Unneeded persistence.** Proposal artifacts are inspection checkouts; loading hundreds of old JSON files into RAM is unnecessary. **Replacement:** Load jobs on-demand when requested by `job_id`. |
| `yagni:` | [`orchestration/desktop_execution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L479-L489) | Hardcoded keystroke automation for Claude workspace trust dialog (`Down`, `Enter`). | **Fragile coupling to third-party CLI UI.** Changes to Claude CLI break this immediately. **Replacement:** Use `--permission-mode acceptEdits` or batch mode where trust dialogs are bypassed cleanly via CLI flags. |
| `yagni:` | [`orchestration/desktop_execution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/desktop_execution.py#L143-L191) | Hand-off JSON file protocol (`result.json`) requiring LLMs to execute a custom file-write tool to signal completion. | **Over-engineered completion detection.** If the model forgets to write the file, the job hangs until timeout. **Replacement:** Prefer batch commands (`visible_batch_command`) where the process exit code is the ground truth. |
| `yagni:` | [`agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/agent_orchestrator.py#L1-L10) | Root-level module shim overriding `sys.modules[__name__]`. | **Backward-compatibility artifact.** Callers should import from canonical package `orchestration.agent_orchestrator`. **Replacement:** Normalize internal imports; remove stub. |
| `native:` | [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L118-L126, L149-164) | Hand-rolled file-locked JSON database (`manager.lock` with `fcntl.flock`, atomic temp file renaming with `fsync`). | **Platform / Stdlib already provides SQLite.** The repository already uses SQLite (`proactive/ledger.py`, `proactive/control.py`). **Replacement:** Use in-memory dict or existing SQLite tables instead of custom atomic JSON files. |
| `shrink:` | [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L115-L117, L195-196) | Linear iteration string replacement `text.replace(secret, '[redacted]')` on every 4KB chunk over all environment secret values. | **Redundant & slow.** Subprocess environment is already sanitized before spawn via `sanitized_subprocess_env`. **Replacement:** Single compiled regex pass on output summary, not streaming replace loop. |
| `shrink:` | [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L17) vs [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L179) | `AGENTS` tuple excludes `'codex'`, but `evolution.py` defaults to `agent='codex'`. | **Agent registry discrepancy.** Causes immediate runtime exception if default evolution is triggered. **Replacement:** Unify default agent to `'claude'` or re-admit `'codex'` into `AGENTS`. |
| `shrink:` | [`orchestration/personas.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/personas.py#L7, L144-145) | `antigravity` persona defined but hardcoded as unsupported in `discover()`; `pi` and `crush` defined without custom CLI adapters. | **Speculative personas.** Dead definitions bloating manifests. **Replacement:** Prune unsupported personas to the active set (`claude`, `opencode`, `hermes`, `gemini`, `omp`). |

---

## 5. Streamlining & Pragmatic Improvement Plan

### Phase 1: Fix Immediate Inconsistencies & Bugs
1. **Fix Default Evolution Agent:**
   In [`orchestration/evolution.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/evolution.py#L179), [`skills/skills.py`](file:///home/g0pi/Projects/JARVIS-OMA/skills/skills.py#L970), and [`scripts/develop.py`](file:///home/g0pi/Projects/JARVIS-OMA/scripts/develop.py#L56), change the default agent from `'codex'` to `'claude'` (or add `'codex'` back to `AGENTS` in [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py#L17)).
2. **Purge `Harness2Adapter`:**
   Remove [`orchestration/harness2_adapter.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/harness2_adapter.py). Inline the 10-line task markdown formatting directly into `_prepare_prompt()` in [`orchestration/agent_orchestrator.py`](file:///home/g0pi/Projects/JARVIS-OMA/orchestration/agent_orchestrator.py). Remove `self.harness2.record_outcome` and `self.harness2.status`. Saves ~120 lines of dead code and eliminates redundant disk I/O.

### Phase 2: Unify Execution Modes in Desktop Orchestration
1. **Standardize on Finite Visible Batch Turns:**
   Make `visible_batch_command` the primary execution path for desktop visibility. Running `claude --print ...` or `opencode run ...` inside a visible tmux pane gives the user real-time visual feedback on the Hyprland desktop without the fragile screen-scraping prompt markers (`PROMPT_MARKERS`), terminal control sequence parsing, or the brittle JSON handoff file requirement.
2. **Eliminate Claude Keystroke Injection:**
   Pass `--permission-mode acceptEdits --permission-prompts none` (or equivalent CLI config) instead of scraping stdout and injecting `Down` + `Enter` keys via tmux.

### Phase 3: Simplify Evolution Subsystem to What Actually Works
1. **Accurate Naming & Scoping:**
   Document the evolution engine for what it actually is: a **Sandboxed 3-Stage Development Proposal Pipeline** (Researcher -> Implementer -> Reviewer in a local git clone verified with `bwrap` unittests).
2. **Drop Custom JSON Persistence:**
   Replace the custom `manager.lock` + atomic file write + directory traversal logic with a simple table in the existing proactive SQLite database, or leave proposals as pure ephemeral checkouts with git commit logs as the source of truth.
3. **Normalize Imports:**
   Replace all root `import agent_orchestrator` with `from orchestration.agent_orchestrator import AgentOrchestrator` across `skills/skills.py`, `scripts/`, and tests. Then remove the root forwarder `agent_orchestrator.py`.

---
*Report submitted by Ponytail Investigator Agent 8.*
