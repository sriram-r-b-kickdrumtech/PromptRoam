"""
Pydantic models for state sub-values (Phase 6).

Validated plans and trip legs use these for strict validation; invalid payloads raise.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def is_valid_uuid_str(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False


class RequestedTripLeg(BaseModel):
    """One requested journey leg with a stable UUID for DyFlow/targeted edits."""

    id: str = Field(..., min_length=1, description="Stable ID (UUID recommended) for this leg")
    summary: str = Field(default="", description="Short description of the leg")
    status: str = Field(default="planned", description="planned | in_progress | completed")
    destination: str | None = None
    dates: str | None = None

    @field_validator("id")
    @classmethod
    def id_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("id must be non-empty")
        return v.strip()


class ValidatedPlanLeg(BaseModel):
    """One leg's API-validated booking data (keyed by trip UUID in validated_plans)."""

    total_cost: float | None = Field(default=None, ge=0, description="Cost for this leg")
    booking_url: str | None = None
    external_id: str | None = None
    price_quote: dict[str, Any] | None = Field(
        default=None,
        description="Optional quote with source and timestamp for verifiable inventory",
    )
    flights: list[dict[str, Any]] = Field(default_factory=list)
    accommodation: dict[str, Any] | None = None
    activities: list[dict[str, Any]] = Field(default_factory=list)
    currency: str = "INR"

    model_config = ConfigDict(extra="allow")  # Allow API-specific fields (e.g. hotel name)


def _leg_has_verifiable_inventory(leg: dict[str, Any] | ValidatedPlanLeg) -> bool:
    """True if leg has at least one of: booking_url, external_id, or price_quote (with source and timestamp)."""
    if isinstance(leg, ValidatedPlanLeg):
        if leg.booking_url and leg.booking_url.strip():
            return True
        if leg.external_id and leg.external_id.strip():
            return True
        pq = leg.price_quote
        if isinstance(pq, dict) and pq.get("source") and pq.get("timestamp"):
            return True
        return False
    # dict
    if leg.get("booking_url") and str(leg["booking_url"]).strip():
        return True
    if leg.get("external_id") and str(leg["external_id"]).strip():
        return True
    pq = leg.get("price_quote")
    if isinstance(pq, dict) and pq.get("source") and pq.get("timestamp"):
        return True
    return False


def check_verifiable_inventory(validated_plans: dict[str, Any]) -> list[str]:
    """
    Enforce Phase 9: every itinerary leg must have at least one of booking_url, external_id,
    or price_quote (with source and timestamp). Returns list of leg IDs that fail the check.
    """
    failing: list[str] = []
    for leg_id, leg_data in validated_plans.items():
        if not _leg_has_verifiable_inventory(leg_data):
            failing.append(leg_id)
    return failing


class HardConstraints(BaseModel):
    """Explicit numerical limits from user (validated before committing plans)."""

    max_budget: int | None = Field(default=None, ge=0)
    currency: str = "INR"
    duration_days: int | None = Field(default=None, ge=1, le=365)
    date_start: date | None = None
    date_end: date | None = None
    date_hint: str | None = None

    model_config = ConfigDict(extra="allow")


def validate_trip_leg_payload(payload: dict[str, Any]) -> RequestedTripLeg:
    """Validate and return RequestedTripLeg; raises ValidationError if invalid."""
    return RequestedTripLeg.model_validate(payload)


def validate_validated_plan_leg_payload(payload: dict[str, Any]) -> ValidatedPlanLeg:
    """Validate and return ValidatedPlanLeg; raises ValidationError if invalid."""
    return ValidatedPlanLeg.model_validate(payload)


def validate_hard_constraints_payload(payload: dict[str, Any]) -> HardConstraints:
    """Validate and return HardConstraints; raises ValidationError if invalid."""
    return HardConstraints.model_validate(payload)


class PlanCommitError(Exception):
    """Raised when a plan fails validation before commit (e.g. over budget)."""

    pass


# ---------------------------------------------------------------------------
# Structured Itinerary (Phase 14+)
# ---------------------------------------------------------------------------

