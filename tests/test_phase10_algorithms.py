"""Phase 10: Algorithmic delegation — budget checker and TSP with time windows."""
import pytest
from src.algorithms.budget import budget_check, BudgetResult
from src.algorithms.tsp import order_waypoints_with_time_windows, TSPInput, TSPResult


def test_budget_check_within() -> None:
    result = budget_check(
        [{"category": "transport", "cost": 1000}, {"category": "hotel", "cost": 2000}],
        max_budget=5000,
    )
    assert result.within_budget is True
    assert result.total == 3000
    assert result.suggested_subset is None


def test_budget_check_over() -> None:
    result = budget_check(
        [{"category": "a", "cost": 50}, {"category": "b", "cost": 60}, {"category": "c", "cost": 40}],
        max_budget=100,
    )
    assert result.within_budget is False
    assert result.total == 150
    assert result.suggested_subset is not None
    assert sum(x.get("cost", 0) for x in result.suggested_subset) <= 100


def test_budget_check_uses_amount_key() -> None:
    result = budget_check([{"category": "x", "amount": 30}], max_budget=50)
    assert result.within_budget is True
    assert result.total == 30


def test_tsp_empty() -> None:
    r = order_waypoints_with_time_windows([])
    assert r.ordered_ids == []
    assert r.total_cost == 0
    assert r.feasible is True


def test_tsp_single() -> None:
    r = order_waypoints_with_time_windows([TSPInput("a", 0.0, 0.0)])
    assert r.ordered_ids == ["a"]
    assert r.feasible is True


def test_tsp_three_no_windows() -> None:
    waypoints = [
        TSPInput("a", 0.0, 0.0),
        TSPInput("b", 1.0, 0.0),
        TSPInput("c", 0.5, 0.5),
    ]
    r = order_waypoints_with_time_windows(waypoints)
    assert len(r.ordered_ids) == 3
    assert set(r.ordered_ids) == {"a", "b", "c"}
    assert r.total_cost >= 0
