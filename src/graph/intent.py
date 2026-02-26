"""
Extract hard_constraints and user_profile_and_context from natural language.

No hardcoded "three-part" decomposition; extract whatever the user specifies.
"""
from __future__ import annotations

import re
from typing import Any

def _title(s: str) -> str:
    """Helper: title case and strip string."""
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^(in|at)\s+", "", s, flags=re.I)
    return s.title()

def extract_constraints_and_profile(user_message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Parse user message into hard_constraints and user_profile_and_context.
    Returns (hard_constraints, user_profile_and_context).
    """
    hard: dict[str, Any] = {}
    profile: dict[str, Any] = {}

    if not user_message:
        return hard, profile

    text = user_message.lower().strip()

    # Explicit Clarifications Parsing (from UI form)
    if "clarifications:" in text.lower():
        # e.g. "Clarifications: interests=adventure; origin=Delhi"
        clean_text = text.lower().replace("clarifications:", "")
        parts = clean_text.split(";")
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "interests":
                    # Append new interests to existing ones
                    new_interests = [x.strip().title() for x in v.split(",") if x.strip()]
                    profile["interests"] = list(set((profile.get("interests") or []) + new_interests))
                elif k == "origin":
                    profile["origin"] = _title(v)
                elif k == "destination":
                    profile["destination"] = _title(v)
                elif k == "budget":
                    # Re-run budget logic on this specific value
                    b_match = re.search(r"(\d+)", v)
                    if b_match:
                        profile["max_budget"] = int(b_match.group(1)) # temp store
                elif k == "dates":
                    profile["date_hint"] = v
                elif k == "transport":
                    profile["preferred_transport"] = v

    # Budget: "under 15k", "₹15000", "15,000", "budget 1000 usd"
    budget_text = text
    if profile.get("max_budget"):
        budget_text = str(profile["max_budget"])
    
    budget_match = re.search(
        r"(?:under|under\s+)?(?:₹|rs\.?|inr)\s*([0-9,]+)(?:\s*k)?|"
        r"(?:under|budget)\s*([0-9,]+)\s*(?:k|thousand)?|"
        r"([0-9,]+)\s*(?:k|inr|rs)",
        budget_text,
        re.I,
    )
    if budget_match:
        g = next(g for g in budget_match.groups() if g)
        amount = int(g.replace(",", ""))
        if amount < 1000:
            amount *= 1000  # 15k -> 15000
        hard["max_budget"] = amount
        hard["currency"] = "INR"

    # Duration: "4 days", "3-day", "weekend"
    days_match = re.search(r"(\d+)\s*[-]?\s*day|(\d+)\s*days", text, re.I)
    if days_match:
        d = next(g for g in days_match.groups() if g)
        hard["duration_days"] = int(d)
    if "weekend" in text and "duration_days" not in hard:
        hard["duration_days"] = 2

    # Dates: concrete for API when possible; else hint
    month_map = {"january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
                 "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12"}
    if "next weekend" in text:
        hard["date_hint"] = "next_weekend"
    # "April 15 2025", "15 April 2025", "April 2025", "april 10-13"
    date_match = re.search(
        r"(?:(\d{1,2})\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s*(?:(\d{4}))?(?:\s*[-–]\s*(\d{1,2}))?",
        text,
        re.I,
    )
    if date_match:
        day1, month_name, year, day2 = date_match.groups()
        month = month_map.get(month_name.lower() if month_name else "", "")
        y = year or "2025"
        d = (day1 or "15").zfill(2)
        if month:
            hard["date_hint"] = "flexible"
            hard["travel_date"] = f"{y}-{month}-{d}"  # API-friendly date (origin date for outbound)

    if not hard.get("travel_date") and re.search(
        r"\b(march|april|may|june|july|august|september|october|november|december)\b", text
    ):
        hard["date_hint"] = hard.get("date_hint", "flexible")

    # Origin and destination: "from Delhi to Goa", "Delhi to Goa", "to Goa", "from Mumbai"
    if " to " in text:
        to_match = re.search(r"from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s+\.|,|\s+on\s+|\s+date|\s+travel|$)", text, re.I)
        if to_match:
            profile["origin"] = _title(to_match.group(1))
            profile["destination"] = _title(to_match.group(2))
        else:
            to_match = re.search(r"([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s+\.|,|\s+on\s+|\s+date|\s+travel|$)", text, re.I)
            if to_match:
                profile["origin"] = _title(to_match.group(1))
                profile["destination"] = _title(to_match.group(2))
    if " to " in text and not profile.get("destination"):
        # Stop at 'under', 'budget', 'for', or digits
        to_match = re.search(r"\bto\s+([a-z][a-z\s]{1,30}?)(?:\s+\.|,|\s+on\s+|\s+date|\s+travel|\s+for\s+|\s+under\s+|\s+budget\s+|\d|$)", text, re.I)
        if to_match:
            profile["destination"] = _title(to_match.group(1))
    
    # New: if no 'to' but we see a city name followed by 'under'
    if not profile.get("destination"):
        # Match 'Goa' in '2 days Goa under 10k'
        simple_dest = re.search(r"(?:days|day|weekend)\s+([a-z\s]{1,20}?)(?:\s+under|\s+budget|\s+for|$)", text, re.I)
        if simple_dest:
            profile["destination"] = _title(simple_dest.group(1))
    if "from " in text and not profile.get("origin"):
        from_match = re.search(r"from\s+([a-z\s]+?)(?:\s+to\s+|\s+next|\s+under|,|$)", text, re.I)
        if from_match:
            profile["origin"] = _title(from_match.group(1))

    # Profile / style from keywords
    if any(w in text for w in ["backpack", "solo", "budget", "cheap"]):
        profile["travel_style"] = "backpacker"
    if any(w in text for w in ["luxury", "comfort", "resort"]):
        profile["travel_style"] = "luxury"
    if any(w in text for w in ["adventure", "trek", "sport", "bungee", "beach", "water sports"]):
        profile["interests"] = profile.get("interests", []) + ["adventure"]
    if any(w in text for w in ["spiritual", "yoga", "meditation", "temple"]):
        profile["interests"] = profile.get("interests", []) + ["spiritual"]

    return hard, profile


def get_last_user_message(state: dict[str, Any]) -> str:
    """Get last user message content from message_history."""
    messages = state.get("message_history") or []
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            return (m.get("content") or "") if isinstance(m.get("content"), str) else str(m.get("content", ""))
        if hasattr(m, "content") and getattr(m, "type", "") == "human":
            return getattr(m, "content", "") or ""
    return ""
