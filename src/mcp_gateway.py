"""
MCP-only gateway: all external API calls go through MCP tools. No direct RapidAPI (or other API) calls.

Flow: App calls call_mcp_tool_cached(tool_name, arguments, category=...)
  → Check Redis for (tool_name, arguments)
  → Cache hit: return cached result
  → Cache miss: call MCP server (SSE or stdio). With category, try each API host in that category until one succeeds.
  → Cache result, return

Configure via env: MCP_SERVER_URL (SSE) or MCP_COMMAND + MCP_ARGS (stdio).
For RapidAPI MCP: use MCP_COMMAND=npx and MCP_ARGS with mcp-remote; use {{HOST}} in MCP_ARGS and set
MCP_FLIGHTS_HOSTS, MCP_HOTELS_HOSTS, MCP_ACTIVITIES_HOSTS (comma-separated, up to 3 per category) for fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from config.logging_config import get_logger, log_mcp_call, log_mcp_result

log = get_logger(__name__)

# Placeholder in MCP_ARGS for per-request API host (e.g. x-api-host: {{HOST}})
HOST_PLACEHOLDER = "{{HOST}}"

# Env keys for comma-separated list of RapidAPI hosts per category (fallback when .mcp_secrets not used)
MCP_CATEGORY_HOSTS_KEYS = {
    "flights": "MCP_FLIGHTS_HOSTS",
    "hotels": "MCP_HOTELS_HOSTS",
    "activities": "MCP_ACTIVITIES_HOSTS",
}

# Map server name / host substring -> our category (flights, hotels, activities)
_MCP_SERVER_CATEGORY_HINTS = (
    ("flight", "flights"),
    ("hotel", "hotels"),
    ("expedia", "hotels"),
    ("booking", "hotels"),
    ("tripadvisor", "activities"),
)


def _load_mcp_secrets_hosts_by_category() -> dict[str, list[str]]:
    """Load .mcp_secrets from project root; return { category: [host, ...] } from each server's x-api-host."""
    out: dict[str, list[str]] = {"flights": [], "hotels": [], "activities": []}
    path = os.environ.get("MCP_SECRETS_PATH") or os.path.join(os.path.dirname(os.path.dirname(__file__)), ".mcp_secrets")
    if not os.path.isfile(path):
        return out
    try:
        raw = open(path, encoding="utf-8").read()
    except Exception:
        return out
    # File can be multiple concatenated {"mcpServers": {...}} blocks; find server name + x-api-host per block
    # Match: mcpServers then inner "Server Name" key, then args array containing x-api-host
    pattern = re.compile(
        r'"mcpServers"\s*:\s*\{\s*"([^"]+)"\s*:\s*\{\s*"command"[^}]*"args"\s*:\s*\[(.*?)\]',
        re.DOTALL,
    )
    for m in pattern.finditer(raw):
        server_name = m.group(1).strip()
        args_block = m.group(2)
        host_m = re.search(r'x-api-host:\s*([^\s",]+)', args_block)
        if not host_m:
            continue
        host = host_m.group(1).strip()
        name_lower = server_name.lower()
        host_lower = host.lower()
        for hint, cat in _MCP_SERVER_CATEGORY_HINTS:
            if hint in name_lower or hint in host_lower:
                if host not in out[cat]:
                    out[cat].append(host)
                break
    return out


def _using_local_promptroam_mcp() -> bool:
    """True if MCP is configured to run the local PromptRoam MCP server (single connection, no host substitution)."""
    cmd = (os.environ.get("MCP_COMMAND") or "").strip().lower()
    args_str = (os.environ.get("MCP_ARGS") or "").strip()
    if "python" in cmd and "mcp_server_promptroam" in args_str:
        return True
    return False


