# Proactive Autonomy Runtime

The proactive runtime (`proactive/`) enables JARVIS to observe desktop activity, maintain a chronological event ledger, plan background tasks, and proactively assist the user within strict safety boundaries.

## Architecture

```text
[Desktop Activity / Idle] ──> [Monitor] ──> [Event Bus] ──> [Activity Ledger (SQLite)]
                                                                  │
                                                                  ▼
[Safety Policy & User Control] <──── [Autonomous Planner] <──────┘
             │
             ▼
[Worker Execution / Live Notification]
```

## Core Modules

- **`events.py`**: Pydantic/dataclass data models representing desktop events, activity states, and audit trails.
- **`monitor.py`**: Observes system idle state, resource spikes, and active windows without blocking voice audio.
- **`planner.py`**: Decomposes user goals or detected triggers into atomic, bounded actions.
- **`policy.py`**: Evaluates proposed actions against safety guardrails. Halts execution if user presence or explicit overrides require pause.
- **`runtime.py`**: Proactive daemon coordinator managing background loops, voice alerts, and execution limits.
- **`storage.py`**: Persistent SQLite storage for historical event logs and activity records.
