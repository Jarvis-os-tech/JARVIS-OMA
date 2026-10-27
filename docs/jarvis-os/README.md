# JARVIS OS Documentation

This directory is the long-term design record for turning JARVIS-OMA into a dependable intelligent operating layer for Linux.

## How to use these documents

1. Read [vision-and-principles.md](vision-and-principles.md) to understand the target.
2. Read [master-blueprint.md](master-blueprint.md) for the full feature brainstorming map.
3. Read [capability-map.md](capability-map.md) to see what JARVIS can do and what is planned.
4. Read [target-architecture.md](target-architecture.md) to understand how the parts should fit together.
5. Read [roadmap.md](roadmap.md) before starting implementation work.
6. Record important choices in [decision-log.md](decision-log.md).
7. Use [verification-matrix-2026-10-18.md](verification-matrix-2026-10-18.md) as the evidence boundary for implementation status.
8. Follow [implementation-progress-2026-10-26.md](implementation-progress-2026-10-26.md) for the current redesign build order, verified increments and unresolved baseline results.

These documents describe intended behavior. The repository and tests remain the source of truth for what is currently implemented.

## Design rule

Every future capability should answer five questions:

- What can JARVIS observe?
- What action can it perform?
- What permission does it need?
- How does it verify success?
- How can the user stop or undo it?
