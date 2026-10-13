# Orchestration Feature Package (`orchestration/`)

The `orchestration/` package manages autonomous multi-agent discovery, workspace reservation, and background job delegation for JARVIS-OMA.

## Components

- **`agent_orchestrator.py` (`AgentOrchestrator`, `OrchestrationError`)**:
  - Auto-discovers installed system CLI agents:
    - **Codex** (`codex`)
    - **Claude Code** (`claude`)
    - **Hermes** (`hermes`)
    - **OpenCode Interpreter** (`opencode`)
    - **Gemini CLI** (`gemini`)
    - **OMP** (`omp`)
  - Concurrency & Isolation:
    - Supervises up to 4 concurrent agents in independent workspaces.
    - Path reservation: prevents multiple agents from overlapping write access to the same project directory.
    - Memory bounding: retains up to 50 historical job records with capped stdout/stderr buffers.
    - Configurable timeouts (default 15 minutes, maximum 2 hours).

## Usage

```python
from orchestration import AgentOrchestrator

orchestrator = AgentOrchestrator()
agents = orchestrator.list_available_agents()

job = await orchestrator.delegate(
    agent_name="codex",
    prompt="Refactor database models to async",
    workspace="/path/to/project"
)
status = orchestrator.check_job(job["job_id"])
```
