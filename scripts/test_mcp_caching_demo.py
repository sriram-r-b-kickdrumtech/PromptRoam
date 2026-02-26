"""
Demo MCP caching: enable cache, call one MCP tool twice with same args.
Second call must be served from Redis (CACHE_HIT); logs show no MCP server call on second time.

Requires: Redis running (e.g. redis-server --port 6380). Use conda env:
  conda activate promptroam
  redis-server --port 6380   # in another terminal if not already running
  python scripts/test_mcp_caching_demo.py

By default uses DEMO_MOCK_MCP=1 (fake success) so cache is written and second call = CACHE_HIT.
Set DEMO_MOCK_MCP=0 to use real MCP (then cache only works if MCP returns success).
Output is printed and saved to scripts/output/test_mcp_caching_demo.txt
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


def _redis_ok() -> bool:
    try:
        from src.cache import get_redis_client
        c = get_redis_client()
        return c is not None and c.ping()
    except Exception:
        return False


def main() -> int:
    # Force cache ON for this script
    os.environ["MCP_CACHE_ENABLED"] = "1"
    use_mock = (os.environ.get("DEMO_MOCK_MCP") or "1").strip().lower() in ("1", "true", "yes")

    if not _redis_ok():
        print("Redis is not running. Start it with: redis-server --port 6380", file=sys.stderr)
        print("Then run (with conda env): conda activate promptroam && python scripts/test_mcp_caching_demo.py", file=sys.stderr)
        return 1

    if not use_mock and not (os.environ.get("RAPIDAPI_API_KEY") or "").strip():
        print("RAPIDAPI_API_KEY not set. Set in .env or use default DEMO_MOCK_MCP=1.", file=sys.stderr)
        return 1

    from src.mcp_gateway import call_mcp_tool_cached, _call_mcp_tool_async

    tool = (os.environ.get("MCP_TOOL_FLIGHTS") or "").strip() or "search_flights"
    args = {"origin": "LHR", "destination": "JFK", "date": "2025-05-01"}

    lines = []
    def log(s: str):
        print(s)
        lines.append(s)

    # Count how many times we actually call the MCP server (or mock)
    mcp_invokes = [0]
    fake_success = {"isError": False, "content": [{"type": "text", "text": '{"flights":[{"id":"M1","origin":"LHR","dest":"JFK"}]}'}]}

    def counted_mcp(tool_name: str, arguments: dict | None, api_host: str | None = None):
        mcp_invokes[0] += 1
        log(f"  [DEMO] MCP server invoked #%d (api_host=%s)" % (mcp_invokes[0], api_host or "(default)"))
        if use_mock:
            return fake_success
        return _call_mcp_tool_async(tool_name, arguments, api_host=api_host)

    import src.mcp_gateway as gw
    gw._call_mcp_tool_async = counted_mcp

    log("=" * 60)
    log("Test: MCP caching (same tool+args called twice)")
    log("=" * 60)
    log("MCP_CACHE_ENABLED=1. Redis verified running.")
    if use_mock:
        log("Using mock MCP response (default) so cache is written; second call = CACHE_HIT.")
    log("")
    log("First call: expect CACHE_MISS and one MCP server invocation.")
    log("Second call (same args): expect CACHE_HIT and zero MCP server invocations.")
    log("")
    log("--- Call 1 ---")
    r1 = call_mcp_tool_cached(tool, args, ttl_seconds=3600, category="flights")
    log("  result: %s" % ("ok" if r1 and not r1.get("isError") else "None/error"))
    log("")
    log("--- Call 2 (same tool + args) ---")
    r2 = call_mcp_tool_cached(tool, args, ttl_seconds=3600, category="flights")
    log("  result: %s" % ("ok" if r2 and not r2.get("isError") else "None/error"))
    log("")
    log("--- Summary ---")
    log("  Total MCP server invocations: %d (expected: 1 if cache worked)" % mcp_invokes[0])
    if mcp_invokes[0] == 1:
        log("  CACHING OK: second call was served from Redis.")
    else:
        log("  CACHING FAIL: second call hit MCP again (Redis down or cache disabled?).")
        log("  Tip: Start Redis (redis-server --port 6380) and run again; use DEMO_MOCK_MCP=1 if MCP returns None.")
    log("--- END ---")

    out_dir = ROOT / "scripts" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "test_mcp_caching_demo.txt"
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print("\nOutput saved to: %s" % out_file)

    return 0 if mcp_invokes[0] == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
