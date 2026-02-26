"""Phase 5: Intent extraction, DAG, execute_all, synthesizer re-plan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.graph.intent import extract_constraints_and_profile, get_last_user_message
from src.graph.workflow import build_graph
from src.persistence import config_for_thread


def test_extract_constraints_and_profile_rich_prompt() -> None:
    msg = "4-day Rishikesh under ₹15,000, adventure + spiritual, from Delhi next weekend"
    hard, profile = extract_constraints_and_profile(msg)
    assert hard.get("max_budget") == 15000
    assert hard.get("duration_days") == 4
    assert "adventure" in (profile.get("interests") or [])
    assert "spiritual" in (profile.get("interests") or [])
    assert profile.get("origin", "").lower() == "delhi"


def test_plan_output_has_dag_and_constraints() -> None:
    g = build_graph(interrupt_before=None)
    cfg = config_for_thread("p5-dag")
    state = {"message_history": [{"role": "user", "content": "4-day Rishikesh under ₹15k, adventure, from Delhi"}]}
    # Run only up to after planner (we need to invoke and get state after planner)
    out = g.invoke(state, cfg)
    assert out.get("hard_constraints")
    assert out.get("user_profile_and_context") is not None
    assert out.get("task_dag")
    dag = out["task_dag"]
    assert len(dag) == 4
    agents = {t["agent"] for t in dag}
    assert agents == {"transport", "accommodation", "experience", "financial"}
    assert dag[-1]["dependencies"] == ["t1", "t2", "t3"]


def test_full_plan_execute_synthesize_cycle() -> None:
    g = build_graph(interrupt_before=None)
    cfg = config_for_thread("p5-full")
    state = {"message_history": [{"role": "user", "content": "2 days Goa under 10k"}]}
    out = g.invoke(state, cfg)
    assert len(out.get("executor_results") or []) == 4
    msgs = out.get("message_history") or []
    last = msgs[-1]
    assert last.get("role") == "assistant"
    assert "stub itinerary" in (last.get("content") or "").lower()
    assert "Executors ran" in (last.get("content") or "")


def test_synthesizer_replan_on_failure() -> None:
    """When an executor returns no_availability, synthesizer clears task_dag and adds re-plan message."""
    from src.graph.nodes import synthesizer_node
    state = {
        "requested_trips": [{"id": "leg-1", "summary": "Trip"}],
        "message_history": [{"role": "user", "content": "hi"}],
        "executor_results": [
            {"agent": "transport", "result": "no_availability"},
        ],
    }
    out = synthesizer_node(state)
    assert "Re-planning" in (out.get("message_history") or [])[-1].get("content", "")
    assert out.get("task_dag") == []
    assert out.get("executor_results") == []
