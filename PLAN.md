# PromptRoam — Implementation Plan

Step-by-step checklist for building the Autonomous Multi-Agent Travel Planning System. Aligned with `AI_Hackathon_Design_initial.md` and `.cursorrules`.

---

## Critical Issues Identified & Fixes Applied

*Review as a criticising architect across both the design doc and the original plan.*

| # | Critical issue | Fix applied |
|---|----------------|-------------|
| 1 | **Intent/constraint extraction** not explicit; design stresses “linguistic density” and dynamic decomposition. | Phase 5: Add explicit task to extract hard constraints and user-profile hints from the first user message into state *before* or inside Planner; avoid implicit or hardcoded decomposition. |
| 2 | **Persistence** tied to implementation; swapping MemorySaver → AsyncPostgresSaver would touch graph code. | Phase 2: Abstract persistence behind an interface (e.g. get/put thread state); document swap path so graph nodes do not depend on concrete backend. |
| 3 | **Env/API keys** only in .env.example; missing keys discovered mid-flow. | Phase 1: Add startup validation of required env vars (or fail fast with a clear message). |
| 4 | **Graph entry** ambiguous; design requires Supervisor as single cognitive router. | Phase 4: Explicit task: set graph’s single entry point to the Supervisor node only. |
| 5 | **DAG representation** in state unspecified; parallel execution and “one leg” updates depend on it. | Phase 5: Define in-state DAG representation (e.g. task list with IDs and dependencies or leg IDs) so Supervisor can dispatch and Synthesizer can wait; Phase 6 reducers use same schema. |
| 6 | **Parallel execution** vague; design requires parallel executors where DAG allows. | Phase 5: Use LangGraph’s parallel invocation (e.g. Send API or fan-out to Transport/Accommodation/Experience in one step) when DAG has no inter-executor dependencies. |
| 7 | **RAG metadata filtering** design says “Orchestrator LLM extracts filters”; pipeline undefined. | Phase 7: Implement NL → metadata filter extraction (LLM or rules) *before* vector search; pick one vector store with metadata support (e.g. Chroma). |
| 8 | **HyPE** is offline; no runnable ingestion. | Phase 8: Add ingestion script/CLI to build HyPE index (hypothetical questions per chunk); run as offline or one-time-per-refresh step. |
| 9 | **.cursorrules** mandate MCP as gateway; plan said “MCP or tool layer”. | Phase 9: Treat MCP as primary; expose travel APIs as MCP tools; document fallback to direct tool layer if MCP not yet integrated. |
| 10 | **“No hallucinated inventory”** not testable. | Phase 9: Define criterion: every itinerary item has at least one of `booking_url`, `external_id`, or `price_quote` (with source and timestamp). |
| 11 | **TSP with time windows** is a large build; risk of scope creep. | Phase 10: MVP: use a library (e.g. OR-Tools) or simple heuristic (nearest-neighbor + time-window check); replace with ILS/ACO later if needed. |
| 12 | **HITL “Edit”** undefined—what can user change at each checkpoint? | Phase 11: Define Edit surface per checkpoint (e.g. shortlist: add/remove; budget: sliders; booking: confirm/cancel). |
| 13 | **Guardrail refinement loop** could run forever. | Phase 12: Cap refinement (e.g. max 3 iterations); after that, halt and surface error to user. |
| 14 | **DyFlow “disruption”** input unspecified. | Phase 13: Support (1) user message in chat and (2) API/webhook for flight status; parse into structured event (e.g. `affected_leg_id`, `new_times`, `reason`). |
| 15 | **Design** mentions “RESTful API endpoints” for decoupling; plan is Streamlit-only. | Phase 3: Note that Streamlit talks to LangGraph in-process for hackathon; optional later: FastAPI/Flask layer for programmatic/mobile access. |

---

## Phase 1: Project Initialization

