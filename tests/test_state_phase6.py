"""Phase 6: Pydantic state models, validation before commit, reducer behavior."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.state_models import (
    RequestedTripLeg,
    ValidatedPlanLeg,
    HardConstraints,
    validate_trip_leg_payload,
    validate_validated_plan_leg_payload,
    validate_hard_constraints_payload,
    validate_before_commit,
    PlanCommitError,
)
from src.state import update_validated_plan_leg, GraphState


def test_validated_plan_leg_valid_payload() -> None:
    payload = {"total_cost": 100.5, "booking_url": "https://example.com", "currency": "INR"}
    leg = validate_validated_plan_leg_payload(payload)
    assert leg.total_cost == 100.5
    assert leg.booking_url == payload["booking_url"]


def test_validated_plan_leg_invalid_raises() -> None:
    with pytest.raises(Exception):  # Pydantic ValidationError
        validate_validated_plan_leg_payload({"total_cost": -1})
    with pytest.raises(Exception):
        validate_validated_plan_leg_payload("not a dict")


def test_trip_leg_valid_payload() -> None:
    payload = {"id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "summary": "Goa", "status": "planned"}
    leg = validate_trip_leg_payload(payload)
    assert leg.id == payload["id"]
    assert leg.summary == "Goa"


def test_trip_leg_empty_id_raises() -> None:
    with pytest.raises(Exception):
        validate_trip_leg_payload({"id": "", "summary": "x"})


def test_hard_constraints_valid() -> None:
    payload = {"max_budget": 15000, "duration_days": 4, "currency": "INR"}
    hc = validate_hard_constraints_payload(payload)
    assert hc.max_budget == 15000
    assert hc.duration_days == 4


def test_hard_constraints_invalid_raises() -> None:
    with pytest.raises(Exception):
        validate_hard_constraints_payload({"max_budget": -1})
    with pytest.raises(Exception):
        validate_hard_constraints_payload({"duration_days": 400})


def test_reducer_update_leg_a_only_b_unchanged() -> None:
    """Reducer updates one leg in validated_plans by UUID; other keys unchanged."""
    state: GraphState = {
        "validated_plans": {
            "uuid-a": {"total_cost": 100, "booking_url": "https://a.com"},
            "uuid-b": {"total_cost": 200, "booking_url": "https://b.com"},
        },
    }
    update = update_validated_plan_leg(state, "uuid-a", {"total_cost": 150, "booking_url": "https://a2.com"})
    assert update["validated_plans"]["uuid-a"]["total_cost"] == 150
    assert update["validated_plans"]["uuid-b"] == {"total_cost": 200, "booking_url": "https://b.com"}


def test_validate_before_commit_under_budget_passes() -> None:
    validate_before_commit(
        {"max_budget": 200},
        {"leg-1": {"total_cost": 50}, "leg-2": {"total_cost": 100}},
    )


def test_validate_before_commit_over_budget_raises() -> None:
    with pytest.raises(PlanCommitError) as exc_info:
        validate_before_commit(
            {"max_budget": 100},
            {"leg-1": {"total_cost": 60}, "leg-2": {"total_cost": 50}},
        )
    assert "exceeds max_budget" in str(exc_info.value)


def test_validate_before_commit_no_constraints_passes() -> None:
    validate_before_commit(None, {"leg-1": {"total_cost": 999}})
    validate_before_commit({}, {"leg-1": {"total_cost": 999}})
