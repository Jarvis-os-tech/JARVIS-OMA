"""Small, conservative rules for occasional listening backchannels."""
import re


_REJECT = re.compile(
    r"\b(?:can you|could you|would you|please|"
    r"tell me|show me|find|search|open|set|turn|change|don't|dont|do not|not|never|avoid)\b",
    re.IGNORECASE,
)


class InteractionPolicy:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._played_turn = None
        self._last_at = float('-inf')

    def candidate(self, turn_id, transcript, started_at, now, quiet_seconds,
                  remaining_seconds, *, allowed=True):
        """Return a quiet backchannel candidate for a long narrative, or None."""
        text = str(transcript or '').strip()
        if (not self.enabled or not allowed or turn_id is None or not text or '?' in text
                or now - started_at < 8 or quiet_seconds < .4 or remaining_seconds <= 0
                or turn_id == self._played_turn or now - self._last_at < 20
                or re.match(r'^(?:what|why|when|where|who|how)\b', text, re.IGNORECASE)
                or _REJECT.search(text)
                # shortcut: first-person English narrative heuristic, upgrade with validated semantic turn data.
                or not re.match(r'^(?:I|we|my|our)\b', text, re.IGNORECASE)):
            return None
        return 'ack_short_hmm'

    def mark_played(self, turn_id, now):
        """Record only a backchannel that was successfully queued."""
        self._played_turn = turn_id
        self._last_at = now
