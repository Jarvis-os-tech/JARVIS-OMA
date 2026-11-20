"""Bounded, local lexical retrieval with conservative concept expansion.

This is not embedding or semantic search: only words, explicit concept groups,
and normalized phrases match. Negation, intent, and prompt injection are not
interpreted; callers must scan/filter candidates before using retrieved text.
Only the first 32,768 text characters and 2,048 query characters are searched,
and at most 10,000 candidates and 100 results are considered.
"""

from datetime import datetime, timezone
import math
import re
import unicodedata


_STOPWORDS = frozenset("a an and are as at be been by do does for from how i in is it me my of on or please that the this to was what when where which who with you your".split())
_GROUPS = (
    "remember remembered remembering recollection recollections recall recalled memory memories",
    "code codes coding programming program programmer programmers",
    "preference preferences prefer prefers preferred favorite favorites favourite favourites",
    "todo todos task tasks",
    "agent agents",
    "language languages",
)
_CONCEPTS = {word: index for index, group in enumerate(_GROUPS) for word in group.split()}


def _tokens(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    # Preserve technical tokens such as C++, C#, and dotted identifiers.
    return re.findall(r"[^\W_]+(?:[._][^\W_]+)*(?:\+\+|#)?", normalized, re.UNICODE)


def recall_with_evidence(query, ranked):
    """Abstain on slot and keyword lookups without enough matching evidence."""
    tokens = _tokens(query)
    if not tokens:
        return ranked if not query.strip() else []
    attribute = (
        tokens[0] in {"what", "which"}
        and len(tokens) >= 3
        and tokens[1] in {"is", "are", "was", "were", "s"}
        and tokens[2] in {"my", "our"}
    )
    if not attribute and tokens[0] in {
        "what", "when", "where", "why", "how", "which", "who",
        "do", "does", "did", "is", "are", "can", "could", "should",
    }:
        return ranked
    # shortcut: topical similarity cannot establish a named attribute, revisit with verified reranking evidence
    terms = [_CONCEPTS.get(word, word) for word in tokens[3 if attribute else 0:] if word not in _STOPWORDS]
    if not terms:
        return []
    required = set(terms)

    def coverage(item):
        text = item.get("text") or item.get("content") or ""
        words = {_CONCEPTS.get(word, word) for word in _tokens(text[:32768])}
        return required & words

    if attribute:
        return [item for item in ranked if (matched := coverage(item)) and terms[-1] in matched
                and (len(required) == 1 or len(matched) >= 2)
                and 2 * len(matched) >= len(required)]
    if any(2 * len(coverage(item)) >= len(required) for item in ranked):
        return ranked
    return []


def _timestamp(candidate):
    value = candidate.get("updated_at") or candidate.get("timestamp") or candidate.get("created_at")
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result = float(value)
        elif isinstance(value, datetime):
            result = (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).timestamp()
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            result = (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
        else:
            return 0.0
        return result if math.isfinite(result) else 0.0
    except (ValueError, OverflowError, OSError):
        return 0.0


def rank_candidates(query, candidates, limit=20):
    """Return copied candidate dictionaries with ``score`` and ``match_reason``.

    Text alone supplies relevance; metadata cannot manufacture a match. Recency
    contributes less than 0.01, breaking close ties without outranking a word
    match. Empty queries return recent candidates; nonempty queries with no
    searchable terms return nothing. Ties preserve input order.
    """
    limit = max(0, min(int(limit), 100))
    if not limit:
        return []
    query = str(query or "")[:2048]
    query_tokens = _tokens(query)
    terms = set(query_tokens) - _STOPWORDS
    if query.strip() and not terms:
        return []
    phrase = " ".join(query_tokens)
    ranked = []
    for index, candidate in enumerate(candidates):
        if index >= 10000:
            break
        if not isinstance(candidate, dict) or not isinstance(candidate.get("text"), str):
            continue
        tokens = _tokens(candidate["text"][:32768])
        words = set(tokens)
        exact = terms & words
        concepts = {_CONCEPTS[word] for word in words if word in _CONCEPTS}
        expanded = {term for term in terms - exact if term in _CONCEPTS and _CONCEPTS[term] in concepts}
        if terms and not (exact or expanded):
            continue
        phrase_match = bool(terms and phrase and f" {phrase} " in f" {' '.join(tokens)} ")
        lexical = (4 * len(exact) + 2 * len(expanded)) / max(1, len(terms))
        if phrase_match:
            lexical += 2
        # Absolute bounded recency avoids other candidates influencing scores.
        stamp = max(0.0, _timestamp(candidate))
        recency = 0.009 * (stamp / (stamp + 2_000_000_000))
        reasons = []
        if exact:
            reasons.append("lexical: " + ", ".join(sorted(exact)))
        if expanded:
            reasons.append("concept expansion: " + ", ".join(sorted(expanded)))
        if phrase_match:
            reasons.append("normalized phrase")
        result = dict(candidate)
        result.update(score=lexical + recency, match_reason="; ".join(reasons) or "empty query: recency")
        ranked.append(result)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]
