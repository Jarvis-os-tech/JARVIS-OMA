"""Dependency-free safety and trigger policy for proactive actions.

The policy is deliberately conservative: unknown effects require approval.
Callers should provide an action effect from this module's vocabulary rather
than relying on natural-language intent to grant permission.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Deque, Dict, Optional


class ActionEffect(str, Enum):
    READ_ONLY = "read_only"
    LOCAL_REVERSIBLE = "local_reversible"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


class AutonomyLevel(int, Enum):
    """System-wide autonomy tiers (L0 to L5).

    L0 - Manual: Zero autonomous action execution; user must initiate every action.
    L1 - Assisted: Suggestions and drafting only; all actions require human approval.
    L2 - Partial (Read-Only): Autonomous execution of read-only observation/inspection.
    L3 - Conditional (Default): Autonomous read-only and local reversible operations.
    L4 - High: Autonomous execution of local and safe external actions; destructive requires approval.
    L5 - Full: Complete autonomy for all action types without human gating.
    """

    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4
    L5 = 5

    # Semantic aliases
    MANUAL = 0
    ASSISTED = 1
    READ_ONLY = 2
    CONDITIONAL = 3
    HIGH = 4
    FULL = 5


class DecisionStatus(str, Enum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"
    DUPLICATE = "duplicate"
    COOLDOWN = "cooldown"
    RATE_LIMITED = "rate_limited"
    PAUSED = "paused"
    QUIET_HOURS = "quiet_hours"


@dataclass(frozen=True)
class Action:
    """An intended action and its declared effect.

    External side effects and destructive changes require explicit approval.
    ``UNKNOWN`` also requires approval; omissions must never grant autonomy.
    """

    name: str
    effect: ActionEffect = ActionEffect.UNKNOWN


@dataclass(frozen=True)
class PolicyDecision:
    status: DecisionStatus
    allowed: bool
    requires_approval: bool
    reason: str
    trigger_id: str


@dataclass(frozen=True)
class PolicyLimits:
    dedupe_window: float = 300.0
    cooldown: float = 30.0
    rate_limit_count: int = 20
    rate_limit_window: float = 60.0

    def __post_init__(self) -> None:
        for name in ('dedupe_window', 'cooldown', 'rate_limit_window'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f'{name} must be a number')
            if not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
        if self.dedupe_window < 0 or self.cooldown < 0:
            raise ValueError("dedupe_window and cooldown must be non-negative")
        if self.rate_limit_window <= 0:
            raise ValueError("rate_limit_window must be positive")
        if isinstance(self.rate_limit_count, bool) or not isinstance(self.rate_limit_count, int):
            raise TypeError('rate_limit_count must be an integer')
        if self.rate_limit_count < 1:
            raise ValueError("rate_limit_count must be at least 1")


class ProactivePolicy:
    """In-memory policy gate with deduplication, cooldown and rate limiting.

    Supply a monotonic timestamp to :meth:`evaluate` for deterministic tests
    and integration with the host scheduler. State is process-local by design.
    """

    _AUTONOMOUS_EFFECTS = frozenset(
        {ActionEffect.READ_ONLY, ActionEffect.LOCAL_REVERSIBLE}
    )

    def __init__(self, limits: Optional[PolicyLimits] = None) -> None:
        self.limits = limits or PolicyLimits()
        self._paused = False
        self._seen: Dict[str, float] = {}
        self._last_by_trigger: Dict[str, float] = {}
        self._accepted: Deque[float] = deque()

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """Stop all proactive execution until explicitly resumed."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def classify(self, action: Action) -> bool:
        """Return true only for known safe autonomous effect classes."""
        return action.effect in self._AUTONOMOUS_EFFECTS

    def evaluate(self, trigger_id: str, action: Action, now: float, *, approved: bool = False) -> PolicyDecision:
        """Evaluate a trigger, optionally with explicit approval from a trusted caller.

        Approval covers this action only. In particular approval to delegate does
        not approve arbitrary downstream actions or reclassify their effects.
        """
        if not isinstance(trigger_id, str) or not trigger_id.strip():
            raise ValueError("trigger_id must be a non-empty string")
        if not isinstance(action, Action):
            raise TypeError("action must be an Action")
        if type(approved) is not bool:
            raise TypeError("approved must be a boolean from the trusted caller")
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("now must be a monotonic number")
        timestamp = float(now)
        if not math.isfinite(timestamp):
            raise ValueError('now must be finite')

        if self._paused:
            return self._decision(DecisionStatus.PAUSED, trigger_id, "global pause is active")

        self._expire(timestamp)
        if trigger_id in self._seen:
            return self._decision(DecisionStatus.DUPLICATE, trigger_id, "trigger already handled in dedupe window")

        previous = self._last_by_trigger.get(trigger_id)
        if previous is not None and timestamp - previous < self.limits.cooldown:
            return self._decision(DecisionStatus.COOLDOWN, trigger_id, "trigger is within its cooldown")

        self._trim_rate_window(timestamp)
        if len(self._accepted) >= self.limits.rate_limit_count:
            return self._decision(DecisionStatus.RATE_LIMITED, trigger_id, "proactive action rate limit reached")

        safe = self.classify(action)
        if not safe and not approved:
            return self._decision(
                DecisionStatus.APPROVAL_REQUIRED,
                trigger_id,
                f"{action.effect.value} actions require explicit approval",
                requires_approval=True,
            )

        self._seen[trigger_id] = timestamp
        self._last_by_trigger[trigger_id] = timestamp
        self._accepted.append(timestamp)
        return PolicyDecision(
            DecisionStatus.ALLOWED, True, False,
            "explicitly approved action" if approved else "safe action allowed by policy", trigger_id
        )

    def _expire(self, now: float) -> None:
        dedupe_cutoff = now - self.limits.dedupe_window
        self._seen = {key: value for key, value in self._seen.items() if value > dedupe_cutoff}
        cooldown_cutoff = now - self.limits.cooldown
        self._last_by_trigger = {
            key: value for key, value in self._last_by_trigger.items() if value > cooldown_cutoff
        }
        self._trim_rate_window(now)

    def _trim_rate_window(self, now: float) -> None:
        cutoff = now - self.limits.rate_limit_window
        while self._accepted and self._accepted[0] <= cutoff:
            self._accepted.popleft()

    @staticmethod
    def _decision(
        status: DecisionStatus,
        trigger_id: str,
        reason: str,
        requires_approval: bool = False,
    ) -> PolicyDecision:
        return PolicyDecision(status, False, requires_approval, reason, trigger_id)


