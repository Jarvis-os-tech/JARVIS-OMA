# Test Suite (`tests/`)

The `tests/` directory houses the unit and integration suite for JARVIS-OMA, organized into domain packages matching the project's feature architecture.

## Test Directory Structure

```text
tests/
├── README.md
├── __init__.py
├── test_core/            # Voice session loop, interruption, CLI flags, configuration
│   ├── test_agent.py
│   └── test_config.py
├── test_audio/           # PipeWire AEC module loading, volume restoration, virtual nodes
│   └── test_echo_cancel.py
├── test_skills/          # Dynamic manifests, adapters, input bar, and awareness OCR
│   ├── test_skills.py
│   ├── test_awareness.py
│   ├── test_input_bar.py
│   └── test_system_control.py
├── test_filesystem/      # Filesystem security limits, critical root guard, task runner
│   ├── test_filesystem.py
│   └── test_task_runner.py
├── test_orchestration/   # Agent discovery, workspace reservation, timeout enforcement
│   └── test_agent_orchestrator.py
├── test_memory/          # SQLite knowledge ledger, vector store, hybrid retrieval, Obsidian
│   ├── test_memory_capture.py
│   ├── test_memory_config.py
│   ├── test_memory_embeddings.py
│   ├── test_memory_hybrid.py
│   ├── test_memory_integration.py
│   ├── test_memory_knowledge.py
│   ├── test_memory_retrieval.py
│   ├── test_memory_strength.py
│   ├── test_memory_summaries.py
│   ├── test_memory_upgrade_integration.py
│   ├── test_memory_vector_store.py
│   ├── test_obsidian_memory.py
│   └── test_semantic_memory_eval.py
└── test_proactive/       # Proactive activity monitor, planner, safety policy, runtime daemon
    ├── test_proactive_control.py
    ├── test_proactive_events.py
    ├── test_proactive_monitor.py
    ├── test_proactive_planner.py
    ├── test_proactive_policy.py
    └── test_proactive_runtime.py
```

## Running Tests

Supported isolated test run:

```sh
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
timeout -k 5 180 .venv/bin/python -m pytest -q
```

Pytest collects only `tests/`; preserved upstream memory tests and live agent
smoke scripts are excluded from default discovery. Tests isolate connector
credentials and use a local executable search path. Local UNIX sockets and
loopback listeners must be allowed for IPC tests. Mock tests do not certify
live desktop or cloud behavior. The unittest commands below do not apply the
isolation fixtures in `conftest.py`.

For real Linux sandbox verification (requires `bwrap` and permitted user
namespaces), run `JARVIS_TEST_SANDBOX=1 .venv/bin/python -m pytest -q`.
These extra tests use temporary repositories and fake agents; they do not
contact paid models. They exercise the real sandbox's filesystem, environment,
and network boundaries.

Run the full suite across all feature packages:
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Run tests for an individual feature:
```sh
# Core runtime & config
.venv/bin/python -m unittest discover -s tests/test_core

# PipeWire audio AEC
.venv/bin/python -m unittest discover -s tests/test_audio

# Skills & desktop automation
.venv/bin/python -m unittest discover -s tests/test_skills

# Filesystem & task runner
.venv/bin/python -m unittest discover -s tests/test_filesystem

# Agent orchestration
.venv/bin/python -m unittest discover -s tests/test_orchestration

# Memory subsystem
.venv/bin/python -m unittest discover -s tests/test_memory

# Proactive background autonomy
.venv/bin/python -m unittest discover -s tests/test_proactive
```
