# Filesystem Feature Package (`filesystem/`)

The `filesystem/` package provides secure, autonomous desktop file operations and bounded multi-step task execution for JARVIS-OMA.

## Components

- **`filesystem.py` (`FileOperationError`)**:
  - Full-autonomy file and directory tools: `list_directory`, `read_text`, `write_text`, `append_text`, `replace_text`, `make_directory`, `move_path`, `copy_path`, `trash_path`, `delete_path`, `inspect_path`, `search_files`, and `search_file_content`.
  - Safety Guards:
    - Critical system roots (`/`, `~`, `/bin`, `/boot`, `/dev`, `/etc`, `/lib`, `/proc`, `/root`, `/sys`, `/usr`) are strictly protected from permanent deletion or displacement.
    - Max characters limit per read (up to 100,000 characters with offset support).
    - File size limits on search and atomic write operations (up to 5 MiB).

- **`task_runner.py` (`TaskRunner`, `TaskPlanError`)**:
  - Plans and executes multi-step filesystem operations asynchronously in worker threads (`asyncio.to_thread`).
  - Supports up to 30 validated steps per plan with real-time status reporting, per-step logging, and clean cooperative cancellation.

## Usage

```python
from filesystem import read_text, write_text, TaskRunner

# Read file
data = read_text("/path/to/file.txt", offset=0, max_chars=1000)

# Multi-step task runner
runner = TaskRunner(executor_func, validator_func)
task_id = runner.start([{"action": "write_file", "path": "test.txt", "content": "..."}])
status = runner.status(task_id)
```
