"""
Deterministic budget checker (Phase 10). Cross-reference line items; if over limit,
return within_budget=False and optional Knapsack-style subset suggestion.

Used by Financial agent; LLM sets strategy, this enforces numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class BudgetResult:
    """Result of budget check."""
    within_budget: bool
    total: float
    max_budget: float
    currency: str
    line_items: list[dict[str, Any]]  # as passed
    suggested_subset: list[dict[str, Any]] | None  # if over, optional subset within budget


def budget_check(
    line_items: list[dict[str, Any]],
    max_budget: float,
    currency: str = "INR",
) -> BudgetResult:
    """
    Check if sum of line item costs is within max_budget. Each item can have
    'cost' or 'amount' or 'price' key (first found). If over, return suggested_subset
    as greedy by cost (lowest first) until within budget.
    """
    log.debug("[BUDGET_CHECK] entry max_budget=%s currency=%s items_count=%s", max_budget, currency, len(line_items))

    def _cost(item: dict) -> float:
        for key in ("cost", "amount", "price", "total_cost"):
            if key in item and item[key] is not None:
                try:
                    return float(item[key])
                except (TypeError, ValueError):
                    pass
        return 0.0

    total = sum(_cost(it) for it in line_items)
    within = total <= max_budget

    suggested_subset: list[dict[str, Any]] | None = None
    if not within and line_items:
        # Greedy: sort by cost ascending, take until sum <= max_budget
        sorted_items = sorted(line_items, key=_cost)
        running = 0.0
        for it in sorted_items:
            c = _cost(it)
            if running + c <= max_budget:
                if suggested_subset is None:
                    suggested_subset = []
                suggested_subset.append(it)
                running += c
        log.debug("[BUDGET_CHECK] over_budget total=%s suggested_subset_sum=%s", total, sum(_cost(it) for it in (suggested_subset or [])))
    else:
        log.debug("[BUDGET_CHECK] within_budget total=%s", total)

    return BudgetResult(
        within_budget=within,
        total=total,
        max_budget=max_budget,
        currency=currency,
        line_items=line_items,
        suggested_subset=suggested_subset,
    )