- [x] Create project directory structure (`src/`, `app/`, `tests/`, `config/`, `docs/`)
- [x] Set up **conda** environment and dependency management (`environment.yml`, `requirements.txt`, optional `pyproject.toml`)
- [x] Install core dependencies: `langgraph`, `langchain-core`, `langchain-openai` (or chosen LLM), `streamlit`, `pydantic`, `python-dotenv`
- [x] Add supporting libs: `httpx`, `folium` or `plotly`, `fpdf2` (for PDF export); `firecrawl-py` when integrating (optional)
- [x] Create `.env.example` with placeholders for API keys (Amadeus, Expedia, Kiwi, OpenWeatherMap/Tomorrow.io, Firecrawl, LLM)
- [x] Add startup validation: app or CLI fails fast with a clear message if required env vars are missing (at least LLM key for early phases)
- [x] Configure basic tooling: Ruff (in pyproject.toml), optional Black/mypy; add pre-commit or CI stub if desired
- [x] Add a minimal `README.md` with setup (conda) and run instructions

### Expected results (how to test)

- [x] `conda env create -f environment.yml` then `conda activate promptroam` (or `conda create -n promptroam python=3.11 -y && conda activate promptroam && pip install -r requirements.txt`) succeed.
- [x] Running `python -c "from config.env import validate_env; validate_env()"` with no `OPENAI_API_KEY` exits with a clear error (e.g. “Missing required environment variable(s): OPENAI_API_KEY”).
- [x] With `.env` populated (at least `OPENAI_API_KEY`), the same command completes without error.
- [x] `ruff check .` runs and passes on project code (ruff installed in conda env via requirements.txt).

**Phase 1 complete.**

---

## Phase 2: Database & Persistence Setup

- [x] Choose persistence: start with LangGraph `MemorySaver` for development.
- [x] Abstract persistence behind an interface (e.g. `get_checkpointer()`, `get_thread_state(thread_id)`) so swapping to `AsyncPostgresSaver` does not require changing graph code; document migration path in `src/persistence.py` and `docs/persistence-migration.md`.
- [x] Define the **graph state** `TypedDict` (or minimal Pydantic model) with:
  - [x] `user_profile_and_context` (preferences, accessibility, travel style)
  - [x] `hard_constraints` (max budget, date range, max duration)
  - [x] `requested_trips` (array of trip legs with stable UUIDs)
  - [x] `validated_plans` (dict keyed by trip UUID: API-validated bookings and links)
  - [x] `message_history` (conversation for multi-turn and transparency)
- [x] Implement state reducer/update helpers so individual legs can be updated without corrupting the rest of the itinerary (`update_validated_plan_leg`, `update_requested_trip_leg`).
- [x] Wire LangGraph checkpointing to the persistence abstraction (thread/session IDs via `config_for_thread(thread_id)` for HITL resume).

### Expected results (how to test)

- [x] State type is importable and type-checkers accept it (e.g. `mypy` or IDE).
- [x] Unit test: reducer updates one leg in `validated_plans` by UUID and leaves other keys unchanged.
- [x] With MemorySaver, run a minimal graph that writes and reads state by `thread_id`; assert state round-trips correctly.
- [x] Documentation or code comment describes how to swap in AsyncPostgresSaver without changing node logic (`src/persistence.py`, `docs/persistence-migration.md`).

**Phase 2 complete.** Run: `python -m pytest tests/ -v`

---

## Phase 3: Basic UI (Streamlit Shell)

- [x] Create Streamlit entry point (e.g. `app/main.py` or `streamlit run app/main.py`).
- [x] Implement simple layout: sidebar for session/thread selection, main area for chat.
- [x] Add user input: text area or chat input for travel request (dates, budget, destination, preferences).
- [x] Add placeholder area for agent response and “reasoning in progress” indicator.
- [x] Add minimal styling and clear sections (input vs output vs logs).
- [x] Ensure app runs end-to-end with a stub “echo” response (no agents yet).
- [x] Note: Streamlit talks to LangGraph in-process for the hackathon; optional later: FastAPI/Flask layer for programmatic or mobile access.

### Expected results (how to test)

- [x] `streamlit run app/main.py` launches; no console errors (requires `.env` with `OPENAI_API_KEY`).
- [x] User can type a message and see a stub echo (e.g. “You said: …”) in the response area.
- [x] Sidebar shows session/thread selector (can be a single default for now).
- [x] Layout clearly separates input, output, and (placeholder) logs.

