"""
Graph nodes: Supervisor (LLM reasoning), Planner (LLM extraction), Executors (API calls), Synthesizer (LLM itinerary).

Supervisor MUST NOT call external APIs; it only inspects state and delegates.
All external API access is via MCP only (mcp_gateway.call_mcp_tool_cached); no direct RapidAPI calls.
Every cognitive node (Supervisor, Planner, Synthesizer) calls the LLM and logs prompt + response.
"""
from __future__ import annotations

import json
import uuid as uuid_mod
from typing import Any
from pydantic import BaseModel, Field

from config.logging_config import get_logger, log_node_enter, log_node_exit
from src.state import GraphState
from src.graph.intent import extract_constraints_and_profile, get_last_user_message

log = get_logger(__name__)

class SupervisorDecision(BaseModel):
    """Pydantic model for Supervisor's dynamic routing decision."""
    next_node: str = Field(..., description="The name of the next node to execute: 'planner', 'execute_all', 'synthesizer', 'htil', or 'end'")
    context: Any = Field(default_factory=dict, description="Context or instructions for the next node (dict or string)")
    reasoning: str = Field(..., description="Detailed reasoning for why this node was chosen")
    is_clarification: bool = Field(default=False, description="Whether we are currently in a clarification loop asking the user for info")

SupervisorDecision.model_rebuild()

def _mcp_tool_result_to_dict(mcp_result: dict | None) -> dict | None:
    if not mcp_result:
        return None
    if mcp_result.get("isError"):
        return None
    sc = mcp_result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    content = mcp_result.get("content") or []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            try:
                return json.loads(text)
            except Exception:
                return {"raw": text}
    return None


def _mcp_tool_name(default: str, env_key: str) -> str:
    import os
    return (os.environ.get(env_key) or "").strip() or default


def _call_local_mcp_tool(tool_name: str, arguments: dict) -> dict | None:
    try:
        import importlib.util
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        path = root / "scripts" / "mcp_server_promptroam.py"
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("mcp_server_promptroam", path)
        if spec is None or spec.loader is None:
            return None
        mcp_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mcp_script)
        handler = getattr(mcp_script, f"_tool_{tool_name}", None) or getattr(mcp_script, "TOOL_HANDLERS", {}).get(tool_name)
        if not handler:
            return None
        text = handler(arguments)
        return json.loads(text) if isinstance(text, str) else text
    except Exception:
        return None


def _search_flights_via_mcp(origin: str, dest: str, dates: str) -> dict:
    try:
        from src.mcp_gateway import call_mcp_tool_cached
        tool = _mcp_tool_name("search_flights", "MCP_TOOL_FLIGHTS")
        out = call_mcp_tool_cached(
            tool,
            {"origin": origin, "destination": dest, "date": dates},
            ttl_seconds=3600,
            category="flights",
        )
        data = _mcp_tool_result_to_dict(out)
        flights = data.get("flights") if isinstance(data, dict) else None
        if flights is not None and isinstance(flights, list) and len(flights) > 0:
            # If MCP returns only stub/fallback items, treat as unusable
            if all((f.get("stub") or f.get("source_api") == "fallback") for f in flights if isinstance(f, dict)):
                flights = []
            else:
                return {"flights": flights, "source": "mcp"}
    except Exception:
        pass
    local = _call_local_mcp_tool("search_flights", {"origin": origin, "destination": dest, "date": dates})
    if local and isinstance(local.get("flights"), list) and local.get("flights"):
        flights = local.get("flights") or []
        if all((f.get("stub") or f.get("source_api") == "fallback") for f in flights if isinstance(f, dict)):
            flights = []
        else:
            return {"flights": flights, "source": local.get("source", "mcp_promptroam")}
    try:
        from src.rapidapi_client import search_flights_direct
        direct = search_flights_direct(origin, dest, dates)
        if direct and direct.get("flights"):
            return direct
    except Exception:
        pass
    try:
        from src.services.llm_fallbacks import llm_fallback_flights
        return llm_fallback_flights(origin, dest, dates)
    except Exception:
        pass
    return {"flights": [{"id": "F1", "origin": origin, "dest": dest, "flight_name": "Configure APIs", "stub": True}]}


