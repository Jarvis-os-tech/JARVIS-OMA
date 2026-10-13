"""In-memory job monitoring and retry scheduling for proactive workflows.

The monitor only records state and returns retry work that is due. Callers own
the event loop, persistence, and execution of jobs; this module never sleeps or
starts, stops, or signals a process.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


ACTIVE = frozenset({"running"})
TERMINAL = frozenset({"completed", "failed", "timed_out", "cancelled"})
RETRYABLE = frozenset({"failed", "timed_out"})


class MonitorError(ValueError):
    """Raised when a job transition or monitoring policy is invalid."""


def _number(value: Any, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MonitorError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise MonitorError(f"{name} must be finite and at least {minimum}")
    return result


class ProactiveMonitor:
    """Track jobs, detect expired deadlines, and expose bounded retry work.

    Times are caller-supplied monotonic seconds. Supplying ``now`` makes the
    monitor deterministic and lets a scheduler poll it without blocking.
    ``max_retries`` counts retries after the initial attempt.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def track(
        self,
        job_id: str,
        *,
        timeout_seconds: float,
        max_retries: int = 0,
        backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        now: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a running job and its first deadline."""
        if not isinstance(job_id, str) or not job_id.strip():
            raise MonitorError("job_id must be a non-empty string")
        if job_id in self._jobs:
            raise MonitorError(f"job {job_id!r} is already tracked")
        timeout = _number(timeout_seconds, "timeout_seconds", minimum=0.001)
        base_backoff = _number(backoff_seconds, "backoff_seconds")
        backoff_cap = _number(max_backoff_seconds, "max_backoff_seconds")
        timestamp = _number(now, "now")
        if base_backoff <= 0 or backoff_cap <= 0:
            raise MonitorError("backoff values must be greater than zero")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise MonitorError("max_retries must be a non-negative integer")
        if metadata is not None and not isinstance(metadata, dict):
            raise MonitorError("metadata must be a dictionary")
        job = {
            "id": job_id.strip(),
            "status": "running",
            "attempt": 1,
            "retry_count": 0,
            "max_retries": max_retries,
            "timeout_seconds": timeout,
            "backoff_seconds": base_backoff,
            "max_backoff_seconds": backoff_cap,
            "started_at": timestamp,
            "updated_at": timestamp,
            "deadline_at": timestamp + timeout,
            "retry_at": None,
            "detail": None,
            "metadata": deepcopy(metadata or {}),
        }
        self._jobs[job["id"]] = job
        return deepcopy(job)

    def update(
        self,
        job_id: str,
        status: str,
        *,
        now: float,
        detail: str | None = None,
    ) -> dict[str, Any]:
        """Record an execution result; failed jobs may enter retry_wait."""
        if status not in TERMINAL | ACTIVE:
            raise MonitorError(f"unsupported job status: {status!r}")
        job = self._get(job_id)
        timestamp = _number(now, "now")
        if job["status"] not in ACTIVE:
            raise MonitorError(f"job {job_id!r} is not running")
        if timestamp < job["updated_at"]:
            raise MonitorError("now cannot move backwards for a job")
        job["updated_at"] = timestamp
        job["detail"] = detail
        if status == "running":
            # A running update is a heartbeat and extends the deadline.
            job["deadline_at"] = timestamp + job["timeout_seconds"]
            return deepcopy(job)
        job["status"] = status
        job["deadline_at"] = None
        if status in RETRYABLE:
            self._schedule_retry(job, timestamp)
        return deepcopy(job)

    def poll(self, *, now: float) -> list[dict[str, Any]]:
        """Mark overdue running jobs timed out and return their new snapshots."""
        timestamp = _number(now, "now")
        changed = []
        for job in self._jobs.values():
            if job["status"] == "running" and timestamp >= job["deadline_at"]:
                job["status"] = "timed_out"
                job["updated_at"] = timestamp
                job["deadline_at"] = None
                job["detail"] = "Job exceeded its timeout."
                self._schedule_retry(job, timestamp)
                changed.append(deepcopy(job))
        return changed

    def due_retries(self, *, now: float) -> list[dict[str, Any]]:
        """Return retry_wait jobs whose backoff elapsed; does not claim them."""
        timestamp = _number(now, "now")
        return [deepcopy(job) for job in self._jobs.values()
                if job["status"] == "retry_wait" and job["retry_at"] <= timestamp]

    def start_retry(self, job_id: str, *, now: float) -> dict[str, Any]:
        """Claim a due retry and begin its next attempt without launching it."""
        job = self._get(job_id)
        timestamp = _number(now, "now")
        if job["status"] != "retry_wait":
            raise MonitorError(f"job {job_id!r} is not waiting for retry")
        if timestamp < job["retry_at"]:
            raise MonitorError(f"retry for job {job_id!r} is not due")
        job["attempt"] += 1
        job["status"] = "running"
        job["started_at"] = timestamp
        job["updated_at"] = timestamp
        job["deadline_at"] = timestamp + job["timeout_seconds"]
        job["retry_at"] = None
        job["detail"] = None
        return deepcopy(job)

    def get(self, job_id: str) -> dict[str, Any]:
        """Return a defensive copy of one job snapshot."""
        return deepcopy(self._get(job_id))

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return defensive copies of all tracked jobs in registration order."""
        return [deepcopy(job) for job in self._jobs.values()]

    def _schedule_retry(self, job: dict[str, Any], timestamp: float) -> None:
        if job["retry_count"] >= job["max_retries"]:
            job["retry_at"] = None
            return
        job["retry_count"] += 1
        delay = min(job["backoff_seconds"] * (2 ** (job["retry_count"] - 1)),
                    job["max_backoff_seconds"])
        job["status"] = "retry_wait"
        job["retry_at"] = timestamp + delay
        job["metadata"]["retry"] = {
            "count": job["retry_count"],
            "max_retries": job["max_retries"],
            "delay_seconds": delay,
            "scheduled_at": timestamp,
            "retry_at": job["retry_at"],
        }

    def _get(self, job_id: str) -> dict[str, Any]:
        try:
            return self._jobs[job_id]
        except (KeyError, TypeError):
            raise MonitorError(f"job {job_id!r} is not tracked") from None


# Short alias for callers that already establish the proactive namespace.
JobMonitor = ProactiveMonitor
