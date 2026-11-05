"""Deterministic, user-evidenced memory candidates; no storage or model calls.

The caller must additionally apply its scanner/trust gate before persistence.
Only clearly single-valued language, identity, and coding-agent preferences share keys.
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
_PREFIX = r"(?:(?:actually|correction|instead|from now on|also|listen|so|then|and|well|okay|ok)[,:]?\s+)*"
_AGENTS = r"Hermes|Codex|OpenCode|Gemini|OMP|Claude"
_LANGUAGES = r"English|Hindi|Tamil|Bengali|Telugu|Kannada|Malayalam|Marathi|Gujarati|Urdu|Spanish|French|German|Japanese|Chinese|Korean"

_NON_NAMES = {
    "a", "an", "the", "not", "here", "ready", "sure", "tired", "busy", "fine", "ok", "okay",
    "sorry", "back", "done", "going", "asking", "moving", "trying", "looking", "testing",
    "using", "on", "in", "at", "to", "working", "building", "fixing", "happy", "glad", "sad",
    "afraid", "worried", "wondering", "thinking", "curious", "interested", "planning", "hoping",
    "free", "available", "logged", "signed", "leaving", "arriving", "standing", "sitting",
    "speaking", "talking", "listening", "running", "writing", "reading", "coding", "what"
}

_ROLES = (
    r"software\s+engineer|software\s+developer|web\s+developer|full[- ]stack\s+developer|"
    r"frontend\s+developer|backend\s+developer|devops\s+engineer|cloud\s+architect|"
    r"systems\s+architect|solutions\s+architect|data\s+scientist|data\s+engineer|"
    r"machine\s+learning\s+engineer|ml\s+engineer|ai\s+engineer|security\s+engineer|"
    r"qa\s+engineer|test\s+engineer|developer|engineer|coder|programmer|student|cse\s+student|"
    r"student\s+of\s+cse|computer\s+science\s+student|designer|ui\s+designer|ux\s+designer|"
    r"product\s+manager|project\s+manager|scrum\s+master|researcher|consultant|admin|sysadmin|"
    r"creator|writer|author|founder|co-founder|ceo|cto|freelancer|analyst|intern"
)


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
        statement = re.sub('^' + _PREFIX, '', text, flags=re.I).strip()
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

        # 1. Instructions & explicit persistent directives
        if re.match(r'^(?:remember this instruction:|for future replies[, :]?|from now on[, :]?)\s*\S', text, re.I):
            kind = 'instruction'
        elif language:
            kind, slot = 'preference', 'preference:language'
        elif agent:
            kind, slot = 'preference', 'preference:coding_agent'
        # 2. Explicit memory / note requests (checked before identity to preserve 'remember that ...' -> 'fact')
        elif re.match(r"^(?:please )?(?:remember|note|keep in mind)(?: that)?\s+\S", statement, re.I):
            kind = 'fact'
        elif re.match(r"^(?:save|take|store)(?: this)? (?:note|memo|fact|to memory)[: ]\s*\S", statement, re.I):
            kind = 'fact'
        elif re.match(r"^(?:don't forget|do not forget)(?: that| to)?\s+\S", statement, re.I):
            kind = 'fact'
        elif re.match(r"^(?:fyi|just so you know)[, :]\s*\S", statement, re.I):
            kind = 'fact'
        # 3. Identity: Name
        elif re.match(r"^(?:my name is|call me|my full name is|my nickname is)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:name'
        elif (m := re.match(r"^(?:I am|I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$", statement)):
            candidate_name = m.group(1).strip()
            if candidate_name.lower() not in _NON_NAMES:
                kind, slot = 'identity', 'identity:name'
        # 4. Identity: Location, Role, Contact, Bio
        elif re.match(r"^(?:I (?:live|reside) in|I am based in|I'm based in|my location is|my home is in)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:location'
        elif (m_from := re.match(r"^(?:I am|I'm)\s+from\s+([A-Z][A-Za-z\s,.-]+)\b", statement)):
            kind, slot = 'identity', 'identity:location'
        elif re.match(rf"^(?:I (?:work|am working) as (?:a|an)|I am (?:a|an)|I'm (?:a|an))\s+(?:{_ROLES})\b", statement, re.I):
            kind, slot = 'identity', 'identity:role'
        elif re.match(r"^(?:I (?:work|am working) at|my company is)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:company'
        elif re.match(r"^(?:I study|I am studying|I'm a student at)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:education'
        elif re.match(r"^(?:my email(?: address)? is|reach me at|my email:)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:email'
        elif re.match(r"^(?:my phone(?: number)? is|call me at)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:phone'
        elif re.match(r"^(?:my (?:github|git|website|portfolio|blog)(?: username| handle| url| profile)? is)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:github'
        elif re.match(r"^(?:my timezone is|my time zone is)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:timezone'
        elif re.match(r"^(?:my (?:birthday|birth date) is)\s+\S", statement, re.I):
            kind, slot = 'identity', 'identity:birthday'
        # 5. Preferences
        elif re.match(r"^I (?:now )?prefer\s+\S", statement, re.I):
            kind = 'preference'
        elif re.match(r"^I (?:really |always )?(?:like|love|dislike|hate|favor|enjoy)\s+\S", statement, re.I):
            kind = 'preference'
        elif re.match(r"^my (?:preferred|favorite|favourite)\s+\S", statement, re.I):
            kind = 'preference'
        elif re.match(r"^my preference is\s+\S", statement, re.I):
            kind = 'preference'
        # 6. Negative constraints & authorization rules
        elif re.match(r"^(?:do not|don't|never)\s+(?:use|choose|authorize|enable|touch|modify|override|install|run|call)\s+\S", statement, re.I):
            kind = 'constraint'
        elif re.match(r"^(?:I don't|I do not)\s+(?:want|need|authorize|allow)\s+\S", statement, re.I):
            kind = 'constraint'
        elif re.match(r"^(?:we|I)\s+(?:will\s+)?(?:only|always)\s+(?:use|authenticate|authorize|run|call)\s+\S", statement, re.I):
            kind = 'constraint'
        elif re.match(r"^(?:[A-Za-z0-9_ -]+?)\s+(?:don't|do not|never)\s+(?:use|choose|authorize|enable)\s+\S", statement, re.I):
            kind = 'constraint'
        elif re.match(r"^(?:only|always)\s+(?:authorize|connect|authenticate|run)\s+\S", statement, re.I):
            kind = 'constraint'
        # 7. Decisions
        elif re.match(r"^(?:I|we) (?:have )?decided (?:to|on|that)\s+\S", statement, re.I):
            kind = 'decision'
        elif re.match(r"^(?:our|my) decision is (?:to|that)\s+\S", statement, re.I):
            kind = 'decision'
        elif re.match(r"^(?:we|I) chose (?:to|that)\s+\S", statement, re.I):
            kind = 'decision'
        # 8. Tasks & Action items
        elif re.match(r"^(?:(?:please )?(?:help me|can you|could you) (?:build|implement|fix|finish|add|create|complete)|(?:I|we) (?:still )?(?:need|want) to (?:build|implement|fix|finish|add|create|complete)|(?:please |let[\'’]?s |lets )?(?:build|implement|fix|finish|add|create|complete))\s+\S", statement, re.I):
            kind, confidence = 'task', 0.8
        elif re.match(r"^(?:create a task|add a task|todo:|task:)\s+\S", statement, re.I):
            kind, confidence = 'task', 0.8
        # 9. Requirements
        elif re.match(r"^(?:I|we) (?:want|need|require)\s+\S", statement, re.I):
            kind = 'requirement'
        # 10. Goals
        elif re.match(r"^(?:the|our|my) (?:goal|objective|plan) is (?:to )?\s*\S", statement, re.I):
            kind = 'goal'
        # 11. Projects & Tech stack / Environment
        elif re.match(r"^(?:I am|I'm|we are|we're) (?:currently )?(?:working on|building|developing|creating|maintaining)\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:the|our) project (?:name )?is\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:our|the) (?:tech )?stack is\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:we|I) (?:are using|use|run on)\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:we are|we're|I am|I'm) migrating (?:from .* )?to\s+\S", statement, re.I):
            kind = 'project'
        elif re.match(r"^(?:I|we)\s+(?:have|installed|set up|configured|added)\s+(?:Arch Linux|Ubuntu|Debian|Fedora|Hyprland|Linux)\b", statement, re.I):
            kind = 'project'
        # 12. Technical facts
        elif re.match(r"^(?:the|our|my) (?:database|server|backend|frontend|api|port|host|ip|path|directory|repo|repository|os|window manager)\s+(?:is|runs on)\s+\S", statement, re.I):
            kind = 'fact'

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
