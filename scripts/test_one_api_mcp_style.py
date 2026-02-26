"""
Test one API the same way it would be called via MCP (same backend, same key from env).

This script performs the HTTP request that an MCP tool would trigger when you ask
e.g. "get TripAdvisor location details for location_id 113992". MCP and direct HTTP
both hit RapidAPI with x-api-key (from env) and x-api-host.

Input:  host_key = "tripadvisor_data", path = "/location-details", params = {"location_id": "113992"}
Call:   GET https://tripadvisor-data.p.rapidapi.com/location-details?location_id=113992
        Headers: x-rapidapi-key=<from env>, x-rapidapi-host=tripadvisor-data.p.rapidapi.com
"""
from __future__ import annotations

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

# Same registry as LangGraph node
from src.rapidapi_client import get_rapidapi_headers, RAPIDAPI_HOSTS


def main() -> int:
    host_key = "tripadvisor_data"
    path = "/location-details"
    params = {"location_id": "113992"}

    key = os.environ.get("RAPIDAPI_API_KEY", "").strip()
    if not key:
        print("RAPIDAPI_API_KEY not set in .env", file=sys.stderr)
        return 1

    host = RAPIDAPI_HOSTS.get(host_key)
    if not host:
        print(f"Unknown host_key: {host_key}", file=sys.stderr)
        return 1

    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": host,
    }
    url = f"https://{host}{path}"

    print("--- Input (same as MCP tool call) ---")
    print(f"  host_key: {host_key}")
    print(f"  path: {path}")
    print(f"  params: {params}")
    print("--- How this is called (MCP uses same key + host) ---")
    print(f"  GET {url}")
    print(f"  Headers: x-rapidapi-key=<from env>, x-rapidapi-host={host}")
    print()

    import httpx
    try:
        r = httpx.get(url, headers=headers, params=params, timeout=15.0)
        print("--- Result ---")
        print(f"  HTTP status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Response (truncated): {str(data)[:500]}...")
        else:
            print(f"  Body: {r.text[:300]}")
        return 0 if r.status_code == 200 else 1
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
