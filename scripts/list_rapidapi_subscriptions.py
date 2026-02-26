"""
List RapidAPI subscriptions for the key in RAPIDAPI_API_KEY.

Uses RapidAPI GraphQL Platform API when available. Run from repo root with .env loaded:
  python scripts/list_rapidapi_subscriptions.py

If the Platform API is not available for your hub, use the dashboard:
  https://rapidapi.com/developer/dashboard → Subscriptions & Usage
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

# GraphQL Platform API (public hub – may require subscription to this API)
GRAPHQL_URL = "https://graphql-platform.p.rapidapi.com/"
GRAPHQL_HOST = "graphql-platform.p.rapidapi.com"

SUBSCRIPTIONS_QUERY = """
query subscriptions($where: SubscriptionsWhereInput, $pagination: PaginationInput) {
  subscriptions(where: $where, pagination: $pagination) {
    nodes {
      id
      userId
      apiId
      status
    }
    totalCount
  }
}
"""


def main() -> None:
    key = os.environ.get("RAPIDAPI_API_KEY", "").strip()
    if not key:
        print("Missing RAPIDAPI_API_KEY in environment. Set it in .env and run again.")
        sys.exit(1)

    app_name = os.environ.get("RAPIDAPI_APP_NAME", "")
    if app_name:
        print(f"Application: {app_name}\n")

    headers = {
        "content-type": "application/json",
        "x-rapidapi-host": GRAPHQL_HOST,
        "x-rapidapi-key": key,
    }
    payload = {
        "operationName": "subscriptions",
        "query": SUBSCRIPTIONS_QUERY,
        "variables": {"where": {}, "pagination": {"first": 50}},
    }

    try:
        resp = httpx.post(GRAPHQL_URL, headers=headers, json=payload, timeout=15.0)
        data = resp.json()
    except Exception as e:
        print(f"Request failed: {e}")
        print("\nList your subscribed APIs in the dashboard instead:")
        print("  https://rapidapi.com/developer/dashboard")
        print("  → Subscriptions & Usage")
        sys.exit(1)

    if "errors" in data:
        print("GraphQL errors (Platform API may be for Enterprise Hub only):")
        print(json.dumps(data["errors"], indent=2))
        print("\nList your subscribed APIs in the dashboard instead:")
        print("  https://rapidapi.com/developer/dashboard → Subscriptions & Usage")
        sys.exit(1)

    subs = data.get("data", {}).get("subscriptions", {})
    nodes = subs.get("nodes", [])
    total = subs.get("totalCount", len(nodes))

    if not nodes:
        print("No subscriptions returned.")
        print("If you have subscriptions, they may be under a different context (e.g. team).")
        print("Dashboard: https://rapidapi.com/developer/dashboard → Subscriptions & Usage")
        return

    print(f"Subscribed APIs ({len(nodes)} shown, total: {total}):\n")
    for s in nodes:
        print(f"  apiId: {s.get('apiId', '?')}  status: {s.get('status', '?')}  id: {s.get('id', '?')}")
    print("\nUse apiId to get API name/host from the API’s page on RapidAPI.")


if __name__ == "__main__":
    main()
