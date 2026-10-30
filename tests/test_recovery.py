# tests/test_recovery.py
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