class ItineraryDay(BaseModel):
    day: int = Field(..., ge=1)
    title: str = Field(default="")
    activities: list[str] = Field(default_factory=list)
    lodging: str | None = None
    transport: str | None = None
    notes: str | None = None


class BudgetBreakdown(BaseModel):
    total: float | None = Field(default=None, ge=0)
    max_budget: float | None = Field(default=None, ge=0)
    currency: str | None = None
    line_items: list[dict[str, Any]] = Field(default_factory=list)


class Itinerary(BaseModel):
    summary: str = Field(default="")
    days: list[ItineraryDay] = Field(default_factory=list)
    budget: BudgetBreakdown | None = None
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


def parse_itinerary_payload(payload: dict[str, Any]) -> Itinerary:
    """Validate and return Itinerary; raises ValidationError if invalid."""
    return Itinerary.model_validate(payload)


def itinerary_to_markdown(itinerary: Itinerary) -> str:
    """Render structured itinerary as markdown for chat output."""
    lines: list[str] = []
    if itinerary.summary:
        lines.append(f"**Trip summary:** {itinerary.summary}")
    if itinerary.days:
        for d in itinerary.days:
            lines.append(f"\n### Day {d.day}: {d.title or 'Plan'}")
            if d.transport:
                lines.append(f"- Transport: {d.transport}")
            if d.lodging:
                lines.append(f"- Lodging: {d.lodging}")
            if d.activities:
                lines.append("- Activities:")
                for a in d.activities:
                    lines.append(f"  - {a}")
            if d.notes:
                lines.append(f"- Notes: {d.notes}")
    if itinerary.budget:
        b = itinerary.budget
        lines.append("\n### Budget")
        lines.append(f"- Total: {b.total} {b.currency or ''}".strip())
        if b.max_budget is not None:
            lines.append(f"- Max budget: {b.max_budget} {b.currency or ''}".strip())
        if b.line_items:
            lines.append("- Line items:")
            for li in b.line_items:
                cat = li.get("category", "item")
                cost = li.get("cost", "")
                lines.append(f"  - {cat}: {cost}")
    if itinerary.warnings:
        lines.append("\n### Warnings")
        for w in itinerary.warnings:
            lines.append(f"- {w}")
    if itinerary.sources:
        lines.append("\n### Sources")
        for s in itinerary.sources:
            lines.append(f"- {s}")
    return "\n".join(lines).strip() or "Itinerary generated."


def validate_before_commit(
    hard_constraints: dict[str, Any] | None,
    validated_plans: dict[str, Any],
) -> None:
    """
    Check hard constraints before committing validated_plans.
    Raises PlanCommitError if total cost exceeds max_budget or dates out of range.
    """
    if not hard_constraints:
        return
    try:
        hc = HardConstraints.model_validate(hard_constraints)
    except Exception:
        return  # Skip if constraints not fully shaped
    max_budget = hc.max_budget
    if max_budget is not None and validated_plans:
        total = 0.0
        for leg_data in validated_plans.values():
            if isinstance(leg_data, dict) and leg_data.get("total_cost") is not None:
                total += float(leg_data["total_cost"])
            elif isinstance(leg_data, ValidatedPlanLeg):
                total += leg_data.total_cost or 0.0
        if total > max_budget:
            raise PlanCommitError(f"Total cost {total} exceeds max_budget {max_budget}")
    if hc.date_start and hc.date_end and validated_plans:
        for leg_data in validated_plans.values():
            if not isinstance(leg_data, dict):
                continue
            leg_start = leg_data.get("date_start")
            leg_end = leg_data.get("date_end")
            if leg_start and leg_end:
                try:
                    ls = date.fromisoformat(leg_start) if isinstance(leg_start, str) else leg_start
                    le = date.fromisoformat(leg_end) if isinstance(leg_end, str) else leg_end
                    if ls < hc.date_start or le > hc.date_end:
                        raise PlanCommitError(
                            f"Leg dates {ls}–{le} outside constraint range {hc.date_start}–{hc.date_end}"
                        )
                except (TypeError, ValueError):
                    pass