def _get_hosts_for_category(category: str | None) -> list[str]:
    """Return list of API hosts for category. Uses .mcp_secrets first, then env MCP_*_HOSTS. Empty when using local PromptRoam MCP."""
    if not category:
        return []
    if _using_local_promptroam_mcp():
        return []
    cat = (category or "").strip().lower()
    # 1) From .mcp_secrets (your list of MCP server configs)
    by_cat = _load_mcp_secrets_hosts_by_category()
    hosts = by_cat.get(cat) or []
    if hosts:
        return hosts[:5]
    # 2) Fallback: env
    key = MCP_CATEGORY_HOSTS_KEYS.get(cat)
    if not key:
        return []
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return []
    return [h.strip() for h in raw.split(",") if h.strip()][:3]


def _expand_env_in_args(args_list: list[str]) -> list[str]:
    """Replace ${VAR_NAME} in each arg with os.environ.get('VAR_NAME', ''). Used for RapidAPI MCP x-api-key."""
    out = []
    for a in args_list:
        if not isinstance(a, str):
            out.append(a)
            continue
        for match in re.finditer(r"\$\{([A-Za-z0-9_]+)\}", a):
            key = match.group(1)
            a = a.replace(match.group(0), os.environ.get(key, ""))
        out.append(a)
    return out


def _substitute_host_in_args(args_list: list[str], api_host: str) -> list[str]:
    """Replace {{HOST}} in each arg with api_host. Used for per-category RapidAPI host."""
    out = []
    for a in args_list:
        if isinstance(a, str) and HOST_PLACEHOLDER in a:
            a = a.replace(HOST_PLACEHOLDER, api_host)
        out.append(a)
    return out


def _serialize_tool_result(result: Any) -> dict[str, Any]:
    """Turn MCP CallToolResult into a JSON-serializable dict for cache and return."""
    out: dict[str, Any] = {"isError": getattr(result, "isError", False)}
    content = getattr(result, "content", None) or []
    out["content"] = []
    for block in content:
        if hasattr(block, "type") and hasattr(block, "text"):
            out["content"].append({"type": block.type, "text": block.text})
        elif isinstance(block, dict):
            out["content"].append(block)
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        out["structuredContent"] = result.structuredContent
    return out


def _parse_cached(cached: dict[str, Any]) -> dict[str, Any]:
    """Return cached dict as-is; callers can use content[].text or structuredContent."""
    return cached


def _call_mcp_tool_async(
    tool_name: str,
    arguments: dict[str, Any] | None,
    api_host: str | None = None,
) -> dict[str, Any] | None:
    """Actually call the MCP server (SSE or stdio). If api_host is set, substitute {{HOST}} in MCP_ARGS. Returns serialized result or None on failure."""
    url = (os.environ.get("MCP_SERVER_URL") or "").strip()
    command = (os.environ.get("MCP_COMMAND") or "").strip()
    args_str = os.environ.get("MCP_ARGS", "[]").strip()
    if not url and not command:
        return None

    async def _run() -> dict[str, Any] | None:
        try:
            from mcp import ClientSession
        except ImportError:
            return None  # pip install mcp when using MCP

        if url:
            # SSE transport (no host substitution)
            try:
                from mcp.client.sse import sse_client
            except ImportError:
                return None
            try:
                async with sse_client(url, timeout=10.0, sse_read_timeout=60.0) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments or {})
                        return _serialize_tool_result(result)
            except Exception as e:
                log.debug("[MCP] SSE call failed: %s", e)
                return None

        if command:
            # Stdio transport (e.g. npx mcp-remote for RapidAPI MCP). Support {{HOST}} when api_host given.
            try:
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError:
                return None
            try:
                args_list = json.loads(args_str) if args_str else []
                args_list = _expand_env_in_args(args_list)
                if api_host:
                    args_list = _substitute_host_in_args(args_list, api_host)
                params = StdioServerParameters(command=command, args=args_list)
                async with stdio_client(params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments or {})
                        return _serialize_tool_result(result)
            except Exception as e:
                log.info("[MCP] stdio call failed api_host=%s: %s", api_host, e)
                return None

        return None

    try:
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if not running:
            return asyncio.run(_run())

        # If we're already in an event loop (e.g. FastAPI), run in a new thread.
        import threading
        result_holder: dict[str, Any | None] = {"result": None}

        def _thread_target():
            try:
                result_holder["result"] = asyncio.run(_run())
            except Exception:
                result_holder["result"] = None

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()
        t.join()
        return result_holder["result"]
    except Exception as e:
        log.info("[MCP] asyncio.run failed: %s", e)
        return None


