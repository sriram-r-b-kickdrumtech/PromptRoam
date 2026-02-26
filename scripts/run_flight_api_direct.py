"""
Run the flight API directly with RAPIDAPI_API_KEY and log the full response.

Usage (from repo root, .env loaded via dotenv):
  python scripts/run_flight_api_direct.py
  python scripts/run_flight_api_direct.py --origin Mumbai --dest Goa --date 2025-04-15
  python scripts/run_flight_api_direct.py --probe   # try several flight APIs and log which work

When one API returns 200, we log the full raw response and the normalized result (same shape
as the graph uses). The graph falls back to this direct call when MCP returns nothing.
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

# (host, path, params) to probe for flight search – first 200 with body wins
FLIGHT_API_PROBES: list[tuple[str, str, str, dict]] = [
    ("skyscanner-skyscanner-flight-search-v1.p.rapidapi.com", "/apiservices/browseroutes/v1.0/IN/INR/en-IN/DEL-sky/GOI-sky/2025-04-15", "GET", {}),
    ("multi-site-flight-search.p.rapidapi.com", "/search", "GET", {"from": "DEL", "to": "BOM", "date": "2025-04-15"}),
    ("multi-site-flight-search.p.rapidapi.com", "/v1/search", "GET", {"from": "DEL", "to": "BOM", "date": "2025-04-15"}),
    ("aerodatabox.p.rapidapi.com", "/flights/number/AI101/2025-04-01/2025-04-15", "GET", {}),
    ("sky-scrapper.p.rapidapi.com", "/search", "GET", {"from": "DEL", "to": "GOI", "date": "2025-04-15"}),
]


def main() -> int:
    key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    if not key:
        print("RAPIDAPI_API_KEY not set. Set in .env and run again.", file=sys.stderr)
        return 1

    origin = "Delhi"
    dest = "Goa"
    date = "2025-04-15"
    if "--origin" in sys.argv:
        i = sys.argv.index("--origin")
        if i + 1 < len(sys.argv):
            origin = sys.argv[i + 1]
    if "--dest" in sys.argv:
        i = sys.argv.index("--dest")
        if i + 1 < len(sys.argv):
            dest = sys.argv[i + 1]
    if "--date" in sys.argv:
        i = sys.argv.index("--date")
        if i + 1 < len(sys.argv):
            date = sys.argv[i + 1]

    import httpx
    from src.rapidapi_client import get_rapidapi_headers, _origin_dest_to_places, search_flights_direct

    if "--probe" in sys.argv:
        print("Probing flight APIs with your key (full response logged for each):\n")
        for host, path, method, params in FLIGHT_API_PROBES:
            url = f"https://{host}{path}"
            headers = {"x-rapidapi-key": key, "x-rapidapi-host": host}
            try:
                with httpx.Client(timeout=15.0) as client:
                    r = client.get(url, headers=headers, params=params) if method == "GET" else client.post(url, headers=headers, json=params)
                print(f"--- {host} {path} -> {r.status_code} ---")
                try:
                    print(json.dumps(r.json(), indent=2, default=str)[:4000])
                except Exception:
                    print(r.text[:2000])
                if r.status_code == 200:
                    print("  ^ 200 OK – use this host in MCP_FLIGHTS_HOSTS or we use it as direct fallback.")
                print()
            except Exception as e:
                print(f"  Error: {e}\n")
        return 0

    print(f"Calling flight API directly: origin={origin} dest={dest} date={date}")
    print("(Same key as MCP; graph falls back to this when MCP returns nothing.)\n")

    # 1) Raw API call and log full response (Skyscanner first; if not subscribed we still try direct and show stub)
    origin_place, dest_place = _origin_dest_to_places(origin, dest)
    path = f"/apiservices/browseroutes/v1.0/IN/INR/en-IN/{origin_place}/{dest_place}/{date}"
    headers = get_rapidapi_headers("flights_skyscanner")
    if not headers:
        print("No RAPIDAPI_API_KEY or host.", file=sys.stderr)
        return 1
    url = f"https://{headers['x-rapidapi-host']}{path}"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, headers=headers)
        print(f"=== Raw API response (status={r.status_code}) ===")
        try:
            raw = r.json()
            print(json.dumps(raw, indent=2, default=str))
        except Exception:
            print(r.text[:2000])
        if r.status_code != 200:
            print("Non-200. Run with --probe to try other flight APIs; subscribe to one and set MCP_FLIGHTS_HOSTS.")
            # Still try normalized path (may use different API in future)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)

    # 2) Normalized result (same shape graph uses when MCP is unavailable)
    result = search_flights_direct(origin, dest, date)
    if result is None:
        print("\nNormalized result: None. Subscribe to a flight API (e.g. Skyscanner) or run with --probe.")
        return 0

    print("\n=== Normalized result (same shape as graph / MCP) ===")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
