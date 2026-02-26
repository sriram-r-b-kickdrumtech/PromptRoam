"""
Output guardrails (Phase 12): validate final payload—no PII in logs; costs within budget.
On failure: return error message; caller can trigger refinement (cap 3).
"""
from __future__ import annotations

import re
from typing import Any

from config.logging_config import get_logger, log_guardrail

log = get_logger(__name__)

# Simple PII patterns (do not log these)
PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{10,12}\b"),  # long number (phone-like)
]


def redact_pii(text: str) -> str:
    """Replace PII with [REDACTED] for safe logging."""
    out = text
    for pat in PII_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def check_no_pii_in_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    """
    Return (passed, detail). If PII detected in string values, fail.
    """
    def _scan(obj: Any) -> bool:
        if isinstance(obj, str):
            for pat in PII_PATTERNS:
                if pat.search(obj):
                    return False
            return True
        if isinstance(obj, dict):
            return all(_scan(v) for v in obj.values())
        if isinstance(obj, list):
            return all(_scan(v) for v in obj)
        return True

    if not _scan(payload):
        log_guardrail(log, "no_pii", False, "PII detected in payload")
        return False, "PII detected in payload; redact before logging."
    log_guardrail(log, "no_pii", True, "")
    return True, ""


def check_budget_guardrail(
    validated_plans: dict[str, Any],
    hard_constraints: dict[str, Any] | None,
) -> tuple[bool, str]:
    """
    Return (passed, detail). Fail if total cost across validated_plans exceeds max_budget.
    """
    max_budget = (hard_constraints or {}).get("max_budget")
    if max_budget is None:
        log_guardrail(log, "budget", True, "no max_budget constraint")
        return True, ""

    total = 0.0
    for leg in (validated_plans or {}).values():
        if isinstance(leg, dict) and leg.get("total_cost") is not None:
            total += float(leg["total_cost"])
        elif hasattr(leg, "total_cost") and leg.total_cost is not None:
            total += float(leg.total_cost)

    if total > float(max_budget):
        log_guardrail(log, "budget", False, f"total={total} max_budget={max_budget}")
        return False, f"Total cost {total} exceeds max_budget {max_budget}"
    log_guardrail(log, "budget", True, f"total={total}")
    return True, f"total={total}"


def run_output_guardrails(
    validated_plans: dict[str, Any],
    hard_constraints: dict[str, Any] | None,
    message_history_last_content: str = "",
) -> tuple[bool, list[str]]:
    """
    Run all output guardrails. Return (all_passed, list of failure messages).
    """
    failures: list[str] = []
    pii_ok, pii_msg = check_no_pii_in_payload(
        {"validated_plans": validated_plans, "last_message": message_history_last_content}
    )
    if not pii_ok:
        failures.append(pii_msg)
    budget_ok, budget_msg = check_budget_guardrail(validated_plans, hard_constraints)
    if not budget_ok:
        failures.append(budget_msg)
    all_passed = len(failures) == 0
    if not all_passed:
        log.warning("[GUARDRAIL] output guardrails failed: %s", failures)
    return all_passed, failures