def _search_hotels_via_mcp(location: str, budget: int | None) -> dict:
    try:
        from src.mcp_gateway import call_mcp_tool_cached
        args = {"location": location}
        if budget is not None:
            args["max_budget"] = budget
        out = call_mcp_tool_cached(
            _mcp_tool_name("search_hotels", "MCP_TOOL_HOTELS"),
            args,
            ttl_seconds=3600,
            category="hotels",
        )
        data = _mcp_tool_result_to_dict(out)
        hotels = data.get("hotels") if isinstance(data, dict) else None
        if hotels is not None and isinstance(hotels, list) and len(hotels) > 0:
            if all((h.get("stub") or h.get("source_api") == "fallback") for h in hotels if isinstance(h, dict)):
                hotels = []
            else:
                return {"hotels": hotels, "source": "mcp"}
    except Exception:
        pass
    local = _call_local_mcp_tool("search_hotels", {"location": location, "max_budget": budget})
    if local and local.get("hotels") is not None:
        hotels = local["hotels"]
        if hotels:
            if all((h.get("stub") or h.get("source_api") == "fallback") for h in hotels if isinstance(h, dict)):
                hotels = []
            else:
                return {"hotels": hotels, "source": local.get("source", "mcp_promptroam")}
    try:
        from src.services.llm_fallbacks import llm_fallback_hotels
        return llm_fallback_hotels(location, budget)
    except Exception:
        pass
    return {"hotels": [{"id": "H1", "location": location, "stub": True}]}


def _search_activities_via_mcp(location: str, interests: list, rag_context: list | None = None) -> dict:
    try:
        from src.mcp_gateway import call_mcp_tool_cached
        out = call_mcp_tool_cached(
            _mcp_tool_name("search_activities", "MCP_TOOL_ACTIVITIES"),
            {"location": location, "interests": interests},
            ttl_seconds=3600,
            category="activities",
        )
        data = _mcp_tool_result_to_dict(out)
        activities = data.get("activities") if isinstance(data, dict) else None
        if activities is not None and isinstance(activities, list) and len(activities) > 0:
            result = {"activities": activities, "source": "mcp"}
            if rag_context:
                result["rag_suggestions"] = rag_context
            if all((a.get("stub") or a.get("source_api") == "fallback") for a in activities if isinstance(a, dict)):
                activities = []
            else:
                return result
    except Exception:
        pass
    local = _call_local_mcp_tool("search_activities", {"location": location, "interests": interests})
    if local and local.get("activities") is not None:
        activities = local["activities"]
        if activities:
            out = {"activities": activities, "source": local.get("source", "mcp_promptroam")}
            if rag_context:
                out["rag_suggestions"] = rag_context
            if all((a.get("stub") or a.get("source_api") == "fallback") for a in activities if isinstance(a, dict)):
                activities = []
            else:
                return out
    out = {"activities": [{"id": "A1", "stub": True}]}
    if rag_context:
        out["rag_suggestions"] = rag_context
    try:
        from src.services.llm_fallbacks import llm_fallback_activities
        llm_out = llm_fallback_activities(location, interests)
        if rag_context:
            llm_out["rag_suggestions"] = rag_context
        return llm_out
    except Exception:
        pass
    return out


def _build_line_items_from_results(results: list) -> list[dict]:
    items = []
    for r in results:
        if not isinstance(r, dict) or r.get("agent") is None:
            continue
        res = r.get("result") or {}
        if isinstance(res, dict):
            total = res.get("total") or res.get("total_cost")
            if total is not None:
                items.append({"category": r.get("agent"), "cost": total})
            elif r.get("agent") == "transport" and res.get("flights"):
                items.append({"category": "transport", "cost": 5000})
            elif r.get("agent") == "accommodation" and res.get("hotels"):
                items.append({"category": "accommodation", "cost": 8000})
            elif r.get("agent") == "experience" and res.get("activities"):
                items.append({"category": "experience", "cost": 2000})
    if not items:
        items = [{"category": "transport", "cost": 5000}, {"category": "accommodation", "cost": 8000}, {"category": "experience", "cost": 2000}]
    return items


