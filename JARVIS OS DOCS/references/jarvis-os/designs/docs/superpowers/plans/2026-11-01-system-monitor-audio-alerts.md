# System Monitor with Specialized Audio Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a comprehensive, standalone and integratable system monitoring utility (`core/system_monitor.py` and `scripts/system_monitor.py`) that checks network connectivity, server status, host resources, and systemd services, playing distinct synthesized audio alerts and emitting desktop notifications for failures and recoveries.

**Architecture:**
- `core/system_monitor.py` contains the modular architecture:
  - `AlertAudioEngine`: Procedural WAV tone generator (pure standard library: `wave`, `struct`, `math`) and async audio dispatcher with player auto-detection (`pw-play`, `paplay`, `canberra-gtk-play`, `aplay`, `mpv`).
  - `DesktopNotifier`: Non-blocking `notify-send` wrapper with urgency levels.
  - `SystemProbes`: Network probe (gateway, DNS, WAN HTTP), Server probe (TCP ports, HTTP/HTTPS endpoints with latency), Resource probe (CPU, RAM, Disks, Thermals), and Service probe (systemd units).
  - `AlertStateManager`: Debounced state engine tracking healthy/warning/critical states, managing alarm cooldowns, and triggering recovery chimes on state transitions.
- `scripts/system_monitor.py`: The executable CLI entry point providing `--once`, `--daemon`, `--test-audio`, `--config`, and `--json` modes.
- `configs/monitoring.json`: Default configuration template with servers, endpoints, thresholds, and service names.

**Tech Stack:** Python 3.8+ (standard library only for maximum portability, utilizing `/proc`, `/sys`, `socket`, `urllib.request`, `wave`, `struct`, `shutil`), PipeWire / PulseAudio / ALSA audio backends, `notify-send` for desktop intimation.

**Spec:** Architectural design approved in conversation fb03ec57-0563-4f4b-9e3d-30d26a9b1817.

## Global Constraints
- Pure Python standard library foundation with zero mandatory external pip dependencies.
- Non-blocking audio playback and notification calls so probe intervals never stall.
- Automatic generation and caching of clean, non-clipping PCM WAV alert audio into `~/.cache/jarvis/alerts/`.
- Debounced audio alerting: immediate alert on failure, cooldown window for ongoing failures, recovery chime when fixed.

---

### Task 1: Procedural Audio Synthesizer & Audio Player Engine

**Files:**
- Create: `core/system_monitor.py`
- Test: `tests/test_system_monitor_audio.py`

**Interfaces:**
- Produces:
  - `AlertAudioEngine.synthesize_alert_wav(alert_type: str, cache_dir: Path) -> Path`
  - `AlertAudioEngine.play_alert(alert_type: str, async_play: bool = True) -> bool`
  - `AlertAudioEngine.list_supported_alerts() -> list[str]`
  - `DesktopNotifier.notify(title: str, message: str, urgency: str = "normal") -> None`

- [ ] **Step 1: Write the failing tests for audio synthesis and desktop notification**
Write tests in `tests/test_system_monitor_audio.py` verifying that:
1. `synthesize_alert_wav` generates valid WAV files with correct RIFF headers and non-empty PCM samples for all alert types (`network_down`, `server_down`, `cpu_overload`, `memory_critical`, `disk_exhaustion`, `service_failure`, `thermal_critical`, `recovery`).
2. `AlertAudioEngine` correctly caches synthesized files without re-generating on every check.
3. `AudioPlayer` identifies the available audio binary (`pw-play` or `paplay` or `aplay`).

- [ ] **Step 2: Run test to verify it fails**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_audio.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement AlertAudioEngine and DesktopNotifier in `core/system_monitor.py`**
Implement procedural WAV tone generation with envelope attack/decay (to prevent clicking) for:
- `network_down` (880Hz / 587Hz alternating warble)
- `server_down` (900Hz -> 675Hz -> 450Hz descending triad)
- `cpu_overload` (1200Hz rapid pulsing trill)
- `memory_critical` (700Hz + 740Hz dual dissonance)
- `disk_exhaustion` (300Hz low resonant double thump)
- `service_failure` (750Hz staccato double burst)
- `thermal_critical` (900Hz -> 1400Hz frequency sweep)
- `recovery` (523Hz -> 659Hz -> 784Hz ascending major chord)
Implement async audio playback with player discovery (`pw-play`, `paplay`, `aplay`, `mpv`).
Implement `DesktopNotifier` with `notify-send`.

