"""
PromptRoam — Streamlit UI (Phases 3–4, 11, 14).

- Chat, node transitions, verbose logging.
- HITL: interrupt before synthesizer → show proposal, Approve / Edit / Reject → resume.
- Itinerary blocks, map placeholder, PDF/JSON export.
Run: streamlit run app/main.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.env import validate_env
from config.logging_config import get_logger, get_log_buffer_snapshot

validate_env()
log = get_logger(__name__)

import streamlit as st

# --- Helpers ---
def render_proposal_at_checkpoint(state: dict) -> None:
    """Show what the user is approving: flights, hotels, activities, budget from executor_results."""
    results = state.get("executor_results") or []
    trips = state.get("requested_trips") or []
    st.subheader("What you're approving")
    if trips:
        for t in trips:
            st.markdown(f"**Trip:** {t.get('summary', t.get('id', '?'))}")
    if not results:
        st.caption("_No executor results in state (run a message first)._")
    for r in results:
        if not isinstance(r, dict):
            continue
        ag = r.get("agent", "?")
        res = r.get("result") or {}
        if ag == "transport":
            flights = res.get("flights") if isinstance(res, dict) else []
            st.markdown("**Flights**")
            if flights:
                for f in flights[:10]:
                    name = f.get("flight_name") or f.get("flight_number") or "Flight"
                    orig = f.get("origin", "")
                    dest = f.get("dest", "")
                    dep = f.get("scheduled_departure", "")
                    arr = f.get("scheduled_arrival", "")
                    st.caption(f"• {name}: {orig} → {dest}  Dep: {dep}  Arr: {arr}")
            else:
                st.caption("_No flights returned (stub or API empty)_")
        elif ag == "accommodation":
            hotels = res.get("hotels") if isinstance(res, dict) else []
            st.markdown("**Hotels**")
            if hotels:
                for h in hotels[:10]:
                    name = h.get("name") or h.get("id", "?")
                    loc = h.get("location", "")
                    price = h.get("price", "")
                    st.caption(f"• {name}  {loc}  {price}")
            else:
                st.caption("_No hotels returned (stub or API empty)_")
        elif ag == "experience":
            activities = res.get("activities") if isinstance(res, dict) else []
            st.markdown("**Activities**")
            if activities:
                for a in activities[:10]:
                    name = a.get("name") or a.get("id", "?")
                    loc = a.get("location", "")
                    st.caption(f"• {name}  {loc}")
            else:
                st.caption("_No activities returned (stub or API empty)_")
        elif ag == "financial":
            st.markdown("**Budget**")
            total = res.get("total")
            max_b = res.get("max_budget")
            within = res.get("within_budget")
            st.caption(f"Total: {total}  Max budget: {max_b}  Within budget: {within}")


def render_per_node_prompts_and_outputs(state: dict) -> None:
    """Show per-node 'prompt' (input) and output. No LLM in current flow; planner uses rules."""
    st.subheader("Per-node: inputs & outputs")
    st.caption("Current flow uses rule-based extraction (no LLM). Inputs/outputs below are from state.")
    msg_hist = state.get("message_history") or []
    last_user = ""
    for m in reversed(msg_hist):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = (m.get("content") or "")[:500]
            break
    hard = state.get("hard_constraints") or {}
    profile = state.get("user_profile_and_context") or {}
    trips = state.get("requested_trips") or []
    dag = state.get("task_dag") or []
    results = state.get("executor_results") or []

    with st.expander("Supervisor", expanded=False):
        st.write("**Input:** Full state (inspect Node I/O log for full snapshot).")
        st.write("**Output:** Empty (routing only).")

    with st.expander("Planner", expanded=True):
        st.write("**Input (user message):**")
        st.code(last_user or "(none)", language=None)
        st.write("**Output (extracted):**")
        st.json({"hard_constraints": hard, "user_profile_and_context": profile, "requested_trips": trips, "task_dag": dag})

    with st.expander("execute_all (Transport, Accommodation, Experience, Financial)", expanded=True):
        st.write("**Input:** hard_constraints + user_profile (origin, destination, date, max_budget) used for API calls.")
        st.write("**Output (executor_results):**")
        summary = []
        for r in results:
            if isinstance(r, dict):
                ag = r.get("agent", "?")
                res = r.get("result")
                if isinstance(res, dict):
                    if res.get("flights"):
                        summary.append(f"{ag}: {len(res['flights'])} flight(s)")
                    elif res.get("hotels"):
                        summary.append(f"{ag}: {len(res['hotels'])} hotel(s)")
                    elif res.get("activities"):
                        summary.append(f"{ag}: {len(res['activities'])} activity(ies)")
                    elif res.get("total") is not None:
                        summary.append(f"{ag}: total={res.get('total')} within_budget={res.get('within_budget')}")
                    else:
                        summary.append(f"{ag}: (see result)")
                else:
                    summary.append(f"{ag}: ran")
        st.caption(" • ".join(summary))
        st.json([{"agent": r.get("agent"), "task_id": r.get("task_id"), "result_keys": list((r.get("result") or {}).keys())} for r in results if isinstance(r, dict)])


def render_itinerary_blocks(state: dict) -> None:
    """Phase 14: itinerary UI from validated_plans and executor_results."""
    structured = state.get("structured_itinerary") or {}
    validated = state.get("validated_plans") or {}
    results = state.get("executor_results") or []
    trips = state.get("requested_trips") or []
    if not trips and not validated and not results and not structured:
        return
    st.subheader("Itinerary")
    if structured:
        st.markdown(f"**Summary:** {structured.get('summary', '')}")
        days = structured.get("days") or []
        for d in days:
            day_num = d.get("day", "?")
            title = d.get("title") or "Plan"
            with st.expander(f"Day {day_num}: {title}", expanded=True):
                if d.get("transport"):
                    st.write("**Transport:**", d.get("transport"))
                if d.get("lodging"):
                    st.write("**Lodging:**", d.get("lodging"))
                if d.get("activities"):
                    st.write("**Activities:**")
                    for a in d.get("activities") or []:
                        st.caption(f"- {a}")
                if d.get("notes"):
                    st.write("**Notes:**", d.get("notes"))
        budget = structured.get("budget") or {}
        if budget:
            st.write("**Budget:**", budget.get("total"), budget.get("currency"))
            if budget.get("max_budget") is not None:
                st.caption(f"Max budget: {budget.get('max_budget')} {budget.get('currency', '')}")
    for t in trips:
        with st.expander(f"Trip: {t.get('summary', t.get('id', '?'))}", expanded=True):
            st.write("**Status:**", t.get("status", "planned"))
            leg_id = t.get("id")
            if leg_id and leg_id in validated:
                leg = validated[leg_id]
                if isinstance(leg, dict):
                    st.write("**Total cost:**", leg.get("total_cost"), leg.get("currency", "INR"))
                    if leg.get("booking_url"):
                        st.markdown(f"Booking: [{leg.get('booking_url', '')[:50]}...]({leg['booking_url']})")
    if results and not validated:
        st.write("**Executor summary:**")
        for r in results:
            if isinstance(r, dict):
                ag = r.get("agent", "?")
                res = r.get("result") or {}
                if isinstance(res, dict) and res.get("total") is not None:
                    st.caption(f"{ag}: total={res.get('total')} within_budget={res.get('within_budget')}")
                else:
                    st.caption(f"{ag}: ran")

def render_map_placeholder(state: dict) -> None:
    """Phase 14: map placeholder (Folium can be wired with real coords later)."""
    try:
        import folium
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
        folium.Marker([20.5937, 78.9629], popup="India (placeholder)").add_to(m)
        html = m.get_root().render()
        with st.expander("Map (placeholder)", expanded=False):
            st.components.v1.html(html, height=300)
    except Exception:
        with st.expander("Map (placeholder)", expanded=False):
            st.info("Map: coordinates from itinerary can be wired here (Folium).")

def _pdf_safe_text(s: str, max_len: int = 200) -> str:
    """Replace chars that Helvetica cannot encode (e.g. curly apostrophe) so PDF export does not fail."""
    if not s:
        return ""
    s = str(s)[:max_len]
    # Curly/smart quotes and apostrophes -> ASCII
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    # Any other non-ASCII -> replacement
    s = "".join(c if ord(c) < 128 else "?" for c in s)
    return s


def export_pdf_json(state: dict) -> None:
    """Phase 14: export PDF and JSON."""
    out = {
        "requested_trips": state.get("requested_trips"),
        "validated_plans": state.get("validated_plans"),
        "message_history": state.get("message_history"),
        "structured_itinerary": state.get("structured_itinerary"),
    }
    st.download_button(
        "Download itinerary (JSON)",
        data=json.dumps(out, indent=2, default=str),
        file_name="promptroam_itinerary.json",
        mime="application/json",
        key="dl_json",
    )
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        for msg in (state.get("message_history") or [])[-10:]:
            role = _pdf_safe_text(msg.get("role", ""), 20)
            content = _pdf_safe_text(msg.get("content", ""), 200)
            line = f"{role}: {content}"
            pdf.cell(0, 10, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        buf = bytes(pdf.output())
        st.download_button("Download itinerary (PDF)", data=buf, file_name="promptroam_itinerary.pdf", mime="application/pdf", key="dl_pdf")
    except Exception as e:
        st.caption(f"PDF export: {e}")

st.set_page_config(
    page_title="PromptRoam",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "node_log" not in st.session_state:
    st.session_state.node_log = []
if "interrupt_pending" not in st.session_state:
    st.session_state.interrupt_pending = False
if "last_state" not in st.session_state:
    st.session_state.last_state = {}

def _new_thread_id() -> str:
    return f"session-{uuid.uuid4().hex[:8]}"

def _reset_session_for_new_thread(thread_id: str) -> None:
    st.session_state.thread_id = thread_id
    st.session_state.messages = []
    st.session_state.node_log = []
    st.session_state.interrupt_pending = False
    st.session_state.last_state = {}
    st.session_state.loaded_thread_id = None

def _load_thread_state(thread_id: str) -> None:
    if st.session_state.get("loaded_thread_id") == thread_id:
        return
    try:
        from src.persistence import get_thread_state, config_for_thread
        from src.graph.workflow import get_graph
        state = get_thread_state(thread_id)
        if state:
            st.session_state.last_state = state
            if state.get("message_history"):
                st.session_state.messages = list(state.get("message_history") or [])
        try:
            graph = get_graph()
            snap = graph.get_state(config_for_thread(thread_id))
            snap_values = snap.values if hasattr(snap, "values") else {}
            if snap_values:
                st.session_state.last_state = snap_values
                if snap_values.get("message_history"):
                    st.session_state.messages = list(snap_values.get("message_history") or [])
            next_nodes = getattr(snap, "next", None) or []
            st.session_state.interrupt_pending = bool(next_nodes)
        except Exception as e:
            log.debug("[UI] graph.get_state failed: %s", e)
    except Exception as e:
        log.debug("[UI] load_thread_state failed: %s", e)
    st.session_state.loaded_thread_id = thread_id

query_thread_id = st.query_params.get("thread_id")
if query_thread_id:
    if st.session_state.get("thread_id") != query_thread_id:
        _reset_session_for_new_thread(query_thread_id)
    _load_thread_state(query_thread_id)
else:
    if "thread_id" not in st.session_state:
        _reset_session_for_new_thread(_new_thread_id())
    st.query_params["thread_id"] = st.session_state.thread_id

with st.sidebar:
    st.header("Session")
    thread_id = st.text_input(
        "Thread ID",
        help="Same ID resumes the same conversation (HITL).",
        key="thread_id",
        on_change=lambda: st.query_params.update({"thread_id": st.session_state.thread_id}),
    )
    st.caption("One thread per conversation.")

st.title("PromptRoam")
st.caption("Autonomous multi-agent travel planning. Phases 10–14: budget, HITL, guardrails, itinerary, export.")

# --- HITL checkpoint: show WHAT you're approving, then Approve/Edit/Reject ---
if st.session_state.interrupt_pending:
    st.warning("⚠️ **ACTION REQUIRED: Review & Approve Proposal**")
    if st.session_state.last_state:
        with st.container(border=True):
            render_proposal_at_checkpoint(st.session_state.last_state)
    else:
        st.error("Error: No proposal data found in state.")
    
    st.markdown("### Decision")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        approve_btn = st.button("✅ Approve & Generate Itinerary", type="primary", use_container_width=True)
    with col_b:
        edit_btn = st.button("✏️ Edit Constraints (stub)", use_container_width=True)
    with col_c:
        reject_btn = st.button("❌ Reject & Start Over", use_container_width=True)
    
    if approve_btn or edit_btn:
        st.session_state.resume_choice = "approve" if approve_btn else "edit"
        st.session_state.interrupt_pending = False
        st.rerun()
    elif reject_btn:
        st.session_state.resume_choice = "reject"
        st.session_state.interrupt_pending = False
        st.rerun()
    st.markdown("---")

# --- Clarifications ---
clarify_state = st.session_state.last_state or {}
is_awaiting = clarify_state.get("awaiting_clarification") and clarify_state.get("clarification_questions")
if is_awaiting:
    missing_ids = {q.get("id") for q in clarify_state.get("clarification_questions", []) if q.get("id")}
    with st.expander("Required details checklist", expanded=True):
        checklist = [
            ("origin", "Origin (where are you traveling from)"),
            ("destination", "Destination"),
            ("dates", "Dates or trip duration"),
            ("budget", "Total budget"),
            ("interests", "Interests / preferred experiences"),
        ]
        for fid, label in checklist:
            status = "Missing" if fid in missing_ids else "Provided"
            st.caption(f"{label}: {status}")
    st.info("I need a few quick details before I can plan.")
    with st.form("clarifications"):
        answers = {}
        for q in clarify_state.get("clarification_questions", []):
            qid = q.get("id") or "q"
            qtext = q.get("question") or "Please clarify."
            answers[qid] = st.text_input(qtext)
        submitted = st.form_submit_button("Submit details")
    if submitted:
        details = "; ".join([f"{k}={v}" for k, v in answers.items() if v])
        if details:
            st.session_state.messages.append({"role": "user", "content": f"Clarifications: {details}"})
            st.session_state.last_state["awaiting_clarification"] = False
            st.session_state.last_state["clarification_questions"] = []
            st.session_state.resume_choice = "clarify"
            st.rerun()

# --- Main input ---
input_disabled = is_awaiting or st.session_state.interrupt_pending
placeholder = "Please submit details above or approve/reject the proposal..." if input_disabled else "Describe your trip: dates, budget, destination, preferences…"

user_input = st.chat_input(placeholder, disabled=input_disabled)
resume_choice = st.session_state.pop("resume_choice", None)

if user_input or resume_choice is not None:
    from src.graph.workflow import get_graph
    from src.persistence import config_for_thread

    graph = get_graph()
    config = config_for_thread(thread_id)

    if resume_choice == "approve" or resume_choice == "edit":
        log.info("[UI] Resuming graph resume_choice=%s thread_id=%s", resume_choice, thread_id)
        try:
            for chunk in graph.stream(None, config, stream_mode="updates"):
                for node_name in chunk:
                    st.session_state.node_log.append(node_name)
            snap = graph.get_state(config)
            state_value = snap.values if hasattr(snap, "values") else {}
            st.session_state.last_state = state_value
            
            # Sync messages: only add what's new
            messages_out = state_value.get("message_history") or []
            for m in messages_out:
                if m not in st.session_state.messages:
                    st.session_state.messages.append(m)
        except Exception as e:
            log.exception("Resume failed: %s", e)
            st.error(str(e))
    elif resume_choice == "reject":
        st.session_state.messages.append({"role": "user", "content": "Please re-plan with different options."})
        st.rerun()
    elif resume_choice == "clarify" or user_input is not None:
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.node_log = []
        message_history = list(st.session_state.messages)
        initial_state = {"message_history": message_history}
        if resume_choice == "clarify":
            initial_state["awaiting_clarification"] = False
            initial_state["clarification_questions"] = []
        log.info("[UI] Invoking graph thread_id=%s message_len=%s", thread_id, len(user_input) if user_input else 0)

        with st.status("Running graph…", state="running") as status:
            try:
                for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                    for node_name in chunk:
                        st.session_state.node_log.append(node_name)
                snap = graph.get_state(config)
                state_value = snap.values if hasattr(snap, "values") else {}
                st.session_state.last_state = state_value
                next_nodes = getattr(snap, "next", None) or []
                if next_nodes:
                    log.info("[UI] Interrupt before %s; set interrupt_pending=True", next_nodes)
                    st.session_state.interrupt_pending = True
                    status.update(state="complete", label="Paused at checkpoint")
                    st.rerun()
                else:
                    status.update(state="complete", label="Done")
                
                # Sync messages: only add what's new
                messages_out = state_value.get("message_history") or []
                for m in messages_out:
                    if m not in st.session_state.messages:
                        st.session_state.messages.append(m)
            except Exception as e:
                status.update(state="error", label="Error")
                log.exception("Graph error: %s", e)
                st.error(str(e))

# --- Node transitions ---
with st.expander("Node transitions", expanded=False):
    if st.session_state.node_log:
        for n in st.session_state.node_log:
            st.caption(f"→ {n}")
    else:
        st.info("Node transitions will appear here after you send a message.")

# --- Node input/output log (each node's state in, updates out) ---
with st.expander("Node I/O log (input & output per node)", expanded=True):
    buf = get_log_buffer_snapshot()
    if buf:
        st.text_area("Log", value="\n".join(buf), height=400, disabled=True, label_visibility="collapsed")
    else:
        st.info("Run a message to see each node's input (state) and output (updates) here and in the terminal.")

# --- Per-node prompts & outputs (what each node saw and returned) ---
if st.session_state.last_state:
    with st.expander("Per-node: prompts & outputs (inputs and outputs per node)", expanded=True):
        render_per_node_prompts_and_outputs(st.session_state.last_state)

# --- Itinerary & map & export ---
if st.session_state.last_state:
    with st.expander("🛠️ Debug: Full State Snapshot (Raw JSON)", expanded=False):
        st.json(st.session_state.last_state)
    render_itinerary_blocks(st.session_state.last_state)
    render_map_placeholder(st.session_state.last_state)
    export_pdf_json(st.session_state.last_state)

# --- Chat history ---
# Suppress redundant rendering of HTIL questions in the main chat history
# if the clarification form is already active at the top.
for msg in st.session_state.messages:
    if is_awaiting and msg.get("role") == "assistant" and ("traveling from" in msg.get("content", "") or "activities" in msg.get("content", "")):
        continue
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("_Send a message to start (e.g. «2 days Goa under 10k»). After executors run, you'll see a checkpoint: Approve to get the final itinerary._")
