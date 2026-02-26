"""
Download OpenAPI/API specs for all APIs in config/api_registry.json.

- RapidAPI APIs: tries RapidAPI spec endpoint (with API key from .env).
- OpenWeatherMap: builds a minimal OpenAPI 3 spec from registry endpoints and saves it.

Run from repo root (so config and .env are found):
  python tests/download_specs.py

Requires: RAPIDAPI_API_KEY in .env for RapidAPI specs.
Output: tests/api_specs/<api_id>_openapi.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

# Load registry
REGISTRY_PATH = ROOT / "config" / "api_registry.json"
OUTPUT_DIR = ROOT / "tests" / "api_specs"

# RapidAPI spec endpoint (api_id may be internal id or provider/api/slug)
RAPIDAPI_SPEC_BASE = "https://rapidapi.com/api/v1/apis"


def _load_registry() -> tuple[list[dict], dict]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    apis = data.get("apis", [])
    tool_to_apis = data.get("tool_to_apis", {})
    return apis, tool_to_apis


def _rapidapi_spec_candidate_ids(api: dict) -> list[str]:
    """Return candidate api_id values to try for RapidAPI spec URL."""
    reg_id = api.get("id", "")
    docs = (api.get("docs_url") or "").strip()
    candidates = [reg_id]
    # From docs_url like https://rapidapi.com/airlineconsolidator/api/multi-site-flight-search
    if "rapidapi.com/" in docs:
        match = re.search(r"rapidapi\.com/([^/#?\s]+)", docs)
        if match:
            path = match.group(1).rstrip("/")
            if path and path != reg_id:
                candidates.append(path)
    return candidates


def _fetch_rapidapi_spec(api: dict, key: str) -> dict | None:
    if not httpx or not key:
        return None
    # RapidAPI spec endpoint: try both host headers (dashboard vs hub)
    for host in ("rapidapi.p.rapidapi.com", "rapidapi.com"):
        headers = {
            "X-RapidAPI-Key": key,
            "X-RapidAPI-Host": host,
            "Accept": "application/json",
        }
        for candidate in _rapidapi_spec_candidate_ids(api):
            url = f"https://rapidapi.com/api/v1/apis/{candidate}/spec"
            try:
                with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                    r = client.get(url, headers=headers)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        pass
            except Exception:
                continue
    return None


def _build_openweathermap_spec(api: dict) -> dict:
    """Build minimal OpenAPI 3 spec for OpenWeatherMap from registry."""
    base = (api.get("base_url") or "https://api.openweathermap.org/data/2.5").rstrip("/")
    endpoints = api.get("endpoints", [])
    paths: dict = {}
    for ep in endpoints:
        path_key = (ep.get("path") or "/weather").strip()
        if not path_key.startswith("/"):
            path_key = "/" + path_key
        params = []
        for p in ep.get("params_query") or []:
            params.append({
                "name": p,
                "in": "query",
                "required": p == "appid",
                "schema": {"type": "string"},
            })
        paths[path_key] = {
            "get": {
                "summary": (ep.get("description") or path_key),
                "parameters": params,
                "responses": {"200": {"description": "Success"}},
            }
        }
    return {
        "openapi": "3.0.0",
        "info": {
            "title": api.get("name", "OpenWeatherMap"),
            "version": "1.0.0",
        },
        "servers": [{"url": base}],
        "paths": paths,
    }


def _build_stub_spec(api: dict) -> dict:
    """Build stub OpenAPI 3 spec (base_url + placeholder path) when no endpoints in registry."""
    base = (api.get("base_url") or "").rstrip("/")
    return {
        "openapi": "3.0.0",
        "info": {"title": api.get("name", api.get("id", "API")), "version": "1.0.0"},
        "servers": [{"url": base}] if base else [],
        "paths": {
            "/": {"get": {"summary": "Placeholder (endpoints from RapidAPI page)", "responses": {"200": {"description": "OK"}}}},
        },
    }


def _build_minimal_spec_from_registry(api: dict) -> dict:
    """Build minimal OpenAPI 3 spec from registry endpoints (for any API with endpoints)."""
    base = (api.get("base_url") or "").rstrip("/")
    endpoints = api.get("endpoints", [])
    paths: dict = {}
    for ep in endpoints:
        path_key = (ep.get("path") or "/").strip()
        if not path_key.startswith("/"):
            path_key = "/" + path_key
        params = []
        for p in ep.get("params_path") or []:
            params.append({
                "name": p,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            })
        for p in ep.get("params_query") or []:
            params.append({
                "name": p,
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
            })
        method = (ep.get("method") or "get").lower()
        paths[path_key] = {
            method: {
                "summary": (ep.get("description") or path_key),
                "parameters": params,
                "responses": {"200": {"description": "Success"}},
            }
        }
    return {
        "openapi": "3.0.0",
        "info": {
            "title": api.get("name", api.get("id", "API")),
            "version": "1.0.0",
        },
        "servers": [{"url": base}] if base else [],
        "paths": paths,
    }


def download_specs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    apis, _ = _load_registry()
    rapidapi_key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()

    for api in apis:
        api_id = api.get("id", "unknown")
        name = api.get("name", api_id)
        auth = api.get("auth", "")
        out_path = OUTPUT_DIR / f"{api_id}_openapi.json"

        if auth == "rapidapi":
            spec = _fetch_rapidapi_spec(api, rapidapi_key)
            if spec:
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(spec, f, indent=2)
                print(f"  [OK] {api_id}: saved RapidAPI spec -> {out_path}")
            else:
                # Fallback: generate minimal spec from registry, or a stub with base_url
                spec = _build_minimal_spec_from_registry(api) if api.get("endpoints") else _build_stub_spec(api)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(spec, f, indent=2)
                print(f"  [OK] {api_id}: saved minimal/stub spec -> {out_path}")
        elif api_id == "openweathermap" or (auth != "rapidapi" and api.get("base_url")):
            spec = _build_openweathermap_spec(api) if api_id == "openweathermap" else _build_minimal_spec_from_registry(api)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            print(f"  [OK] {api_id}: saved generated spec -> {out_path}")
        else:
            spec = _build_minimal_spec_from_registry(api) if api.get("endpoints") else _build_stub_spec(api)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            print(f"  [OK] {api_id}: saved minimal/stub spec -> {out_path}")


if __name__ == "__main__":
    if not REGISTRY_PATH.exists():
        print(f"Registry not found: {REGISTRY_PATH}")
        sys.exit(1)
    if not httpx:
        print("Install httpx: pip install httpx")
        sys.exit(1)
    print("Downloading specs for all APIs in api_registry.json...")
    print(f"Output dir: {OUTPUT_DIR}\n")
    download_specs()
    print("\nDone.")
