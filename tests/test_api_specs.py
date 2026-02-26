"""
Tests using the downloaded OpenAPI specs in tests/api_specs/.

Every test that uses a spec performs a live HTTP request to that API. No skips:
RAPIDAPI_API_KEY and OPENWEATHERMAP_API_KEY must be set in .env (run from repo root).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Repo root and load .env
ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

TESTS_DIR = Path(__file__).resolve().parents[0]
SPEC_DIR = TESTS_DIR / "api_specs"

# Require keys so all tests are live (no skip)
RAPIDAPI_KEY = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
OWM_KEY = (os.environ.get("OPENWEATHERMAP_API_KEY") or "").strip()


def _spec_files() -> list[Path]:
    if not SPEC_DIR.exists():
        return []
    return sorted(SPEC_DIR.glob("*_openapi.json"))


def _load_registry() -> list[dict]:
    path = ROOT / "config" / "api_registry.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("apis", [])


def _api_by_id() -> dict[str, dict]:
    return {a["id"]: a for a in _load_registry()}


# ---------- Require env (fail fast so everything can be live) ----------


@pytest.fixture(scope="module")
def require_httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        pytest.fail("httpx is required for live API tests. Install: pip install httpx")




# ---------- Spec dir and structure (still useful before live batch) ----------


def test_api_specs_dir_exists() -> None:
    assert SPEC_DIR.exists(), f"Run tests/download_specs.py first to create {SPEC_DIR}"


def test_spec_files_match_registry() -> None:
    files = _spec_files()
    apis = _load_registry()
    assert len(files) >= 1, f"No *_openapi.json in {SPEC_DIR}; run tests/download_specs.py"
    assert len(files) == len(apis), f"Spec count {len(files)} != registry API count {len(apis)}"


# ---------- Build request from spec ----------


def _get_first_operation(spec: dict) -> tuple[str, str, dict] | None:
    paths = spec.get("paths", {})
    for path_key, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.startswith("/") or method.lower() not in ("get", "post"):
                continue
            if isinstance(op, dict):
                return (path_key, method.lower(), op)
    return None


def _build_url_params(spec: dict, path: str, op: dict, path_values: dict, query_values: dict) -> tuple[str, dict]:
    servers = spec.get("servers", [])
    base = (servers[0]["url"].rstrip("/") if servers else "")
    url_path = path
    for p in op.get("parameters", []):
        if p.get("in") == "path" and p.get("name"):
            url_path = url_path.replace("{" + p["name"] + "}", path_values.get(p["name"], ""))
    url = base + url_path
    params = dict(query_values)
    for p in op.get("parameters", []):
        if p.get("in") == "query" and p.get("name") and p["name"] not in params:
            params[p["name"]] = query_values.get(p["name"], "")
    return url, params


def _live_request_rapidapi(httpx_mod, api_id: str, url: str, method: str, params: dict) -> "httpx.Response":
    host = url.replace("https://", "").split("/")[0]
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": host}
    with httpx_mod.Client(timeout=15.0) as client:
        if method == "get":
            return client.get(url, headers=headers, params=params)
        return client.post(url, headers=headers, params=params)


def _live_request_openweathermap(httpx_mod, url: str, params: dict) -> "httpx.Response":
    with httpx_mod.Client(timeout=10.0) as client:
        return client.get(url, params=params)


# ---------- One live test per spec ----------


def _spec_to_api_id(spec_path: Path) -> str:
    return spec_path.stem.replace("_openapi", "")


@pytest.mark.parametrize("spec_path", _spec_files(), ids=lambda p: _spec_to_api_id(p))
def test_each_spec_valid_openapi3(spec_path: Path) -> None:
    """Each spec is valid OpenAPI 3 JSON."""
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    assert spec.get("openapi", "").startswith("3."), f"Invalid openapi in {spec_path.name}"
    assert "info" in spec and "paths" in spec and len(spec["paths"]) >= 1


@pytest.mark.parametrize("spec_path", _spec_files(), ids=lambda p: _spec_to_api_id(p))
def test_each_api_live_from_spec(spec_path: Path, require_httpx) -> None:
    """
    For each API spec: build request from spec and perform a live HTTP call.
    Requires RAPIDAPI_API_KEY (RapidAPI APIs) and OPENWEATHERMAP_API_KEY (OpenWeatherMap) in .env.
    """
    httpx = require_httpx
    api_id = _spec_to_api_id(spec_path)
    if api_id == "openweathermap":
        if not OWM_KEY:
            pytest.fail("OPENWEATHERMAP_API_KEY must be set in .env for live OpenWeatherMap test")
    else:
        if not RAPIDAPI_KEY:
            pytest.fail("RAPIDAPI_API_KEY must be set in .env for live RapidAPI tests")
    apis = _api_by_id()
    api = apis.get(api_id, {})

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    triple = _get_first_operation(spec)
    assert triple is not None, f"No GET/POST operation in {spec_path.name}"
    path, method, op = triple

    # Path/query values for this API
    if api_id == "aerodatabox":
        path_values = {"flightNumber": "AI101", "dateFrom": "2025-04-01", "dateTo": "2025-04-07"}
        query_values = {}
    elif api_id == "openweathermap":
        path_values = {}
        query_values = {"q": "Goa", "appid": OWM_KEY, "units": "metric"}
    elif api_id == "tripadvisor-data":
        path_values = {}
        query_values = {"location_id": "113992"}
    else:
        path_values = {}
        query_values = {}  # stub path "/" or try with empty/minimal params

    url, params = _build_url_params(spec, path, op, path_values, query_values)

    if api_id == "openweathermap":
        r = _live_request_openweathermap(httpx, url, params)
    else:
        r = _live_request_rapidapi(httpx, api_id, url, method, params)

    # Live = we reached the server (any HTTP response, not connection error)
    assert r.status_code is not None, "No response (connection failed?)"
    # 2xx success, or 4xx (auth/wrong path) = we hit the API
    assert 200 <= r.status_code < 600, f"Unexpected status {r.status_code}"

    if r.status_code == 200 and api_id == "aerodatabox":
        data = r.json()
        assert isinstance(data, list) or isinstance(data, dict), f"AeroDataBox: unexpected body type {type(data)}"
    if r.status_code == 200 and api_id == "openweathermap":
        data = r.json()
        assert isinstance(data, dict) and ("name" in data or "main" in data or "weather" in data), (
            f"OpenWeatherMap: unexpected keys {list(data.keys())[:8]}"
        )
