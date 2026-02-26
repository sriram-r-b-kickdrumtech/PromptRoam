"""
Test MCP gateway and Redis caching.

1. Phase 1 (cache disabled): Call MCP once to verify the server responds. Requires npx, .env with
   RAPIDAPI_API_KEY, MCP_COMMAND, MCP_ARGS. Run: MCP_CACHE_ENABLED=0 python scripts/test_mcp_and_cache.py

2. Phase 2 (cache enabled): Call same tool twice with same args. Second call must be served from
   Redis (no MCP server call). Redis must be running (e.g. redis-server --port 6380). Logs show
   CACHE_MISS then CACHE_HIT; script asserts MCP is only invoked once.

Usage:
  # Ensure npx is available: npm install -g npx  (or use Node installer)
  # From repo root with .env configured:
  python scripts/test_mcp_and_cache.py              # runs both phases (1 then 2)
  python scripts/test_mcp_and_cache.py --mcp-only  # only verify MCP (cache disabled)
  python scripts/test_mcp_and_cache.py --cache-only # only verify cache (assumes MCP works)
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


def _check_npx() -> bool:
    import subprocess
    try:
        subprocess.run(
            ["npx", "--version"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _tool_name() -> str:
    return (os.environ.get("MCP_TOOL_FLIGHTS") or "").strip() or "search_flights"


def _sample_args() -> dict:
    return {
        "origin": "LHR",
        "destination": "JFK",
        "date": "2025-04-15",
    }


def run_mcp_only() -> bool:
    """Call MCP once with cache disabled. Return True if we got a non-None response (MCP works)."""
    os.environ["MCP_CACHE_ENABLED"] = "0"
    # Re-import so gateway reads env
    import importlib.util
    spec = importlib.util.find_spec("src.mcp_gateway")
    if spec and spec.origin:
        import importlib
        import src.mcp_gateway as gw
        importlib.reload(gw)
    from src.mcp_gateway import call_mcp_tool_cached

    tool = _tool_name()
    args = _sample_args()
    print("[test_mcp_and_cache] Phase 1: MCP only (cache disabled)")
    print(f"  Tool: {tool}, Args: {args}")
    print("  Expect log line: [MCP] CACHE_MISS ... (calling MCP server)")
    result = call_mcp_tool_cached(tool, args, ttl_seconds=3600)
    if result is None:
        print("  Result: None (MCP not configured, wrong tool/args for this API, or call failed).")
        print("  Check MCP_COMMAND, MCP_ARGS, and that your RapidAPI subscription exposes this tool.")
        return False
    content = (result.get("content") or [])
    text = ""
    for block in content:
        if isinstance(block, dict) and block.get("text"):
            text += block.get("text", "")
    print(f"  Result: isError={result.get('isError')}, content length={len(text)} chars")
    if text:
        print(f"  Preview: {text[:300]}...")
    print("  MCP responded successfully.")
    return True


def run_cache_test() -> bool:
    """Call same MCP tool twice with cache enabled. Assert second call does not hit MCP (cache hit)."""
    os.environ["MCP_CACHE_ENABLED"] = "1"
    import importlib
    import src.mcp_gateway as gw
    importlib.reload(gw)

    from src.mcp_gateway import call_mcp_tool_cached, _call_mcp_tool_async

    mcp_call_count = [0]  # list so closure can mutate

    def counted_async(tool_name: str, arguments: dict | None):
        mcp_call_count[0] += 1
        print(f"  [test_mcp_and_cache] MCP server invoked (count={mcp_call_count[0]})")
        return _call_mcp_tool_async(tool_name, arguments)

    gw._call_mcp_tool_async = counted_async

    tool = _tool_name()
    args = _sample_args()
    print("[test_mcp_and_cache] Phase 2: Cache verification (cache enabled)")
    print(f"  Tool: {tool}, Args: {args}")
    print("  First call: expect CACHE_MISS and one MCP server invocation.")
    r1 = call_mcp_tool_cached(tool, args, ttl_seconds=3600)
    print("  Second call (same args): expect CACHE_HIT and NO MCP server invocation.")
    r2 = call_mcp_tool_cached(tool, args, ttl_seconds=3600)

    if mcp_call_count[0] != 1:
        print(f"  FAIL: MCP was invoked {mcp_call_count[0]} times (expected 1). Caching did not prevent second call.")
        return False
    if r1 is None or r2 is None:
        print("  FAIL: One or both calls returned None.")
        return False
    print("  OK: Second call was served from Redis; MCP server was not called again.")
    return True


def main() -> int:
    if not _check_npx():
        print("npx not found. Install Node.js (includes npx) or run: npm install -g npx", file=sys.stderr)
        return 1

    key = (os.environ.get("RAPIDAPI_API_KEY") or "").strip()
    if not key:
        print("RAPIDAPI_API_KEY not set in .env", file=sys.stderr)
        return 1

    cmd = (os.environ.get("MCP_COMMAND") or "").strip()
    if not cmd:
        print("MCP_COMMAND not set (e.g. npx)", file=sys.stderr)
        return 1

    mcp_only = "--mcp-only" in sys.argv
    cache_only = "--cache-only" in sys.argv

    if cache_only:
        ok = run_cache_test()
        return 0 if ok else 1
    if mcp_only:
        ok = run_mcp_only()
        return 0 if ok else 1

    # Default: run both phases
    print("--- Phase 1: Verify MCP works (cache disabled) ---")
    if not run_mcp_only():
        print("MCP phase failed. Fix MCP config and run again before enabling cache.", file=sys.stderr)
        return 1
    print()
    print("--- Phase 2: Verify caching (cache enabled) ---")
    if not run_cache_test():
        print("Cache phase failed.", file=sys.stderr)
        return 1
    print()
    print("All checks passed. You can set MCP_CACHE_ENABLED=1 in .env for production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
