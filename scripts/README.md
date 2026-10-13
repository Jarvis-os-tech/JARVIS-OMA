# Maintenance & Diagnostic Scripts (`scripts/`)

The `scripts/` directory contains standalone administrative, setup, and verification utilities for JARVIS-OMA.

## Scripts Overview

- **`register_obsidian_vault.py`**:
  - Automatically inspects the local user environment for existing Obsidian installations and registers the `JARVIS-OMA Memory` vault path.
  - Usage:
    ```sh
    python scripts/register_obsidian_vault.py
    ```

- **`sync_obsidian_memory.py`**:
  - Standalone CLI trigger to immediately sync local SQLite memory facts, profiles, and conversation journals to the configured Obsidian vault.
  - Usage:
    ```sh
    python scripts/sync_obsidian_memory.py
    ```

- **`test_agent_delegation.py`**:
  - Offline integration test script that discovers installed system agents (Codex, Claude, etc.) and tests bounded background delegation without starting a live voice connection.
  - Usage:
    ```sh
    python scripts/test_agent_delegation.py
    ```
