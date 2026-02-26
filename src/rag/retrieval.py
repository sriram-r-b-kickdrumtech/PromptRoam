"""
Retrieval: NL → metadata filter extraction, then threshold-gated search.

No pure RRF; absolute confidence scores retained; return "no results" when none pass threshold.
"""
from __future__ import annotations

import re
from typing import Any

# Default: cosine distance / similarity; higher score = more similar in some backends
# Chroma similarity_search_with_score returns (doc, distance); lower distance = better
SCORE_IS_DISTANCE = True  # Chroma returns distance
DEFAULT_SCORE_THRESHOLD = 0.0  # caller can set; e.g. max distance allowed


def extract_metadata_filters_from_nl(nl_query: str) -> dict[str, Any]:
    """
    Rule-based extraction of metadata filters from natural language.
    Narrows search space before vector search. Supports price_tier, location, type, category.
    """
    filters: dict[str, Any] = {}
    q = (nl_query or "").strip().lower()

    # Price: "cheap", "under 100", "budget", "luxury", "mid-range"
    if re.search(r"\b(cheap|budget|low[- ]?cost)\b", q):
        filters["price_tier"] = {"$lte": 50}
    elif re.search(r"\b(mid[- ]?range|moderate|medium)\b", q):
        filters["price_tier"] = {"$lte": 150}
    elif re.search(r"\b(luxury|high[- ]?end|premium)\b", q):
        filters["price_tier"] = {"$gte": 150}
    elif m := re.search(r"\bunder\s+(\d+)\b", q):
        filters["price_tier"] = {"$lte": float(m.group(1))}
    elif m := re.search(r"\b(?:max|below|less than)\s+(\d+)\b", q):
        filters["price_tier"] = {"$lte": float(m.group(1))}

    # Type: hotel, attraction, trip
    if re.search(r"\b(hotel|stay|accommodation|lodging)\b", q):
        filters["type"] = "Hotel"
    elif re.search(r"\b(attraction|activity|thing to do|place to see)\b", q):
        filters["type"] = "TouristAttraction"
    elif re.search(r"\b(trip|itinerary|tour)\b", q):
        filters["type"] = "TouristTrip"

    # Category (simple keyword → category; first match wins to avoid overwrite)
    if re.search(r"\b(spiritual|yoga|meditation|temple)\b", q):
        filters["category"] = "spiritual"
    elif re.search(r"\b(adventure|hiking|trek|outdoor)\b", q):
        filters["category"] = "adventure"
    elif re.search(r"\b(boutique|small hotel)\b", q):
        filters["category"] = "boutique"

    return filters


def _chroma_where(filters: dict[str, Any]) -> dict[str, Any] | None:
    """Convert flat filter dict to Chroma where: use $and when multiple conditions."""
    if not filters:
        return None
    if len(filters) == 1:
        k, v = next(iter(filters.items()))
        return {k: v}
    return {"$and": [{k: v} for k, v in filters.items()]}


def threshold_gated_retrieve(
    store,
    query: str,
    *,
    filter_metadata: dict[str, Any] | None = None,
    k: int = 5,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    score_is_distance: bool = SCORE_IS_DISTANCE,
) -> tuple[list[tuple[Any, float]], bool]:
    """
    Run semantic search with optional metadata filter; apply score threshold.
    Returns (list of (doc, score), passed_threshold).
    If score_is_distance=True, scores below threshold are kept (lower = better).
    When no result passes threshold, return ([], False) — no RRF, no low-confidence results.
    """
    from src.rag.store import query_with_metadata

    where = _chroma_where(filter_metadata) if filter_metadata else None
    results = query_with_metadata(
        store, query, filter_metadata=where, k=k
    )
    if not results:
        return [], False

    if score_is_distance:
        passed = [(doc, s) for doc, s in results if s <= score_threshold]
    else:
        passed = [(doc, s) for doc, s in results if s >= score_threshold]

    return passed, len(passed) > 0


def _is_likely_vague(query: str) -> bool:
    """Heuristic: short or abstract queries benefit from HyDE."""
    q = (query or "").strip()
    if len(q) < 20:
        return True
    vague_terms = ("adventure", "experience", "something", "things to do", "ideas", "suggest")
    return any(t in q.lower() for t in vague_terms)


def retrieve_for_agent(
    store,
    nl_query: str,
    *,
    k: int = 5,
    score_threshold: float = 1.0,
    use_hyde: bool = True,
) -> list[dict[str, Any]]:
    """
    Full pipeline: optionally HyDE for vague queries → extract filters → threshold-gated search.
    Returns list of doc.metadata + page_content as structured context for Experience/Accommodation agents.
    If nothing passes threshold, returns [] (clear "no results" signal).
    """
    search_query = nl_query
    if use_hyde and _is_likely_vague(nl_query):
        try:
            from src.rag.hyde import generate_hypothetical_document
            search_query = generate_hypothetical_document(nl_query)
        except Exception:
            pass  # fallback to raw query
    filters = extract_metadata_filters_from_nl(nl_query)
    pairs, ok = threshold_gated_retrieve(
        store, search_query,
        filter_metadata=filters if filters else None,
        k=k,
        score_threshold=score_threshold,
        score_is_distance=True,
    )
    if not ok:
        return []
    out = []
    for doc, score in pairs:
        out.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
        })
    return out