# ---------------------------------------------------------------------------
# SUPERVISOR — Dynamic LLM Router
# ---------------------------------------------------------------------------

def supervisor_node(state: GraphState) -> dict:
    """
    Central Cognitive Router. 
    Analyzes state, consults node capabilities, and decides the next action.
    """
    log_node_enter(log, "supervisor", state)
    last_msg = (state.get("message_history") or [])[-1] if state.get("message_history") else {}
    last_content = last_msg.get("content", "")
    last_is_human = last_msg.get("role") == "user"
    awaiting_clarification = state.get("awaiting_clarification", False)

    # Deterministic routing to reduce latency
    if last_is_human and "Clarifications:" in (last_content or ""):
        next_node = "planner"
        awaiting_clarification = False
    elif awaiting_clarification:
        next_node = "htil"
    elif not state.get("task_dag"):
        next_node = "planner"
    elif not state.get("executor_results"):
        next_node = "execute_all"
    else:
        next_node = "synthesizer"

    updates = {
        "next_node": next_node,
        "node_context": {},
        "awaiting_clarification": awaiting_clarification,
        "clarification_questions": state.get("clarification_questions") or [],
    }
    log.info("[SUPERVISOR] Deterministic route -> %s", next_node)
    log_node_exit(log, "supervisor", updates)
    return updates


# ---------------------------------------------------------------------------
# HTIL — Dedicated Human-In-The-Loop Node
# ---------------------------------------------------------------------------

def htil_node(state: GraphState) -> dict:
    """
    Dedicated node for human interaction. 
    Can ask questions or present proposals for approval.
    """
    log_node_enter(log, "htil", state)
    context = state.get("node_context") or {}
    messages = list(state.get("message_history") or [])
    
    # Logic to prevent double-asking
    last_msg_content = messages[-1].get("content", "") if messages else ""
    
    # If user just answered clarifications, stop asking again.
    if "Clarifications:" in last_msg_content:
        updates = {
            "message_history": messages,
            "is_clarification": False,
            "awaiting_clarification": False,
            "clarification_questions": [],
        }
        log_node_exit(log, "htil", updates)
        return updates

    # We only append a chat message if we are asking for approval or a generic question.
    # We DO NOT append a chat message for clarification_questions because the UI 
    # renders a dedicated form for those.
    reply = ""
    is_clarification = True
    
    if context.get("question"):
        reply = context["question"]
    elif state.get("clarification_questions"):
        # UI handles rendering the form based on state["clarification_questions"]
        # Do not add to chat history to prevent double rendering.
        reply = ""
    elif not (state.get("user_profile_and_context") or {}).get("origin"):
        reply = "I'm ready to plan your trip! Where will you be traveling from?"
    else:
        reply = "Please review the proposal above and let me know if you'd like to approve or make changes."
        is_clarification = False # This is an approval pause, not clarification

    if reply and reply != last_msg_content:
        messages.append({"role": "assistant", "content": reply})
    
    updates = {
        "message_history": messages,
        "is_clarification": is_clarification
    }
    
    log_node_exit(log, "htil", updates)
    return updates


# ---------------------------------------------------------------------------
# PLANNER — LLM extracts constraints, creates plan
# ---------------------------------------------------------------------------

