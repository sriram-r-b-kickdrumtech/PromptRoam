"""
Persistence abstraction for LangGraph checkpointing.

Use get_checkpointer() when compiling the graph so node logic never
depends on MemorySaver vs AsyncPostgresSaver. Swap implementation here only.

Migration to AsyncPostgresSaver:
  - Install: pip install langgraph-checkpoint-postgres
  - Replace _checkpointer in get_checkpointer() with:
      from langgraph.checkpoint.postgres import PostgresSaver
      # or from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver for async
      with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
          ... use checkpointer same as MemorySaver ...
  - Call checkpointer.setup() once on first use.
  - Graph code stays unchanged: still compile(checkpointer=get_checkpointer()).
"""
from __future__ import annotations

from typing import Any

_checkpointer: Any = None


def get_checkpointer() -> Any:
    """Return the checkpointer for graph.compile(checkpointer=...). Default: MemorySaver."""
    global _checkpointer
    if _checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
    return _checkpointer


def get_thread_state(thread_id: str) -> dict[str, Any] | None:
    """
    Read the latest graph state for a thread. Uses the same checkpointer as the graph.
    Returns None if no checkpoint exists.
    """
    cp = get_checkpointer()
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    t = cp.get_tuple(config)
    if t is None or not t.checkpoint:
        return None
    return t.checkpoint.get("channel_values")


def config_for_thread(thread_id: str) -> dict[str, Any]:
    """Build config for invoke/stream/get_state with thread_id."""
    return {"configurable": {"thread_id": thread_id}}