**Phase 3 complete.** Run: `streamlit run app/main.py`

---

## Phase 4: LangGraph Skeleton & Supervisor

- [x] Create LangGraph workflow module (e.g. `src/graph/` or `src/workflow/`).
- [x] Set the graph’s **single entry point** to the **Supervisor** node only (no direct entry to Planner or Executors).
- [x] Implement **Supervisor** node: no external API tools; only state inspection, constraint checks, delegation decisions.
- [x] Add placeholder nodes: **Planner**, **Transport**, **Accommodation**, **Experience**, **Financial**, **Synthesizer**.
- [x] Define graph edges: entry → Supervisor; Supervisor → Planner or Executors or Synthesizer; Executors → Synthesizer; Synthesizer → Supervisor or END.
- [x] Implement conditional routing from Supervisor (e.g. “plan” vs “execute” vs “synthesize” vs “interrupt”).
- [x] Integrate **StreamlitCallbackHandler** so token-by-token reasoning and node transitions stream into the Streamlit UI (node transitions via `stream_mode="updates"` in Reasoning & logs).
- [x] Run a minimal flow: user message → Supervisor → Planner (stub) → Synthesizer (stub) → response in UI.

### Expected results (how to test)

- [x] Invoking the graph always enters via Supervisor first (inspect graph definition or add a log at Supervisor entry).
- [x] Supervisor never has tools that call external APIs (grep or static check).
- [x] From UI, submit one message; response area shows a synthesized reply; Streamlit shows node transitions (e.g. Supervisor → Planner → Synthesizer) in the callback area.
- [x] No runtime errors for one full stub flow.

**Phase 4 complete.** Run: `streamlit run app/main.py` then send a message; run: `python -m pytest tests/test_graph_phase4.py -v`

---

## Phase 5: Plan-and-Execute & Agent Topology

- [x] **Intent & constraints:** Extract hard constraints (budget, dates, duration) and user-profile hints from the first user message into state (`hard_constraints`, `user_profile_and_context`) before or inside the Planner; no hardcoded “three-part” decomposition.
- [x] **Planner Agent:** Accept user intent and state; output a **DAG of discrete tasks** (e.g. fetch transport, accommodation, weather, optimize budget).
- [x] **In-state DAG representation:** Define how the DAG is stored in state (e.g. list of tasks with IDs and dependencies, or leg IDs with dependency list) so Supervisor can dispatch and Synthesizer can wait for completion.
- [x] **Executor agents** (stub tools first):
  - [x] **Transport Agent:** tools for flight/train/route APIs (stub)
  - [x] **Accommodation Agent:** tools for hotel search (stub)
  - [x] **Experience Agent:** tools for activities, weather, “hidden gems” (stub)
  - [ ] **Financial Agent:** tools for price checks and budget math (stub)
- [x] **Synthesizer Agent:** Aggregate executor outputs; detect critical failures (e.g. no availability); trigger targeted re-plan (adjust DAG) when needed.
- [x] Wire Supervisor to delegate to Planner vs specific Executors vs Synthesizer based on state and DAG.
- [x] **Parallel execution:** Use LangGraph’s parallel node invocation (e.g. Send API or fan-out to Transport/Accommodation/Experience in one step) where the DAG has no dependencies between those executors.
- [x] End-to-end test: one full plan → execute (stub) → synthesize cycle.

### Expected results (how to test)

- [x] Given a rich prompt (e.g. “4-day Rishikesh under ₹15k, adventure + spiritual, from Delhi next weekend”), state contains populated `hard_constraints` and/or `user_profile_and_context` (inspect state after Planner).
- [x] Planner output is a structured DAG (e.g. list of tasks with IDs/dependencies); Supervisor uses it to decide next node(s).
- [x] When DAG allows, Transport and Accommodation (or other pair) run in one step without sequential dependency; graph visualization or logs show parallel invocation.
**Phase 5 complete.** Run: `python -m pytest tests/test_graph_phase5.py tests/test_graph_phase4.py -v`
- [x] One full run produces a synthesized text response in the UI; if a stub “failure” is simulated, Synthesizer triggers a re-plan path (e.g. Planner invoked again with updated state).