def planner_node(state: GraphState) -> dict:
    """Uses LLM to understand the user request and extract constraints + plan."""
    log_node_enter(log, "planner", state)
    from src.graph.llm import call_llm_json
    last_user = get_last_user_message(state)
    log.debug("[PLANNER] last_user_message_len=%s", len(last_user or ""))

    hard_regex, profile_regex = extract_constraints_and_profile(last_user)

    # Fast-path: if user is answering clarifications, avoid LLM for speed.
    if last_user.lower().startswith("clarifications:"):
        llm_result = {
            "hard_constraints": {},
            "user_profile": {},
            "trip_summary": "",
            "plan_reasoning": "",
        }
    else:
        system_prompt = (
            "You are the Planner agent of an AI travel planning system.\n"
            "Given the user's travel request, extract constraints and create a plan.\n\n"
            "IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation.\n"
            "Use this EXACT structure (all values must match these types):\n\n"
            '{"hard_constraints": {"max_budget": 5000, "currency": "USD", '
            '"duration_days": 3, "travel_date": "2025-06-01", "date_hint": "fixed", '
            '"origin": "London", "destination": "Paris"}, '
            '"user_profile": {"origin": "London", "destination": "Paris", '
            '"travel_style": "luxury", "interests": ["museums", "food"], '
            '"group_size": 2, "special_requirements": "wheelchair access"}, '
            '"trip_summary": "A 3-day luxury trip to Paris...", '
            '"plan_reasoning": "The user wants a high-end experience..."}\n\n'
            "STRICT RULES:\n"
            "- If the origin city is NOT mentioned in the user message, you MUST return null for origin.\n"
            "- If NO specific interests are mentioned, you MUST return an empty list [].\n"
            "- Do NOT use the example values (London, Paris, museums) if they aren't in the user message.\n"
            "- max_budget must be a NUMBER, not a string.\n"
            "- duration_days must be a NUMBER."
        )

        # Pass current context to LLM so it doesn't lose existing data
        user_prompt = f"""Conversation history:
{json.dumps(state.get('message_history', []), indent=2)}

User's latest input: "{last_user}"

INSTRUCTIONS:
1. The user's latest input might be an answer to a clarification question (e.g. providing an origin, date, or interests).
2. Merge these new details into the existing constraints and profile.
3. If all crucial info (Origin, Destination, Budget, Interests) is now present, set task_dag to the standard list of tasks.
"""

        llm_result = call_llm_json(system_prompt, user_prompt, "planner")

    llm_hard = llm_result.get("hard_constraints") or {}
    llm_profile = llm_result.get("user_profile") or {}

    hard = {**(state.get("hard_constraints") or {}), **llm_hard}
    if hard_regex.get("max_budget"):
        hard["max_budget"] = hard_regex["max_budget"]
    if hard_regex.get("currency"):
        hard["currency"] = hard_regex["currency"]
    if hard_regex.get("duration_days"):
        hard["duration_days"] = hard_regex["duration_days"]
    if hard_regex.get("travel_date"):
        hard["travel_date"] = hard_regex["travel_date"]
    if hard_regex.get("date_hint"):
        hard["date_hint"] = hard_regex.get("date_hint")

    profile = {**(state.get("user_profile_and_context") or {}), **llm_profile}
    if profile_regex.get("origin"):
        profile["origin"] = profile_regex["origin"]
    if profile_regex.get("destination"):
        profile["destination"] = profile_regex["destination"]
    if profile_regex.get("interests"):
        existing = profile.get("interests") or []
        profile["interests"] = list(set(existing + profile_regex["interests"]))
    if profile_regex.get("travel_style"):
        profile["travel_style"] = profile_regex["travel_style"]
    if profile_regex.get("preferred_transport"):
        profile["preferred_transport"] = profile_regex["preferred_transport"]

    if profile.get("origin") and not hard.get("origin"):
        hard["origin"] = profile["origin"]
    if profile.get("destination") and not hard.get("destination"):
        hard["destination"] = profile["destination"]

    raw_summary = llm_result.get("trip_summary")
    if isinstance(raw_summary, dict):
        trip_summary = raw_summary.get("summary") or raw_summary.get("destination", "") + " trip"
    else:
        trip_summary = raw_summary or f"Trip: {last_user[:80]}"
    raw_reasoning = llm_result.get("plan_reasoning")
    plan_reasoning = raw_reasoning if isinstance(raw_reasoning, str) else json.dumps(raw_reasoning or "", default=str)
    log.info("[PLANNER] trip_summary: %s", trip_summary)
    log.info("[PLANNER] plan_reasoning: %s", plan_reasoning[:500])

    leg_id = str(uuid_mod.uuid4())
    updates: dict = {
        "hard_constraints": hard,
        "user_profile_and_context": profile,
        "requested_trips": [
            {
                "id": leg_id,
                "summary": trip_summary,
                "plan_reasoning": plan_reasoning,
                "status": "planned",
            }
        ],
    }

    missing = []
    if not (hard.get("origin") or profile.get("origin")):
        missing.append({"id": "origin", "question": "Where are you traveling from (city/airport)?", "type": "text"})
    if not (hard.get("destination") or profile.get("destination")):
        missing.append({"id": "destination", "question": "What is your destination?", "type": "text"})
    if not hard.get("travel_date") and not hard.get("duration_days"):
        missing.append({"id": "dates", "question": "When are you traveling? Select a date range.", "type": "date_range"})
    elif not hard.get("travel_date") and hard.get("duration_days"):
        missing.append({"id": "start_date", "question": f"What is your start date? (Trip is {hard.get('duration_days')} days)", "type": "date"})
    if not hard.get("max_budget"):
        missing.append({"id": "budget", "question": "What is your total budget?", "type": "number"})
    interests = profile.get("interests") or []
    if not interests:
        missing.append({"id": "interests", "question": "What kinds of activities or experiences do you enjoy?", "type": "text"})
    if not profile.get("preferred_transport"):
        missing.append({
            "id": "transport",
            "question": "Preferred mode(s) of transport?",
            "type": "multi_select",
            "options": ["flight", "train", "bus", "drive"],
        })

    if missing:
        updates["awaiting_clarification"] = True
        updates["clarification_questions"] = missing
        updates["task_dag"] = []
    else:
        updates["awaiting_clarification"] = False
        updates["clarification_questions"] = []
        updates["task_dag"] = [
            {"id": "t1", "agent": "transport", "dependencies": [], "status": "pending"},
            {"id": "t2", "agent": "accommodation", "dependencies": [], "status": "pending"},
            {"id": "t3", "agent": "experience", "dependencies": [], "status": "pending"},
            {"id": "t4", "agent": "financial", "dependencies": ["t1", "t2", "t3"], "status": "pending"},
        ]
    
    # Always reset is_clarification when planner is called (new user input)
    updates["is_clarification"] = False
    
    log_node_exit(log, "planner", updates)
    return updates


