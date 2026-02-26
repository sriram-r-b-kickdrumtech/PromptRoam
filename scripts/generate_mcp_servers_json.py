"""
Generate mcpServers JSON from .env so you can use RapidAPI MCP in Cursor or other clients.

RapidAPI MCP uses:
  - x-api-host: <variable>  (one per API, e.g. aerodatabox.p.rapidapi.com)
  - x-api-key: <key>        (your RAPIDAPI_API_KEY)

Run from repo root (loads .env):
  python scripts/generate_mcp_servers_json.py

Output is valid JSON you can paste into Cursor MCP config or use as reference.
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

# Env keys for per-category hosts (same as mcp_gateway)
MCP_FLIGHTS_HOSTS = "MCP_FLIGHTS_HOSTS"
MCP_HOTELS_HOSTS = "MCP_HOTELS_HOSTS"
MCP_ACTIVITIES_HOSTS = "MCP_ACTIVITIES_HOSTS"


def _hosts(env_key: str) -> list[str]:
    raw = (os.environ.get(env_key) or "").strip()
    if not raw:
        return []
    return [h.strip() for h in raw.split(",") if h.strip()][:3]


def main() -> int:
    use_template = "--template" in sys.argv
    key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    if not key and not use_template:
        print("RAPIDAPI_API_KEY not set in .env (use --template to output placeholders only).", file=sys.stderr)
        return 1
    if use_template:
        key = "key"  # placeholder

    mcp_servers: dict[str, dict] = {}

    # One server entry per category; variable = x-api-host, key = RAPIDAPI_API_KEY
    for env_key, label in [
        (MCP_FLIGHTS_HOSTS, "rapidapi-flights"),
        (MCP_HOTELS_HOSTS, "rapidapi-hotels"),
        (MCP_ACTIVITIES_HOSTS, "rapidapi-activities"),
    ]:
        hosts = _hosts(env_key)
        if use_template:
            mcp_servers[label] = {
                "command": "npx",
                "args": [
                    "mcp-remote",
                    "https://mcp.rapidapi.com",
                    "--header",
                    "x-api-host: variable",
                    "--header",
                    "x-api-key: key",
                ],
            }
            continue
        if not hosts:
            continue
        # Use first host for this category; app tries rest on failure
        variable = hosts[0]
        mcp_servers[label] = {
            "command": "npx",
            "args": [
                "mcp-remote",
                "https://mcp.rapidapi.com",
                "--header",
                f"x-api-host: {variable}",
                "--header",
                f"x-api-key: {key}",
            ],
        }

    out = {"mcpServers": mcp_servers}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
