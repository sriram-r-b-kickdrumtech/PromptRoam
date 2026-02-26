"""
Knowledge Object schemas (Schema.org-aligned, JSON-LD style).

One object = one entity (hotel, attraction, trip) with narrative + metadata bound together.
No fixed-size chunking; pricing and booking links stay with the entity.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseKnowledgeObject(BaseModel):
    """Base for Schema.org-aligned travel entities."""

    type: str = Field(..., description="Schema.org type: Hotel, TouristAttraction, TouristTrip")
    name: str = Field(default="", description="Entity name")
    description: str = Field(default="", description="Narrative for semantic search")
    url: str | None = Field(default=None, description="Booking or official link")


class HotelKnowledgeObject(BaseKnowledgeObject):
    """Schema.org Hotel-like; metadata for filtering before vector search."""

    type: str = "Hotel"
    price_tier: float | None = Field(default=None, ge=0, description="Price or tier for filter")
    location: str | None = None
    location_coordinates: tuple[float, float] | None = None  # lat, lon
    amenities: list[str] = Field(default_factory=list)
    seasonality: str | None = None  # e.g. "peak", "off-season"
    category: str | None = None  # e.g. "boutique", "resort"

    model_config = ConfigDict(extra="allow")


class TouristAttractionKnowledgeObject(BaseKnowledgeObject):
    """Schema.org TouristAttraction-like."""

    type: str = "TouristAttraction"
    location: str | None = None
    location_coordinates: tuple[float, float] | None = None
    category: str | None = None  # e.g. "adventure", "spiritual"
    price_tier: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="allow")


class TouristTripKnowledgeObject(BaseKnowledgeObject):
    """Schema.org TouristTrip-like (itinerary or experience)."""

    type: str = "TouristTrip"
    location: str | None = None
    duration_days: int | None = None
    price_tier: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="allow")


def to_metadata(obj: BaseKnowledgeObject) -> dict[str, Any]:
    """Extract filterable metadata for vector store (no large text)."""
    d = obj.model_dump()
    # Keep only indexable/filterable fields; drop long description for metadata
    meta = {k: v for k, v in d.items() if v is not None and k in (
        "type", "name", "price_tier", "location", "category", "seasonality", "url"
    )}
    if "location_coordinates" in d and d["location_coordinates"]:
        meta["lat"], meta["lon"] = d["location_coordinates"]
    return meta
