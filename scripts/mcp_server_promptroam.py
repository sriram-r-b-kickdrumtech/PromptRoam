#!/usr/bin/env python3
"""
PromptRoam local MCP server: exposes registered APIs as MCP tools.

Uses config/api_registry.json for API list and endpoints. Calls real HTTP APIs
(RapidAPI, OpenWeatherMap) and returns results as MCP tool content.

Run as MCP server (stdio):
  python scripts/mcp_server_promptroam.py

Configure in .env to use this instead of RapidAPI MCP:
  MCP_COMMAND=python
  MCP_ARGS=["scripts/mcp_server_promptroam.py"]
  (and unset or leave empty MCP_FLIGHTS_HOSTS so gateway uses single connection)
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

# Load registry
REGISTRY_PATH = ROOT / "config" / "api_registry.json"
with open(REGISTRY_PATH, encoding="utf-8") as f:
    REGISTRY = json.load(f)
APIS_BY_ID = {a["id"]: a for a in REGISTRY.get("apis", [])}
TOOL_TO_APIS = REGISTRY.get("tool_to_apis", {})


def _rapidapi_headers(host: str) -> dict[str, str]:
    key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    return {"x-rapidapi-key": key, "x-rapidapi-host": host}


def _call_rapidapi(host: str, path: str, params: dict | None = None) -> dict | None:
    import httpx
    url = f"https://{host.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, headers=_rapidapi_headers(host), params=params or {})
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _normalize_flight_item(seg: dict, i: int, origin: str = "", dest: str = "", source: str = "") -> dict:
    dep = (seg.get("departure") or {}).get("airport") or {}
    arr = (seg.get("arrival") or {}).get("airport") or {}
    airline = seg.get("airline") or {}
    return {
        "id": f"F{i+1}",
        "origin": dep.get("name") or dep.get("iata", origin),
        "dest": arr.get("name") or arr.get("iata", dest),
        "flight_name": airline.get("name", "Flight"),
        "flight_number": seg.get("number"),
        "scheduled_departure": (seg.get("departure") or {}).get("scheduledTime", {}).get("local"),
        "scheduled_arrival": (seg.get("arrival") or {}).get("scheduledTime", {}).get("local"),
        "aircraft": (seg.get("aircraft") or {}).get("model"),
        "status": seg.get("status"),
        "source_api": source,
    }


def _collect_flights_from_api(api_id: str, host: str, origin: str, dest: str, date_from: str, date_to: str) -> list:
    out = []
    # Map common city names to IATA if the user didn't provide codes
    iata_map = {"delhi": "DEL", "goa": "GOI", "mumbai": "BOM", "bangalore": "BLR", "london": "LHR", "new york": "JFK"}
    orig_code = iata_map.get(origin.lower(), origin[:3].upper())
    dest_code = iata_map.get(dest.lower(), dest[:3].upper())

    if api_id == "aerodatabox":
        # Search by route instead of hardcoded AI101
        path = f"/flights/from/{orig_code}/to/{dest_code}/{date_from}"
        data = _call_rapidapi(host, path)
        if data and isinstance(data, dict) and "flights" in data:
            for i, seg in enumerate(data["flights"][:5]):
                out.append(_normalize_flight_item(seg, len(out) + 1, origin, dest, "aerodatabox"))
    elif api_id in ("multi-site-flight-search", "flight-price-comparison"):
        for path, params in [
            ("/search", {"from": orig_code, "to": dest_code, "date": date_from}),
            ("/v1/search", {"origin": orig_code, "destination": dest_code, "date": date_from}),
        ]:
            data = _call_rapidapi(host, path, params)
            if data and isinstance(data, dict):
                items = data.get("flights", data.get("data", data.get("results", [])))
                if isinstance(items, list):
                    for i, seg in enumerate(items[:10]):
                        if isinstance(seg, dict):
                            out.append({
                                "id": f"F{len(out)+1}",
                                "origin": seg.get("origin", origin),
                                "dest": seg.get("dest", seg.get("destination", dest)),
                                "flight_name": seg.get("flight_name", seg.get("airline", seg.get("carrier", "Flight"))),
                                "flight_number": seg.get("flight_number", seg.get("number")),
                                "source_api": api_id,
                            })
                    break
    return out


def _tool_search_flights(arguments: dict) -> str:
    origin = (arguments.get("origin") or "Delhi").strip()
    dest = (arguments.get("destination") or "Goa").strip()
    date = (arguments.get("date") or "2025-04-15").strip()[:10]
    from datetime import datetime, timedelta
    try:
        d0 = datetime.strptime(date, "%Y-%m-%d")
        d1 = d0 + timedelta(days=5)
        date_from, date_to = d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d")
    except Exception:
        date_from = date_to = date
    all_flights = []
    for api_id in TOOL_TO_APIS.get("search_flights", []):
        api = APIS_BY_ID.get(api_id)
        if not api or api.get("auth") != "rapidapi":
            continue
        host = api["base_url"].replace("https://", "").split("/")[0]
        flights = _collect_flights_from_api(api_id, host, origin, dest, date_from, date_to)
        for f in flights:
            f["id"] = f"F{len(all_flights)+1}"
            all_flights.append(f)
    return json.dumps({"flights": all_flights, "source": "mcp_promptroam", "sources_used": list(TOOL_TO_APIS.get("search_flights", []))})


def _normalize_hotel_item(h: dict, i: int, source: str) -> dict:
    if not isinstance(h, dict):
        return {"id": f"H{i+1}", "name": str(h), "source_api": source}
    return {
        "id": h.get("id", f"H{i+1}"),
        "name": h.get("name", h.get("title", h.get("hotel_name", ""))),
        "location": h.get("location", h.get("address", h.get("city", ""))),
        "price": h.get("price", h.get("rate", h.get("min_rate"))),
        "source_api": source,
    }


def _tool_search_hotels(arguments: dict) -> str:
    location = (arguments.get("location") or "").strip() or "Goa"
    all_hotels = []
    path_variants = [
        ("/search", {"location": location, "query": location, "city": location}),
        ("/properties/list", {"destinationId": location}),
        ("/v1/hotels/search", {"city": location}),
    ]
    for api_id in TOOL_TO_APIS.get("search_hotels", []):
        api = APIS_BY_ID.get(api_id)
        if not api:
            continue
        host = api["base_url"].replace("https://", "").split("/")[0]
        for path, params in path_variants:
            data = _call_rapidapi(host, path, params)
            if data is None:
                continue
            if isinstance(data, list):
                for i, h in enumerate(data[:10]):
                    all_hotels.append(_normalize_hotel_item(h, len(all_hotels), api_id))
                break
            if isinstance(data, dict):
                hotels = data.get("hotels", data.get("properties", data.get("results", data.get("data", []))))
                if isinstance(hotels, list) and hotels:
                    for i, h in enumerate(hotels[:10]):
                        all_hotels.append(_normalize_hotel_item(h, len(all_hotels), api_id))
                    break
    return json.dumps({"hotels": all_hotels, "source": "mcp_promptroam", "sources_used": list(TOOL_TO_APIS.get("search_hotels", []))})


def _normalize_activity_item(a: dict, i: int, source: str) -> dict:
    if not isinstance(a, dict):
        return {"id": f"A{i+1}", "name": str(a), "source_api": source}
    return {
        "id": a.get("id", a.get("location_id", f"A{i+1}")),
        "name": a.get("name", a.get("title", "")),
        "location": a.get("address", a.get("location_string", "")),
        "rating": a.get("rating", a.get("rating_image_url")),
        "source_api": source,
    }


def _tool_search_activities(arguments: dict) -> str:
    location = (arguments.get("location") or "").strip() or "Goa"
    all_activities = []
    for api_id in TOOL_TO_APIS.get("search_activities", []):
        api = APIS_BY_ID.get(api_id)
        if not api:
            continue
        host = api["base_url"].replace("https://", "").split("/")[0]
        if api_id == "tripadvisor-data":
            for loc_id in ["113992", "274938", "297478"]:
                data = _call_rapidapi(host, "/location-details", {"location_id": loc_id})
                if data and isinstance(data, dict):
                    all_activities.append(_normalize_activity_item(data, len(all_activities), api_id))
        else:
            for path, params in [("/search", {"query": location}), ("/location-details", {"location_id": "113992"})]:
                data = _call_rapidapi(host, path, params)
                if data and isinstance(data, (list, dict)):
                    items = data if isinstance(data, list) else data.get("data", data.get("results", [data]))
                    for a in (items or [])[:10]:
                        all_activities.append(_normalize_activity_item(a, len(all_activities), api_id))
                    break
    return json.dumps({"activities": all_activities, "source": "mcp_promptroam", "sources_used": list(TOOL_TO_APIS.get("search_activities", []))})


def _tool_get_weather(arguments: dict) -> str:
    key = (os.environ.get("OPENWEATHERMAP_API_KEY") or "").strip()
    if not key:
        return json.dumps({"error": "OPENWEATHERMAP_API_KEY not set"})
    q = (arguments.get("q") or arguments.get("location") or "Goa").strip()
    import httpx
    url = "https://api.openweathermap.org/data/2.5/weather"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params={"q": q, "appid": key, "units": "metric"})
        if r.status_code != 200:
            return json.dumps({"error": r.text[:200]})
        return json.dumps(r.json())
    except Exception as e:
        return json.dumps({"error": str(e)})


TOOLS = [
    {
        "name": "search_flights",
        "description": "Search flights by origin, destination, and date. Returns list of flights with airline name, times, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin city or airport"},
                "destination": {"type": "string", "description": "Destination city or airport"},
                "date": {"type": "string", "description": "Travel date YYYY-MM-DD"},
            },
        },
    },
    {
        "name": "search_hotels",
        "description": "Search hotels by location. Optional max_budget.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "max_budget": {"type": "integer"},
            },
        },
    },
    {
        "name": "search_activities",
        "description": "Search activities/attractions by location and interests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "interests": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city (OpenWeatherMap).",
        "inputSchema": {
            "type": "object",
            "properties": {"q": {"type": "string"}, "location": {"type": "string"}},
        },
    },
]

TOOL_HANDLERS = {
    "search_flights": _tool_search_flights,
    "search_hotels": _tool_search_hotels,
    "search_activities": _tool_search_activities,
    "get_weather": _tool_get_weather,
}


def handle_tools_list() -> dict:
    return {"tools": TOOLS}


def handle_tools_call(name: str, arguments: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}], "isError": True}
    try:
        text = handler(arguments or {})
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True}


def read_message() -> dict | None:
    """Read one MCP message: Content-Length header then JSON body."""
    line = sys.stdin.readline()
    if not line:
        return None
    if not line.lower().startswith("content-length:"):
        return None
    try:
        length = int(line.split(":", 1)[1].strip())
    except (ValueError, IndexError):
        return None
    if sys.stdin.readline().strip() != "":
        pass  # blank line after header
    body = sys.stdin.read(length) if length else ""
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def write_message(obj: dict) -> None:
    """Write one MCP message with Content-Length framing."""
    body = json.dumps(obj, separators=(",", ":"))
    sys.stdout.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
    sys.stdout.flush()


def main() -> None:
    while True:
        msg = read_message()
        if msg is None:
            break
        method = msg.get("method")
        params = msg.get("params") or {}
        msg_id = msg.get("id")
        result = None
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "promptroam-mcp", "version": "1.0.0"}}
        elif method == "tools/list":
            result = handle_tools_list()
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            result = handle_tools_call(name, args)
        if result is not None and msg_id is not None:
            write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


if __name__ == "__main__":
    main()
