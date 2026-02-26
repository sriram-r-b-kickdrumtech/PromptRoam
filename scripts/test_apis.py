#!/usr/bin/env python3
"""Lightweight API smoke tests for RapidAPI + OpenWeatherMap.

Usage:
  python scripts/test_apis.py

Relies on env:
  RAPIDAPI_API_KEY
  OPENWEATHERMAP_API_KEY (optional)
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable

import httpx

def _load_env_fallback() -> None:
    try:
        from config.env import load_dotenv_if_present
        load_dotenv_if_present()
        return
    except Exception:
        pass
    # Fallback: minimal .env parser (no interpolation)
    try:
        from pathlib import Path
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if not env_path.is_file():
            return
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")  # basic unquote
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass

_load_env_fallback()

RAPIDAPI_KEY = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
OPENWEATHERMAP_API_KEY = (os.environ.get("OPENWEATHERMAP_API_KEY") or "").strip()


def _rapidapi_headers(host: str) -> dict[str, str] | None:
    if not RAPIDAPI_KEY:
        return None
    return {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
    }


def _try_requests(host: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    headers = _rapidapi_headers(host)
    if headers is None:
        return {"ok": False, "error": "missing RAPIDAPI_API_KEY"}

    last_err = None
    with httpx.Client(timeout=20.0) as client:
        for c in candidates:
            path = c.get("path", "/")
            method = c.get("method", "GET")
            params = c.get("params") or {}
            url = f"https://{host}{path}"
            try:
                if method.upper() == "GET":
                    r = client.get(url, headers=headers, params=params)
                else:
                    r = client.request(method, url, headers=headers, json=params)
                if r.status_code < 400:
                    return {
                        "ok": True,
                        "status": r.status_code,
                        "url": url,
                        "params": params,
                    }
                if r.status_code == 429:
                    return {
                        "ok": True,
                        "rate_limited": True,
                        "status": r.status_code,
                        "url": url,
                        "params": params,
                    }
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                last_err = str(e)
    return {"ok": False, "error": last_err or "unknown error"}


def _test_openweathermap() -> dict[str, Any]:
    if not OPENWEATHERMAP_API_KEY:
        return {"ok": False, "error": "missing OPENWEATHERMAP_API_KEY"}
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": "Goa,IN", "appid": OPENWEATHERMAP_API_KEY, "units": "metric"}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
        if r.status_code < 400:
            return {"ok": True, "status": r.status_code, "url": url, "params": params}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main() -> int:
    tests: list[tuple[str, Callable[[], dict[str, Any]]]] = []

    tests.append((
        "multi-site-flight-search",
        lambda: _try_requests(
            "multi-site-flight-search.p.rapidapi.com",
            [
                {"path": "/flights/airports"},
                {"path": "/flights/auto-complete", "params": {"query": "Delhi", "locale": "en-US", "market": "IN"}},
            ],
        ),
    ))

    tests.append((
        "flight-price-comparison",
        lambda: _try_requests(
            "flight-price-comparison.p.rapidapi.com",
            [
                {"path": "/search", "params": {"origin": "DEL", "destination": "GOI", "date": "2025-04-15"}},
                {"path": "/v1/flights/search", "params": {"origin": "DEL", "destination": "GOI", "date": "2025-04-15"}},
            ],
        ),
    ))

    tests.append((
        "aerodatabox",
        lambda: _try_requests(
            "aerodatabox.p.rapidapi.com",
            [
                {"path": "/airports/search/term", "params": {"q": "Delhi"}},
                {"path": "/airports/search/term", "params": {"term": "Delhi"}},
                {"path": "/airports/search/term", "params": {"query": "Delhi"}},
            ],
        ),
    ))

    tests.append((
        "expedia13",
        lambda: _try_requests(
            "expedia13.p.rapidapi.com",
            [
                {"path": "/2.2/properties/content", "params": {"language": "en-US", "property_id": "1"}},
            ],
        ),
    ))

    tests.append((
        "hotel-api6",
        lambda: _try_requests(
            "hotel-api6.p.rapidapi.com",
            [
                {"path": "/v2/hotels/summary", "params": {"hotel-name": "Taj Mahal Palace"}},
                {"path": "/v2/hotels/search", "params": {"hotel-name": "Taj Mahal Palace"}},
            ],
        ),
    ))

    tests.append((
        "booking-search",
        lambda: _try_requests(
            "booking-search.p.rapidapi.com",
            [
                {"path": "/booking/facilityTypes", "params": {"languages": "en-us"}},
            ],
        ),
    ))

    tests.append((
        "tripadvisor-data",
        lambda: _try_requests(
            "tripadvisor-data.p.rapidapi.com",
            [
                {"path": "/flights/auto-complete", "params": {"query": "Goa", "limit": 3, "language": "en"}},
                {"path": "/location-details", "params": {"location_id": "297604"}},
            ],
        ),
    ))

    tests.append((
        "tripadvisor-scraper",
        lambda: _try_requests(
            "tripadvisor-scraper.p.rapidapi.com",
            [
                {"path": "/tripadvisor/hotels/search", "params": {"query": "Goa", "locale": "en_US"}},
            ],
        ),
    ))

    results: list[dict[str, Any]] = []
    for name, fn in tests:
        start = time.time()
        res = fn()
        res["name"] = name
        res["elapsed_ms"] = int((time.time() - start) * 1000)
        results.append(res)

    results.append({"name": "openweathermap", **_test_openweathermap()})

    ok = True
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        print(f"{r['name']}: {status} ({r.get('status', r.get('error', ''))})")
        if not r.get("ok"):
            ok = False

    if not ok:
        print("\nDetails:")
        for r in results:
            if not r.get("ok"):
                print(f"- {r['name']}: {r.get('error')}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
