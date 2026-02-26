"""
RapidAPI client for LangGraph nodes. Key is read from env at runtime only.

No keys in config files. When a node runs, it calls get_rapidapi_headers(host)
or call_rapidapi(...); the key is taken from os.environ["RAPIDAPI_API_KEY"] at that time.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Host registry (key-free): logical name -> RapidAPI host
# Matches .mcp_secrets subscribed APIs; key is never stored here
RAPIDAPI_HOSTS: dict[str, str] = {
    "flights": "multi-site-flight-search.p.rapidapi.com",
    "flights_skyscanner": "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
    "flights_aerodatabox": "aerodatabox.p.rapidapi.com",
    "flights_airscraper": "sky-scrapper.p.rapidapi.com",
    "booking_com": "booking-com15.p.rapidapi.com",
    "hotels": "hotel-api6.p.rapidapi.com",
    "expedia": "expedia13.p.rapidapi.com",
    "booking": "booking-search.p.rapidapi.com",
    "tripadvisor": "tripadvisor-scraper.p.rapidapi.com",
    "tripadvisor_data": "tripadvisor-data.p.rapidapi.com",
}


def get_rapidapi_key() -> str:
    """Read RapidAPI key from env at runtime. No key in files."""
    return (os.environ.get("RAPIDAPI_API_KEY") or "").strip()


def get_rapidapi_headers(host_key: str) -> dict[str, str] | None:
    """
    Headers for RapidAPI (x-api-key from env, x-api-host from registry).
    Returns None if key is missing (caller should fall back to stub).
    """
    key = get_rapidapi_key()
    if not key:
        return None
    host = RAPIDAPI_HOSTS.get(host_key) or host_key
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": host,
    }


def call_rapidapi(
    host_key: str,
    path: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    cache_ttl_seconds: int | None = 3600,
) -> dict[str, Any] | None:
    """
    Call RapidAPI endpoint. Key from env at call time. Responses are cached in Redis
    (when REDIS_URL or REDIS_PORT is set) to reduce cost and latency.
    Returns None if key missing or request fails (node can fall back to stub).
    """
    # Cache lookup (Redis on separate port from existing cluster)
    if cache_ttl_seconds:
        try:
            from src.cache import cache_get
            cached = cache_get(host_key, path, method, params)
            if cached is not None:
                return cached
        except Exception:
            pass

    headers = get_rapidapi_headers(host_key)
    if not headers:
        return None
    try:
        import httpx
        url = f"https://{headers['x-rapidapi-host']}{path}"
        with httpx.Client(timeout=15.0) as client:
            if method.upper() == "GET":
                r = client.get(url, headers=headers, params=params or {})
            else:
                r = client.request(method, url, headers=headers, json=params or {})
            r.raise_for_status()
            data = r.json()
            # Store in cache for next time
            if cache_ttl_seconds and data is not None:
                try:
                    from src.cache import cache_set
                    cache_set(host_key, path, method, params, data, ttl_seconds=cache_ttl_seconds)
                except Exception:
                    pass
            return data
    except Exception:
        return None


# IATA-like codes for common Indian cities (Skyscanner uses {code}-sky)
_CITY_TO_PLACE: dict[str, str] = {
    "delhi": "DEL-sky",
    "mumbai": "BOM-sky",
    "bombay": "BOM-sky",
    "goa": "GOI-sky",
    "bangalore": "BLR-sky",
    "bengaluru": "BLR-sky",
    "chennai": "MAA-sky",
    "hyderabad": "HYD-sky",
    "kolkata": "CCU-sky",
    "kochi": "COK-sky",
    "jaipur": "JAI-sky",
    "udaipur": "UDR-sky",
}


def _origin_dest_to_places(origin: str, dest: str) -> tuple[str, str]:
    """Convert city names to Skyscanner place IDs (e.g. DEL-sky)."""
    o = (origin or "").strip().lower()
    d = (dest or "").strip().lower()
    return (_CITY_TO_PLACE.get(o) or (o[:3].upper() + "-sky" if len(o) >= 2 else "DEL-sky"), _CITY_TO_PLACE.get(d) or (d[:3].upper() + "-sky" if len(d) >= 2 else "BOM-sky"))


def _aerodatabox_flights(origin: str, dest: str, date: str) -> list[dict[str, Any]]:
    """Call Aerodatabox for flights by route. Returns normalized list."""
    headers = get_rapidapi_headers("flights_aerodatabox")
    if not headers:
        return []
    
    # Map common city names to IATA
    iata_map = {"delhi": "DEL", "goa": "GOI", "mumbai": "BOM", "bangalore": "BLR", "london": "LHR", "new york": "JFK"}
    orig_code = iata_map.get(origin.lower(), origin[:3].upper())
    dest_code = iata_map.get(dest.lower(), dest[:3].upper())
    
    date_from = date[:10]
    path = f"/flights/from/{orig_code}/to/{dest_code}/{date_from}"
    url = f"https://{headers['x-rapidapi-host']}{path}"
    
    import httpx
    all_flights: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            items = data.get("flights", [])
            if isinstance(items, list):
                for i, seg in enumerate(items[:10]):
                    if not isinstance(seg, dict):
                        continue
                    dep = (seg.get("departure") or {}).get("airport") or {}
                    arr = (seg.get("arrival") or {}).get("airport") or {}
                    airline = (seg.get("airline") or {})
                    flight_name = airline.get("name") or seg.get("number") or "Flight"
                    all_flights.append({
                        "id": f"F{len(all_flights) + 1}",
                        "origin": dep.get("name") or dep.get("iata", origin),
                        "dest": arr.get("name") or arr.get("iata", dest),
                        "flight_name": flight_name,
                        "flight_number": seg.get("number"),
                        "scheduled_departure": (seg.get("departure") or {}).get("scheduledTime", {}).get("local"),
                        "scheduled_arrival": (seg.get("arrival") or {}).get("scheduledTime", {}).get("local"),
                        "aircraft": (seg.get("aircraft") or {}).get("model"),
                        "status": seg.get("status"),
                    })
    except Exception:
        pass
    return all_flights


def search_flights_direct(origin: str, dest: str, date: str) -> dict[str, Any] | None:
    """
    Call a flight search API directly with RAPIDAPI_API_KEY. Tries Skyscanner first; if not subscribed
    falls back to Aerodatabox (flight-by-route) so you still get real flight names.
    Returns normalized dict with "flights" list. Used when MCP returns nothing.
    """
    key = get_rapidapi_key()
    if not key:
        return None
    origin_place, dest_place = _origin_dest_to_places(origin, dest)
    path = f"/apiservices/browseroutes/v1.0/IN/INR/en-IN/{origin_place}/{dest_place}/{date}"
    headers = get_rapidapi_headers("flights_skyscanner")
    if headers:
        try:
            import httpx
            url = f"https://{headers['x-rapidapi-host']}{path}"
            with httpx.Client(timeout=20.0) as client:
                r = client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                carriers = {c["CarrierId"]: c.get("Name", c.get("DisplayCode", str(c["CarrierId"]))) for c in (data.get("Carriers") or []) if isinstance(c, dict)}
                places = {p["PlaceId"]: p.get("Name", p.get("SkyscannerCode", p["PlaceId"])) for p in (data.get("Places") or []) if isinstance(p, dict)}
                quotes = data.get("Quotes") or []
                flights: list[dict[str, Any]] = []
                for i, q in enumerate(quotes[:20]):
                    if not isinstance(q, dict):
                        continue
                    outbound = q.get("OutboundLeg") or {}
                    carrier_ids = outbound.get("CarrierIds") or []
                    flight_name = (carriers.get(carrier_ids[0], "") if carrier_ids else "") or "Flight"
                    origin_id = outbound.get("OriginId")
                    dest_id = outbound.get("DestinationId")
                    flights.append({
                        "id": f"F{i+1}",
                        "origin": places.get(origin_id, origin) if origin_id else origin,
                        "dest": places.get(dest_id, dest) if dest_id else dest,
                        "flight_name": flight_name,
                        "min_price": q.get("MinPrice"),
                        "direct": q.get("Direct", False),
                    })
                if flights:
                    return {"flights": flights, "source": "rapidapi_direct"}
        except Exception:
            pass
    # Fallback: Aerodatabox (by route)
    aerodata = _aerodatabox_flights(origin, dest, date)
    if aerodata:
        return {"flights": aerodata, "source": "rapidapi_direct_aerodatabox"}
    return None