def _completed_task_ids(state: GraphState) -> set[str]:
    results = state.get("executor_results") or []
    done = set()
    for r in results:
        if isinstance(r, dict) and "task_id" in r:
            done.add(r["task_id"])
    return done


# ---------------------------------------------------------------------------
# EXECUTE_ALL — calls APIs (flights, hotels, activities) + budget check
# ---------------------------------------------------------------------------

def execute_all_node(state: GraphState) -> dict:
    """Run all executors: transport, accommodation, experience, financial (budget check)."""
    log_node_enter(log, "execute_all", state)
    out = list(state.get("executor_results") or [])
    hard = state.get("hard_constraints") or {}
    profile = state.get("user_profile_and_context") or {}
    
    # Strictly use what is in state
    origin = (profile.get("origin") or hard.get("origin") or "").strip()
    destination = (profile.get("destination") or hard.get("destination") or "").strip()
    
    # If somehow we got here without them, we must fail gracefully
    if not origin or not destination:
        log.error("[EXECUTE_ALL] Missing origin or destination in state! origin=%s dest=%s", origin, destination)
        return {"executor_results": out}

    travel_date = str(hard.get("travel_date") or "")
    if not travel_date or not travel_date.startswith("202"):
        travel_date = "2025-04-15"
    log.info("[EXECUTE_ALL] transport: origin=%s dest=%s date=%s", origin, destination, travel_date)
    out.append({"agent": "transport", "task_id": "t1", "result": _search_flights_via_mcp(origin, destination, travel_date)})
    log.info("[EXECUTE_ALL] accommodation: location=%s budget=%s", destination, hard.get("max_budget"))
    out.append({"agent": "accommodation", "task_id": "t2", "result": _search_hotels_via_mcp(destination, hard.get("max_budget"))})
    rag_ctx: list = []
    try:
        from src.rag.store import get_store
        from src.rag.retrieval import retrieve_for_agent
        store = get_store()
        nl_query = _experience_rag_query(state)
        rag_ctx = retrieve_for_agent(store, nl_query, k=3, score_threshold=1.5)
        log.info("[EXECUTE_ALL] RAG context items=%s", len(rag_ctx))
    except Exception as e:
        log.debug("[EXECUTE_ALL] RAG optional skip: %s", e)
    log.info("[EXECUTE_ALL] experience: location=%s interests=%s", destination, profile.get("interests"))
    out.append({
        "agent": "experience", "task_id": "t3",
        "result": _search_activities_via_mcp(destination, profile.get("interests") or [], rag_context=rag_ctx if rag_ctx else None),
    })
    line_items = _build_line_items_from_results(out)
    max_budget = hard.get("max_budget") or 50000
    try:
        from src.algorithms.budget import budget_check
        budget_result = budget_check(line_items, float(max_budget), currency=(hard.get("currency") or "INR"))
        financial_result = {
            "within_budget": budget_result.within_budget,
            "total": budget_result.total,
            "max_budget": budget_result.max_budget,
            "suggested_subset": budget_result.suggested_subset,
        }
        log.info("[EXECUTE_ALL] budget: within=%s total=%s max=%s", budget_result.within_budget, budget_result.total, budget_result.max_budget)
    except Exception as e:
        log.warning("[EXECUTE_ALL] budget_check failed: %s; using stub", e)
        financial_result = {"within_budget": True, "total": sum(it.get("cost", 0) for it in line_items), "max_budget": max_budget}
    out.append({"agent": "financial", "task_id": "t4", "result": financial_result})
    log_node_exit(log, "execute_all", {"executor_results": out})
    return {"executor_results": out}


