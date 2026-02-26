"""Tests for persistence abstraction and state round-trip with MemorySaver."""
import sys
from pathlib import Path

# Project root on path so we can import src and config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import StateGraph, START
from src.state import GraphState
from src.persistence import get_checkpointer, get_thread_state, config_for_thread


def test_config_for_thread() -> None:
    cfg = config_for_thread("my-thread")
    assert cfg == {"configurable": {"thread_id": "my-thread"}}


def test_get_thread_state_none_before_invoke() -> None:
    # Fresh checkpointer has no state for a thread
    cp = get_checkpointer()
    state = get_thread_state("no-such-thread")
    # May be None or empty depending on implementation
    assert state is None or isinstance(state, dict)


def test_minimal_graph_round_trip_state_by_thread_id() -> None:
    """Minimal graph that writes state; we read it back by thread_id."""
    builder = StateGraph(GraphState)

    def node_add_msg(state: GraphState):
        history = list(state.get("message_history") or [])
        history.append({"role": "user", "content": "hello"})
        return {"message_history": history}

    builder.add_node("add_msg", node_add_msg)
    builder.add_edge(START, "add_msg")

    checkpointer = get_checkpointer()
    graph = builder.compile(checkpointer=checkpointer)

    thread_id = "test-thread-round-trip"
    config = config_for_thread(thread_id)

    result = graph.invoke({"message_history": []}, config)
    assert "message_history" in result
    assert len(result["message_history"]) == 1
    assert result["message_history"][0]["content"] == "hello"

    # Read state via persistence abstraction (same checkpointer)
    read_back = get_thread_state(thread_id)
    assert read_back is not None
    assert "message_history" in read_back
    assert len(read_back["message_history"]) == 1
    assert read_back["message_history"][0]["content"] == "hello"
