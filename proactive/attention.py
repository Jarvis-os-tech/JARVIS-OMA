"""Pure metadata policy for notices that respect the live conversation.

The caller owns the notice queue and supplies monotonic timestamps. The policy
stores only activity times and bounded caller-provided identifiers, never speech
or notification content. Admitting a notice does not authorize any other work.
"""
from __future__ import annotations

from collections import OrderedDict
import math


def _seconds(value, name):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0):
        raise ValueError(f'{name} must be a finite nonnegative number')
    return float(value)


class AttentionPolicy:
    """Apply a conversation quiet period, notice cooldown and bounded dedupe.

    ``admit`` is intended to run once before enqueueing. ``can_deliver`` must
    be checked again at the actual send boundary, using current session state.
    ``delivered`` records a successful send; failed attempts need not consume
    the cooldown. Repeated duplicate admissions do not prolong their window.
    """

    def __init__(self, *, quiet_seconds=2, cooldown_seconds=30,
                 dedupe_seconds=300, max_keys=128):
        self.quiet_seconds = _seconds(quiet_seconds, 'quiet_seconds')
        self.cooldown_seconds = _seconds(cooldown_seconds, 'cooldown_seconds')
        self.dedupe_seconds = _seconds(dedupe_seconds, 'dedupe_seconds')
        if type(max_keys) is not int or max_keys < 1:
            raise ValueError('max_keys must be a positive integer')
        self.max_keys = max_keys
        self._last_activity = None
        self._last_delivery = None
        self._keys = OrderedDict()

    def note_activity(self, now):
        now = _seconds(now, 'now')
        self._last_activity = (now if self._last_activity is None
                               else max(self._last_activity, now))

    def can_deliver(self, now, *, busy=False, muted=False, standby=False):
        now = _seconds(now, 'now')
        if busy or muted or standby:
            return False
        if (self._last_activity is not None
                and now - self._last_activity < self.quiet_seconds):
            return False
        if (self._last_delivery is not None
                and now - self._last_delivery < self.cooldown_seconds):
            return False
        return True

    def delivered(self, now):
        now = _seconds(now, 'now')
        self._last_delivery = (now if self._last_delivery is None
                               else max(self._last_delivery, now))

    def admit(self, key, now):
        """Deduplicate a caller identity; ``None`` requests no deduplication.

        Keys should identify an event revision or task outcome, rather than
        contain private message text. Once capacity is reached, the oldest
        admitted identity is evicted. This is intentionally process-local.
        """
        now = _seconds(now, 'now')
        if key is None:
            return True
        if (not isinstance(key, str) or not key.strip()
                or len(key.encode('utf-8')) > 512):
            raise ValueError('notice key must be a nonempty string of at most 512 bytes')
        for previous, admitted_at in tuple(self._keys.items()):
            if now - admitted_at >= self.dedupe_seconds:
                del self._keys[previous]
        if key in self._keys:
            return False
        if len(self._keys) >= self.max_keys:
            self._keys.popitem(last=False)
        self._keys[key] = now
        return True
