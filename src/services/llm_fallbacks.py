"""
LLM-backed JSON fallbacks for external API gaps.

Modeled after the ai-planner services style: strict JSON output via LLM.
These are used only when real APIs are unavailable or fail.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from src.graph.llm import call_llm_json
from src.cache import cache_get_mcp, cache_set_mcp


def _safe_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []

def _maps_search_url(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)


def _hotel_search_urls(query: str) -> list[str]:
    q = quote_plus(query)
    return [
        f"https://www.booking.com/searchresults.html?ss={q}",
        f"https://www.expedia.com/Hotel-Search?destination={q}",
        f"https://www.hotels.com/Hotel-Search?destination={q}",
        f"https://www.agoda.com/search?city=0&text={q}",
        f"https://www.tripadvisor.com/Search?q={q}",
    ]


def _activity_search_urls(query: str) -> list[str]:
    q = quote_plus(query)
    return [
        f"https://www.tripadvisor.com/Search?q={q}",
        f"https://www.getyourguide.com/s/?q={q}",
        f"https://www.viator.com/searchResults/all?text={q}",
        f"https://www.klook.com/search/?query={q}",
        f"https://www.airbnb.com/s/experiences?query={q}",
    ]


def _flight_search_urls(query: str) -> list[str]:
    q = quote_plus(query)
    return [
        f"https://www.google.com/travel/flights?q={q}",
        f"https://www.skyscanner.com/transport/flights/{q}",
        f"https://www.kayak.com/flights/{q}",
        f"https://www.expedia.com/Flights-Search?trip=oneway&leg1={q}",
        f"https://www.kiwi.com/en/search/results/{q}",
    ]

def _sanitize_urls(items: list[dict[str, Any]], *, query_key: str, search_urls: list[str] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        name = item.get(query_key) or item.get("name") or ""
        location = item.get("location") or ""
        query = f"{name} {location}".strip() or location or name
        # Remove any LLM-provided URLs to avoid fabricated links
        if "booking_url" in item:
            item.pop("booking_url", None)
        if "url" in item:
            item.pop("url", None)
        # Force real, deterministic search URLs to avoid hallucinated links
        if search_urls:
            item["search_urls"] = search_urls
        else:
            item["search_url"] = _maps_search_url(query)
        out.append(item)
    return out

def llm_fallback_flights(origin: str, dest: str, date: str, budget: int | None = None) -> dict[str, Any]:
    cache_args = {"origin": origin, "dest": dest, "date": date, "budget": budget}
    cached = cache_get_mcp("llm_fallback_flights", cache_args)
    if cached is not None:
        return cached.get("structuredContent") or cached
    system_prompt = (
        "You are a travel data assistant. Return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  "flights": [\n'
        '    {\n'
        '      "flight_name": "string",\n'
        '      "origin": "string",\n'
        '      "dest": "string",\n'
        '      "scheduled_departure": "string",\n'
        '      "scheduled_arrival": "string",\n'
        '      "price_estimate": number,\n'
        '      "currency": "INR",\n'
        '      "source_api": "llm_fallback",\n'
        '      "stub": true,\n'
        '      "search_url": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Include a search_url users can click to find tickets (e.g., Google Flights or airline search).\n"
        "- Use reasonable estimates if exact data is unavailable.\n"
        "- Keep 2-4 options.\n"
    )
    user_prompt = f"Origin: {origin}; Destination: {dest}; Date: {date}; Budget: {budget}"
    try:
        payload = call_llm_json(system_prompt, user_prompt, "llm_fallback_flights")
        flights = _safe_list(payload.get("flights"))
        if flights:
            q = f"{origin} to {dest} {date}"
            urls = _flight_search_urls(q)
            flights = _sanitize_urls(flights, query_key="flight_name", search_urls=urls)
            result = {"flights": flights, "source": "llm_fallback"}
            cache_set_mcp("llm_fallback_flights", cache_args, {"structuredContent": result}, ttl_seconds=3600)
            return result
    except Exception:
        pass
    return {"flights": [{"id": "F1", "origin": origin, "dest": dest, "flight_name": "Fallback Flight", "stub": True}]}


def llm_fallback_hotels(location: str, budget: int | None = None) -> dict[str, Any]:
    cache_args = {"location": location, "budget": budget}
    cached = cache_get_mcp("llm_fallback_hotels", cache_args)
    if cached is not None:
        return cached.get("structuredContent") or cached
    system_prompt = (
        "You are a travel data assistant. Return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  "hotels": [\n'
        '    {\n'
        '      "name": "string",\n'
        '      "location": "string",\n'
        '      "price_estimate": number,\n'
        '      "currency": "INR",\n'
        '      "source_api": "llm_fallback",\n'
        '      "stub": true,\n'
        '      "search_url": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Include a search_url users can click to find booking options.\n"
        "- Keep 3-6 options.\n"
    )
    user_prompt = f"Location: {location}; Budget: {budget}"
    try:
        payload = call_llm_json(system_prompt, user_prompt, "llm_fallback_hotels")
        hotels = _safe_list(payload.get("hotels"))
        if hotels:
            q = f"hotels in {location}"
            urls = _hotel_search_urls(q)
            hotels = _sanitize_urls(hotels, query_key="name", search_urls=urls)
            result = {"hotels": hotels, "source": "llm_fallback"}
            cache_set_mcp("llm_fallback_hotels", cache_args, {"structuredContent": result}, ttl_seconds=3600)
            return result
    except Exception:
        pass
    return {"hotels": [{"id": "H1", "name": f"Hotels in {location}", "location": location, "stub": True}]}


def llm_fallback_activities(location: str, interests: list[str] | None = None) -> dict[str, Any]:
    interests = interests or []
    cache_args = {"location": location, "interests": interests}
    cached = cache_get_mcp("llm_fallback_activities", cache_args)
    if cached is not None:
        return cached.get("structuredContent") or cached
    system_prompt = (
        "You are a travel data assistant. Return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  "activities": [\n'
        '    {\n'
        '      "name": "string",\n'
        '      "location": "string",\n'
        '      "category": "string",\n'
        '      "price_estimate": number,\n'
        '      "currency": "INR",\n'
        '      "source_api": "llm_fallback",\n'
        '      "stub": true,\n'
        '      "search_url": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Include a search_url users can click to learn more.\n"
        "- Keep 4-8 options.\n"
    )
    user_prompt = f"Location: {location}; Interests: {', '.join(interests) if interests else 'general'}"
    try:
        payload = call_llm_json(system_prompt, user_prompt, "llm_fallback_activities")
        activities = _safe_list(payload.get("activities"))
        if activities:
            q = f"things to do in {location}"
            urls = _activity_search_urls(q)
            activities = _sanitize_urls(activities, query_key="name", search_urls=urls)
            result = {"activities": activities, "source": "llm_fallback"}
            cache_set_mcp("llm_fallback_activities", cache_args, {"structuredContent": result}, ttl_seconds=3600)
            return result
    except Exception:
        pass
    return {"activities": [{"id": "A1", "name": f"Things to do in {location}", "location": location, "stub": True}]}
