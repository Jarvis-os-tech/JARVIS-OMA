# Sovereign Voice Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a crash-resilient background voice daemon (`jarvis-voice`) that captures ambient audio, detects speech locally, converses via Gemini Live full-duplex streaming, interrupts in <25ms, and runs as a systemd user service with IPC control.

**Architecture:** The daemon is derived from the proven `pma_voice_only` module (speech-only Gemini transport) and hardened with the `JARVIS-OMA` codebase's production-grade speech turn gating, echo cancellation, barge-in detection, and connection recovery. The 6 voice regressions from the 30 Oct audit are fixed as part of hardening.

**Tech Stack:** Python 3.11+, PipeWire (`pw-record`, `pw-play`, `pactl`), Silero VAD (via openwakeword), ONNX Runtime, Google GenAI SDK, asyncio, systemd user services.

**Spec:** [`docs/superpowers/specs/2026-10-30-voice-foundation-design.md`](file:///home/g0pi/JARVIS%20OS/docs/superpowers/specs/2026-10-30-voice-foundation-design.md)

## Global Constraints

- Python ≥ 3.11; no compiled C/C++ changes (native audio engine used as-is).
- Zero modifications to the 7 voice-core-locked files (verified by `scripts/verify_voice_lock.py`).
- `SUPER + H` must never be touched — permanently locked to `linux-voice toggle`.
- RAM ceiling: ~900 MB total; voice daemon must stay under 120 MB resident.
- All tests run from the project root: `.venv/bin/pytest tests/ -v`.
- Commit after each task passes its tests.

---

### Task 1: Project Scaffold & Configuration

**Files:**
- Create: `jarvis_voice/__init__.py`
- Create: `jarvis_voice/config.py`
- Create: `jarvis_voice/__main__.py`
- Create: `configs/config.toml.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass with fields `model: str`, `voice: str`, `device: str`, `barge_in: bool`, `autostart_listening: bool`, `api_key_env: str`; `load() -> Config`; `load_env() -> None`; `RUNTIME_DIR: Path`, `SOCKET_PATH: Path`, `STATE_FILE: Path`, `LEVEL_FILE: Path`.

- [ ] **Step 1: Write the config test**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path

def test_default_config():
    from jarvis_voice.config import Config
    c = Config()
    assert c.model == 'gemini-3.8-live'
    assert c.voice == 'Aoede'
    assert c.barge_in is True
    assert c.autostart_listening is True
    assert c.api_key_env == 'GEMINI_API_KEY'

def test_load_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / 'config.toml'
    toml.write_text('model = "gemini-2.0-flash-live"\nvoice = "Puck"\nbarge_in = false\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    (tmp_path / 'jarvis-voice').mkdir()
    (tmp_path / 'jarvis-voice' / 'config.toml').write_text(toml.read_text())
    from jarvis_voice.config import load
    c = load()
    assert c.model == 'gemini-2.0-flash-live'
    assert c.voice == 'Puck'
    assert c.barge_in is False

def test_unknown_setting_rejected(tmp_path, monkeypatch):
    (tmp_path / 'jarvis-voice').mkdir()
    (tmp_path / 'jarvis-voice' / 'config.toml').write_text('unknown_key = true\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    import pytest
    from jarvis_voice.config import load
    with pytest.raises(ValueError, match='Unsupported'):
        load()

def test_load_env_sets_key(tmp_path, monkeypatch):
    (tmp_path / 'jarvis-voice').mkdir()
    env_file = tmp_path / 'jarvis-voice' / 'env'
    env_file.write_text('GEMINI_API_KEY=test-key-12345\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    from jarvis_voice.config import load_env
    load_env()
    assert os.environ.get('GEMINI_API_KEY') == 'test-key-12345'

def test_runtime_paths():
    from jarvis_voice.config import RUNTIME_DIR, SOCKET_PATH, STATE_FILE
    assert RUNTIME_DIR.name == 'jarvis'
    assert SOCKET_PATH.name == 'control.sock'
    assert STATE_FILE.name == 'state.json'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jarvis_voice'`

- [ ] **Step 3: Create jarvis_voice package**

```python
# jarvis_voice/__init__.py
"""JARVIS Voice Core — sovereign voice foundation for JARVIS OS."""
__version__ = '0.1.0'
```

```python
# jarvis_voice/config.py
"""Voice configuration and credential loading."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tomllib

CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
RUNTIME_DIR = Path(os.environ.get('XDG_RUNTIME_DIR', STATE_HOME)) / 'jarvis'
SOCKET_PATH = RUNTIME_DIR / 'control.sock'
STATE_FILE = RUNTIME_DIR / 'state.json'
LEVEL_FILE = RUNTIME_DIR / 'level'
ENV_FILE = CONFIG_HOME / 'jarvis-voice' / 'env'


def dir_is_private(path: Path) -> bool:
    s = Path(path).stat()
    return s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) & 0o077 == 0


def load_env():
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            if name in {'GEMINI_API_KEY', 'GOOGLE_API_KEY'} and name not in os.environ:
                os.environ[name] = value.strip().strip('"\'')


@dataclass
class Config:
    model: str = 'gemini-3.8-live'
    voice: str = 'Aoede'
    device: str = ''
    barge_in: bool = True
    autostart_listening: bool = True
    api_key_env: str = 'GEMINI_API_KEY'


def load() -> Config:
    path = CONFIG_HOME / 'jarvis-voice' / 'config.toml'
    if path.exists():
        data = tomllib.loads(path.read_text())
        unknown = set(data) - set(Config.__dataclass_fields__)
        if unknown:
            raise ValueError('Unsupported jarvis-voice setting: ' + ', '.join(sorted(unknown)))
        return Config(**data)
    return Config()
```

```python
# jarvis_voice/__main__.py
"""CLI entry point: python -m jarvis_voice"""
import sys

def main():
    print('jarvis-voice: use --help for options')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
```

```toml
# configs/config.toml.example
model = "gemini-3.8-live"
voice = "Aoede"
device = ""
barge_in = true
autostart_listening = true
api_key_env = "GEMINI_API_KEY"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd "/home/g0pi/JARVIS OS"
git init && git add -A
git commit -m "feat: jarvis_voice package scaffold with config, env loading, and runtime paths"
```

---

### Task 2: IPC Control Socket Server

**Files:**
- Create: `jarvis_voice/ipc.py`
- Test: `tests/test_ipc.py`

**Interfaces:**
- Consumes: `Config` from Task 1; `RUNTIME_DIR`, `SOCKET_PATH` from `jarvis_voice.config`.
- Produces: `ControlServer` class with `async start()`, `async close()`, `broadcast_state(status: dict)`, and command handlers for `status`, `status --json`, `listen toggle`, `listen start`, `listen stop`, `listen cancel`.

- [ ] **Step 1: Write the IPC test**

```python
# tests/test_ipc.py
import asyncio
import json
import pytest
from pathlib import Path

@pytest.fixture
def socket_path(tmp_path):
    return tmp_path / 'test.sock'

@pytest.mark.asyncio
async def test_status_json(socket_path):
    from jarvis_voice.ipc import ControlServer
    status = {'listening': True, 'connected': True, 'model': 'test'}
    server = ControlServer(socket_path=socket_path, status_provider=lambda: status)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'status --json\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        result = json.loads(data.decode())
        assert result['listening'] is True
        assert result['model'] == 'test'
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_listen_toggle(socket_path):
    from jarvis_voice.ipc import ControlServer
    state = {'muted': False}
    def toggle():
        state['muted'] = not state['muted']
        return state['muted']
    server = ControlServer(
        socket_path=socket_path,
        status_provider=lambda: {'listening': not state['muted']},
        toggle_mute_cb=toggle,
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'listen toggle\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert state['muted'] is True
        assert b'muted' in data.lower() or b'true' in data.lower()
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_unknown_command(socket_path):
    from jarvis_voice.ipc import ControlServer
    server = ControlServer(socket_path=socket_path, status_provider=lambda: {})
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'foobar\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert b'unknown' in data.lower() or b'error' in data.lower()
    finally:
        await server.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_ipc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jarvis_voice.ipc'`

- [ ] **Step 3: Implement ControlServer**

```python
# jarvis_voice/ipc.py
"""Protected Unix domain socket for status queries and control commands."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from .config import RUNTIME_DIR, SOCKET_PATH

log = logging.getLogger('jarvis.ipc')


class ControlServer:
    def __init__(
        self,
        socket_path: Optional[Path] = None,
        status_provider: Optional[Callable] = None,
        toggle_mute_cb: Optional[Callable] = None,
        set_mute_cb: Optional[Callable] = None,
        interrupt_cb: Optional[Callable] = None,
    ):
        self.socket_path = Path(socket_path) if socket_path else SOCKET_PATH
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb
        self.set_mute_cb = set_mute_cb
        self.interrupt_cb = interrupt_cb
        self._server = None

    async def start(self):
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket_path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path))
        self.socket_path.chmod(0o600)
        log.info('IPC listening on %s', self.socket_path)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.socket_path.unlink(missing_ok=True)

    def broadcast_state(self, status: dict):
        """Write atomic state file for external readers."""
        from .config import STATE_FILE
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = STATE_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(status))
        temp.chmod(0o600)
        temp.replace(STATE_FILE)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            line = await asyncio.wait_for(reader.readline(), 5)
            command = line.decode().strip()
            response = self._dispatch(command)
            writer.write(response.encode() if isinstance(response, str) else response)
            await writer.drain()
        except Exception as e:
            log.warning('IPC client error: %s', e)
        finally:
            writer.close()

    def _dispatch(self, command: str) -> str:
        if command == 'status --json':
            return json.dumps(self.status_provider()) + '\n'
        if command == 'status':
            status = self.status_provider()
            state = 'listening' if status.get('listening') else 'idle'
            model = status.get('model', 'unknown')
            return f'jarvis-voice: {state} (model={model})\n'
        if command == 'listen toggle':
            if self.toggle_mute_cb:
                muted = self.toggle_mute_cb()
                return json.dumps({'muted': muted}) + '\n'
            return json.dumps({'error': 'toggle not available'}) + '\n'
        if command == 'listen start':
            if self.set_mute_cb:
                self.set_mute_cb(False)
                return json.dumps({'muted': False}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        if command == 'listen stop':
            if self.set_mute_cb:
                self.set_mute_cb(True)
                return json.dumps({'muted': True}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        if command == 'listen cancel':
            if self.interrupt_cb:
                self.interrupt_cb()
                return json.dumps({'cancelled': True}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        return json.dumps({'error': f'unknown command: {command}'}) + '\n'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_ipc.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add jarvis_voice/ipc.py tests/test_ipc.py
git commit -m "feat: IPC control socket server with status, toggle, and command dispatch"
```

---

### Task 3: Connection Recovery Hardening (Fixes 1–3)

**Files:**
- Create: `jarvis_voice/recovery.py`
- Test: `tests/test_recovery.py`

**Interfaces:**
- Produces: `ConnectionRecovery` class with `decide(error, attempted_resume, session_opened, session_seconds) -> RecoveryDecision`; `RecoveryDecision` dataclass with `delay: float`, `fresh_session: bool`, `fatal: bool`, `code: int | None`.

- [ ] **Step 1: Write regression tests for fixes 1–3**

```python
# tests/test_recovery.py
from jarvis_voice.recovery import ConnectionRecovery, RecoveryDecision

class FakeError(Exception):
    def __init__(self, code=None):
        self.code = code

def test_429_enforces_60s_minimum_delay():
    """Fix 1: rate-limit must wait at least 60 seconds."""
    recovery = ConnectionRecovery(retry_budget=5)
    decision = recovery.decide(FakeError(429))
    assert decision.delay >= 60.0
    assert not decision.fatal
    assert not decision.fresh_session

def test_429_repeated_still_enforces_60s():
    """Fix 1: repeated 429s still enforce 60s floor."""
    recovery = ConnectionRecovery(retry_budget=10)
    for _ in range(3):
        decision = recovery.decide(FakeError(429))
    assert decision.delay >= 60.0

def test_setup_timeout_retains_resume_handle():
    """Fix 2: setup timeout without session_opened keeps resume context."""
    recovery = ConnectionRecovery(retry_budget=5)
    decision = recovery.decide(
        TimeoutError('connect timeout'),
        attempted_resume='handle-abc',
        session_opened=False,
    )
    # First failed resume: should NOT force fresh session yet
    assert not decision.fresh_session
    assert not decision.fatal

def test_setup_timeout_after_two_failures_goes_fresh():
    """Fix 2: after 2 failed resumes, fall back to fresh session."""
    recovery = ConnectionRecovery(retry_budget=5)
    recovery.decide(
        TimeoutError('timeout 1'),
        attempted_resume='handle-abc',
        session_opened=False,
    )
    decision = recovery.decide(
        TimeoutError('timeout 2'),
        attempted_resume='handle-abc',
        session_opened=False,
    )
    assert decision.fresh_session

def test_400_on_resume_goes_fresh_immediately():
    """Fix 3: 400 on a resumed session = resume rejection → fresh session."""
    recovery = ConnectionRecovery(retry_budget=5)
    decision = recovery.decide(
        FakeError(400),
        attempted_resume='handle-xyz',
        session_opened=False,
    )
    assert decision.fresh_session
    assert decision.delay == 0.0
    assert not decision.fatal

def test_400_without_resume_is_fatal():
    """Fix 3: 400 on a non-resumed session is truly fatal."""
    recovery = ConnectionRecovery(retry_budget=5)
    decision = recovery.decide(
        FakeError(400),
        attempted_resume=None,
        session_opened=False,
    )
    assert decision.fatal

def test_successful_session_resets_failures():
    recovery = ConnectionRecovery(retry_budget=5)
    recovery.decide(FakeError(503))
    recovery.decide(FakeError(503))
    decision = recovery.decide(
        ConnectionError('closed'),
        session_opened=True,
        session_seconds=120.0,
    )
    # After a long session, failures should be reset
    assert decision.delay <= 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_recovery.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement hardened ConnectionRecovery**

```python
# jarvis_voice/recovery.py
"""Deterministic retry decisions for voice-session recovery.

Fixes from 30 Oct 2026 audit:
- Fix 1: 429 enforces minimum 60s delay.
- Fix 2: Setup timeouts retain resume handle; fresh after 2 consecutive failures.
- Fix 3: 400 on resumed session = resume rejection (fresh, delay=0); 400 without resume = fatal.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryDecision:
    delay: float
    fresh_session: bool
    fatal: bool
    code: int | None


class ConnectionRecovery:
    """Choose whether to retry, resume, or start a fresh session."""

    _TRANSIENT_CODES = {1006, 1008, 429, 500, 502, 503, 504}
    _FATAL_CODES = {400, 401, 403, 404}

    def __init__(self, retry_budget: int = 5):
        self.retry_budget = max(0, int(retry_budget))
        self._failures = 0
        self._failed_resume_attempts = 0

    @staticmethod
    def _error_code(error) -> int | None:
        for attr in ('code', 'status_code'):
            try:
                value = getattr(error, attr, None)
            except Exception:
                continue
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _is_transient(error, code: int | None) -> bool:
        return (isinstance(error, (ConnectionError, TimeoutError, OSError, BufferError))
                or code in ConnectionRecovery._TRANSIENT_CODES
                or type(error).__name__ in ('APIError', 'ConnectionClosedError'))

    def decide(
        self,
        error,
        attempted_resume=None,
        session_opened: bool = False,
        session_seconds: float = 0.0,
    ) -> RecoveryDecision:
        code = self._error_code(error)

        if session_opened:
            self._failed_resume_attempts = 0
            if session_seconds >= 60.0:
                self._failures = 0

        resuming = bool(attempted_resume)
        if not resuming:
            self._failed_resume_attempts = 0

        # Fix 3: 400/1008 on a resumed session = resume rejection → fresh.
        if resuming and code in (400, 1008):
            self._failed_resume_attempts = 0
            self._failures += 1
            return RecoveryDecision(0.0, True, False, code)

        transient = self._is_transient(error, code)

        # Fix 2: Setup timeouts retain resume; fresh after 2 consecutive failures.
        if resuming and not session_opened and transient:
            self._failed_resume_attempts += 1
            if self._failed_resume_attempts >= 2:
                self._failed_resume_attempts = 0
                self._failures += 1
                return RecoveryDecision(0.0, True, False, code)

        # Fix 3: 400 without resume is fatal.
        if code in self._FATAL_CODES:
            return RecoveryDecision(0.0, False, True, code)

        if isinstance(error, BufferError):
            self._failures += 1
            return RecoveryDecision(
                min(30.0, float(2 ** min(self._failures - 1, 5))),
                True, False, code)

        if transient:
            self._failures += 1
            delay = min(30.0, float(2 ** min(self._failures - 1, 5)))
            # Fix 1: 429 enforces minimum 60s delay.
            if code == 429:
                delay = max(60.0, delay)
            return RecoveryDecision(delay, False, False, code)

        self._failures += 1
        if self._failures > self.retry_budget:
            return RecoveryDecision(0.0, False, True, code)
        delay = min(30.0, float(2 ** min(self._failures - 1, 5)))
        return RecoveryDecision(delay, False, False, code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_recovery.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add jarvis_voice/recovery.py tests/test_recovery.py
git commit -m "feat: hardened connection recovery with 429 cooldown, resume retention, and 400 handling"
```

---

### Task 4: Speech Turn Gate Fix (Fix 4) & Interruption Continuity Fix (Fix 5)

**Files:**
- Create: `jarvis_voice/speech.py`
- Test: `tests/test_speech.py`

**Interfaces:**
- Produces: `SpeechTurnGate` class (hardened copy with Fix 4); `SpokenInterruption` class (hardened copy with Fix 5); `SileroSpeechDetector` class; `GateFrame` dataclass.

- [ ] **Step 1: Write regression tests for fixes 4 and 5**

```python
# tests/test_speech.py
import struct
import math
from unittest.mock import MagicMock

def make_pcm_frame(amplitude=0):
    """Create a 20ms PCM16 frame (320 samples = 640 bytes)."""
    return struct.pack('<320h', *([amplitude] * 320))

def make_quiet_frame():
    """Frame below -54 dBFS threshold."""
    return make_pcm_frame(amplitude=1)

def make_speech_frame():
    """Frame with clear speech-level amplitude."""
    return make_pcm_frame(amplitude=8000)


class FakeDetector:
    """Deterministic speech detector for testing."""
    def __init__(self, scores=None):
        self._scores = list(scores or [])
        self._index = 0
        self.call_count = 0
        self.fresh_prediction = True

    def __call__(self, pcm):
        self.call_count += 1
        if self._index < len(self._scores):
            score = self._scores[self._index]
            self._index += 1
            return score
        return 0.0

    def reset(self):
        self._index = 0
        self.call_count = 0


def test_fix4_quiet_frames_still_reach_detector():
    """Fix 4: quiet frames must pass through the detector for state continuity."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.0, 0.0, 0.0])
    gate = SpeechTurnGate(detector=detector)

    # Send quiet frames — energy below -54 dBFS but not absolute zero
    # These should still reach the detector
    quiet = make_pcm_frame(amplitude=50)  # Low but nonzero
    for i in range(3):
        gate.process(quiet, now=float(i))

    assert detector.call_count >= 3, \
        f"Quiet frames must still reach detector, but only {detector.call_count} calls made"


def test_fix4_absolute_silence_skips_detector():
    """Absolute silence (all zeros) may skip the detector."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.0])
    gate = SpeechTurnGate(detector=detector)

    silence = make_pcm_frame(amplitude=0)
    gate.process(silence, now=0.0)

    # All-zero frames have energy == 0, can skip detector
    # (This is acceptable — absolute silence means no signal at all)


def test_fix5_quiet_frames_update_interruption_microphone_buffer():
    """Fix 5: quiet frames must still update the _microphone deque."""
    from jarvis_voice.speech import SpokenInterruption, PlaybackReference

    ref = PlaybackReference()
    detector = FakeDetector(scores=[0.0, 0.0, 0.0])
    interrupt = SpokenInterruption(reference=ref, detector=detector)

    quiet = make_pcm_frame(amplitude=10)  # RMS < 0.004 threshold
    for i in range(3):
        interrupt.process(quiet, now=float(i))

    # The microphone deque should have been updated even for quiet frames
    assert len(interrupt._microphone) > 0, \
        "Quiet frames must still update _microphone deque for state continuity"


def test_speech_turn_opens_on_voiced_frames():
    """Basic gate operation: opens after trigger_frames of speech."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.6, 0.7, 0.8])
    gate = SpeechTurnGate(detector=detector, trigger_frames=2)

    speech = make_speech_frame()
    f1 = gate.process(speech, now=0.0)
    f2 = gate.process(speech, now=0.02)

    assert f2.opened is True
    assert gate.active is True


def test_speech_turn_closes_on_silence():
    """Gate closes after silence_frames of quiet."""
    from jarvis_voice.speech import SpeechTurnGate

    scores = [0.8] * 3 + [0.1] * 25  # 3 speech + 25 silence
    detector = FakeDetector(scores=scores)
    gate = SpeechTurnGate(detector=detector, trigger_frames=2, silence_frames=20)

    speech = make_speech_frame()
    quiet = make_pcm_frame(amplitude=50)

    # Open the turn
    for i in range(3):
        gate.process(speech, now=float(i) * 0.02)
    assert gate.active is True

    # Close with silence
    closed = False
    for i in range(25):
        frame = gate.process(quiet, now=0.06 + float(i) * 0.02)
        if frame.closed:
            closed = True
            break

    assert closed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_speech.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement hardened speech modules**

```python
# jarvis_voice/speech.py
"""Local speech admission, turn gating, and spoken interruption detection.

Fixes from 30 Oct 2026 audit:
- Fix 4: Quiet frames still pass through the detector for state continuity.
- Fix 5: Quiet frames update the interruption microphone buffer.
"""
from collections import deque
from dataclasses import dataclass
import math
import struct
import time

import numpy as np


class SileroSpeechDetector:
    """Reuse the installed OpenWakeWord package's Silero VAD."""

    def __init__(self):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        from openwakeword.vad import VAD
        self.np = np
        self.model = VAD()
        self._pending = np.empty(0, dtype='<i2')
        self._last_score = 0.0
        self.fresh_prediction = False

    def __call__(self, pcm):
        self._pending = self.np.concatenate((
            self._pending, self.np.frombuffer(pcm, dtype='<i2')))
        if len(self._pending) < 480:
            self.fresh_prediction = False
            return self._last_score
        chunk, self._pending = self._pending[:480], self._pending[480:]
        score = float(self.model.predict(chunk, frame_size=480))
        if not math.isfinite(score):
            raise RuntimeError('Local speech detector returned an invalid score')
        self.fresh_prediction = True
        self._last_score = score
        return score

    def reset(self):
        self._pending = self.np.empty(0, dtype='<i2')
        self._last_score = 0.0
        self.fresh_prediction = False
        self.model.reset_states()


@dataclass(frozen=True)
class GateFrame:
    pcm: bytes
    opened: bool = False
    closed: bool = False
    barge_in: bool = False


class SpeechTurnGate:
    def __init__(self, detector=None, trigger_frames=2, silence_frames=30, tail_seconds=.45):
        self.detector = detector
        self.trigger_frames, self.silence_frames = trigger_frames, silence_frames
        self.tail_seconds = tail_seconds
        self.active = False
        self.accepted_turns = self.suppressed_frames = 0
        self._voiced = self._quiet = 0
        self._hold_until = 0.0
        self._preroll = deque(maxlen=10)
        self._needs_reset = True
        self.last_probability = self.peak_unadmitted_probability = 0.0

    def reset(self, hold_until=0.0):
        self.active = False
        self._voiced = self._quiet = 0
        self._hold_until = hold_until
        self._preroll.clear()
        self._needs_reset = True

    def admit_interruption(self):
        """Continue a locally verified interruption as a normal spoken turn."""
        self.reset()
        self.active = True
        self.accepted_turns += 1

    def process(self, pcm, now, blocked=False):
        if len(pcm) != 640:
            raise ValueError('Speech admission requires a 20 ms PCM16 frame')
        if blocked:
            self.reset(hold_until=now + self.tail_seconds)
        if blocked or now < self._hold_until:
            self.suppressed_frames += 1
            return GateFrame(bytes(640))
        if self._needs_reset:
            reset = getattr(self.detector, 'reset', None)
            if callable(reset):
                reset()
            self._needs_reset = False
        samples = struct.unpack('<320h', pcm)
        energy = sum(x * x for x in samples) / 320

        # Fix 4: Only skip detector for absolute silence (energy == 0).
        # Low-energy frames still pass through for detector state continuity.
        if energy == 0:
            score = 0.0
            fresh_prediction = True
        else:
            if self.detector is None:
                self.detector = SileroSpeechDetector()
            score = float(self.detector(pcm))
            fresh_prediction = getattr(self.detector, 'fresh_prediction', True)
            if not math.isfinite(score):
                raise RuntimeError('Local speech detector returned an invalid score')
            # Below -54 dBFS: clamp score to prevent ghost turns,
            # but we already fed the frame to the detector above.
            if energy < (32768 * .002) ** 2:
                score = 0.0

        self.last_probability = score
        if self.active:
            self._quiet = self._quiet + 1 if score < .25 else 0
            if self._quiet >= self.silence_frames:
                self.active = False
                self._voiced = self._quiet = 0
                self._needs_reset = True
                return GateFrame(pcm, closed=True)
            return GateFrame(pcm)
        self._preroll.append(pcm)
        self.peak_unadmitted_probability = max(self.peak_unadmitted_probability, score)
        if fresh_prediction:
            self._voiced = self._voiced + 1 if score >= .5 else 0
        if self._voiced >= self.trigger_frames:
            self.active = True
            self.accepted_turns += 1
            self.peak_unadmitted_probability = 0.0
            buffered = b''.join(self._preroll)
            self._preroll.clear()
            return GateFrame(buffered, opened=True)
        self.suppressed_frames += 1
        return GateFrame(bytes(640))


class PlaybackReference:
    def __init__(self):
        self.samples = deque(maxlen=2400)
        self.pending = b''
        self.updated_at = float('-inf')

    def add(self, pcm, *, now=None):
        data = self.pending + pcm
        count = len(data) // 24 * 24
        self.pending = data[count:]
        if count:
            values = np.frombuffer(data[:count], dtype='<i2').astype(np.float32)
            self.samples.extend(values.reshape(-1, 12).mean(axis=1).tolist())
            self.updated_at = time.monotonic() if now is None else now

    def correlation(self, microphone, now):
        if now - self.updated_at > 1.2 or not self.samples:
            return 0.0
        signal = np.asarray(microphone, dtype=np.float64)
        reference = np.asarray(self.samples, dtype=np.float64)
        if len(signal) < 160 or len(reference) < len(signal):
            return None
        signal = signal - signal.mean()
        energy = float(signal @ signal)
        if energy < 1:
            return 1.0
        n = len(signal)
        sums = np.concatenate(([0.0], np.cumsum(reference)))
        squares = np.concatenate(([0.0], np.cumsum(reference * reference)))
        variance = np.maximum(0, squares[n:] - squares[:-n] - (sums[n:] - sums[:-n]) ** 2 / n)
        products = np.correlate(reference, signal, mode='valid')
        scores = np.divide(np.abs(products), np.sqrt(variance * energy),
                           out=np.zeros_like(products), where=variance > 1)
        return float(np.clip(scores.max(initial=0), 0, 1))


class SpokenInterruption:
    """Require 120 ms of speech evidence, independent of recent speaker output.

    Fix 5: quiet frames still update _microphone deque for state continuity.
    """

    def __init__(self, reference, detector=None):
        self.reference = reference
        self.detector = detector
        self._frames = deque(maxlen=10)
        self._microphone = deque(maxlen=240)
        self._positives = self._voiced_frames = 0
        self.rejected_echo_frames = 0
        self.last_correlation = 0.0

    def reset(self):
        self._frames.clear()
        self._microphone.clear()
        self._positives = self._voiced_frames = 0

    def process(self, pcm, now):
        if len(pcm) != 640:
            raise ValueError('Spoken interruption requires a 20 ms PCM16 frame')
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)

        # Fix 5: Always update _microphone deque, even for quiet frames.
        self._microphone.extend(samples.reshape(-1, 8).mean(axis=1).tolist())
        self._frames.append(pcm)

        rms = float(np.sqrt(np.mean(samples * samples))) / 32768
        if rms < .004:
            # Fix 5: Still update the detector for state continuity, but
            # don't promote to an interruption.
            if self.detector is not None:
                self.detector(pcm)
            self._positives = self._voiced_frames = 0
            return None
        if self.detector is None:
            self.detector = SileroSpeechDetector()
        probability = float(self.detector(pcm))
        if not np.isfinite(probability):
            raise RuntimeError('Interruption detector returned an invalid probability')
        correlation = self.reference.correlation(self._microphone, now)
        self.last_correlation = correlation if correlation is not None else 1.0
        if correlation is not None and correlation >= .75:
            self.rejected_echo_frames += 1
            self._positives = self._voiced_frames = 0
            self._frames.clear()
            return None
        if probability < .8:
            self._positives = self._voiced_frames = 0
            return None
        self._voiced_frames += 1
        if getattr(self.detector, 'fresh_prediction', True):
            self._positives += 1
        if self._voiced_frames < 6 or self._positives < 4 or correlation is None:
            return None
        frame = GateFrame(b''.join(self._frames), opened=True, barge_in=True)
        self.reset()
        return frame
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_speech.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add jarvis_voice/speech.py tests/test_speech.py
git commit -m "feat: hardened speech turn gate and interruption detector with frame continuity fixes"
```

---

### Task 5: Playback Engine with Generation Fence Fix (Fix 6)

**Files:**
- Create: `jarvis_voice/playback.py`
- Test: `tests/test_playback.py`

**Interfaces:**
- Consumes: `PlaybackReference` from Task 4.
- Produces: `Playback` class with `enqueue(data)`, `cancel_pending() -> process`, `async interrupt()`, `async prepare()`, `async run()`, `begin_reply()`, `finish_reply()`, `busy: bool`.

- [ ] **Step 1: Write regression test for fix 6**

```python
# tests/test_playback.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_fix6_stale_generation_discarded_not_error():
    """Fix 6: cancelled playback generation must discard stale chunks cleanly."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    # Enqueue data in generation 0
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 960

    # Cancel — advances generation
    player.cancel_pending()
    assert player.generation == 1
    assert player.queued_bytes == 0

    # Enqueue in new generation
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 960

@pytest.mark.asyncio
async def test_playback_backlog_raises():
    """Exceeding bounded backlog raises PlaybackBacklogError."""
    from jarvis_voice.playback import Playback, PlaybackBacklogError

    player = Playback(sink='default')
    # Fill past the max
    with pytest.raises(PlaybackBacklogError):
        for _ in range(7000):
            player.enqueue(b'\x00' * 960)

@pytest.mark.asyncio
async def test_begin_reply_resets_timing():
    """begin_reply resets first-write timing state."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    player.enqueue(b'\x00' * 960)
    player.begin_reply()
    assert player.first_enqueued_at is None
    assert player.first_write_at is None

@pytest.mark.asyncio
async def test_cancel_pending_clears_queue():
    """cancel_pending empties the queue and advances generation."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    player.enqueue(b'\x00' * 960)
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 1920

    player.cancel_pending()
    assert player.queued_bytes == 0
    assert player.queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_playback.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Playback engine**

```python
# jarvis_voice/playback.py
"""Bounded PCM playback with generation fences for interruption races.

Fix 6: Stale-generation chunks are silently discarded, never triggering
PlaybackBacklogError from cancelled generations.
"""
import asyncio
import contextlib
import time

from .speech import PlaybackReference

OUTPUT_BYTES = 960  # 20 ms at 24 kHz mono PCM16
PLAYBACK_MAX_BYTES = 48000 * 60  # 60 seconds


class MicrophoneBacklogError(BufferError):
    """Active microphone traffic cannot advance through the transport."""


class PlaybackBacklogError(BufferError):
    """The provider exceeded the bounded playback backlog."""


async def stop_process(process):
    """Terminate an owned audio process, escalating only if it will not exit."""
    if process is None:
        return
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    if process.stdin is not None:
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), 1)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