---

## Phase 6: State Schema & Trip Identity

- [x] Finalize state schema with Pydantic models where appropriate (e.g. for `validated_plans`, trip legs).
- [x] Ensure every requested trip leg has a stable UUID for targeted edits and DyFlow.
- [x] Implement reducer/update logic so one leg can be updated (e.g. after replan) without overwriting others; align with the DAG/leg representation from Phase 5.
- [x] Add validation: hard constraints (budget, dates) checked before committing to `validated_plans`.

### Expected results (how to test)

- [x] Pydantic models validate sample `validated_plans` and trip leg payloads; invalid payloads raise validation errors.
- [x] Reducer test: update leg `uuid-A` only; `validated_plans[uuid-B]` unchanged.
- [x] Validation test: committing a plan that exceeds stated budget (or outside date range) is rejected or flagged before write.

**Phase 6 complete.** Run: `python -m pytest tests/test_state_phase6.py tests/test_state.py -v`

---

## Phase 7: RAG & Knowledge Objects

- [x] Design **Knowledge Object** schema (JSON-LD, Schema.org-aligned: e.g. `Hotel`, `TouristAttraction`, `TouristTrip`).
- [x] Build ingestion pipeline: **no fixed-size chunking**; document/semantic-aware parsing so pricing, links, and metadata stay bound to entities.
- [x] Set up one vector store with metadata filter support (e.g. **Chroma** or LangChain integration); store metadata fields (price_tier, location, amenities, seasonality, etc.).
- [x] Implement **NL → metadata filter extraction** (e.g. small LLM call or rule-based) from the user prompt before vector search; apply filters at query time to narrow the search space.
- [x] Implement **threshold-gated reranking**: retain absolute confidence scores; do not use pure RRF; halt or notify user when no result passes the threshold.
- [x] Connect RAG retrieval to Experience (and optionally Accommodation) agents for qualitative suggestions.

### Expected results (how to test)

- [x] Ingest a small set of documents (e.g. 2–3 hotels with pricing/links); query by metadata (e.g. `price_tier < 100`) returns only matching entities; pricing and booking link remain attached to the correct entity.
- [x] A vague query (e.g. “spiritual stay”) plus extracted filters returns a bounded result set; no raw RRF merge without scores.
- [x] When threshold is set and no document passes, the pipeline returns “no results” or a clear signal instead of returning low-confidence items as top results.
- [x] Experience agent (or stub) can call the RAG layer and receive structured Knowledge Objects (not plain text chunks).

**Phase 7 complete.** Run: `python -m pytest tests/test_rag_phase7.py -v`. RAG: `src/rag/` (schema, ingestion, store, retrieval). Experience node and execute_all call `retrieve_for_agent` when store is available.

---

## Phase 8: HyDE & HyPE (Semantic Gap)

- [x] **HyDE:** For vague queries (e.g. “spiritual adventure”), generate a hypothetical ideal answer with the LLM, embed it, search the vector store with that embedding.
- [x] **HyPE:** Add an **ingestion script or CLI** that, for each chunk, generates hypothetical user questions and stores their embeddings with chunk metadata; run as an offline or one-time-per-refresh step.
- [x] Integrate HyDE (and HyPE if used) into the RAG path used by agents.

### Expected results (how to test)

- [x] HyDE: Given “spiritual adventure”, the system returns relevant results (e.g. bungee/Ganges) that would not rank highly for the raw query embedding alone; compare with and without HyDE on the same query.
- [x] HyPE: Run the ingestion script on a small corpus; index builds without errors; a query that matches one of the hypothetical questions returns the corresponding chunk.
- [x] End-to-end: one agent query that triggers HyDE (or HyPE) returns context that is used in the response.

**Phase 8 complete.** Run: `python -m pytest tests/test_rag_phase8.py -v`. HyDE: `src/rag/hyde.py` + `retrieve_for_agent(..., use_hyde=True)`. HyPE: `python scripts/ingest_sample.py --hype`.

