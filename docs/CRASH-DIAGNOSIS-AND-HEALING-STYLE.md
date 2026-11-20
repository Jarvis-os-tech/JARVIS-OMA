# JARVIS Unified Crash Diagnosis & Auto-Healing Style (Omarchy Crash Protocol)

This unified style specification integrates all crash diagnosis, investigation, prompt conventions, and auto-healing workflows from Omarchy's `diagnose-crash` skill, `omarchy-crash-watch`, `omarchy-agent-crash`, and upstream reporting standards into a single, cohesive style for JARVIS OS.

---

## 1. Core Operating Principles

1. **Evidence Over Guesswork**: Work strictly from evidence. The goal is an honest, precise account of what happened, not a plausible-sounding story.
2. **Clear Separation of Facts & Inferences**: Clearly distinguish what the core dump and logs **prove** from what you are **inferring**.
3. **Leave No In-Memory Artifacts**: Extracted memory cores can hold passwords, session tokens, and sensitive documents. Always extract to an ephemeral `mktemp` path and delete it immediately upon analysis.
4. **Clean Delivery Without Fluff**: State the findings, mechanism, and fix directly. Do not preface with acknowledgement words (e.g. "Sure", "Certainly", "Understood", "Okay", "On it").

---

## 2. Automatic Detection & Fact Gathering

When an application crashes, segfaults, disappears, aborts, or is reported via a coredump notification:

### Step 1: Establish Primary Facts
```bash
# List recent crash records and check pattern vs one-off
coredumpctl list

# Inspect exact crash details
coredumpctl info <pid>
```
Extract and record:
- **Process Name** (`comm`): Note that kernel comm can be truncated to 15 characters; prefer the executable binary basename.
- **PID**: Numeric process identifier.
- **Binary Path** (`exe`): Full path to executable.
- **Signal**: Termination signal (e.g. `SIGSEGV`, `SIGABRT`, `SIGBUS`, `SIGTRAP`).
- **Timestamp**: Exact second of crash.
- **Command Line**: The starting arguments — reveals what work was being processed at death.

### Step 2: Rule Out Resource Exhaustion
Check before blaming application logic:
```bash
free -h
journalctl -b -g "Out of memory|oom-killer|killed process" -n 50 --no-pager
```
*A process terminated by the kernel OOM killer is resource starvation, not an application code defect.*

### Step 3: Correlate Against Timeline
Compare crash timestamp against:
- **Filesystem mtimes**: Directory or file mtimes landing on the exact second of the crash pinpoint the file being read or written.
- **Systemd Journal**: Warnings or errors emitted by the process or its dependencies right before termination.
- **Recent Package Updates**: Check `/var/log/pacman.log` to see if a system update just altered a shared library.

### Step 4: Full Stack & Thread Inspection
- Thread stacks other than the crashing frame reveal in-flight background operations (IPC readers, image decoders, GPU submissions).
- Note third-party modules or extensions in the address space.

### Step 5: Symbolize via Arch Debuginfod
When debug symbols are absent:
```bash
core=$(mktemp -t crash-XXXXXX.core)
trap 'rm -f "$core"' EXIT
coredumpctl dump <pid> --output="$core"
DEBUGINFOD_URLS="https://debuginfod.archlinux.org" \
  gdb -q <executable> "$core" \
  -batch -ex 'set debuginfod enabled on' -ex 'bt'
```
*If frames remain unresolved, acknowledge the missing symbols honestly. Never invent function names.*

---

## 3. Diagnostic Report Structure

Structure all crash reports according to this standard:

1. **What crashed and what it was doing**: Process name, binary, PID, signal, and the command line / activity in flight.
2. **Most likely mechanism**: The causal sequence leading to failure, explicitly separating verified evidence from deductions.
3. **User data loss & recovery**: Whether any unsaved data, cache, or file was damaged. Always check trash (`~/.local/share/Trash/`) and temp backup files before declaring data lost.
4. **Recurrence & fix**: Whether this failure is a one-off anomaly or recurring, and the concrete remediation steps.

---

## 4. Auto-Healing & Remediation Protocol

1. **Recover Fixable System States**:
   - Stale lock files (e.g. socket locks, PID files preventing restart).
   - Corrupted runtime cache files (safely purge and regenerate).
   - Invalid or corrupted configuration syntax in `~/.config/`.
2. **Notification Suppression (Muting)**:
   If a crash is known, recurring, and cannot be patched immediately in user-space, offer single-program mute:
   ```bash
   omarchy-crash-mute '<program>'        # silence notifications for this program
   omarchy-crash-mute '<program>' off    # un-silence
   omarchy-crash-mute                    # list muted programs
   ```
3. **Upstream Bug Reporting (Omarchy)**:
   Only report upstream to Omarchy if all three conditions are satisfied:
   - **Within Omarchy scope**: `omarchy-*` commands, Quickshell/plugins, Hyprland configs, bundled themes, or installer scripts.
   - **User explicit consent**: Present exact title and body to user and obtain confirmation first.
   - **GitHub authentication**: `gh auth status` must succeed.
   - Search existing issues before creating: `gh search issues --repo omacom/omarchy "<program> crash"`.

---

## 5. Spoken & Text Delivery Style for JARVIS

- Lead directly with the diagnosis and outcome:
  *"Antigravity-ide terminated with SIGTRAP due to an IPC socket disconnect during indexing. The workspace state is intact, and no files were lost."*
- Propose or execute the verified fix immediately:
  *"I've cleared the stale socket lock and restarted the process."*
- Omit all conversational filler, hedges, and polite acknowledgement delays.
