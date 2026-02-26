"""
Phase 8: HyDE & HyPE — vague-query handling and hypothetical question ingestion.
"""
from __future__ import annotations

import pytest

from src.rag.retrieval import _is_likely_vague, retrieve_for_agent


def test_is_likely_vague_short():
    assert _is_likely_vague("spiritual trip") is True
    assert _is_likely_vague("something fun") is True


def test_is_likely_vague_terms():
    assert _is_likely_vague("I want an adventure near Rishikesh") is True
    assert _is_likely_vague("suggest things to do") is True
    assert _is_likely_vague("give me ideas for a weekend") is True


def test_is_not_vague_long_specific():
    assert _is_likely_vague("I want a cheap boutique hotel in Rishikesh with yoga and river view") is False


def test_retrieve_for_agent_use_hyde_false_uses_raw_query():
    """When use_hyde=False, search uses the raw query (no LLM call)."""
    seen_queries = []

    class CaptureStore:
        def similarity_search_with_score(self, query, k=5, filter=None):
            seen_queries.append(query)
            return []

    store = CaptureStore()
    retrieve_for_agent(store, "spiritual adventure", k=2, use_hyde=False)
    assert len(seen_queries) == 1
    assert seen_queries[0] == "spiritual adventure"


def test_retrieve_for_agent_use_hyde_true_may_replace_query():
    """When use_hyde=True and query is vague, HyDE can replace query (we only check it runs)."""
    # Mock HyDE to avoid LLM call in test
    import src.rag.retrieval as retrieval_mod
    original_vague = retrieval_mod._is_likely_vague
    try:
        retrieval_mod._is_likely_vague = lambda q: True
        seen_queries = []
        original_hyde = None
        try:
            from src.rag import hyde
            original_hyde = hyde.generate_hypothetical_document
            hyde.generate_hypothetical_document = lambda q: "yoga by the Ganges and bungee jumping"
        except ImportError:
            pytest.skip("hyde module not available")

        class CaptureStore:
            def similarity_search_with_score(self, query, k=5, filter=None):
                seen_queries.append(query)
                return []

        store = CaptureStore()
        retrieve_for_agent(store, "spiritual adventure", k=2, use_hyde=True)
        assert len(seen_queries) == 1
        # Should be the hypothetical doc we mocked, not the raw "spiritual adventure"
        assert seen_queries[0] == "yoga by the Ganges and bungee jumping"
    finally:
        retrieval_mod._is_likely_vague = original_vague
        if original_hyde is not None:
            try:
                from src.rag import hyde
                hyde.generate_hypothetical_document = original_hyde
            except ImportError:
                pass