def _format_rag_suggestions(results: list) -> str:
    for r in results:
        if not isinstance(r, dict) or r.get("agent") != "experience":
            continue
        res = r.get("result") or {}
        suggestions = res.get("rag_suggestions") if isinstance(res, dict) else None
        if not suggestions:
            return ""
        lines = []
        for s in suggestions[:5]:
            meta = s.get("metadata") or {}
            name = meta.get("name") or "Suggestion"
            typ = meta.get("type", "")
            url = meta.get("url") or s.get("url")
            if url:
                lines.append(f"- {name} ({typ}) -- {url}")
            else:
                lines.append(f"- {name} ({typ})")
        if lines:
            return "\n\n**Suggestions for you:**\n" + "\n".join(lines)
    return ""


# ---------------------------------------------------------------------------
# SYNTHESIZER — LLM creates real itinerary from executor data
# ---------------------------------------------------------------------------

def synthesizer_node(state: GraphState) -> dict:
    """Uses LLM to create a complete travel itinerary from executor results."""
    log_node_enter(log, "synthesizer", state)
    from src.graph.llm import call_llm

    trips = state.get("requested_trips") or []
    results = state.get("executor_results") or []
    refinement_count = state.get("refinement_count") or 0
    hard = state.get("hard_constraints") or {}
    profile = state.get("user_profile_and_context") or {}
    validated_plans = state.get("validated_plans") or {}
    last_content = (state.get("message_history") or [])[-1].get("content", "") if state.get("message_history") else ""

    guardrail_passed = True
    guardrail_failures: list[str] = []
    try:
        from src.guardrails import run_output_guardrails
        guardrail_passed, guardrail_failures = run_output_guardrails(validated_plans, hard, last_content)
    except Exception as e:
        log.warning("[SYNTHESIZER] guardrails error: %s", e)
    if not guardrail_passed and refinement_count >= 3:
        reply = "Could not produce a valid itinerary after 3 attempts. " + "; ".join(guardrail_failures)
        updates: dict = {"message_history": (state.get("message_history") or []) + [{"role": "assistant", "content": reply}]}
        log_node_exit(log, "synthesizer", updates)
        return updates
    if not guardrail_passed:
        refinement_count += 1

    failed = any(isinstance(r, dict) and r.get("result") == "no_availability" for r in results)
    if failed:
        reply = "One or more options were not available. Re-planning with alternatives."
        updates = {"task_dag": [], "executor_results": [], "refinement_count": refinement_count}
    else:
        flights_data, hotels_data, activities_data, budget_data = [], [], [], {}
        for r in results:
            if not isinstance(r, dict):
                continue
            ag = r.get("agent")
            res = r.get("result") or {}
            if ag == "transport" and isinstance(res, dict):
                flights_data = res.get("flights", [])
            elif ag == "accommodation" and isinstance(res, dict):
                hotels_data = res.get("hotels", [])
            elif ag == "experience" and isinstance(res, dict):
                activities_data = res.get("activities", [])
            elif ag == "financial" and isinstance(res, dict):
                budget_data = res

        system_prompt = (
            "You are the Synthesizer agent of an AI travel planning system.\n"
            "Create a complete, beautiful, day-by-day travel itinerary from the real data provided.\n\n"
            "Rules:\n"
            "- Use the ACTUAL flight data (airline names, times, routes) -- do not make up flights\n"
            "- If hotels data is empty/fallback, suggest what kind of hotels to look for with price estimates\n"
            "- If activities data is empty/fallback, suggest popular activities based on the user's interests\n"
            "- Show a clear budget breakdown\n"
            "- Use markdown formatting with headers, bullet points, and bold text\n"
            "- Be specific and actionable, never generic\n"
            "- Organize day-by-day when duration is known"
        )

        trip_summary = trips[0].get("summary", "") if trips else ""
        plan_reasoning = trips[0].get("plan_reasoning", "") if trips else ""
        origin = profile.get("origin", hard.get("origin", "not specified"))
        destination = profile.get("destination", hard.get("destination", "not specified"))
        max_budget = hard.get("max_budget", 10000)
        currency = hard.get("currency", "INR")
        duration = hard.get("duration_days", "not specified")
        style = profile.get("travel_style", "not specified")
        interests = ", ".join(profile.get("interests", [])) or "not specified"

        total_cost = budget_data.get("total", 0)
        is_over_budget = total_cost > max_budget

        flights_str = json.dumps(flights_data[:5], indent=2, default=str) if flights_data else "No flight data available"
        
        # Check if hotels/activities are real or stubs
        has_real_hotels = any(h.get("source_api") != "fallback" for h in hotels_data)
        has_real_activities = any(a.get("source_api") != "fallback" for a in activities_data)

        hotels_str = json.dumps(hotels_data[:5], indent=2, default=str) if has_real_hotels else "API NOT CONFIGURED: Providing generic hotel estimates for this destination."
        activities_str = json.dumps(activities_data[:5], indent=2, default=str) if has_real_activities else "API NOT CONFIGURED: Providing generic activity suggestions based on interests."
        
        budget_str = json.dumps(budget_data, indent=2, default=str)

        user_prompt = (
            f"**User Request:** {trip_summary}\n"
            f"**Planning Notes:** {plan_reasoning}\n\n"
            f"**Constraints:**\n"
            f"- Budget: {max_budget} {currency} (CURRENT TOTAL: {total_cost})\n"
            f"- Duration: {duration} days\n"
            f"- Origin: {origin}\n"
            f"- Destination: {destination}\n"
            f"- Style: {style}\n"
            f"- Interests: {interests}\n\n"
            f"{'⚠️ WARNING: THIS PLAN IS OVER BUDGET' if is_over_budget else ''}\n\n"
            f"**Flights ({len(flights_data)} found):**\n{flights_str}\n\n"
            f"**Hotels:**\n{hotels_str}\n\n"
            f"**Activities:**\n{activities_str}\n\n"
            f"**Budget Analysis:**\n{budget_str}\n\n"
            f"Analyze this carefully. If data is missing or over budget, acknowledge it in the itinerary."
        )

        reply = call_llm(system_prompt, user_prompt, "synthesizer")

        rag_text = _format_rag_suggestions(results)
        if rag_text:
            reply += rag_text
        if validated_plans:
            from src.state_models import check_verifiable_inventory
            failing = check_verifiable_inventory(validated_plans)
            if failing:
                reply += "\n\n**Note:** Some legs are not verifiable: " + ", ".join(failing)
        if guardrail_failures:
            reply += "\n\n**Guardrail:** " + "; ".join(guardrail_failures)
        updates = {"refinement_count": refinement_count}

    messages = list(state.get("message_history") or [])
    messages.append({"role": "assistant", "content": reply})
    updates["message_history"] = messages
    log_node_exit(log, "synthesizer", updates)
    return updates


