"""Phase 4: Graph entry = Supervisor, no tools on Supervisor, minimal flow."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import StateGraph, START, END
from src.graph.workflow import build_graph, route_after_supervisor
from src.graph import nodes
from src.persistence import config_for_thread


def test_supervisor_has_no_tools() -> None:
    """Supervisor MUST NOT possess tools to call external APIs."""
    # Supervisor is a plain function, not a bind_tools model
    import inspect
    sig = inspect.signature(nodes.supervisor_node)
    assert "tools" not in sig.parameters
    # Node is not a runnable with tools
    assert not getattr(nodes.supervisor_node, "bind_tools", None)


def test_graph_entry_is_supervisor() -> None:
    """Single entry point is Supervisor only."""
    g = build_graph(interrupt_before=None)
    # LangGraph: entry point is the node that START connects to
    builder = g.builder
    if hasattr(builder, "entry_point"):
        assert builder.entry_point == "supervisor"
    # Alternatively: first node in stream is supervisor
    cfg = config_for_thread("entry-test")
    chunks = list(g.stream({"message_history": [{"role": "user", "content": "hi"}]}, cfg, stream_mode="updates"))
    assert chunks
    assert list(chunks[0].keys())[0] == "supervisor"


def test_minimal_flow_supervisor_planner_synthesizer() -> None:
    """One full stub flow: user message → Supervisor → Planner → Synthesizer → response."""
    g = build_graph(interrupt_before=None)
    cfg = config_for_thread("flow-test")
    state = {"message_history": [{"role": "user", "content": "2 days in Goa"}]}
    out = g.invoke(state, cfg)
    assert "message_history" in out
    msgs = out["message_history"]
    assert any(m.get("role") == "assistant" for m in msgs)
    last = msgs[-1]
    assert last.get("role") == "assistant"
    assert "stub itinerary" in last.get("content", "").lower() or "goa" in last.get("content", "").lower()
    assert out.get("requested_trips")
    assert out["requested_trips"][0]["summary"]


def test_route_after_supervisor_no_trips_goes_to_planner() -> None:
    assert route_after_supervisor({}) == "planner"
    assert route_after_supervisor({"task_dag": []}) == "planner"


def test_route_after_supervisor_has_trips_goes_to_synthesizer() -> None:
    # Phase 5: route uses task_dag + executor_results; with both set we go to synthesizer
    assert route_after_supervisor({
        "task_dag": [{"id": "t1", "agent": "transport"}],
        "executor_results": [{"task_id": "t1", "result": {}}],
    }) == "synthesizer"