---

## Phase 9: External APIs & MCP Gateway

- [ ] Introduce **MCP** as the primary gateway for external APIs; expose travel APIs as MCP tools; document fallback to a direct tool layer if MCP is not yet integrated.
- [ ] **Flights:** Integrate Amadeus Travel API and/or Skyscanner; real-time pricing and delay info for replanning.
- [ ] **Accommodation:** Integrate Expedia Rapid API; dynamic pricing and direct booking URLs.
- [ ] **Routing:** Integrate Kiwi.com (Tequila) for multi-city and complex itineraries.
- [ ] **Weather:** Integrate OpenWeatherMap or Tomorrow.io; feed forecasts into state for activity rescheduling.
- [ ] **Scraping:** Integrate Firecrawl for forums/blogs; parse Markdown with Pydantic into **HiddenGems** objects and attach to itinerary state.
- [x] Replace executor stubs with live (or sandbox) API calls when keys present; RapidAPI client with key from env; stubs used when key missing.
- [x] **Verifiable inventory:** Enforce that every itinerary item has at least one of: `booking_url`, `external_id`, or `price_quote` (with source and timestamp); no hallucinated inventory. Implemented in `state_models.check_verifiable_inventory`; synthesizer warns when legs fail.
- [x] **Redis cache:** Dedicated Redis instance (default port 6380) caches API responses to reduce cost and latency; see `docs/redis-setup.md`. No change to existing cluster.

### Expected results (how to test)

- [ ] Each approved API (flights, accommodation, routing, weather) is callable via MCP or direct tool and returns valid, non-empty responses for at least one test query (e.g. fixed route and dates).
- [ ] Firecrawl returns Markdown; parsing produces at least one `HiddenGems`-like object (Pydantic validation passes).
- [x] A full itinerary produced by the graph has every item passing the verifiable-inventory check (script or assertion). Run: `python -m pytest tests/test_phase9_verifiable_inventory.py -v`.
- [ ] Missing or invalid API key for a provider fails fast or is handled with a clear user-facing message.

**Phase 9 (partial).** Implemented: RapidAPI client with env key + Redis cache (new cluster on port 6380), verifiable-inventory check in synthesizer. Run cache/verifiable tests: `python -m pytest tests/test_phase9_verifiable_inventory.py -v`. Start Redis: `redis-server --port 6380` (see `docs/redis-setup.md`).

---

## Phase 10: Algorithmic Delegation

- [x] **Spatial/routing:** TSP with time windows (nearest-neighbor heuristic in `src/algorithms/tsp.py`).
- [x] **Budget:** Deterministic budget checker in `src/algorithms/budget.py`; Knapsack-style suggested subset when over.
- [x] Expose as functions used by Financial and execute_all; budget_check wired in execute_all and financial_node.

### Expected results (how to test)

- [x] TSP: `python -m pytest tests/test_phase10_algorithms.py -v`
- [x] Budget checker: same test file; over-budget returns suggested_subset.
- [x] Financial/execute_all use budget_check on line items from executor results.

---

## Phase 11: Human-in-the-Loop (HITL)

- [x] **Checkpoint:** `interrupt_before=["synthesizer"]` so graph pauses after executors, before final itinerary.
- [ ] **Edit surface:** Per-checkpoint edit (shortlist/budget/booking) — stub in UI.
- [x] Streamlit shows **Approve**, **Edit (stub)**, **Reject** when interrupted; resume via `graph.stream(None, config)`.
- [x] Thread ID in config; checkpointer persists state across pause/resume.

### Expected results (how to test)

- [ ] Trigger a run that hits a checkpoint; UI shows Approve/Edit/Reject and the JSON payload (e.g. shortlist or budget breakdown).
- [ ] Approve: graph resumes and completes the next step without redoing previous work.
- [ ] Edit: change one editable field (e.g. remove a destination); resume; state reflects the edit and downstream steps use it.
- [ ] Reject: provide feedback; Planner is invoked again and a new DAG or proposal is produced.
- [ ] Restart app; select same thread_id; state is restored from persistence (MemorySaver or Postgres).

