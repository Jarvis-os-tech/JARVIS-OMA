# Uninstall Application Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow JARVIS OS to uninstall applications using system package managers (`pacman`, `yay`, `flatpak`).

**Architecture:** Create a centralized `PackageHandler` in `jarvis_control/package_manager.py` that detects the available package manager and executes the appropriate command to uninstall an application. The existing `jarvis_control/tools.py` will expose this via a new tool.

**Tech Stack:** Python, `subprocess` (shell commands), `shutil` (for detecting package managers).

**Spec:** User request to add uninstallation feature for available package managers.

## Global Constraints

- Use `subprocess` for executing commands safely.
- Must detect system available package managers (`pacman`, `yay`, `flatpak`).
- Preserve the existing `jarvis_control` tool structure.

## Review Focus

- **Unsupported package manager:** Program should gracefully error if no manager is found.
- **Permission denied:** Handle shell execution errors (like `sudo` requirements).
- **Application not found:** Handle cases where the package name does not exist.
- **Concurrent commands:** Prevent multiple simultaneous package operations.
- **Non-blocking execution:** Ensure package operations don't block the UI thread.

---

### Task 1: Create Package Manager Handler

**Files:**
- Create: `jarvis_control/package_manager.py`
- Test: `tests/test_package_manager.py`

**Interfaces:**
- Produces: `uninstall_package(package_name: str) -> str`

- [ ] **Step 1: Write `uninstall_package` logic in `jarvis_control/package_manager.py`**

```python
import subprocess
import shutil

class PackageHandler:
    @staticmethod
    def uninstall(package_name: str) -> str:
        if shutil.which("pacman"):
            cmd = ["sudo", "pacman", "-Rns", "--noconfirm", package_name]
        elif shutil.which("yay"):
            cmd = ["yay", "-Rns", "--noconfirm", package_name]
        elif shutil.which("flatpak"):
            cmd = ["flatpak", "uninstall", "-y", package_name]
        else:
            return "ERROR: No supported package manager found."
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"ERROR: {e.stderr}"
```

- [ ] **Step 2: Commit**

```bash
git add jarvis_control/package_manager.py
git commit -m "feat: add package manager handler"
```

### Task 2: Integrate into Tools Interface

**Files:**
- Modify: `jarvis_control/tools.py`

**Interfaces:**
- Consumes: `PackageHandler.uninstall(package_name: str)`

- [ ] **Step 1: Add uninstall tool to `jarvis_control/tools.py`**

Register a new tool `uninstall_app` that calls `PackageHandler.uninstall`.

- [ ] **Step 2: Commit**

```bash
git add jarvis_control/tools.py
git commit -m "feat: add uninstall_app tool"
```