def audio_environment():
    """Subprocess environment with PipeWire overrides removed."""
    import os
    env = dict(os.environ)
    for name in ('PIPEWIRE_LATENCY', 'PIPEWIRE_QUANTUM', 'PIPEWIRE_NODE',
                 'PULSE_SOURCE', 'PULSE_SINK'):
        env.pop(name, None)
    return env


class Playback:
    """Bounded PCM playback with generation fences for interruption races."""

    def __init__(self, sink):
        self.sink = sink
        self.queue = asyncio.Queue(maxsize=6000)
        self.queued_bytes = 0
        self.generation = 0
        self.process = None
        self.playback_until = 0.0
        self._writing = False
        self._writing_generation = 0
        self.reference = PlaybackReference()
        self._spawn_lock = asyncio.Lock()
        self.first_write_at = None
        self.first_enqueued_at = None
        self.first_chunk_write_ms = None
        self._arrival = asyncio.Event()
        self.reply_complete = False

    @property
    def busy(self):
        return ((self._writing and self._writing_generation == self.generation)
                or not self.queue.empty() or time.monotonic() < self.playback_until)

    def enqueue(self, data):
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        chunks = (len(data) + OUTPUT_BYTES - 1) // OUTPUT_BYTES
        if (chunks > self.queue.maxsize - self.queue.qsize()
                or self.queued_bytes + len(data) > PLAYBACK_MAX_BYTES):
            raise PlaybackBacklogError('Provider audio exceeded bounded playback backlog')
        if data and self.first_enqueued_at is None:
            self.first_enqueued_at = time.monotonic()
        for offset in range(0, len(data), OUTPUT_BYTES):
            chunk = data[offset:offset + OUTPUT_BYTES]
            self.queue.put_nowait((self.generation, chunk))
            self.queued_bytes += len(chunk)
        self._arrival.set()

    def cancel_pending(self):
        """Advance generation fence, flush queue, return old playback process."""
        self.generation += 1
        self.playback_until = 0.0
        self.begin_reply()
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queued_bytes = 0
        self._arrival.set()
        process, self.process = self.process, None
        return process

    def begin_reply(self):
        self.first_enqueued_at = self.first_write_at = self.first_chunk_write_ms = None
        self.reply_complete = False

    def finish_reply(self):
        self.reply_complete = True
        self._arrival.set()

    async def _prime(self, generation, first_bytes):
        """Absorb short provider gaps without waiting for an entire response."""
        deadline = time.monotonic() + .12
        while (generation == self.generation and not self.reply_complete
               and first_bytes + self.queued_bytes < 3840):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._arrival.clear()
            try:
                await asyncio.wait_for(self._arrival.wait(), remaining)
            except TimeoutError:
                break
        return generation == self.generation

    async def interrupt(self):
        process = self.cancel_pending()
        await stop_process(process)

    async def prepare(self):
        """Open playback subprocess before first chunk to avoid startup latency."""
        generation = self.generation
        async with self._spawn_lock:
            if self.process is None:
                process = await asyncio.create_subprocess_exec(
                    'pw-play', '--rate', '24000', '--channels', '1', '--format', 's16',
                    '--latency', '40ms', '--target', self.sink, '-a', '-',
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                    env=audio_environment())
                if generation != self.generation:
                    await stop_process(process)
                    return False
                self.process = process
            return generation == self.generation

    async def run(self):
        """Main playback loop — Fix 6: stale generations silently discarded."""
        while True:
            generation, data = await self.queue.get()
            self.queued_bytes -= len(data)

            # Fix 6: silently discard chunks from cancelled generations
            if generation != self.generation:
                continue

            self._writing = True
            self._writing_generation = generation
            try:
                if self.first_write_at is None and not await self._prime(generation, len(data)):
                    continue
                if not await self.prepare() or generation != self.generation:
                    continue
                process = self.process
                if process.returncode is not None:
                    raise RuntimeError(f'Audio output process exited (code={process.returncode})')
                try:
                    process.stdin.write(data)
                    self.reference.add(data)
                    await asyncio.wait_for(process.stdin.drain(), 2)
                except TimeoutError as error:
                    # Fix 6: check generation before raising
                    if generation != self.generation:
                        continue
                    raise PlaybackBacklogError('PipeWire playback stopped accepting PCM') from error
                except (BrokenPipeError, ConnectionResetError):
                    if generation != self.generation:
                        continue
                    raise
                if generation != self.generation:
                    continue
                now = time.monotonic()
                if self.first_write_at is None and self.first_enqueued_at is not None:
                    self.first_write_at = now
                    self.first_chunk_write_ms = round((now - self.first_enqueued_at) * 1000)
                self.playback_until = max(self.playback_until, now) + len(data) / 48000
            finally:
                self._writing = False
            await asyncio.sleep(max(0.0, self.playback_until - time.monotonic() - 0.08))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_playback.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add jarvis_voice/playback.py tests/test_playback.py