class PolicyEngine(ProactivePolicy):
    """Autonomy policy and quiet hours engine supporting L0-L5 autonomy levels.

    Combines progressive autonomy tiers with time-based quiet hours enforcement,
    per-trigger deduplication, cooldowns, and rate limiting.
    """

    _LEVEL_EFFECTS: dict[AutonomyLevel, frozenset[ActionEffect]] = {
        AutonomyLevel.L0: frozenset(),
        AutonomyLevel.L1: frozenset(),
        AutonomyLevel.L2: frozenset({ActionEffect.READ_ONLY}),
        AutonomyLevel.L3: frozenset({ActionEffect.READ_ONLY, ActionEffect.LOCAL_REVERSIBLE}),
        AutonomyLevel.L4: frozenset({
            ActionEffect.READ_ONLY,
            ActionEffect.LOCAL_REVERSIBLE,
            ActionEffect.EXTERNAL,
        }),
        AutonomyLevel.L5: frozenset({
            ActionEffect.READ_ONLY,
            ActionEffect.LOCAL_REVERSIBLE,
            ActionEffect.EXTERNAL,
            ActionEffect.DESTRUCTIVE,
            ActionEffect.UNKNOWN,
        }),
    }

    def __init__(
        self,
        limits: Optional[PolicyLimits] = None,
        *,
        autonomy_level: AutonomyLevel | int = AutonomyLevel.L3,
        quiet_hours_enabled: bool = False,
        quiet_hours_start: int = 22,
        quiet_hours_end: int = 7,
    ) -> None:
        super().__init__(limits)
        self.autonomy_level = AutonomyLevel(autonomy_level)
        self.quiet_hours_enabled = quiet_hours_enabled
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end

    def set_autonomy_level(self, level: AutonomyLevel | int) -> None:
        """Set active autonomy level from L0 (Manual) to L5 (Full)."""
        self.autonomy_level = AutonomyLevel(level)

    def in_quiet_hours(self, dt: datetime | None = None) -> bool:
        """Return True if the current or provided datetime falls inside quiet hours."""
        if not self.quiet_hours_enabled:
            return False
        current_time = dt or datetime.now()
        hour = current_time.hour
        if self.quiet_hours_start > self.quiet_hours_end:
            # Crosses midnight (e.g. 22:00 to 07:00)
            return hour >= self.quiet_hours_start or hour < self.quiet_hours_end
        else:
            return self.quiet_hours_start <= hour < self.quiet_hours_end

    def classify(self, action: Action) -> bool:
        """Classify if action effect is allowed autonomously under current autonomy level."""
        allowed_effects = self._LEVEL_EFFECTS.get(self.autonomy_level, self._AUTONOMOUS_EFFECTS)
        return action.effect in allowed_effects

    def evaluate(
        self,
        trigger_id: str,
        action: Action,
        now: float,
        *,
        approved: bool = False,
        dt: datetime | None = None,
    ) -> PolicyDecision:
        """Evaluate action considering global pause, quiet hours, limits, and autonomy level."""
        if self._paused:
            return self._decision(DecisionStatus.PAUSED, trigger_id, "global pause is active")

        if self.in_quiet_hours(dt):
            return self._decision(
                DecisionStatus.QUIET_HOURS,
                trigger_id,
                f"quiet hours active ({self.quiet_hours_start:02d}:00-{self.quiet_hours_end:02d}:00)",
            )

        return super().evaluate(trigger_id, action, now, approved=approved)