def _mcp_cache_enabled() -> bool:
    """When False (MCP_CACHE_ENABLED=0 or unset), skip Redis cache. Set MCP_CACHE_ENABLED=1 after MCP is verified."""
    v = (os.environ.get("MCP_CACHE_ENABLED") or "0").strip().lower()
    return v in ("1", "true", "yes")


def _is_usable_result(result: dict[str, Any] | None) -> bool:
    """True if result is non-None and not an error (so we can cache and return it)."""
    if result is None:
        return False
    if result.get("isError"):
        return False
    return True


def call_mcp_tool_cached(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    ttl_seconds: int = 3600,
    category: str | None = None,
) -> dict[str, Any] | None:
    """
    Call an MCP tool with Redis caching (when MCP_CACHE_ENABLED=1). This is the only way the app should trigger external APIs.

    - Cache key = (tool_name, arguments). Same call returns cached result.
    - category: optional "flights" | "hotels" | "activities". When set and MCP_<CATEGORY>_HOSTS is set,
      tries each API host in order; on error or failure, tries the next. First successful response is cached and returned.
    - Set MCP_CACHE_ENABLED=0 to disable cache (e.g. while testing MCP).
    - If MCP is not configured (no MCP_SERVER_URL and no MCP_COMMAND), returns None (caller should stub).
    - If Redis is down, still calls MCP and returns; only caching is skipped.
    """
    from src.cache import cache_get_mcp, cache_set_mcp

    arguments = arguments or {}
    if _mcp_cache_enabled():
        cached = cache_get_mcp(tool_name, arguments)
        if cached is not None:
            log_mcp_call(log, tool_name, arguments, cached=True)
            log.info("[MCP] CACHE_HIT tool=%s (response from Redis, no MCP server call)", tool_name)
            log_mcp_result(log, tool_name, cached, from_cache=True)
            return _parse_cached(cached)

    log_mcp_call(log, tool_name, arguments, cached=False)
    hosts = _get_hosts_for_category(category) if category else []

    if hosts:
        # Per-category fallback: try each host until one returns a usable result
        log.info("[MCP] CACHE_MISS tool=%s category=%s trying %d host(s)", tool_name, category, len(hosts))
        for api_host in hosts:
            log.info("[MCP] trying api_host=%s", api_host)
            result = _call_mcp_tool_async(tool_name, arguments, api_host=api_host)
            if _is_usable_result(result):
                log_mcp_result(log, tool_name, result, from_cache=False)
                log.info("[MCP] success with api_host=%s", api_host)
                if _mcp_cache_enabled() and ttl_seconds > 0:
                    try:
                        cache_set_mcp(tool_name, arguments, result, ttl_seconds=ttl_seconds)
                    except Exception:
                        pass
                return result
            if result is not None and isinstance(result, dict):
                log.info("[MCP] api_host=%s returned isError or unusable: %s", api_host, result)
            log.info("[MCP] api_host=%s failed or error, trying next", api_host)
        log_mcp_result(log, tool_name, None, from_cache=False)
        return None
    else:
        # Single connection (no category or no host list): use MCP_ARGS as-is
        log.info("[MCP] CACHE_MISS tool=%s (calling MCP server)", tool_name)
        result = _call_mcp_tool_async(tool_name, arguments, api_host=None)
        log_mcp_result(log, tool_name, result, from_cache=False)
        if _mcp_cache_enabled() and result is not None and ttl_seconds > 0:
            try:
                cache_set_mcp(tool_name, arguments, result, ttl_seconds=ttl_seconds)
            except Exception:
                pass
        return result
