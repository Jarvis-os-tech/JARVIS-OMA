# JARVIS OS Roadmap

This roadmap is ordered by dependency. New features should not bypass the control plane.

## Stage 0: Documentation and baseline

- Keep the vision and capability map current.
- Inventory every manifest, adapter, connector, daemon, and test.
- Define terminology and status meanings.
- Establish a baseline test and health report.

## Stage 1: Unified control plane

- Introduce shared `Intent`, `Plan`, `Action`, `Job`, `Evidence`, and `DesktopState` models.
- Add a capability registry with permissions and risk levels.
- Route current system, filesystem, GUI, proactive, and agent skills through common action records.
- Persist audit events and expose them to voice and dashboard surfaces.

## Stage 2: Desktop and GUI reliability

- Improve desktop snapshots.
- Add stale-observation protection.
- Add action verification and safe retries.
- Add accessibility-tree discovery.
- Add reversible GUI workflows.
- Add emergency stop for input automation.

## Stage 3: Agent supervisor

- Add role-based agents.
- Add task graphs and dependencies.
- Add acceptance criteria and independent verification.
- Add durable job state and restart recovery.
- Add resource, workspace, and permission limits.

## Stage 4: Personal operating memory

- Add project context and long-term goals.
- Link actions, decisions, files, tasks, and agent results.
- Add user-visible memory review and correction.
- Add routine and preference learning with explicit confirmation.

## Stage 5: JARVIS shell and daily workflows

- Build a visual activity center.
- Add approval queue and task timeline.
- Add system health panel.
- Add saved modes such as coding, research, meeting, and focus.
- Add natural-language workflow recovery.

## Stage 6: Wider autonomy

- Add configurable autonomy policies.
- Add service diagnosis and repair workflows.
- Add browser and accessibility automation across applications.
- Add cross-device and remote-agent support only after local safety is mature.
