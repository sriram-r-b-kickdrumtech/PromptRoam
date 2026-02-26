"""Phase 12: Output guardrails — budget and PII checks."""
import pytest
from src.guardrails import (
    check_budget_guardrail,
    check_no_pii_in_payload,
    run_output_guardrails,
    redact_pii,
)


def test_check_no_pii_pass() -> None:
    passed, _ = check_no_pii_in_payload({"summary": "Trip to Goa", "cost": 100})
    assert passed is True


def test_check_no_pii_fail() -> None:
    passed, _ = check_no_pii_in_payload({"email": "user@example.com"})
    assert passed is False


def test_redact_pii() -> None:
    assert "user@example.com" not in redact_pii("Contact user@example.com for details")
    assert "[REDACTED]" in redact_pii("Contact user@example.com for details")


def test_check_budget_guardrail_pass() -> None:
    plans = {"leg1": {"total_cost": 50}, "leg2": {"total_cost": 50}}
    passed, _ = check_budget_guardrail(plans, {"max_budget": 150})
    assert passed is True


def test_check_budget_guardrail_fail() -> None:
    plans = {"leg1": {"total_cost": 100}, "leg2": {"total_cost": 100}}
    passed, msg = check_budget_guardrail(plans, {"max_budget": 150})
    assert passed is False
    assert "150" in msg


def test_run_output_guardrails_all_pass() -> None:
    passed, failures = run_output_guardrails(
        {"leg1": {"total_cost": 50}},
        {"max_budget": 100},
        "2 days Goa",
    )
    assert passed is True
    assert failures == []


def test_run_output_guardrails_budget_fail() -> None:
    passed, failures = run_output_guardrails(
        {"leg1": {"total_cost": 200}},
        {"max_budget": 100},
        "trip",
    )
    assert passed is False
    assert any("budget" in f.lower() or "200" in f for f in failures)