---

## Phase 12: Guardrails & Safety

- [ ] **Corrective RAG (CRAG):** Optional; not yet implemented.
- [x] **Output guardrails:** `src/guardrails.py` — no PII in payload, budget within max; synthesizer runs them, caps refinement at 3.
- [x] Refinement count in state; after 3 failures surface error to user.
- [x] Verbose logging via `config/logging_config.py`; guardrail results logged.

### Expected results (how to test)

- [ ] CRAG: Inject a retrieval that contradicts constraints; pipeline retries or narrows search; generated output does not rely on the contradicting chunk.
- [ ] Output guardrail: payload with PII (e.g. fake email in summary) is rejected or redacted; payload with total cost above budget is rejected.
- [ ] After 3 failed refinements, the system stops and shows an error message; no infinite loop.
- [ ] Guardrail failures appear in logs with enough context to debug.

---

## Phase 13: DyFlow (Dynamic Replanning)

- [x] **Disruption parsing:** `src/disruption.py` — parse user message (e.g. “My flight is delayed 4 hours”) and (2) API/webhook for flight status; parse into a **structured disruption event** (e.g. `affected_leg_id`, `new_times`, `reason`).
- [ ] Identify affected leg and checkpoint in LangGraph state; fork state at the checkpoint preceding that leg.
- [ ] Apply “any-start-time” safe interval path planning: update temporal constraints (check-in, activities), re-run only the affected sub-graph (Transport + possibly Accommodation/Experience).
- [ ] Merge corrected leg back into master itinerary (`validated_plans`, `message_history`) and continue.
- [ ] Avoid full re-plan unless necessary to minimize latency and API cost.

### Expected results (how to test)

- [ ] User sends “Flight delayed 4 hours”; system parses to a disruption event with affected leg and time delta.
- [ ] After fork, only nodes for the affected leg re-run; other legs’ state unchanged (assert or inspect).
- [ ] Merged itinerary shows updated times for the affected day; total cost and other days remain consistent where expected.
- [ ] Optional: mock flight-status API returns delay; same behavior as user-stated delay.

---

## Phase 14: Presentation Layer (Streamlit)

- [x] **Reasoning:** Node transitions and verbose log in expandable section; detailed logging in `config/logging_config.py`.
- [x] **Map:** Folium placeholder in expander (coordinates from itinerary can be wired).
- [x] **Itinerary UI:** Blocks from `validated_plans` and executor summary; booking URL when present.
- [x] **Export:** JSON and PDF download from state (`app/main.py`).

### Expected results (how to test)

- [ ] During a run, expandable sections show which node is running and which APIs were called (or stubbed).
- [ ] For a finalized itinerary, map renders with markers and (where applicable) polylines; day coding is visible.
- [ ] Itinerary blocks show at least one booking URL or external link per bookable item; pricing is visible.
- [ ] PDF and JSON export run without error; opened PDF/JSON contain the same trip data as the UI.

---

## Phase 15: Polish & Production Readiness

- [ ] Centralized error handling and logging (per node and per tool).
- [ ] Unit tests for state reducers, budget solver, and TSP helper.
- [ ] Integration tests for graph flow (mock APIs) and HITL resume.
- [ ] README: architecture summary, env vars, how to run, and links to `AI_Hackathon_Design_initial.md` and `.cursorrules`.
- [ ] Optional: Dockerfile and docker-compose for local run with Postgres and app.

### Expected results (how to test)

- [ ] All unit tests pass; integration tests pass with mocked external APIs.
- [ ] One full E2E scenario (e.g. “3-day budget trip” with mocks or sandbox APIs) completes and produces an exportable itinerary.
- [ ] README instructions allow a new developer to clone, install, set env, and run the app and tests.
- [ ] Optional: `docker-compose up` brings up app and (if used) Postgres; app is reachable and can complete a stub flow.

---

## Reference

- **Design:** `AI_Hackathon_Design_initial.md`
- **Rules:** `.cursorrules` (LangGraph, Streamlit, Pydantic, Plan-and-Execute, Supervisor, HITL, RAG, APIs, guardrails)
