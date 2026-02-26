"""Phase 9: Verifiable inventory — every leg has booking_url, external_id, or price_quote."""
import pytest
from src.state_models import check_verifiable_inventory, ValidatedPlanLeg


def test_check_verifiable_inventory_all_pass() -> None:
    """All legs with at least one of booking_url, external_id, or price_quote pass."""
    plans = {
        "leg-1": {"booking_url": "https://book.example.com/1", "total_cost": 100},
        "leg-2": {"external_id": "EXT-123", "total_cost": 200},
        "leg-3": {"price_quote": {"source": "api", "timestamp": "2025-02-25T12:00:00"}, "total_cost": 50},
    }
    assert check_verifiable_inventory(plans) == []


def test_check_verifiable_inventory_some_fail() -> None:
    """Legs missing all of booking_url, external_id, price_quote fail."""
    plans = {
        "ok": {"booking_url": "https://x.com", "total_cost": 10},
        "missing": {"total_cost": 20, "flights": []},
        "empty_url": {"booking_url": "", "external_id": None},
        "price_quote_no_timestamp": {"price_quote": {"source": "api"}},
    }
    failing = check_verifiable_inventory(plans)
    assert "ok" not in failing
    assert "missing" in failing
    assert "empty_url" in failing
    assert "price_quote_no_timestamp" in failing


def test_check_verifiable_inventory_validated_plan_leg() -> None:
    """ValidatedPlanLeg instances are checked correctly."""
    leg = ValidatedPlanLeg(booking_url="https://x.com", total_cost=100)
    assert check_verifiable_inventory({"id": leg}) == []

    leg_no_verifiable = ValidatedPlanLeg(total_cost=100)
    assert check_verifiable_inventory({"id": leg_no_verifiable}) == ["id"]
