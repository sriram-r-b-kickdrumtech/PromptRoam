# PromptRoam

Autonomous Multi-Agent Travel Planning System — LangGraph, Plan-and-Execute, HITL, and RAG per [AI_Hackathon_Design_initial.md](AI_Hackathon_Design_initial.md) and [.cursorrules](.cursorrules).

## Setup (Conda)

From the project root:

```bash
# Create conda env from environment.yml (installs Python 3.11 + pip deps)
conda env create -f environment.yml

# Activate
conda activate promptroam
```

If you prefer to create the env manually:

```bash
conda create -n promptroam python=3.11 -y
conda activate promptroam
pip install -r requirements.txt
```

## Environment variables

```bash
cp .env.example .env
# Edit .env and set at least OPENAI_API_KEY for early phases.
```

The app validates required env vars at startup and exits with a clear error if they are missing.

## Run

- **Streamlit app (verify Phases 10–14 with UI):**  
  `streamlit run app/main.py`  
  Then: type a trip request (e.g. "2 days Goa under 10k"); you’ll see node transitions and a **checkpoint** (Approve / Edit / Reject) before the final itinerary; click **Approve** to get the reply. Use **Reasoning & logs** for verbose output. Download itinerary as JSON or PDF.
- **Verbose logging:** Set `LOG_LEVEL=DEBUG` (default) and optionally `PROMPTROAM_VERBOSE=1` for detailed per-node and MCP logs.

- **Validate env only** (from repo root with `conda activate promptroam`):  
  `python -c "from config.env import validate_env; validate_env()"`

## Testing

From repo root with `conda activate promptroam`:

1. **Unit tests (no API key needed for most)**  
   ```bash
   python -m pytest tests/ -v
   ```
   RAG unit tests: `python -m pytest tests/test_rag_phase7.py -v`

2. **RAG: real ingestion** (needs `OPENAI_API_KEY` in `.env`)  
   ```bash
   python scripts/ingest_sample.py
   python scripts/ingest_sample.py --hype   # optional: add HyPE hypothetical questions
   ```
   Seeds the Chroma store under `data/chroma` with sample hotels and attractions.

3. **RAG: verify retrieval** (run after step 2)  
   ```bash
   python scripts/verify_rag.py
   ```
   Runs a few natural-language queries and prints retrieved Knowledge Objects.

4. **End-to-end in the app**  
   ```bash
   streamlit run app/main.py
   ```
   Send a message like *"I want a spiritual trip to Rishikesh with cheap stays"*. The Experience node calls the RAG layer; if the store is populated, suggestions are attached to the stub result.

5. **MCP and caching (Phase 9)**  
   Use a prompt with origin, destination, and date (e.g. *"From Delhi to Goa, travel date April 15 2025. I need flights, a hotel, activities. Budget 50k."*) so the graph passes real params to MCP.  
   ```bash
   conda activate promptroam
   python scripts/test_all_mcp_via_llm.py
   ```
   Caching demo (requires Redis on port 6380):  
   ```bash
   redis-server --port 6380   # if not already running
   conda activate promptroam
   python scripts/test_mcp_caching_demo.py
   ```
   Second run shows CACHE_HIT (second call served from Redis).

## Project layout

- `app/` — Streamlit UI
- `src/` — Core library (graph, agents)
- `config/` — Config and env validation
- `tests/` — Tests
- `docs/` — Documentation

## Implementation plan

See [PLAN.md](PLAN.md) for the step-by-step checklist.
