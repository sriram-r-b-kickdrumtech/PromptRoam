from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.env import validate_env
from config.logging_config import get_logger

validate_env()
log = get_logger(__name__)

from src.graph.workflow import get_graph
from src.persistence import config_for_thread, get_thread_state

app = FastAPI(title="PromptRoam API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"ok": True}

class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

class ClarificationRequest(BaseModel):
    thread_id: str
    answers: dict[str, str]

class ActionRequest(BaseModel):
    thread_id: str
    action: str  # "approve", "reject"

class StateResponse(BaseModel):
    thread_id: str
    messages: list[Any]
    interrupt_pending: bool
    awaiting_clarification: bool
    clarification_questions: list[Any]
    executor_results: list[Any]
    requested_trips: list[Any]
    validated_plans: dict[str, Any]

class McpCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}
    ttl_seconds: int | None = 3600
    category: str | None = None

class McpCallResponse(BaseModel):
    ok: bool
    result: dict[str, Any] | None
    cached: bool = False
    error: str | None = None


def _call_local_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import importlib.util
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
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
        if isinstance(text, str):
            import json
            payload = json.loads(text)
        else:
            payload = text
        return {"structuredContent": payload, "content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}
    except Exception as e:
        return {"isError": True, "content": [{"type": "text", "text": str(e)}]}

def _build_response(thread_id: str, state: dict, interrupt_pending: bool) -> StateResponse:
    return StateResponse(
        thread_id=thread_id,
        messages=state.get("message_history", []),
        interrupt_pending=interrupt_pending,
        awaiting_clarification=state.get("awaiting_clarification", False),
        clarification_questions=state.get("clarification_questions", []),
        executor_results=state.get("executor_results", []),
        requested_trips=state.get("requested_trips", []),
        validated_plans=state.get("validated_plans", {})
    )

def _apply_clarifications(answers: dict[str, str], state: dict) -> dict:
    """Merge clarification answers into hard_constraints/user_profile."""
    hard = dict(state.get("hard_constraints") or {})
    profile = dict(state.get("user_profile_and_context") or {})
    for k, v in (answers or {}).items():
        if not v:
            continue
        key = k.strip().lower()
        val = str(v).strip()
        if key in ("origin", "from"):
            profile["origin"] = val.title()
        elif key in ("destination", "to"):
            profile["destination"] = val.title()
        elif key in ("budget", "max_budget"):
            try:
                amt = int("".join(ch for ch in val if ch.isdigit()) or 0)
                if amt:
                    hard["max_budget"] = amt
                    hard["currency"] = hard.get("currency") or "INR"
            except Exception:
                pass
        elif key in ("dates", "date", "travel_date", "start_date", "end_date"):
            if val:
                hard["travel_date"] = val
        elif key in ("duration", "duration_days", "days"):
            try:
                d = int("".join(ch for ch in val if ch.isdigit()) or 0)
                if d:
                    hard["duration_days"] = d
            except Exception:
                pass
        elif key in ("interests", "activities"):
            interests = [x.strip() for x in val.split(",") if x.strip()]
            if interests:
                profile["interests"] = list(set((profile.get("interests") or []) + interests))
        elif key in ("transport", "preferred_transport", "mode"):
            profile["preferred_transport"] = val
    return {"hard_constraints": hard, "user_profile_and_context": profile}

@app.post("/thread/new")
async def new_thread():
    return {"thread_id": f"thread-{uuid.uuid4().hex[:8]}"}

@app.get("/state/{thread_id}", response_model=StateResponse)
async def get_state(thread_id: str):
    graph = get_graph(use_interrupt=False)
    config = config_for_thread(thread_id)
    try:
        snap = graph.get_state(config)
        state_value = snap.values if hasattr(snap, "values") else {}
        next_nodes = getattr(snap, "next", None) or []
        interrupt_pending = bool(next_nodes)
        return _build_response(thread_id, state_value, interrupt_pending)
    except Exception as e:
        log.error(f"Error getting state: {e}")
        return _build_response(thread_id, {}, False)

@app.post("/chat", response_model=StateResponse)
async def chat(req: ChatRequest):
    graph = get_graph(use_interrupt=False)
    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    config = config_for_thread(thread_id)
    if not (req.message or "").strip():
        raise HTTPException(status_code=400, detail="message is required")
    
    # Read existing state to get history
    snap = graph.get_state(config)
    state_value = snap.values if hasattr(snap, "values") else {}
    messages = list(state_value.get("message_history") or [])
    
    messages.append({"role": "user", "content": req.message})
    initial_state = {"message_history": messages}
    
    interrupt_pending = False
    try:
        for chunk in graph.stream(initial_state, config, stream_mode="updates"):
            pass
        
        snap = graph.get_state(config)
        state_value = snap.values if hasattr(snap, "values") else {}
        next_nodes = getattr(snap, "next", None) or []
        interrupt_pending = bool(next_nodes)
    except Exception as e:
        log.error(f"Graph error in /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    return _build_response(thread_id, state_value, interrupt_pending)

@app.post("/mcp/call", response_model=McpCallResponse)
async def mcp_call(req: McpCallRequest):
    try:
        from src.mcp_gateway import call_mcp_tool_cached, _mcp_cache_enabled
        from src.cache import cache_get_mcp, cache_set_mcp
        args = req.arguments or {}
        cached = False

        # MCP gateway (with cache)
        result = call_mcp_tool_cached(
            req.tool,
            args,
            ttl_seconds=req.ttl_seconds,
            category=req.category,
        )
        if result is not None:
            return McpCallResponse(ok=True, result=result, cached=bool(result.get("cached")) if isinstance(result, dict) else False)

        # Local MCP fallback (and cache if enabled)
        if _mcp_cache_enabled():
            cached_result = cache_get_mcp(req.tool, args)
            if cached_result is not None:
                return McpCallResponse(ok=True, result=cached_result, cached=True)

        result = _call_local_mcp_tool(req.tool, args)
        if result is not None:
            if _mcp_cache_enabled() and req.ttl_seconds and not result.get("isError"):
                try:
                    cache_set_mcp(req.tool, args, result, ttl_seconds=req.ttl_seconds)
                    cached = True
                except Exception:
                    pass
            return McpCallResponse(ok=True, result=result, cached=cached)

        return McpCallResponse(ok=False, result=None, error="MCP not configured or tool not found")
    except Exception as e:
        return McpCallResponse(ok=False, result=None, error=str(e))

@app.post("/clarify", response_model=StateResponse)
async def clarify(req: ClarificationRequest):
    graph = get_graph(use_interrupt=False)
    config = config_for_thread(req.thread_id)
    
    snap = graph.get_state(config)
    state_value = snap.values if hasattr(snap, "values") else {}
    messages = list(state_value.get("message_history") or [])
    
    details = "; ".join([f"{k}={v}" for k, v in req.answers.items() if v])
    if details:
        messages.append({"role": "user", "content": f"Clarifications: {details}"})
        
    initial_state = {
        "message_history": messages,
        "awaiting_clarification": False,
        "clarification_questions": []
    }
    initial_state.update(_apply_clarifications(req.answers, state_value))
    
    interrupt_pending = False
    try:
        for chunk in graph.stream(initial_state, config, stream_mode="updates"):
            pass
        
        snap = graph.get_state(config)
        state_value = snap.values if hasattr(snap, "values") else {}
        next_nodes = getattr(snap, "next", None) or []
        interrupt_pending = bool(next_nodes)
    except Exception as e:
        log.error(f"Graph error in /clarify: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    return _build_response(req.thread_id, state_value, interrupt_pending)

@app.post("/action", response_model=StateResponse)
async def action(req: ActionRequest):
    graph = get_graph(use_interrupt=False)
    config = config_for_thread(req.thread_id)
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    
    if req.action == "reject":
        snap = graph.get_state(config)
        state_value = snap.values if hasattr(snap, "values") else {}
        messages = list(state_value.get("message_history") or [])
        messages.append({"role": "user", "content": "Please re-plan with different options."})
        initial_state = {"message_history": messages}
        
        # We might need to restart the graph stream if we reject
        try:
            for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                pass
        except Exception as e:
            log.error(f"Graph error in /action (reject): {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    elif req.action == "approve":
        try:
            for chunk in graph.stream(None, config, stream_mode="updates"):
                pass
        except Exception as e:
            log.error(f"Graph error in /action (approve): {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    snap = graph.get_state(config)
    state_value = snap.values if hasattr(snap, "values") else {}
    next_nodes = getattr(snap, "next", None) or []
    interrupt_pending = bool(next_nodes)
    
    return _build_response(req.thread_id, state_value, interrupt_pending)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
