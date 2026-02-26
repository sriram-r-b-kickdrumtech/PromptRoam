"""
DyFlow (Phase 13): parse user message or webhook into structured disruption event.
E.g. "My flight is delayed 4 hours" -> { affected_leg_id, delay_hours, reason }.
"""
from __future__ import annotations

import re
from typing import Any

from config.logging_config import get_logger

log = get_logger(__name__)

# Patterns for delay mention (hours)
DELAY_PATTERNS = [
    re.compile(r"(?:flight|train|bus)\s+(?:is\s+)?delayed\s+(?:by\s+)?(\d+)\s*(?:hours?|hrs?)", re.I),
    re.compile(r"(\d+)\s*(?:hours?|hrs?)\s+delay", re.I),
    re.compile(r"delay(?:ed)?\s+(?:of\s+)?(\d+)\s*(?:hours?|hrs?)", re.I),
]


def parse_disruption_from_message(message: str) -> dict[str, Any] | None:
    """
    If message describes a delay/disruption, return structured event for DyFlow.
    Keys: affected_leg_id (optional), delay_hours, reason (snippet).
    """
    if not (message or message.strip()):
        return None
    msg = message.strip()
    delay_hours: float | None = None
    for pat in DELAY_PATTERNS:
        m = pat.search(msg)
        if m:
            try:
                delay_hours = float(m.group(1))
                break
            except (IndexError, ValueError):
                pass
    if delay_hours is None:
        log.debug("[DISRUPTION] no delay pattern matched in message (len=%s)", len(msg))
        return None
    event: dict[str, Any] = {
        "delay_hours": delay_hours,
        "reason": msg[:200],
        "source": "user_message",
    }
    log.info("[DISRUPTION] parsed delay_hours=%s reason_snippet=%s", delay_hours, msg[:80])
    return event
