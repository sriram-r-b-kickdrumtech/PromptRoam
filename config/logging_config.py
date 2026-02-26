"""
Centralized verbose logging for PromptRoam.

Set LOG_LEVEL=DEBUG (or leave unset for DEBUG) for detailed per-node, per-tool,
and per-checkpoint logs. All graph nodes, MCP gateway, cache, and guardrails use this.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Default to DEBUG for verbose output; override with LOG_LEVEL=INFO or WARNING
DEFAULT_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()
VERBOSE = os.environ.get("PROMPTROAM_VERBOSE", "1").strip() in ("1", "true", "yes")
# When 1, log each node's full input (state) and output (updates) at INFO so they appear in logs
LOG_NODE_IO = os.environ.get("LOG_NODE_IO", "1").strip() in ("1", "true", "yes")

# Max chars for logged state/updates JSON (per node); None = no truncation
NODE_IO_LOG_MAX_CHARS = 8_000


# In-memory buffer for UI (e.g. Streamlit) to show last N log lines (node I/O, etc.)
LOG_BUFFER: list[str] = []
LOG_BUFFER_MAX_LINES = 300


class BufferHandler(logging.Handler):
    """Append log records to LOG_BUFFER for display in UI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            LOG_BUFFER.append(msg)
            while len(LOG_BUFFER) > LOG_BUFFER_MAX_LINES:
                LOG_BUFFER.pop(0)
        except Exception:
            pass


def get_logger(name: str) -> logging.Logger:
    """Return a logger for module `name` (e.g. __name__). Configured for verbose output."""
    log = logging.getLogger(name)
    if not log.handlers:
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Stderr so node I/O appears in terminal
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(fmt)
        log.addHandler(stderr_handler)

        # File logging
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "promptroam.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        file_handler.setLevel(logging.DEBUG)
        log.addHandler(file_handler)

        # Buffer so UI can show last N lines (node I/O in Streamlit)
        buf_handler = BufferHandler()
        buf_handler.setFormatter(fmt)
        buf_handler.setLevel(logging.INFO)
        log.addHandler(buf_handler)
        log.setLevel(getattr(logging, DEFAULT_LEVEL, logging.DEBUG))
        log.propagate = False
    return log

from pathlib import Path


def get_log_buffer_snapshot() -> list[str]:
    """Return a copy of the in-memory log buffer for UI display."""
    return list(LOG_BUFFER)