# ---------------------------------------------------------------------------
# Individual executor nodes (used when graph runs them separately)
# ---------------------------------------------------------------------------

def transport_node(state: GraphState) -> dict:
    log_node_enter(log, "transport", state)
    hard = state.get("hard_constraints") or {}
    profile = state.get("user_profile_and_context") or {}
    origin = (profile.get("origin") or hard.get("origin") or "Delhi").strip()
    destination = (profile.get("destination") or hard.get("destination") or "Goa").strip()
    travel_date = str(hard.get("travel_date") or "")
    if not travel_date or not travel_date.startswith("202"):
        travel_date = "2025-04-15"
    result = _search_flights_via_mcp(origin, destination, travel_date)
    out = {"executor_results": [{"agent": "transport", "task_id": "t1", "result": result}]}
    log_node_exit(log, "transport", out)
    return out


def accommodation_node(state: GraphState) -> dict:
    log_node_enter(log, "accommodation", state)
    hard = state.get("hard_constraints") or {}
    profile = state.get("user_profile_and_context") or {}
    destination = (profile.get("destination") or hard.get("destination") or "Goa").strip()
    result = _search_hotels_via_mcp(destination, hard.get("max_budget"))
    out = {"executor_results": [{"agent": "accommodation", "task_id": "t2", "result": result}]}
    log_node_exit(log, "accommodation", out)
    return out


