"""
Ingestion: unstructured → Knowledge Objects (entity-aware, no fixed-size chunking).

Each document/chunk = one entity; pricing and links stay bound to that entity.
"""
from __future__ import annotations

import json
from typing import Any

from src.rag.schema import (
    HotelKnowledgeObject,
    TouristAttractionKnowledgeObject,
    BaseKnowledgeObject,
    to_metadata,
)


def parse_hotel_from_dict(data: dict[str, Any]) -> HotelKnowledgeObject:
    """Build Hotel Knowledge Object from dict (e.g. from API or parsed HTML)."""
    return HotelKnowledgeObject(
        type="Hotel",
        name=data.get("name", ""),
        description=data.get("description", ""),
        url=data.get("url") or data.get("booking_url"),
        price_tier=data.get("price_tier") or data.get("price"),
        location=data.get("location"),
        location_coordinates=data.get("location_coordinates"),
        amenities=data.get("amenities", []) if isinstance(data.get("amenities"), list) else [],
        seasonality=data.get("seasonality"),
        category=data.get("category"),
    )


def parse_attraction_from_dict(data: dict[str, Any]) -> TouristAttractionKnowledgeObject:
    """Build TouristAttraction Knowledge Object from dict."""
    return TouristAttractionKnowledgeObject(
        type="TouristAttraction",
        name=data.get("name", ""),
        description=data.get("description", ""),
        url=data.get("url"),
        location=data.get("location"),
        location_coordinates=data.get("location_coordinates"),
        category=data.get("category"),
        price_tier=data.get("price_tier") or data.get("price"),
    )


def knowledge_object_to_document(obj: BaseKnowledgeObject) -> tuple[str, dict[str, Any]]:
    """
    Convert a Knowledge Object to (page_content, metadata) for the vector store.
    page_content = searchable text (name + description); metadata = filterable fields.
    Entity stays whole; no splitting.
    """
    text = f"{obj.name}\n{obj.description}".strip()
    meta = to_metadata(obj)
    return text, meta
