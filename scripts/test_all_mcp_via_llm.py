"""
Call all MCP APIs through the LLM/graph. One graph run triggers 3 MCP tools: transport (flights),
accommodation (hotels), experience (activities). Use --all-12 to run 4 different trip requests
(4 × 3 = 12 MCP tool invocations) for verification.

Use a prompt that includes origin, destination, and date so the graph passes real params to MCP
(e.g. "From Delhi to Goa, date April 15 2025" -> MCP gets origin=Delhi, destination=Goa, date=2025-04-15).
If MCP returns real data you'll see flights/hotels/activities; otherwise stubs.

Run with conda env (required):
  conda activate promptroam
  python scripts/test_all_mcp_via_llm.py
  python scripts/test_all_mcp_via_llm.py --all-12
Output is printed and written to scripts/output/test_all_mcp_via_llm.txt
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
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        print("OPENAI_API_KEY not set (required for planner). Set in .env.", file=sys.stderr)
        return 1

    from src.graph.workflow import get_graph
    from src.persistence import config_for_thread

    # No HITL interrupt so we get full run to synthesizer
    graph = get_graph(use_interrupt=False)
    config = config_for_thread("test-all-mcp-via-llm")
    all_12 = "--all-12" in sys.argv

    # Explicit origin, destination, date so MCP gets real params (no stub fallback for missing location)
    prompts = [
        (
            "From Delhi to Goa, travel date April 15 2025. I need flights (e.g. Air India), "
            "a hotel in Goa, and beach or water sports activities. 3 days, budget 50000 INR."
        ),
    ]
    if all_12:
        prompts = [
            "Plan a weekend trip Mumbai to Kerala: flights, one hotel, backwaters and food experiences. 40000 INR.",
            "I want 5 days in Rajasthan: Jaipur and Udaipur, flights and hotels, heritage and culture. 60000 INR.",
            "Beach holiday from Bangalore to Goa: flights, beach resort under 12k/night, water sports. 50000 INR.",
            "Delhi to Goa 3 days: flights, hotel under 15k, beach and water sports. Budget 80000 INR.",
        ]

    lines = []
    def log(s: str):
        print(s)
        lines.append(s)

    log("=" * 60)
    log("Test: All MCP APIs via LLM (graph run)" + (" -- 4 runs × 3 tools = 12 MCP calls" if all_12 else ""))
    log("=" * 60)

    for run_index, user_message in enumerate(prompts, 1):
        if all_12:
            log("")
            log("--- Run %d / 4 ---" % run_index)
        log("User message: %s" % (user_message[:100] + "..." if len(user_message) > 100 else user_message))
        if not all_12:
            log("")
            log("Invoking graph: Supervisor -> Planner -> Execute_all (transport, accommodation, experience) -> ...")
            log("Each executor calls MCP (search_flights, search_hotels, search_activities).")
            log("")
        initial_state = {"message_history": [{"role": "user", "content": user_message}]}
        # Fresh thread per run so each run runs planner + execute_all (no stale state)
        run_config = config_for_thread("test-all-mcp-run-%d" % run_index) if all_12 else config

        try:
            final = graph.invoke(initial_state, run_config)
        except Exception as e:
            log("Error: %s" % e)
            import traceback
            log(traceback.format_exc())
            if all_12:
                continue
            _write_output(lines)
            return 1

        results = final.get("executor_results") or []
        hard = final.get("hard_constraints") or {}
        profile = final.get("user_profile_and_context") or {}

        origin = profile.get("origin") or hard.get("origin") or "Delhi"
        destination = profile.get("destination") or hard.get("destination") or "Goa"
        date_hint = str(hard.get("travel_date") or hard.get("date_hint") or "")
        max_budget = hard.get("max_budget")
        interests = profile.get("interests") or []

        log("INPUTS: transport origin=%s dest=%s date=%s | accommodation location=%s max_budget=%s | experience interests=%s" % (
            origin, destination, date_hint, destination, max_budget, interests,
        ))
        log("RESULTS:")
        for r in results:
            if not isinstance(r, dict):
                continue
            agent = r.get("agent", "")
            result = r.get("result")
            if isinstance(result, dict) and agent != "financial":
                preview = json.dumps(result, default=str)[:200]
                log("  [%s] %s" % (agent, preview + "..." if len(preview) >= 200 else preview))
            elif agent == "financial":
                log("  [financial] %s" % (result if isinstance(result, dict) else result))
        if not all_12:
            log("")
            log("--- Full RESULTS (per executor) ---")
            for r in results:
                if not isinstance(r, dict):
                    continue
                agent = r.get("agent", "")
                task_id = r.get("task_id", "")
                result = r.get("result")
                log("  [%s] task_id=%s" % (agent, task_id))
                if result is None:
                    log("    result: None")
                elif isinstance(result, dict):
                    try:
                        raw = json.dumps(result, indent=4, default=str)
                        if len(raw) > 3000:
                            raw = raw[:3000] + "\n    ... (truncated)"
                        log("    result:")
                        for line in raw.splitlines():
                            log("      " + line)
                    except Exception:
                        log("    result: %s" % str(result)[:500])
                else:
                    log("    result: %s" % str(result)[:500])
                log("")

    log("--- END ---")
    _write_output(lines)
    return 0


def _write_output(lines: list[str]) -> None:
    out_dir = ROOT / "scripts" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "test_all_mcp_via_llm.txt"
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nOutput saved to: {out_file}")


if __name__ == "__main__":
    sys.exit(main())