- [ ] **Step 4: Run test to verify it passes**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_audio.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add core/system_monitor.py tests/test_system_monitor_audio.py
git commit -m "feat(monitor): implement procedural audio synthesizer and alert player engine"
```

---

### Task 2: System Health Probes (Network, Server, Host Resources, Services)

**Files:**
- Modify: `core/system_monitor.py`
- Test: `tests/test_system_monitor_probes.py`

**Interfaces:**
- Produces:
  - `NetworkProbe.check(gateway_ip: str | None, dns_hosts: list[str], test_urls: list[str]) -> ProbeResult`
  - `ServerProbe.check_tcp(host: str, port: int, timeout: float) -> ProbeResult`
  - `ServerProbe.check_http(url: str, expected_codes: list[int], timeout: float) -> ProbeResult`
  - `ResourceProbe.check(cpu_threshold: float, mem_threshold: float, disk_threshold: float, temp_threshold: float) -> list[ProbeResult]`
  - `ServiceProbe.check(services: list[str]) -> list[ProbeResult]`
  - `ProbeResult`: dataclass with `name`, `category`, `status` (`OK`, `WARN`, `CRITICAL`), `message`, `metrics`, `alert_type`.

- [ ] **Step 1: Write the failing tests for all probes**
Write tests in `tests/test_system_monitor_probes.py`:
1. Network probe testing DNS resolution and URL reachability with mock sockets.
2. Server probe testing TCP open/refused ports and HTTP status responses with simulated servers.
3. Resource probe testing CPU, RAM, Disk, and Thermal parsing against fixture files.
4. Service probe testing systemctl status parsing.

- [ ] **Step 2: Run test to verify it fails**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_probes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement probe classes in `core/system_monitor.py`**
Implement:
- `NetworkProbe`: Detects default gateway, checks DNS lookup, tests HTTP connection.
- `ServerProbe`: Performs TCP connect socket checks and HTTP GET status/latency checks.
- `ResourceProbe`: Reads `/proc/stat` & `/proc/loadavg`, `/proc/meminfo`, `shutil.disk_usage`, `/sys/class/thermal`.
- `ServiceProbe`: Checks active/sub states of systemd services via `systemctl --user show` / `systemctl show`.

- [ ] **Step 4: Run test to verify it passes**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_probes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add core/system_monitor.py tests/test_system_monitor_probes.py
git commit -m "feat(monitor): implement network, server, resource, and service health probes"
```

---

### Task 3: State Management, Alert Debouncing & Recovery Notifications

**Files:**
- Modify: `core/system_monitor.py`
- Test: `tests/test_system_monitor_state.py`

**Interfaces:**
- Produces:
  - `AlertStateManager.process_results(results: list[ProbeResult]) -> list[AlertAction]`
  - `AlertAction`: dataclass with `action_type` (`ALERT` or `RECOVERY`), `alert_type`, `category`, `message`, `urgency`.

- [ ] **Step 1: Write the failing tests for AlertStateManager**
Write tests in `tests/test_system_monitor_state.py`:
1. Verify immediate alert on first failure (`OK` -> `CRITICAL`).
2. Verify alert suppression / cooldown when failure persists (does not spam audio every check).
3. Verify recovery action (`CRITICAL` -> `OK`) triggers recovery chime and notification.
4. Verify independent tracking for different failure categories (network vs server vs disk).

- [ ] **Step 2: Run test to verify it fails**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_state.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement AlertStateManager in `core/system_monitor.py`**
Implement state tracking with transition detection, configurable cooldown periods, and alert dispatching logic.

- [ ] **Step 4: Run test to verify it passes**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add core/system_monitor.py tests/test_system_monitor_state.py
git commit -m "feat(monitor): implement state management and debounced audio alert dispatching"
```

---

### Task 4: CLI Interface, Config Loader, and Executable Script

**Files:**
- Create: `scripts/system_monitor.py`
- Create: `configs/monitoring.json`
- Test: `tests/test_system_monitor_cli.py`

**Interfaces:**
- CLI arguments:
  - `--once`: Runs one sweep and exits (code 0 if healthy, 1 if failure detected).
  - `--daemon`: Runs continuous monitoring loop.
  - `--interval <seconds>`: Check interval in seconds (default: 15).
  - `--test-audio`: Sequentially plays all synthesized alert sounds with explanations.
  - `--config <path>`: Specifies JSON configuration file.
  - `--json`: Outputs JSON status to stdout.
  - `--quiet-audio`: Disables audio playback while keeping notifications and console output.

- [ ] **Step 1: Write failing CLI tests**
Write tests in `tests/test_system_monitor_cli.py`:
1. Test `--test-audio` executes without error.
2. Test `--once` runs a check and outputs formatted report.
3. Test `--once --json` outputs valid parseable JSON.
4. Test `--config` correctly overrides default server and threshold targets.

- [ ] **Step 2: Run test to verify it fails**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/system_monitor.py` and `configs/monitoring.json`**
Implement CLI arg parsing, colored ANSI dashboard renderer, config parser, daemon loop with graceful `SIGINT`/`SIGTERM` handling, and integration with `core.system_monitor`.

- [ ] **Step 4: Run test to verify it passes**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add scripts/system_monitor.py configs/monitoring.json tests/test_system_monitor_cli.py
git commit -m "feat(monitor): create executable CLI script and default configuration"
```

---

### Task 5: End-to-End Verification and Documentation

**Files:**
- Modify: `docs/superpowers/plans/2026-11-01-system-monitor-audio-alerts.md`
- Run full test suite: `pytest tests/test_system_monitor*.py`
- Live run: `python3 scripts/system_monitor.py --once`
- Live run: `python3 scripts/system_monitor.py --test-audio`

- [ ] **Step 1: Run all new and existing tests**
Run: `"/home/g0pi/JARVIS OS/.venv/bin/pytest" tests/test_system_monitor*.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Perform live dry-run of `--once` and `--test-audio`**
Run: `python3 scripts/system_monitor.py --once`
Run: `python3 scripts/system_monitor.py --test-audio`
Verify console output, tone generation in cache, and sound playback.

- [ ] **Step 3: Update documentation and mark task complete**
Update README or project docs if appropriate.
Commit final changes.
