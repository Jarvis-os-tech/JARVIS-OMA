from core.stable_recovery import ConnectionRecovery


class CodedError(Exception):
    def __init__(self, code=None, status_code=None):
        # Deliberately keep message contents irrelevant to recovery decisions.
        super().__init__("private details")
        self.code = code
        self.status_code = status_code


def test_resume_rejection_starts_fresh_session_immediately():
    recovery = ConnectionRecovery()

    decision = recovery.decide(CodedError(code=400), attempted_resume=True)

    assert (decision.delay, decision.fresh_session, decision.fatal, decision.code) == (0, True, False, 400)


def test_two_transient_resume_failures_start_fresh_session():
    recovery = ConnectionRecovery()

    first = recovery.decide(TimeoutError("ignored"), attempted_resume=True)
    second = recovery.decide(TimeoutError("ignored"), attempted_resume=True)

    assert first.fresh_session is False
    assert first.fatal is False
    assert second.fresh_session is True
    assert second.fatal is False


def test_transient_errors_retry_past_budget_with_capped_delay():
    recovery = ConnectionRecovery(retry_budget=1)

    decisions = [recovery.decide(CodedError(status_code=503)) for _ in range(8)]

    assert all(not decision.fatal for decision in decisions)
    assert all(decision.delay <= 30 for decision in decisions)
    assert decisions[-1].delay == 30


def test_rate_limit_wait_is_at_least_sixty_seconds():
    decision = ConnectionRecovery().decide(CodedError(status_code=429))

    assert decision.delay >= 60
    assert decision.fatal is False


def test_auth_configuration_codes_are_fatal_without_resume_recovery():
    for code in (400, 401, 403, 404):
        decision = ConnectionRecovery().decide(CodedError(code=code))
        assert decision.fatal is True
        assert decision.fresh_session is False


def test_unexpected_error_becomes_fatal_after_budget():
    recovery = ConnectionRecovery(retry_budget=2)

    assert recovery.decide(ValueError("ignored")).fatal is False
    assert recovery.decide(ValueError("ignored")).fatal is False
    assert recovery.decide(ValueError("ignored")).fatal is True


def test_stable_open_session_resets_general_failure_count():
    recovery = ConnectionRecovery(retry_budget=1)
    recovery.decide(ValueError("ignored"))
    recovery.decide(ValueError("ignored"))

    decision = recovery.decide(ValueError("ignored"), session_opened=True, session_seconds=60)

    assert decision.fatal is False
    assert decision.delay == 1


def test_error_code_must_be_an_integer_and_message_is_not_returned():
    error = CodedError(code="503")

    decision = ConnectionRecovery().decide(error)

    assert decision.code is None
    assert not hasattr(decision, "message")