def _sanitize_for_log(obj: Any, max_str: int = 200) -> Any:
    """Produce a JSON-serializable, PII-safe snapshot for logging (truncate long strings/lists)."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        return obj[:max_str] + ("..." if len(obj) > max_str else "")
    if isinstance(obj, list):
        if len(obj) > 20:
            return [_sanitize_for_log(obj[0], max_str) if obj else None, f"... list(len={len(obj)})"]
        return [_sanitize_for_log(x, max_str) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in list(obj.items())[:25]:
            if k == "message_history" and isinstance(v, list):
                out[k] = f"<list(len={len(v)})>"
            elif k == "content" and isinstance(v, str):
                out[k] = v[:max_str] + "..." if len(v) > max_str else v
            else:
                out[k] = _sanitize_for_log(v, max_str)
        if len(obj) > 25:
            out["_truncated_keys"] = len(obj) - 25
        return out
    return type(obj).__name__


def log_state_snapshot(log: logging.Logger, state: dict[str, Any], prefix: str = "state") -> None:
    """Log a concise snapshot of graph state for debugging (keys and sizes, no PII)."""
    if not VERBOSE or not log.isEnabledFor(logging.DEBUG):
        return
    parts = []
    for k, v in (state or {}).items():
        if v is None:
            parts.append(f"{k}=None")
        elif isinstance(v, list):
            parts.append(f"{k}=list(len={len(v)})")
        elif isinstance(v, dict):
            parts.append(f"{k}=dict(keys={list(v.keys())[:5]})")
        else:
            parts.append(f"{k}={type(v).__name__}")
    log.debug("[%s] %s", prefix, " | ".join(parts))


def log_node_enter(log: logging.Logger, node_name: str, state: dict[str, Any]) -> None:
    """Log node input (state). At INFO: compact summary; if LOG_NODE_IO=1, full sanitized state."""
    log.info("[NODE_ENTER] node=%s", node_name)
    log_state_snapshot(log, state, prefix=f"before_{node_name}")
    if LOG_NODE_IO and log.isEnabledFor(logging.INFO) and state is not None:
        try:
            snap = _sanitize_for_log(state, max_str=150)
            payload = json.dumps(snap, default=str, indent=2)
            if NODE_IO_LOG_MAX_CHARS and len(payload) > NODE_IO_LOG_MAX_CHARS:
                payload = payload[:NODE_IO_LOG_MAX_CHARS] + "\n... (truncated)"
            log.info("[NODE_IN] node=%s\n%s", node_name, payload)
        except Exception as e:
            log.debug("[NODE_IN] serialize failed: %s", e)
    if log.isEnabledFor(logging.DEBUG) and state:
        msg_hist = state.get("message_history") or []
        if msg_hist:
            last = msg_hist[-1] if isinstance(msg_hist[-1], dict) else {}
            content = (last.get("content") or "")[:150]
            log.debug("[NODE_IN] last_message_role=%s content_preview=%s", last.get("role"), content)
        hc = state.get("hard_constraints") or {}
        if hc:
            log.debug("[NODE_IN] hard_constraints max_budget=%s duration_days=%s", hc.get("max_budget"), hc.get("duration_days"))


def log_node_exit(log: logging.Logger, node_name: str, updates: dict[str, Any]) -> None:
    """Log node output (updates). At INFO: keys + if LOG_NODE_IO=1 full sanitized updates."""
    log.info("[NODE_EXIT] node=%s updates_keys=%s", node_name, list(updates.keys()) if isinstance(updates, dict) else type(updates))
    if LOG_NODE_IO and log.isEnabledFor(logging.INFO) and isinstance(updates, dict):
        try:
            snap = _sanitize_for_log(updates, max_str=200)
            payload = json.dumps(snap, default=str, indent=2)
            if NODE_IO_LOG_MAX_CHARS and len(payload) > NODE_IO_LOG_MAX_CHARS:
                payload = payload[:NODE_IO_LOG_MAX_CHARS] + "\n... (truncated)"
            log.info("[NODE_OUT] node=%s\n%s", node_name, payload if snap else "{}")
        except Exception as e:
            log.debug("[NODE_OUT] serialize failed: %s", e)
    if isinstance(updates, dict) and updates and log.isEnabledFor(logging.DEBUG):
        for k, v in updates.items():
            if isinstance(v, list):
                log.debug("[NODE_OUT] %s: list length=%s", k, len(v))
                if k == "task_dag" and v and len(v) > 0:
                    log.debug("[NODE_OUT] task_dag ids=%s", [t.get("id") for t in v[:5] if isinstance(t, dict)])
                if k == "executor_results" and v:
                    log.debug("[NODE_OUT] executor_results agents=%s", [r.get("agent") for r in v if isinstance(r, dict)])
            elif isinstance(v, dict):
                log.debug("[NODE_OUT] %s: dict keys=%s", k, list(v.keys())[:8])
            else:
                log.debug("[NODE_OUT] %s: %s", k, type(v).__name__)


def log_mcp_call(log: logging.Logger, tool_name: str, arguments: dict[str, Any], cached: bool) -> None:
    """Verbose: MCP tool call (cache hit or miss)."""
    log.info("[MCP] tool=%s cached=%s args_keys=%s", tool_name, cached, list(arguments.keys()) if arguments else [])
    if arguments and log.isEnabledFor(logging.DEBUG):
        for k, v in list(arguments.items())[:10]:
            log.debug("[MCP] arg %s=%s", k, v if not isinstance(v, (list, dict)) or len(str(v)) < 200 else f"<len={len(v) if isinstance(v, (list, dict)) else '?'}>")


# Max chars to log for full MCP result (avoid flooding); None = no limit
MCP_RESULT_LOG_MAX_CHARS = 16_000


def log_mcp_result(log: logging.Logger, tool_name: str, result: dict[str, Any] | None, from_cache: bool) -> None:
    """Log MCP tool result: summary at INFO, full result fields at DEBUG."""
    if result is None:
        log.debug("[MCP_RESULT] tool=%s from_cache=%s result=None", tool_name, from_cache)
        return
    keys = list(result.keys())[:12] if isinstance(result, dict) else []
    log.info("[MCP_RESULT] tool=%s from_cache=%s result_keys=%s isError=%s", tool_name, from_cache, keys, result.get("isError") if isinstance(result, dict) else "?")
    if not log.isEnabledFor(logging.DEBUG) or not isinstance(result, dict):
        return
    # Log full result as JSON so all fields returned by MCP are visible
    try:
        payload = json.dumps(result, default=str, indent=2)
    except Exception:
        payload = str(result)
    if MCP_RESULT_LOG_MAX_CHARS and len(payload) > MCP_RESULT_LOG_MAX_CHARS:
        payload = payload[:MCP_RESULT_LOG_MAX_CHARS] + "\n... (truncated, %d chars total)" % len(payload)
    log.debug("[MCP_RESULT] full result:\n%s", payload)
    # Also log parsed content text in full (API response body)
    content = result.get("content") or []
    for i, block in enumerate(content):
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if len(text) > 2000 and MCP_RESULT_LOG_MAX_CHARS:
                log.debug("[MCP_RESULT] content[%d].text (%d chars): %s ... (truncated)", i, len(text), text[:2000])
            else:
                log.debug("[MCP_RESULT] content[%d].text: %s", i, text)


def log_guardrail(log: logging.Logger, guard_name: str, passed: bool, detail: str = "") -> None:
    """Verbose: guardrail check result."""
    log.info("[GUARDRAIL] %s passed=%s %s", guard_name, passed, detail or "")
