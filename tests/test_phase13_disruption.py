"""Phase 13: DyFlow — parse disruption from user message."""
import pytest
from src.disruption import parse_disruption_from_message


def test_no_delay() -> None:
    assert parse_disruption_from_message("I want to book a flight") is None
    assert parse_disruption_from_message("") is None


def test_delay_parsed() -> None:
    event = parse_disruption_from_message("My flight is delayed 4 hours")
    assert event is not None
    assert event.get("delay_hours") == 4
    assert "flight" in (event.get("reason") or "").lower()


def test_delay_2_hrs() -> None:
    event = parse_disruption_from_message("There is a 2 hour delay")
    assert event is not None
    assert event.get("delay_hours") == 2
