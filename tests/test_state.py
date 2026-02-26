"""Unit tests for state schema and reducers."""
import pytest

from src.state import (
    GraphState,
    update_validated_plan_leg,
    update_requested_trip_leg,
)


def test_update_validated_plan_leg_updates_one_leg_only() -> None:
    state: GraphState = {
        "validated_plans": {
            "uuid-a": {"hotel": "A", "price": 100},
            "uuid-b": {"hotel": "B", "price": 200},
        },
    }
    update = update_validated_plan_leg(state, "uuid-a", {"hotel": "A2", "price": 150})
    assert update == {
        "validated_plans": {
            "uuid-a": {"hotel": "A2", "price": 150},
            "uuid-b": {"hotel": "B", "price": 200},
        },
    }
    # Original state unchanged
    assert state["validated_plans"]["uuid-b"] == {"hotel": "B", "price": 200}


def test_update_validated_plan_leg_empty_state() -> None:
    state: GraphState = {}
    update = update_validated_plan_leg(state, "new-uuid", {"flight": "F1"})
    assert update == {"validated_plans": {"new-uuid": {"flight": "F1"}}}


def test_update_requested_trip_leg_replaces_matching_id() -> None:
    state: GraphState = {
        "requested_trips": [
            {"id": "leg-1", "dest": "Delhi"},
            {"id": "leg-2", "dest": "Rishikesh"},
        ],
    }
    update = update_requested_trip_leg(state, "leg-1", {"dest": "Delhi", "dates": "2026-03-01"})
    assert update["requested_trips"] == [
        {"id": "leg-1", "dest": "Delhi", "dates": "2026-03-01"},
        {"id": "leg-2", "dest": "Rishikesh"},
    ]


def test_update_requested_trip_leg_leaves_others_unchanged() -> None:
    state: GraphState = {
        "requested_trips": [
            {"id": "a", "x": 1},
            {"id": "b", "x": 2},
        ],
    }
    update = update_requested_trip_leg(state, "a", {"x": 99})
    assert update["requested_trips"][1] == {"id": "b", "x": 2}
