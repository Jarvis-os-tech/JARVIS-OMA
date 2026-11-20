"""Agent 1: Extractor & Gatekeeper Agent.
The Write Path airlock: sanitizes secrets, filters small talk, assigns importance,
tags provenance and TTL, and traps tool failures into episodic_traces.
"""

from hashlib import sha256
import re
import time
from typing import Any, Dict, List, Optional
import uuid

from .base_memory_agent import BaseMemoryAgent, MemoryCandidate

# Regex markers indicating direct user preference / memory instructions
EXPLICIT_PREFERENCE_TRIGGERS = [
    re.compile(r"\b(remember\s+that|remember\s+to|don't\s+forget|note\s+that)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+prefer|my\s+favorite|i\s+always|i\s+never)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+switched\s+to|my\s+system\s+is|my\s+os\s+is)\b", re.IGNORECASE),
    re.compile(r"\b(rule\s*:\s*|instruction\s*:\s*)\b", re.IGNORECASE),
]

# Ephemeral time markers indicating temporary status / reminders
EPHEMERAL_TRIGGERS = [
    re.compile(r"\b(today|tomorrow|tonight|this\s+afternoon|this\s+morning)\b", re.IGNORECASE),
    re.compile(r"\b(appointment|meeting|reminder|call\s+at|deadline)\b", re.IGNORECASE),
    re.compile(r"\b(temporary|for\s+now|right\s+now)\b", re.IGNORECASE),
]

# Low-signal noise patterns (chit-chat, simple affirmations)
NOISE_PATTERNS = [
    re.compile(r"^(ok|okay|cool|thanks|thank\s+you|got\s+it|sounds\s+good|yes|no|yep|sure)[\.!\?]?$", re.IGNORECASE),
    re.compile(r"^(what\s+time\s+is\s+it|hello|hi|hey|good\s+morning|good\s+night)[\.!\?]?$", re.IGNORECASE),
    re.compile(r"^(test|testing|123|echo)[\.!\?]?$", re.IGNORECASE),
]


class ExtractorGatekeeperAgent(BaseMemoryAgent):
    """The Write Path intake agent filtering noise and creating candidates."""

    agent_id: str = "A1"
    agent_name: str = "ExtractorGatekeeper"

    def process_turn(
        self,
        user_text: str,
        assistant_text: str = "",
        tool_events: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default_session",
    ) -> Optional[MemoryCandidate]:
        """Analyze a conversational exchange or tool execution turn."""
        clean_user = self.mask_secrets(user_text.strip())
        clean_assistant = self.mask_secrets(assistant_text.strip())

        # 1. Trap Tool Failures into episodic_traces for evolution.py
        if tool_events:
            self._trap_tool_failures(tool_events, clean_user, session_id)

        # 2. Check for small talk / noise
        if self._is_noise(clean_user):
            self.logger.debug("Turn filtered as low-signal chit-chat")
            return None

        # 3. Determine Provenance & Importance
        is_explicit = any(p.search(clean_user) for p in EXPLICIT_PREFERENCE_TRIGGERS)
        provenance = "explicit_user" if is_explicit else "inferred_agent"
        importance = self._score_importance(clean_user, is_explicit)

        if importance < self.cfg.min_importance_to_save:
            self.logger.debug("Importance %.2f below threshold (%.2f)", importance, self.cfg.min_importance_to_save)
            return None

        # 4. Classify Memory Layer & Category
        layer, category = self._classify_layer(clean_user, clean_assistant)

        # 5. Calculate TTL (Permanent vs Ephemeral)
        ttl = self._calculate_ttl(clean_user)

        # 6. Generate Clean Title & Deterministic ID
        title = self._generate_title(clean_user, category)
        node_id = f"mem_{layer[:3]}_{sha256(clean_user.lower().encode('utf-8')).hexdigest()[:12]}"

        # 7. Formulate Candidate
        candidate = MemoryCandidate(
            id=node_id,
            layer=layer,
            category=category,
            title=title,
            content=clean_user,
            importance=importance,
            provenance=provenance,
            ttl_expires_at=ttl,
        )
        self.logger.debug("Extracted %s candidate (score: %.2f, provenance: %s)", category, importance, provenance)
        return candidate

    def _trap_tool_failures(
        self,
        tool_events: List[Dict[str, Any]],
        trigger_prompt: str,
        session_id: str,
    ) -> None:
        """Capture tool failures into episodic_traces."""
        for event in tool_events:
            exit_code = event.get("exit_code", 0)
            if exit_code != 0 or event.get("error"):
                trace_id = f"trace_{uuid.uuid4().hex[:12]}"
                self.db.record_trace(
                    trace_id=trace_id,
                    session_id=session_id,
                    trigger_prompt=trigger_prompt,
                    tool_name=event.get("tool_name", "unknown_tool"),
                    tool_input=self.redact_diagnostics(event.get("input", {})),
                    exit_code=exit_code if exit_code != 0 else 1,
                    stdout=self.redact_diagnostics(event.get("stdout")),
                    stderr=self.redact_diagnostics(event.get("stderr")),
                    error_message=self.redact_diagnostics(event.get("error")),
                )
                self.logger.warning("Captured tool failure into episodic trace: %s", trace_id)

    def _is_noise(self, text: str) -> bool:
        """Check if input is trivial conversation."""
        if not text:
            return True
        if any(p.match(text) for p in NOISE_PATTERNS):
            return True
        noise_words = {
            "hello", "hi", "hey", "thanks", "thank", "you", "ok", "okay",
            "cool", "great", "sure", "yes", "no", "yep", "yeah", "bye",
            "good", "morning", "afternoon", "evening", "night", "test", "123"
        }
        words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
        if words and all(w in noise_words for w in words):
            return True
        return False

    def _score_importance(self, text: str, is_explicit: bool) -> float:
        """Compute signal score between 0.0 and 1.0."""
        if is_explicit:
            return 0.95
        score = 0.40
        # Boost for technical keywords
        tech_words = ["arch", "hyprland", "wayland", "pipewire", "python", "git", "config", "socket", "quickshell"]
        matches = sum(1 for w in tech_words if w in text.lower())
        score += min(matches * 0.15, 0.45)
        return min(round(score, 2), 1.0)

    def _classify_layer(self, user_text: str, assistant_text: str) -> tuple[str, str]:
        """Classify into one of the 4 layers: working, semantic, episodic, procedural."""
        lower = user_text.lower()
        if "how to" in lower or "fix" in lower or "solve" in lower or "command" in lower:
            return "procedural", "rule"
        if any(w in lower for w in ["prefer", "favorite", "my", "system", "setup", "always", "never"]):
            return "semantic", "preference"
        if any(w in lower for w in ["yesterday", "did we", "last time", "summary", "project"]):
            return "episodic", "episode"
        return "working", "task"

    def _calculate_ttl(self, text: str) -> Optional[int]:
        """Assign expiry timestamp if ephemeral trigger detected."""
        if any(p.search(text) for p in EPHEMERAL_TRIGGERS):
            return int(time.time()) + self.cfg.ephemeral_default_ttl_seconds
        return None

    def _generate_title(self, text: str, category: str) -> str:
        """Create a clean human-readable title."""
        words = text.split()
        short = " ".join(words[:6])
        return f"{category.capitalize()}: {short}" if len(short) > 0 else f"{category.capitalize()} Memory"
