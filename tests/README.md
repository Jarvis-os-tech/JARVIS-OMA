# Test Suite (`tests/`)

The `tests/` directory houses the complete test suite for JARVIS-OMA (239 unit & integration tests), organized into domain packages matching the project's feature architecture.

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
