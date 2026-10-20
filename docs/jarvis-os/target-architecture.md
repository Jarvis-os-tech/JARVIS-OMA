# JARVIS OS Target Architecture

## System view

```text
User
  ↓ voice / text / screen / camera
Interaction Gateway
  ↓
Intent and Context Manager
  ├── Memory Service
  ├── Desktop State Observer
  ├── Project and Task State
  └── Permission and Risk Engine
  ↓
Planner and Supervisor
  ├── Capability Registry
  ├── GUI Controller
  ├── System Controller
  ├── Filesystem and Project Tools
  ├── External Connectors
  └── Multi-Agent Scheduler
  ↓
Execution Adapters
  ├── Linux / Omarchy / Hyprland
  ├── Accessibility and GUI driver
  ├── Applications and browsers
  ├── Coding agents
  └── Cloud services
  ↓
Verification, Audit, Events, and Recovery
```

## The shared control-plane objects

Future components should use common objects instead of isolated dictionaries.

### DesktopState

Contains focused application, windows, workspaces, visible text, screen metadata, audio state, and system health.

### Intent

Contains the user's original request, interpreted goal, constraints, urgency, and clarification status.

### Plan

Contains ordered steps, dependencies, expected outcomes, risk levels, required capabilities, and approval gates.

### Action

Contains the capability name, arguments, actor, target, permissions, start time, result, and verification evidence.

### Job

Contains task identity, workspace, assigned agent, state, progress, output, artifacts, timeout, and cancellation state.

### Evidence

Contains screenshots, command results, test results, hashes, state comparisons, or human approval associated with a claim.

## Capability contract

Every capability should declare:

- Name and description
- Input schema
- Required permissions
- Risk level
- Whether it changes state
- Preconditions
- Execution adapter
- Verification method
- Failure behavior
- Undo or recovery behavior

## GUI control contract

GUI actions should follow:

```text
fresh observation → target selection → action → new observation → verification
```

Coordinate actions must be tied to a fresh frame and must never assume that a window is still in the same position after another action.

## Agent contract

Agents should receive:

- A specific objective
- Workspace and branch rules
- Allowed tools
- Time and resource limits
- Acceptance criteria
- Reporting format
- Stop conditions

Agent output is evidence to inspect, not authority. A successful process exit is not the same as a successful task.

## Event model

All important state changes should produce events such as:

- `user.requested`
- `plan.created`
- `approval.requested`
- `action.started`
- `action.completed`
- `action.failed`
- `verification.passed`
- `verification.failed`
- `agent.started`
- `agent.progressed`
- `agent.completed`
- `system.warning`
- `jarvis.paused`

This will let voice, dashboard, notifications, memory, and recovery share the same history.
