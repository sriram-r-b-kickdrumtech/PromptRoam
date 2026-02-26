"""
Test each RapidAPI once. Key from env (load .env in script).
Remove failing APIs from registry if others pass; if all fail, config issue.
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

import httpx

# (host_key, host, path, params) - minimal GET to probe each API
# 200 = pass; 400/404/422 = key accepted, wrong params = pass; 401/403 = fail
TESTS: list[tuple[str, str, str, dict]] = [
    ("aerodatabox", "aerodatabox.p.rapidapi.com", "/flights/number/KL1395", {}),
    ("multi-site-flight-search", "multi-site-flight-search.p.rapidapi.com", "/get-config", {}),
    ("flight-price-comparison", "flight-price-comparison.p.rapidapi.com", "/get-config", {}),
    ("hotel-api6", "hotel-api6.p.rapidapi.com", "/search-location", {"query": "London"}),
    ("expedia13", "expedia13.p.rapidapi.com", "/properties/content", {"propertyId": "123"}),
    ("booking", "booking-search.p.rapidapi.com", "/v1/hotels/locations", {"name": "London"}),
    ("tripadvisor_scraper", "tripadvisor-scraper.p.rapidapi.com", "/hotels/list", {"location": "London"}),
    ("tripadvisor_data", "tripadvisor-data.p.rapidapi.com", "/locations/search", {"query": "London"}),
]


def main() -> int:
    key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    if not key:
        print("RAPIDAPI_API_KEY not set. Set in .env and run again.", file=sys.stderr)
        return 1

    results: list[tuple[str, bool, str]] = []
    for host_key, host, path, params in TESTS:
        url = f"https://{host}{path}"
        headers = {"x-rapidapi-key": key, "x-rapidapi-host": host}
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, headers=headers, params=params)
            # 401/403 = key or subscription problem; 200/400/404/422 = key accepted
            ok = r.status_code not in (401, 403)
            msg = f"HTTP {r.status_code}" + (f" - {r.text[:60]}" if r.text else "")
            results.append((host_key, ok, msg))
            status = "PASS" if ok else "FAIL"
            print(f"  {host_key}: {status} - {msg}")
        except Exception as e:
            results.append((host_key, False, str(e)))
            print(f"  {host_key}: FAIL - {e}")

    passed = sum(1 for _, ok, _ in results if ok)
    failed_keys = [k for k, ok, _ in results if not ok]
    print(f"\nPassed: {passed}/{len(results)}")
    if passed == 0:
        print("All failed. Check RAPIDAPI_API_KEY and subscriptions.", file=sys.stderr)
        return 1
    if failed_keys:
        print(f"Failing APIs (candidates to remove): {failed_keys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