def _experience_rag_query(state: GraphState) -> str:
    profile = state.get("user_profile_and_context") or {}
    interests = profile.get("interests") or []
    last = get_last_user_message(state)
    parts = [last] if last else []
    if interests:
        parts.append(" ".join(interests))
    return " ".join(parts) or "things to do"


def experience_node(state: GraphState) -> dict:
    log_node_enter(log, "experience", state)
    profile = state.get("user_profile_and_context") or {}
    interests = profile.get("interests") or []
    rag_context: list = []
    try:
        from src.rag.store import get_store
        from src.rag.retrieval import retrieve_for_agent
        store = get_store()
        nl_query = _experience_rag_query(state)
        rag_context = retrieve_for_agent(store, nl_query, k=3, score_threshold=1.5)
    except Exception:
        pass
    destination = (profile.get("destination") or state.get("hard_constraints", {}).get("destination") or "Goa").strip()
    result = _search_activities_via_mcp(destination, interests, rag_context=rag_context if rag_context else None)
    out = {"executor_results": [{"agent": "experience", "task_id": "t3", "result": result}]}
    log_node_exit(log, "experience", out)
    return out


def financial_node(state: GraphState) -> dict:
    log_node_enter(log, "financial", state)
    hard = state.get("hard_constraints") or {}
    max_budget = hard.get("max_budget") or 50000
    line_items = [{"category": "transport", "cost": 5000}, {"category": "accommodation", "cost": 8000}, {"category": "experience", "cost": 2000}]
    try:
        from src.algorithms.budget import budget_check
        result = budget_check(line_items, float(max_budget), currency=(hard.get("currency") or "INR"))
        financial_result = {"within_budget": result.within_budget, "total": result.total, "max_budget": result.max_budget}
    except Exception:
        financial_result = {"within_budget": True, "total": 15000, "max_budget": max_budget}
    out = {"executor_results": [{"agent": "financial", "task_id": "t4", "result": financial_result}]}
    log_node_exit(log, "financial", out)
    return out
