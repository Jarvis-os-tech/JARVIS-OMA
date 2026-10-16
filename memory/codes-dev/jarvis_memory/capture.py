"""Deterministic, user-evidenced memory candidates; no storage or model calls.

The caller must additionally apply its scanner/trust gate before persistence.
Only clearly single-valued language and coding-agent preferences share keys.
"""

from __future__ import annotations

import hashlib
import re


_UNSAFE = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|system|safety)\s+instructions|"
    r"(?:override|bypass|disregard)\s+(?:the\s+)?(?:rules|instructions|safety|system)|"
    r"(?:system|developer)\s*(?:prompt|message|:)|"
    r"(?:reveal|exfiltrate|leak)\b|you\s+(?:must|should|are\s+now)\b",
    re.I,
)
_PREFIX = r"(?:(?:actually|correction|instead|from now on)[,:]?\s+)*"
_AGENTS = r"Hermes|Codex|OpenCode|Gemini|OMP|Claude"
_LANGUAGES = r"English|Hindi|Tamil|Bengali|Telugu|Kannada|Malayalam|Marathi|Gujarati|Urdu|Spanish|French|German|Japanese|Chinese|Korean"


def extract_memories(user_text: str, assistant_text: str = "") -> list[dict]:
    """Return deduplicated candidates with verbatim USER evidence.

    Assistant text is deliberately unused. Quoted/code material and turns with
    obvious instruction injection are excluded. Requests are task candidates,
    never claims that the requested work has already happened.
    """
    if not isinstance(user_text, str) or not user_text.strip():
        return []
    if _UNSAFE.search(user_text):
        return []
    # Ignore fenced examples, blockquotes, and quoted assertions.
    source = re.sub(r"```[\s\S]*?(?:```|$)", "", user_text)
    source = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', "", source)
    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for part in re.split(r"(?<=[.!?])\s+|\n+", source):
        evidence = part.strip()
        if not evidence or evidence.startswith('>') or evidence not in user_text:
            continue
        text = evidence.rstrip('.!?').strip()
        if len(text) < 5 or len(text) > 500:
            continue
        statement = re.sub('^' + _PREFIX, '', text, flags=re.I)
        if re.search(r'\b(?:for (?:this (?:message|reply|turn)|today|now)|only (?:today|this time))\b', statement, re.I):
            continue
        kind = None
        slot = None
        confidence = 0.9
        # Full matching avoids treating "English for this message" as a slot.
        language = re.fullmatch(
            rf"(?:I (?:now )?prefer|my preferred language is|my language preference is)\s+({_LANGUAGES})(?:\s+(?:for (?:responses|replies)|as my (?:preferred )?language))?",
            statement, re.I,
        )
        agent = re.fullmatch(
            rf"(?:my preferred coding agent is|I (?:now )?prefer(?: to use)?)\s+({_AGENTS})\s*(?:as my (?:preferred )?coding agent|for coding)?",
            statement, re.I,
        )
        if language:
            kind, slot = 'preference', 'preference:language'
        elif agent:
            kind, slot = 'preference', 'preference:coding_agent'
        elif re.match(r"^I (?:now )?prefer\s+\S", statement, re.I):
            kind = 'preference'
        elif re.match(r"^(?:I|we) (?:have )?decided (?:to|on|that)\s+\S", statement, re.I):
            kind = 'decision'
        elif re.match(r"^(?:I am|I'm|we are|we're) (?:currently )?(?:working on|building|developing)\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:please )?remember (?:that\s+)?\S", statement, re.I):
            kind = 'fact'
        elif re.match(r"^(?:(?:please )?(?:help me|can you|could you) (?:build|implement|fix|finish|add|create|complete)|(?:I|we) (?:still )?(?:need|want) to (?:build|implement|fix|finish|add|create|complete)|(?:please |let['’]?s |lets )?(?:build|implement|fix|finish|add|create|complete))\s+\S", statement, re.I):
            kind, confidence = 'task', 0.8
        if kind is None:
            continue
        normalized = ' '.join(text.casefold().split())
        identity = (kind, normalized)
        if identity in seen:
            continue
        seen.add(identity)
        digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        candidates.append(dict(text=text, kind=kind, key=slot or f'{kind}:{digest}',
                               confidence=confidence, evidence=evidence))
    return candidates


__all__ = ['extract_memories']
