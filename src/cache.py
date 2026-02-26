"""
Redis cache for API responses. Reduces cost and latency for repeated API/MCP calls.

- Direct API: cache key = (host_key, path, method, params) — legacy, not used when MCP-only.
- MCP tool calls: cache key = (tool_name, arguments); app always calls MCP, never direct APIs.

Uses a dedicated Redis instance (different port from existing cluster). If Redis is
unavailable, cache is skipped and calls go to MCP (or API).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# Default: new Redis on different port so existing cluster is untouched
# Set REDIS_URL to override (e.g. redis://localhost:6380/0)
DEFAULT_REDIS_PORT = 6380
CACHE_PREFIX = "promptroam:api:"
MCP_CACHE_PREFIX = "promptroam:mcp:"
DEFAULT_TTL_SECONDS = 3600  # 1 hour for API responses


def _mcp_cache_key(tool_name: str, arguments: dict[str, Any] | None) -> str:
    """Cache key for MCP tool call: same tool + same args → same key."""
    raw = f"{tool_name}|{json.dumps(sorted((arguments or {}).items()), default=str, sort_keys=True)}"
    return MCP_CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


def cache_get_mcp(tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return cached MCP tool result if present and Redis available."""
    client = get_redis_client()
    if not client:
        return None
    try:
        key = _mcp_cache_key(tool_name, arguments)
        raw = client.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def cache_set_mcp(
    tool_name: str,
    arguments: dict[str, Any] | None,
    value: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Store MCP tool result in Redis. No-op if Redis unavailable."""
    client = get_redis_client()
    if not client:
        return
    try:
        key = _mcp_cache_key(tool_name, arguments)
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        pass


def _cache_key(host_key: str, path: str, method: str, params: dict[str, Any] | None) -> str:
    raw = f"{host_key}|{path}|{method}|{json.dumps(sorted((params or {}).items()), default=str)}"
    return CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


def get_redis_client():
    """Return Redis client for the PromptRoam cache (new cluster, different port). None if disabled or error."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", DEFAULT_REDIS_PORT))
        url = f"redis://{host}:{port}/0"
    try:
        import redis
        # Check if cluster is enabled
        r = redis.from_url(url, socket_connect_timeout=2, decode_responses=True)
        try:
            info = r.info("cluster")
            if info.get("cluster_enabled"):
                from redis.cluster import RedisCluster
                # Parse host and port from url if possible, or use defaults
                host = os.environ.get("REDIS_HOST", "localhost")
                port = int(os.environ.get("REDIS_PORT", DEFAULT_REDIS_PORT))
                return RedisCluster(host=host, port=port, decode_responses=True)
        except Exception:
            pass
        return r
    except Exception:
        return None


def cache_get(host_key: str, path: str, method: str, params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return cached JSON response if present and Redis available."""
    client = get_redis_client()
    if not client:
        return None
    try:
        key = _cache_key(host_key, path, method, params)
        raw = client.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def cache_set(
    host_key: str,
    path: str,
    method: str,
    params: dict[str, Any] | None,
    value: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Store API response in Redis. No-op if Redis unavailable."""
    client = get_redis_client()
    if not client:
        return
    try:
        key = _cache_key(host_key, path, method, params)
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        pass
