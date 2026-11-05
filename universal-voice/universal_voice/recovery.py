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
            delay = 2.0 if code == 1008 else 0.0
            return RecoveryDecision(delay, True, False, code)

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
