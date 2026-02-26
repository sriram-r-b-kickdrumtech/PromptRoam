#!/usr/bin/env python3
"""
Call every category (flights, hotels, activities, weather) and print each API's results.

Run from repo root with .env loaded (RAPIDAPI_API_KEY, OPENWEATHERMAP_API_KEY):
  python scripts/call_all_apis_show_results.py

Output: merged result per category, then a per-API breakdown so you can see which APIs returned data.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Import tool handlers and registry from local MCP server
import importlib.util
spec = importlib.util.spec_from_file_location("mcp_server_promptroam", ROOT / "scripts" / "mcp_server_promptroam.py")
if spec is None or spec.loader is None:
    print("Could not load mcp_server_promptroam")
    sys.exit(1)
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)

TOOL_HANDLERS = mcp.TOOL_HANDLERS
TOOL_TO_APIS = mcp.TOOL_TO_APIS


def _default_args(tool_name: str) -> dict:
    if tool_name == "search_flights":
        return {"origin": "Delhi", "destination": "Goa", "date": "2025-04-15"}
    if tool_name == "search_hotels":
        return {"location": "Goa"}
    if tool_name == "search_activities":
        return {"location": "Goa"}
    if tool_name == "get_weather":
        return {"location": "Goa"}
    return {}


def _per_api_breakdown(data: dict, item_key: str, source_key: str = "source_api") -> dict[str, list]:
    """Group items by source_api."""
    items = data.get(item_key, [])
    if not isinstance(items, list):
        return {}
    by_api: dict[str, list] = {}
    for x in items:
        if isinstance(x, dict):
            api = x.get(source_key, "?")
            by_api.setdefault(api, []).append(x)
    return by_api


def main() -> None:
    rapidapi = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    owm = (os.environ.get("OPENWEATHERMAP_API_KEY") or "").strip()
    if not rapidapi:
        print("Warning: RAPIDAPI_API_KEY not set. RapidAPI calls will fail.\n")
    if not owm:
        print("Warning: OPENWEATHERMAP_API_KEY not set. Weather will fail.\n")

    categories = [
        ("Flights", "search_flights", "flights", "sources_used"),
        ("Hotels", "search_hotels", "hotels", "sources_used"),
        ("Activities", "search_activities", "activities", "sources_used"),
        ("Weather", "get_weather", None, None),
    ]

    for title, tool_name, list_key, sources_key in categories:
        api_ids = TOOL_TO_APIS.get(tool_name, [])
        print("=" * 60)
        print(f"  {title}")
        print(f"  APIs in registry: {', '.join(api_ids)}")
        print("=" * 60)

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            print("  (no handler)\n")
            continue

        args = _default_args(tool_name)
        try:
            out = handler(args)
        except Exception as e:
            print(f"  Error: {e}\n")
            continue

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            print(out[:1500])
            if len(out) > 1500:
                print("  ... (truncated)")
            print()
            continue

        if "error" in data:
            print(f"  Error: {data['error']}\n")
            continue

        # Pretty-print full result (truncate if huge)
        raw = json.dumps(data, indent=2)
        if len(raw) > 3000:
            raw = raw[:3000] + "\n  ... (truncated)"
        print(raw)
        print()

        # Per-API breakdown when we have a list and source_api
        if list_key and isinstance(data.get(list_key), list):
            by_api = _per_api_breakdown(data, list_key)
            if by_api:
                print("  Per-API result counts:")
                for api_id, items in by_api.items():
                    print(f"    {api_id}: {len(items)} item(s)")
                    if items and len(items) <= 2:
                        for i, it in enumerate(items[:2]):
                            name = it.get("name", it.get("flight_name", it.get("id", "")))
                            print(f"      [{i+1}] {name}")
                    elif items:
                        name0 = items[0].get("name", items[0].get("flight_name", items[0].get("id", "")))
                        print(f"      e.g. {name0} ...")
                print()

    print("=" * 60)
    print("  Done. See config/api_registry.json and docs/apis-working-and-needed.md for status.")
    print("=" * 60)


if __name__ == "__main__":
    main()
