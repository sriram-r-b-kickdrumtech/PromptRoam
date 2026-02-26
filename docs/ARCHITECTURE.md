# PromptRoam Architecture

> Autonomous multi‑agent travel planning system with HITL checkpoints, RAG, and deterministic early‑stage routing.

---

## 1. Executive Summary
PromptRoam is a modular travel‑planning platform that blends deterministic parsing, multi‑agent execution, MCP‑mediated API access, and human‑in‑the‑loop (HITL) approvals. The system is optimized for reliability in early stages (explicit constraints extraction + clarifications) and flexibility in later stages (LLM‑driven synthesis and itinerary composition).

Key principles:
1. **Deterministic early layers** for clarity, speed, and user trust.  
2. **LLM flexibility later** only when structure is established.  
3. **Single graph entrypoint** (Supervisor) with explicit control paths.  
4. **HITL pauses** before final synthesis.  
5. **MCP-only API access** (with caching and fallback).  
6. **Structured outputs** (Pydantic‑validated itineraries).

---

## 2. System Topology

**Frontend (Vite + React + Tailwind)**
- Chat + status UI
- Clarification forms
- Approval UI
- Thread ID persistence (`?thread_id=...`)
- JSON download

**Backend (FastAPI + LangGraph)**
- `/chat`, `/clarify`, `/action`, `/state`, `/mcp/call`
- Graph state persisted via LangGraph checkpointer
- Deterministic routing for low latency

**Execution Layer**
- Graph nodes: Supervisor → Planner → Execute → Synthesizer
- Executors: transport, accommodation, experience, financial
- HITL checkpoint before synthesis

**RAG Layer**
- Knowledge objects + HyDE/HyPE
- Metadata filters + threshold gating

**MCP Layer**
- MCP gateway + local MCP server
- Redis caching for MCP + LLM fallbacks

---

## 3. Request Lifecycle (Happy Path)

1. **User sends prompt**  
   `POST /chat`  

2. **Supervisor (deterministic)**  
   Routes to planner.

3. **Planner**  
   Extracts hard constraints + profile  
   Builds DAG  
   If missing info → Clarification questions returned

4. **User clarifies**  
   `POST /clarify`  
   State updated, Planner re‑executes

5. **Execute_all**  
   Parallel execution of Transport, Accommodation, Experience + Budget
   MCP call attempts → fallback to LLM JSON if needed

6. **HITL**  
   User approves / rejects

7. **Synthesis (LLM)**  
   Generates structured itinerary  
   Validated + serialized

8. **Completion**  
   UI shows approval + itinerary

---

## 4. Data Model

### GraphState (Core)
- `hard_constraints`  
- `user_profile_and_context`  
- `requested_trips`  
- `task_dag`  
- `executor_results`  
- `validated_plans`  
- `structured_itinerary`  
- `awaiting_clarification`  
- `clarification_questions`  

### ClarificationQuestion (UI Contract)
```json
{
  "id": "dates",
  "question": "Select your travel date range (Trip is 3 days).",
  "type": "date_range",
  "duration_days": 3
}
```

### Structured Itinerary (Pydantic)
- `summary`
- `days[]`
- `budget`
- `warnings`
- `sources`

---

## 5. Deterministic vs Dynamic Logic

**Deterministic (Early)**  
- Routing decisions  
- Clarification detection  
- Constraint parsing  

**Dynamic (Later)**  
- Itinerary generation  
- Creative narrative  
- RAG synthesis  

This division reduces latency and prevents state drift.

---

## 6. HITL (Human‑in‑the‑Loop)

HITL is triggered before synthesis:
- User reviews draft proposal
- Approve → synthesize
- Reject → re‑plan

---

## 7. MCP + Caching Strategy

- MCP is the only path to external APIs
- Redis caches:
  - MCP calls  
  - LLM fallback responses  
- If MCP fails → structured LLM fallback

**Benefits**  
Low latency, reproducibility, cost control.

---

## 8. RAG Layer

- Knowledge Objects (schema.org‑aligned)
- Metadata filters (NL → filters)
- HyDE/HyPE for semantic gap
- Threshold gating

---

## 9. Failure Handling

1. **Missing user input**  
   → Clarification questions  

2. **MCP unavailable**  
   → LLM JSON fallback + cached results  

3. **Graph recursion risk**  
   → deterministic routing, single pass after execute_all  

4. **Budget violations**  
   → financial agent + warning  

---

## 10. Extensibility Roadmap

- **Phase 9:** Real API integrations via MCP
- **Phase 11:** Editable checkpoints
- **Phase 12:** CRAG / corrective retrieval
- **Phase 13:** Disruption replan (DyFlow)
- **Phase 15:** Production hardening + Docker

---

## 11. Key Files

- `app/api.py` — FastAPI endpoints  
- `src/graph/workflow.py` — LangGraph wiring  
- `src/graph/nodes.py` — Node implementations  
- `src/graph/intent.py` — Deterministic parsing  
- `src/mcp_gateway.py` — MCP + cache  
- `src/services/llm_fallbacks.py` — JSON fallbacks  
- `frontend/src` — UI + Clarifications  

---

## 12. Design North‑Star

**“Decide early, create late.”**  
The system’s architecture ensures that the earliest steps are fast, explainable, and deterministic. Only after the system knows what the user actually wants does it switch into generative mode.

This creates a travel assistant that’s **fast**, **trustworthy**, and **scalable** without sacrificing the creative power of LLMs.  

---

End of document.*** End Patch}"}}
