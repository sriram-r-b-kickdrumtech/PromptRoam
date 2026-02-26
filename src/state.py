"""
Graph state schema for the travel planning LangGraph.

State is the universal memory bank shared across all agents. Constraints and
computed results are strictly separated (design: AI_Hackathon_Design_initial.md).
"""
import operator
from typing import Annotated, Any, TypedDict

# Optional Pydantic models for structured sub-values (Phase 6 will extend)
# For now we use TypedDict + dict/list types so LangGraph can merge state easily.


def merge_dicts(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Reducer: merge two dictionaries, new overwrites old keys."""
    return {**(old or {}), **(new or {})}

class GraphState(TypedDict, total=False):
    """LangGraph state: requested constraints vs computed results."""

    # User context (preferences, accessibility, travel style)
    user_profile_and_context: Annotated[dict[str, Any], merge_dicts]
    # Explicit limits: max budget, date range, max duration
    hard_constraints: Annotated[dict[str, Any], merge_dicts]
    # Requested journey legs with stable UUIDs for DyFlow/replan
    requested_trips: list[dict[str, Any]]
    # DAG of tasks: [{id, agent, dependencies[], status}]; Planner outputs this
    task_dag: list[dict[str, Any]]
    # API-validated bookings keyed by trip UUID
    validated_plans: dict[str, Any]
    # Parallel executor outputs: list of {agent, task_id, result}; reducer=add for merge
    executor_results: Annotated[list[Any], operator.add]
    # Multi-turn dialogue and transparency
    message_history: list[Any]
    # Phase 11 HITL: when set, graph is interrupted; UI shows Approve/Edit/Reject
    pending_checkpoint: dict[str, Any] | None
    # Phase 12: guardrail refinement loop cap (max 3)
    refinement_count: int
    # Phase 13 DyFlow: parsed disruption (affected_leg_id, new_times, reason)
    disruption_event: dict[str, Any] | None
    
    # Dynamic Routing fields
    next_node: str
    node_context: dict[str, Any]
    is_clarification: bool
    # Clarification flow: when true, UI should ask follow-up questions
    awaiting_clarification: bool
    clarification_questions: list[dict[str, str]]
    # Structured itinerary output (Pydantic-validated)
    structured_itinerary: dict[str, Any] | None


def update_validated_plan_leg(
    state: GraphState,
    trip_uuid: str,
    leg_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Reducer: update a single leg in validated_plans by UUID without touching others.
    Returns a partial state update to merge (validated_plans only).
    Call validate_before_commit(state["hard_constraints"], updated_plans) before
    applying to state if committing from user/API (Phase 6).
    """
    current = state.get("validated_plans") or {}
    if not isinstance(current, dict):
        current = {}
    updated = {**current, trip_uuid: leg_data}
    return {"validated_plans": updated}


def update_requested_trip_leg(
    state: GraphState,
    trip_uuid: str,
    leg_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Reducer: update a single requested trip leg by UUID (e.g. after user Edit).
    requested_trips is a list; we replace the item whose id matches trip_uuid.
    """
    trips = list(state.get("requested_trips") or [])
    out = []
    for t in trips:
        if t.get("id") == trip_uuid:
            out.append({**t, **leg_data})
        else:
            out.append(t)
    return {"requested_trips": out}