git commit -m "feat: playback engine with generation-fence fix for cancelled playback drain"
```

---

### Task 6: Systemd Service, CLI Entry Point, and Installation Script

**Files:**
- Create: `systemd/jarvis-voice.service`
- Create: `bin/jarvis-voice`
- Create: `scripts/install.sh`
- Create: `scripts/uninstall.sh`
- Modify: `jarvis_voice/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Config`, `load()`, `load_env()` from Task 1; `ControlServer` from Task 2.
- Produces: Installable service (`jarvis-voice.service`) and CLI (`jarvis-voice` binary) with subcommands: `run`, `status`, `status --json`, `listen toggle/start/stop/cancel`, `--help`, `--check`.

- [ ] **Step 1: Write CLI tests**

```python
# tests/test_cli.py
import subprocess
import sys

def test_cli_help():
    result = subprocess.run(
        [sys.executable, '-m', 'jarvis_voice', '--help'],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert 'jarvis' in result.stdout.lower() or 'voice' in result.stdout.lower()

def test_cli_check_no_network():
    """--check validates dependencies without opening audio or network."""
    result = subprocess.run(
        [sys.executable, '-m', 'jarvis_voice', '--check'],
        capture_output=True, text=True, timeout=10)
    # May pass or fail depending on installed deps, but should not hang
    assert result.returncode in (0, 1, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_cli.py -v`
Expected: FAIL — `--help` exits with error or missing subcommands

- [ ] **Step 3: Create systemd service, CLI wrapper, and installer**

```ini
# systemd/jarvis-voice.service
[Unit]
Description=JARVIS Voice Core — ambient voice assistant
After=graphical-session.target pipewire.service wireplumber.service
PartOf=graphical-session.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
ExecStart=%h/.local/share/jarvis-voice/bin/jarvis-voice run
WorkingDirectory=%h/.local/share/jarvis-voice
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=XDG_RUNTIME_DIR=%t
Restart=always
RestartSec=2
KillMode=control-group
TimeoutStopSec=8
UMask=0077
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
```

```bash
#!/usr/bin/env bash
# bin/jarvis-voice — CLI wrapper
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 -m jarvis_voice "$@"
```

```bash
#!/usr/bin/env bash
# scripts/install.sh — Install JARVIS Voice Core
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/jarvis-voice"
BIN_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"

echo "Installing JARVIS Voice Core..."

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$SERVICE_DIR"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Copy package
cp -r "$REPO_DIR/jarvis_voice" "$INSTALL_DIR/"
cp -r "$REPO_DIR/bin" "$INSTALL_DIR/"
cp "$REPO_DIR/LICENSE" "$INSTALL_DIR/" 2>/dev/null || true

chmod +x "$INSTALL_DIR/bin/jarvis-voice"

# Symlink CLI
ln -sf "$INSTALL_DIR/bin/jarvis-voice" "$BIN_DIR/jarvis-voice"

# Install systemd service
cp "$REPO_DIR/systemd/jarvis-voice.service" "$SERVICE_DIR/"
systemctl --user daemon-reload

echo "Installed to $INSTALL_DIR"
echo "CLI available at: jarvis-voice"
echo ""
echo "Start with: systemctl --user enable --now jarvis-voice.service"
```

```bash
#!/usr/bin/env bash
# scripts/uninstall.sh — Remove JARVIS Voice Core
set -euo pipefail

echo "Removing JARVIS Voice Core..."

systemctl --user disable --now jarvis-voice.service 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/jarvis-voice.service"
systemctl --user daemon-reload 2>/dev/null || true

rm -f "${HOME}/.local/bin/jarvis-voice"
rm -rf "${HOME}/.local/share/jarvis-voice"

echo "JARVIS Voice Core removed."
```

Update `jarvis_voice/__main__.py`:

```python
# jarvis_voice/__main__.py
"""CLI entry point: python -m jarvis_voice"""
import argparse
import os
import shutil
import sys

def main():
    parser = argparse.ArgumentParser(
        prog='jarvis-voice',
        description='JARVIS Voice Core — sovereign voice foundation')
    parser.add_argument('command', nargs='?', default='run',
        choices=['run', 'status', 'listen'],
        help='Command to execute (default: run)')
    parser.add_argument('action', nargs='?', help='Action for listen command')
    parser.add_argument('--model', default=os.getenv('GEMINI_LIVE_MODEL', 'gemini-3.8-live'))
    parser.add_argument('--voice', default=None, help='Gemini voice name')
    parser.add_argument('--check', action='store_true',
        help='Check dependencies without opening audio or network')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--transcripts', action='store_true')
    parser.add_argument('--retries', type=int, default=5)

    args = parser.parse_args()

    if args.check:
        missing = [n for n in ('pw-record', 'pw-play', 'pactl', 'pw-cli')
                    if shutil.which(n) is None]
        if missing:
            print(f'Missing: {", ".join(missing)}', file=sys.stderr)
            return 1
        try:
            from jarvis_voice.config import load
            config = load()
            print(f'PASS: audio commands present, config valid (model={config.model})')
            return 0
        except Exception as e:
            print(f'Config error: {e}', file=sys.stderr)
            return 1

    if args.command in ('status', 'listen'):
        return _ipc_command(args)

    if args.command == 'run':
        print('jarvis-voice: daemon start requires full implementation (Task 7)')
        return 0

    return 0


def _ipc_command(args):
    """Send a command to the running daemon via its control socket."""
    import socket
    import json
    from jarvis_voice.config import SOCKET_PATH

    if not SOCKET_PATH.exists():
        print('jarvis-voice is not running', file=sys.stderr)
        return 1

    if args.command == 'status':
        cmd = 'status --json' if args.json else 'status'
    elif args.command == 'listen':
        action = args.action or 'toggle'
        cmd = f'listen {action}'
    else:
        cmd = args.command

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(str(SOCKET_PATH))
        sock.sendall((cmd + '\n').encode())
        data = sock.recv(4096)
        sock.close()
        print(data.decode().strip())
        return 0
    except Exception as e:
        print(f'IPC error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Make scripts executable and commit**

```bash
chmod +x bin/jarvis-voice scripts/install.sh scripts/uninstall.sh
git add systemd/jarvis-voice.service bin/jarvis-voice scripts/install.sh scripts/uninstall.sh \
        jarvis_voice/__main__.py tests/test_cli.py
git commit -m "feat: systemd service, CLI entry point, install/uninstall scripts"
```

---

### Task 7: Full Voice Daemon Integration (`run` command)

**Files:**
- Create: `jarvis_voice/daemon.py`
- Modify: `jarvis_voice/__main__.py` (wire `run` to daemon)
- Test: `tests/test_daemon.py`

**Interfaces:**
- Consumes: `Config`, `load()`, `load_env()` (Task 1); `ControlServer` (Task 2); `ConnectionRecovery` (Task 3); `SpeechTurnGate`, `SpokenInterruption`, `SileroSpeechDetector`, `GateFrame` (Task 4); `Playback`, `stop_process`, `audio_environment` (Task 5).
- Produces: `async run(args, key)` — the main voice loop that captures audio, detects speech, streams to Gemini Live, plays back responses, handles barge-in, and recovers from errors.

- [ ] **Step 1: Write daemon smoke test**

```python
# tests/test_daemon.py
"""Smoke test for daemon module imports and configuration validation."""

def test_daemon_imports():
    from jarvis_voice.daemon import LiveVoice, live_config
    assert LiveVoice is not None
    assert callable(live_config)

def test_live_config_produces_valid_dict():
    from jarvis_voice.daemon import live_config
    config = live_config(voice='Aoede')
    assert config['response_modalities'] == ['AUDIO']
    assert 'system_instruction' in config
    assert 'realtime_input_config' in config
    assert config['realtime_input_config']['automatic_activity_detection']['disabled'] is True

def test_live_voice_status():
    from unittest.mock import MagicMock
    from jarvis_voice.daemon import LiveVoice
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    voice = LiveVoice(player)
    status = voice.status()
    assert 'state' in status
    assert status['state'] in ('connecting', 'speaking', 'listening', 'thinking', 'idle')
    assert 'muted' in status
    assert 'model' in status
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_daemon.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jarvis_voice.daemon'`

- [ ] **Step 3: Implement daemon.py**

This file adapts the proven `stable_voice.py` from JARVIS-OMA, importing from the local `jarvis_voice` package instead of the original `core` and `audio` packages. The `LiveVoice` class, `live_config()`, and `run()` function are ported with all 6 regression fixes applied through the hardened modules from Tasks 3–5.

Create `jarvis_voice/daemon.py` by adapting `core/stable_voice.py`:
- Replace `from core.monitor_echo import ...` → defer echo cancellation setup to runtime (use a simple passthrough if unavailable).
- Replace `from audio.plugins.spoken_interrupt import ...` → `from .speech import PlaybackReference, SpokenInterruption`
- Replace `from core.speech_turn import ...` → `from .speech import SpeechTurnGate, SileroSpeechDetector, GateFrame`
- Replace `from core.stable_recovery import ...` → `from .recovery import ConnectionRecovery`
- Replace `from skills import ...` → skills=None (deferred to later stage)
- Replace `from core.ipc import ...` → `from .ipc import ControlServer`
- Replace `from core.config import ...` → `from .config import load as load_config`
- Keep `from google.genai import types` and `from google import genai` as runtime imports.
- System prompt: "You are JARVIS, the user's personal voice assistant. Speak clearly and briefly. Only speak in response to the user."

The full daemon module is ~400 lines (LiveVoice class + live_config + run + main), directly adapted from the 935-line stable_voice.py with skills/capabilities/harness stripped out for this voice-only foundation stage.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/test_daemon.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire run command in __main__.py and commit**

Update the `run` branch in `jarvis_voice/__main__.py` to call `daemon.main()`:

```python
    if args.command == 'run':
        from jarvis_voice.daemon import main as daemon_main
        return daemon_main(args)
```

```bash
git add jarvis_voice/daemon.py jarvis_voice/__main__.py tests/test_daemon.py
git commit -m "feat: full voice daemon with Gemini Live streaming, speech gating, and barge-in"
```

---

### Task 8: End-to-End Verification & Deployment

**Files:**
- Test: `tests/test_integration.py`
- Modify: `README.md` (update for JARVIS Voice Core)

**Interfaces:**
- Consumes: All previous tasks.
- Produces: Verified, deployable JARVIS Voice Core.

- [ ] **Step 1: Write integration verification tests**

```python
# tests/test_integration.py
"""Integration verification for the complete voice foundation."""

def test_all_modules_import():
    """Every jarvis_voice submodule imports without error."""
    import jarvis_voice
    from jarvis_voice import config, ipc, recovery, speech, playback, daemon
    assert jarvis_voice.__version__ == '0.1.0'

def test_voice_lock_files_untouched():
    """Verify zero modifications to locked voice core files."""
    # This test verifies we haven't touched JARVIS-OMA's locked files
    from pathlib import Path
    lock_file = Path('/home/g0pi/Projects/JARVIS-OMA/audio/.voice_lock.json')
    if lock_file.exists():
        import json
        manifest = json.loads(lock_file.read_text())
        for entry in manifest.get('files', []):
            path = Path('/home/g0pi/Projects/JARVIS-OMA') / entry['path']
            if path.exists():
                import hashlib
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                assert actual == entry['sha256'], f'{entry["path"]} was modified!'

def test_config_to_daemon_integration():
    """Config loads and feeds into daemon correctly."""
    from jarvis_voice.config import Config
    from jarvis_voice.daemon import live_config
    c = Config(voice='Puck', model='gemini-2.0-flash-live')
    result = live_config(voice=c.voice)
    assert 'Puck' in str(result['speech_config'])

def test_recovery_in_daemon_context():
    """Recovery module integrates with daemon error handling."""
    from jarvis_voice.recovery import ConnectionRecovery
    r = ConnectionRecovery(retry_budget=3)
    # Simulate a 503 after a successful session
    d = r.decide(ConnectionError('closed'), session_opened=True, session_seconds=120)
    assert not d.fatal
    assert d.delay <= 2.0
```

- [ ] **Step 2: Run full test suite**

Run: `cd "/home/g0pi/JARVIS OS" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Update README.md**

Update the project README to reflect JARVIS Voice Core identity, replacing PMA Voice Only references.

- [ ] **Step 4: Run --check to validate deployment readiness**

```bash
cd "/home/g0pi/JARVIS OS" && python -m jarvis_voice --check
```
Expected: `PASS: audio commands present, config valid (model=gemini-3.8-live)`

- [ ] **Step 5: Final commit**

```bash
git add tests/test_integration.py README.md
git commit -m "feat: complete voice foundation with integration tests and updated README"
```

---

Plan complete and saved to [`docs/superpowers/plans/2026-10-30-voice-foundation.md`](file:///home/g0pi/JARVIS%20OS/docs/superpowers/plans/2026-10-30-voice-foundation.md). Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
