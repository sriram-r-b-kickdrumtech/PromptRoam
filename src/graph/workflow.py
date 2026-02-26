"""
Build and compile the travel planning LangGraph.

Single entry point: Supervisor only. Plan-and-Execute with parallel executors.
Phase 11: interrupt_before synthesizer for HITL (Approve/Edit/Reject).
"""
from __future__ import annotations

from langgraph.graph import START, END
from langgraph.graph import StateGraph

from config.logging_config import get_logger
from src.state import GraphState
from src.persistence import get_checkpointer
from src.graph.nodes import (
    supervisor_node,
    planner_node,
    synthesizer_node,
    transport_node,
    accommodation_node,
    experience_node,
    financial_node,
    execute_all_node,
    htil_node,
)

log = get_logger(__name__)


def route_after_supervisor(state: GraphState) -> str:
    """
    Dynamic routing: follow the decision made by the Supervisor LLM.
    """
    next_node = state.get("next_node")
    
    # If the Supervisor specifically chose 'end' or 'end' mapping
    if next_node == "end":
        return "end"

    # If the PREVIOUS node was htil, and it signaled clarification, we STOP.
    # But only if the Supervisor didn't explicitly just route us to planner
    # to process new input.
    if state.get("is_clarification") and next_node == "htil":
        log.debug("[ROUTE] Previous node was htil (clarification) -> wait for user")
        return "end"

    log.debug("[ROUTE] supervisor -> %s", next_node)
    return next_node or "planner"


def build_graph(interrupt_before: tuple[str, ...] | None = ("synthesizer",)):
    """Build graph with single entry = Supervisor; compile with checkpointer. Optionally HITL interrupt before nodes."""
    log.info("[WORKFLOW] building graph interrupt_before=%s", interrupt_before)
    builder = StateGraph(GraphState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("execute_all", execute_all_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("htil", htil_node)

    builder.add_node("transport", transport_node)
    builder.add_node("accommodation", accommodation_node)
    builder.add_node("experience", experience_node)
    builder.add_node("financial", financial_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "planner": "planner",
            "execute_all": "execute_all",
            "synthesizer": "synthesizer",
            "htil": "htil",
            "end": END,
        },
    )

    builder.add_edge("planner", "supervisor")
    builder.add_edge("execute_all", "supervisor")
    builder.add_edge("htil", END)
    builder.add_edge("synthesizer", END)

    checkpointer = get_checkpointer()
    kwargs = {"checkpointer": checkpointer}
    if interrupt_before:
        kwargs["interrupt_before"] = list(interrupt_before)
    compiled = builder.compile(**kwargs)
    return compiled


_graph = None
_graph_no_interrupt = None


def get_graph(use_interrupt: bool = True):
    """Return compiled graph. use_interrupt=False for tests (no HITL pause)."""
    global _graph, _graph_no_interrupt
    if use_interrupt:
        if _graph is None:
            _graph = build_graph(interrupt_before=("synthesizer",))
        return _graph
    if _graph_no_interrupt is None:
        _graph_no_interrupt = build_graph(interrupt_before=None)
    return _graph_no_interrupt
