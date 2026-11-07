# Living JARVIS OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform JARVIS from a rule-gated, regex-intercepted assistant into an autonomous, living OS agent with full-spectrum system agency and natural voice presence.

**Architecture:** Layered Cognitive OS where Gemini Live 3.8 receives full-duplex natural audio directly, selects tools via self-describing schemas from an always-on Sovereign Core (`run_shell`, `tmux`, `hyprland`, `filesystem`), and executes with native host feedback, holding only for irreversible destructive actions.

**Tech Stack:** Python 3.11+, Gemini Live API, PipeWire, Hyprland Wayland IPC, Bash/tmux, Silero VAD.

**Spec:** [`docs/superpowers/specs/2026-11-07-living-jarvis-os-design.md`](file:///home/g0pi/JARVIS%20OS/docs/superpowers/specs/2026-11-07-living-jarvis-os-design.md)

## Global Constraints

- Preserve all existing comments and docstrings unrelated to code changes.
- Voice subsystem modifications are authorized by user instruction (2026-11-07). All updates to `voice_layer/` must be recorded in [`audio/.voice_lock.json`](file:///home/g0pi/JARVIS%20OS/audio/.voice_lock.json) and verified via `python scripts/verify_voice_lock.py`.
- Fast non-destructive operations (shell read/write, window movement, workspace switching, volume/brightness) execute immediately. Destructive operations (disk wipe, shutdown, reboot) enforce conversational confirmation.

---

### Task 1: Voice Subsystem Unlock, Configuration, and Baseline Update

**Files Touched:**
- `voice_layer/config.py`
- `voice_layer/local_speech.py`
- `voice_layer/persona.py`
- `audio/.voice_lock.json`

- [x] **Step 1.1**: Set `allow_shell = True` as default in [`voice_layer/config.py`](file:///home/g0pi/JARVIS%20OS/voice_layer/config.py).
- [x] **Step 1.2**: Update [`voice_layer/local_speech.py`](file:///home/g0pi/JARVIS%20OS/voice_layer/local_speech.py) so `command_for()` does not hijack natural conversational speech turns with brittle regex matches, while retaining Whistle for genuine offline fallback.
- [x] **Step 1.3**: Update [`voice_layer/persona.py`](file:///home/g0pi/JARVIS%20OS/voice_layer/persona.py) to remove rigid 5-word rules and pseudo-code constraints, framing JARVIS as an intelligent, autonomous Linux partner.
- [x] **Step 1.4**: Update the SHA256 checksums in [`audio/.voice_lock.json`](file:///home/g0pi/JARVIS%20OS/audio/.voice_lock.json) for the modified `voice_layer/` files.
- [x] **Step 1.5**: Run `python scripts/verify_voice_lock.py` and verify it reports `Voice lock PASS`.
- [x] **Step 1.6**: Commit Task 1 changes.

---

### Task 2: Dismantle Brittle Regex Tool Gating in `jarvis_control/nlu.py`

**Files Touched:**
- `jarvis_control/nlu.py`
- `tests/test_nlu.py`

- [x] **Step 2.1**: Refactor [`validate_tool_intent`](file:///home/g0pi/JARVIS%20OS/jarvis_control/nlu.py#L396) in [`jarvis_control/nlu.py`](file:///home/g0pi/JARVIS%20OS/jarvis_control/nlu.py):
  - Broadened authorization and platform vocabulary (`integrate`, `setup`, `sync`, etc.).
  - Validate parameters against schema types and provide structured error feedback on bad input.
  - Preserve device targeting disambiguation (PC default vs phone) and confirmation safety logic.
- [x] **Step 2.2**: Update [`tests/test_nlu.py`](file:///home/g0pi/JARVIS%20OS/tests/test_nlu.py) to reflect schema-driven validation instead of keyword rejection.
- [x] **Step 2.3**: Run `.venv/bin/pytest tests/test_nlu.py` to ensure all tests pass (141 passed).
- [x] **Step 2.4**: Commit Task 2 changes.

---

### Task 3: Guarantee Sovereign Core Tools & Shell Agency

**Files Touched:**
- `jarvis_control/skills.py`
- `skills/skills.py`
- `jarvis_control/config.py`

- [x] **Step 3.1**: Verify `allow_shell = True` in [`jarvis_control/config.py`](file:///home/g0pi/JARVIS%20OS/jarvis_control/config.py).
- [x] **Step 3.2**: Ensure the Sovereign Core tools (`run_shell`, `run_in_terminal`, `read_terminal`, `watch_terminal`, `hypr_dispatch`, `hypr_query`, `read_screen`, `click_text`, `file_operation`, `system_control`) are always attached to the Live session in [`jarvis_control/skills.py`](file:///home/g0pi/JARVIS%20OS/jarvis_control/skills.py) and [`skills/skills.py`](file:///home/g0pi/JARVIS%20OS/skills/skills.py).
- [x] **Step 3.3**: Run unit tests in `tests/test_control/` to verify execution of shell, terminal, and desktop controls (160 passed).
- [x] **Step 3.4**: Commit Task 3 changes.

---

### Task 4: Dynamic Tool Discovery Across All 247 Domain Capabilities

**Files Touched:**
- `orchestration/tool_tiers.py`
- `skills/skills.py`

- [x] **Step 4.1**: Modernize [`orchestration/tool_tiers.py`](file:///home/g0pi/JARVIS%20OS/orchestration/tool_tiers.py):
  - Attached all Sovereign Core tools to `CORE_TOOLS`.
  - Provide dynamic semantic tool discovery (`discover_domain_tools`) that can query across all 247 domain tools without needing regex hints.
- [x] **Step 4.2**: Verify `tests/test_voice_tool_catalog.py` and `tests/test_orchestration.py` pass (15 passed).
- [x] **Step 4.3**: Commit Task 4 changes.

---

### Task 5: End-to-End Verification & Baseline Lock Assurance

- [x] **Step 5.1**: Run `python scripts/verify_voice_lock.py` to confirm the baseline is intact (PASS).
- [x] **Step 5.2**: Run full regression test suite `.venv/bin/pytest` across control, nlu, contracts, and orchestration (337 passed).
- [x] **Step 5.3**: Perform end-to-end sanity check on shell execution, window management, and dynamic tool invocation.
- [x] **Step 5.4**: Final commit and summary report.
