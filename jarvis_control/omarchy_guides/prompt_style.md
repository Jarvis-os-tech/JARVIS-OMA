# Omarchy / JARVIS Prompt Style & Delegation Guide

## 1. Core Architectural Invariants

### 1.1 Radical Epistemic Honesty (Evidence-First)
- Work strictly from physical evidence: logs, coredumpctl info, journalctl, file mtimes.
- Strictly partition proven physical facts from inferences.
- Never guess or hallucinate missing debug symbols or root causes.

### 1.2 Non-Destructive State Invariance
- Package root (`/usr/share/omarchy/` / `$OMARCHY_PATH`) is strictly read-only.
- All user customizations and configuration overrides live in `~/.config/`.
- 5-step mutation cycle: Read -> Backup (`file.bak.$(date +%s)`) -> Write -> Validate -> Rollback on error.

### 1.3 Zero-Polling Hardware Multiplier
- Widgets build per-monitor; periodic polling timers destroy battery life and c-states.
- 4-Tier event hierarchy:
  1. Quickshell native service properties (UPower, Pipewire, Hyprland, Mpris).
  2. Persistent shared pipes (`pactl subscribe`, Hyprland IPC socket).
  3. Filesystem watches (`FileView { watchChanges: true }`).
  4. Explicit CLI command pushes (`omarchy-shell -q <target> refresh`).

### 1.4 Purposeful Motion Physics & Budgets
- Instant jumps (0ms) for one-shot ephemeral tools (launchers, clipboards, OSDs).
- Dwell surfaces ceiling < 300ms.
- Asymmetric 2/3 exits (180ms entrance -> 120ms exit).
- Mandatory `Style.duration(ms)` wrapping for reduced-motion accessibility.

### 1.5 Dual-Surface Native Applications ("One Window, One Job")
- C++ backend logic + QML UI presentation.
- DBus file pickers via `xdg-desktop-portal` (no QFileDialog).
- Dual interface: every app must expose headless CLI commands (`check`, `render`, `export --json`).

---

## 2. Delegation & Task Brief Schema

When delegating a task to an agent or subagent:
```
Task
<Clear, unambiguous imperative goal>

Evidence & Context
<Physical observations, error logs, or file contents; proven facts separated from inferences>

Operating Principles (JARVIS / Omarchy Style)
<Applicable invariants: non-destructive boundaries, zero-polling, motion budgets>

Expected Result
- Implement the required functionality or diagnosis
- Run relevant checks and automated tests with explicit output evidence
- Report changed files and remaining limitations

Constraints
- Do not modify locked voice core files (audio/engine.py, audio/downstream.py, audio/echo_cancel.py)
- Work strictly within the designated workspace
- Never make unverified completion claims
```
