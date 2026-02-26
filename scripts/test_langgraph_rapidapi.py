"""
Test one RapidAPI (AeroDataBox) via LangGraph.

Uses the same code path as the app: graph runs, execute_all calls transport,
transport uses rapidapi_client (key from env) to call AeroDataBox.
Run: python scripts/test_langgraph_rapidapi.py
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

def main() -> int:
    if not (os.environ.get("RAPIDAPI_API_KEY") or "").strip():
        print("RAPIDAPI_API_KEY not set. Set in .env and run again.", file=sys.stderr)
        return 1

    from src.graph.workflow import get_graph
    from src.persistence import config_for_thread

    graph = get_graph()
    config = config_for_thread("test-langgraph-rapidapi")
    initial_state = {"message_history": [{"role": "user", "content": "I need a flight next week"}]}

    print("Invoking LangGraph (Supervisor → Planner → Supervisor → execute_all → ...)")
    print("Transport node will call AeroDataBox via rapidapi_client (key from env).\n")

    try:
        final = graph.invoke(initial_state, config)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    results = final.get("executor_results") or []
    transport_result = None
    for r in results:
        if isinstance(r, dict) and r.get("agent") == "transport":
            transport_result = r.get("result")
            break

    print("--- Transport node result (MCP-style call via LangGraph) ---")
    if transport_result:
        print(json.dumps(transport_result, indent=2, default=str)[:2000])
        if transport_result.get("source") == "rapidapi_aerodatabox":
            print("\n[SUCCESS] AeroDataBox API was called from LangGraph (key from env).")
    else:
        print("No transport result in state (check executor_results).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
