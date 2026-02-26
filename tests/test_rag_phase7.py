"""
Phase 7: RAG — Knowledge Objects, ingestion, NL→metadata filters, threshold retrieval.
"""
from __future__ import annotations

import pytest

from src.rag.schema import (
    HotelKnowledgeObject,
    TouristAttractionKnowledgeObject,
    to_metadata,
)
from src.rag.ingestion import (
    parse_hotel_from_dict,
    parse_attraction_from_dict,
    knowledge_object_to_document,
)
from src.rag.retrieval import extract_metadata_filters_from_nl


def test_hotel_knowledge_object_metadata():
    hotel = HotelKnowledgeObject(
        name="Test Resort",
        description="A peaceful stay by the Ganges.",
        url="https://example.com/book",
        price_tier=80.0,
        location="Rishikesh",
        category="boutique",
    )
    meta = to_metadata(hotel)
    assert meta["type"] == "Hotel"
    assert meta["name"] == "Test Resort"
    assert meta["price_tier"] == 80.0
    assert meta["location"] == "Rishikesh"
    assert meta["category"] == "boutique"
    assert "description" not in meta


def test_attraction_knowledge_object():
    attr = TouristAttractionKnowledgeObject(
        name="Bungee by Ganges",
        description="Spiritual adventure activity.",
        category="spiritual",
        price_tier=50.0,
    )
    text, meta = knowledge_object_to_document(attr)
    assert "Bungee" in text and "Spiritual" in text
    assert meta["type"] == "TouristAttraction"
    assert meta["category"] == "spiritual"


def test_parse_hotel_from_dict():
    data = {
        "name": "River Lodge",
        "description": "Eco lodge with yoga.",
        "booking_url": "https://book.example.com",
        "price_tier": 120,
        "location": "Rishikesh",
        "amenities": ["wifi", "yoga"],
    }
    hotel = parse_hotel_from_dict(data)
    assert hotel.name == "River Lodge"
    assert hotel.url == "https://book.example.com"
    assert hotel.price_tier == 120
    assert hotel.amenities == ["wifi", "yoga"]


def test_extract_metadata_filters_cheap():
    f = extract_metadata_filters_from_nl("I want cheap hotels in Rishikesh")
    assert "price_tier" in f
    assert f["price_tier"] == {"$lte": 50}


def test_extract_metadata_filters_under_100():
    f = extract_metadata_filters_from_nl("accommodation under 100 per night")
    assert f["price_tier"] == {"$lte": 100.0}


def test_extract_metadata_filters_type_hotel():
    f = extract_metadata_filters_from_nl("find me a hotel or stay")
    assert f.get("type") == "Hotel"


def test_extract_metadata_filters_category_spiritual():
    f = extract_metadata_filters_from_nl("spiritual adventure and yoga")
    assert f.get("category") == "spiritual"


def test_extract_metadata_filters_empty():
    f = extract_metadata_filters_from_nl("")
    assert f == {}


def test_threshold_gated_retrieve_returns_empty_when_none_pass():
    """When no result passes threshold, return ([], False) — no RRF, no low-confidence."""
    from src.rag.retrieval import threshold_gated_retrieve

    class MockStore:
        def similarity_search_with_score(self, query, k, filter=None):
            # Simulate high distance (bad) for all
            from langchain_core.documents import Document
            return [(Document(page_content="x", metadata={}), 2.0)]

    store = MockStore()
    passed, ok = threshold_gated_retrieve(
        store, "test", k=5, score_threshold=0.5, score_is_distance=True
    )
    assert ok is False
    assert passed == []
