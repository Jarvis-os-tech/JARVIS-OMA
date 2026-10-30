"""Deterministic fusion of local lexical and semantic memory results.

The inputs are already-ranked candidate dictionaries.  Fusion uses a bounded
normalized blend rather than comparing backend-specific raw scores directly:
lexical evidence contributes up to 0.55, semantic similarity up to 0.35, and
current structured-memory provenance up to 0.10.  An exact lexical hit sorts
ahead of semantic-only candidates so embeddings can add paraphrases without
displacing direct evidence.

Callers should supply active candidates only.  This module also rejects every
candidate with an explicit status other than ``active`` as a defence in depth.
"""

import math
import re
import unicodedata


_STRUCTURED_SOURCES = frozenset((
    "explicit-user-correction",
    "explicit-user-memory",
    "structured-capture",
))


def _number(value, default=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _semantic_score(candidate):
    # Semantic backends may retain their channel score under either name.
    return max(0.0, min(1.0, _number(
        candidate.get("semantic_score", candidate.get("score")))))


def _lexical_score(candidate):
    return max(0.0, _number(
        candidate.get("lexical_score", candidate.get("score"))))


def _text_key(value):
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _candidate_key(candidate):
    """Return a typed, stable key without conflating unrelated identifier fields."""
    for field in ("canonical_key", "memory_id", "id", "chunk_id"):
        value = candidate.get(field)
        if value is not None and str(value) != "":
            return field + ":" + str(value)
    # A structured slot is a useful identity when channel adapters omit IDs.
    if candidate.get("key"):
        return "slot:" + str(candidate.get("kind", "")) + ":" + str(candidate["key"])
    return "text:" + _text_key(candidate.get("text", candidate.get("content", "")))


def _is_active(candidate):
    status = candidate.get("status")
    return status is None or str(status).casefold() == "active"


def _is_structured(candidate):
    return bool(candidate.get("kind") or candidate.get("key") or
                candidate.get("memory_id") or
                candidate.get("source") in _STRUCTURED_SOURCES)


def _lexical_reason(candidate):
    reason = str(candidate.get("match_reason") or "").strip()
    return reason if reason else "lexical match"


def fuse_results(lexical, semantic, limit=20, semantic_min_score=0.35):
    """Fuse lexical and semantic candidates into copied, metadata-rich results.

    Low-confidence semantic-only candidates are excluded.  A below-threshold
    semantic duplicate can still be returned through its lexical evidence, but
    its semantic contribution is zero.  Ties are resolved by channel ranks and
    canonical key, making output independent of mapping insertion behaviour.
    """
    if type(limit) is not int:
        raise TypeError("limit must be an integer")
    if not 0 <= limit <= 100:
        raise ValueError("limit must be between 0 and 100")
    threshold = _number(semantic_min_score, default=-1.0)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("semantic_min_score must be between 0 and 1")
    if not limit:
        return []

    merged = {}
    for channel, candidates in (("lexical", lexical), ("semantic", semantic)):
        for rank, candidate in enumerate(candidates or (), 1):
            if not isinstance(candidate, dict) or not _is_active(candidate):
                continue
            key = _candidate_key(candidate)
            entry = merged.setdefault(key, {
                "candidate": {}, "lexical_rank": None, "semantic_rank": None,
                "lexical_score": 0.0, "semantic_score": 0.0,
                "lexical_reason": "",
            })
            # Earlier-ranked metadata is authoritative; fill absent fields from
            # the other channel so fusion never discards useful metadata.
            for name, value in candidate.items():
                entry["candidate"].setdefault(name, value)
            if channel == "lexical" and entry["lexical_rank"] is None:
                entry["lexical_rank"] = rank
                entry["lexical_score"] = _lexical_score(candidate)
                entry["lexical_reason"] = _lexical_reason(candidate)
            elif channel == "semantic" and entry["semantic_rank"] is None:
                entry["semantic_rank"] = rank
                entry["semantic_score"] = _semantic_score(candidate)

    fused = []
    for key, entry in merged.items():
        has_lexical = entry["lexical_rank"] is not None
        semantic_score = entry["semantic_score"]
        semantic_accepted = entry["semantic_rank"] is not None and semantic_score >= threshold
        if not has_lexical and not semantic_accepted:
            continue

        candidate = entry["candidate"]
        lexical_score = entry["lexical_score"]
        # Saturation accommodates lexical backends whose scores exceed one.
        lexical_normalized = lexical_score / (lexical_score + 1.0) if lexical_score else 0.0
        structured = _is_structured(candidate)
        corrected = candidate.get("source") == "explicit-user-correction"
        final_score = (0.55 * lexical_normalized +
                       0.35 * (semantic_score if semantic_accepted else 0.0) +
                       (0.07 if structured else 0.0) +
                       (0.03 if corrected else 0.0))
        result = dict(candidate)
        reasons = []
        if has_lexical:
            reasons.append(entry["lexical_reason"])
        if semantic_accepted:
            reasons.append("semantic similarity %.3f" % semantic_score)
        if structured:
            reasons.append("active structured memory")
        result.update(
            lexical_score=lexical_score,
            semantic_score=semantic_score if semantic_accepted else 0.0,
            score=round(max(0.0, min(1.0, final_score)), 12),
            match_reason="; ".join(reasons),
            provenance={
                "canonical_key": key,
                "channels": (["lexical"] if has_lexical else []) +
                            (["semantic"] if semantic_accepted else []),
                "lexical_rank": entry["lexical_rank"],
                "semantic_rank": entry["semantic_rank"] if semantic_accepted else None,
            },
        )
        result["_fusion_sort"] = (
            0 if has_lexical else 1,
            -result["score"],
            entry["lexical_rank"] or 10 ** 9,
            entry["semantic_rank"] or 10 ** 9,
            key,
        )
        fused.append(result)

    fused.sort(key=lambda item: item["_fusion_sort"])
    for item in fused:
        del item["_fusion_sort"]
    return fused[:limit]

