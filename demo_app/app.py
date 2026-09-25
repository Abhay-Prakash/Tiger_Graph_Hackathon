"""Streamlit console for operational HHGOA investigations."""

from __future__ import annotations

import streamlit as st

from demo_app.adapters.runner_adapter import PRIORITY_CASE_IDS, case_by_id, load_cases, run_live_case
from demo_app.components import assessment_panel, case_overview, evidence_panel, explanation_panel
from demo_app.components import graph_memory, nba_panel, policy_panel, timeline, trace_panel


st.set_page_config(page_title="HHGOA Investigation Console", page_icon="F", layout="wide")

st.markdown(
    """
    <style>
      [data-testid="stAppViewContainer"] { background: #f4f7fb; }
      [data-testid="stMain"] { color: #172b4d; }
      [data-testid="stMain"] h1,
      [data-testid="stMain"] h2,
      [data-testid="stMain"] h3 { color: #102a43 !important; letter-spacing: 0 !important; }
      [data-testid="stMain"] p,
      [data-testid="stMain"] label,
      [data-testid="stMain"] .stMarkdown,
      [data-testid="stMain"] .stCaption { color: #486581 !important; }
      [data-testid="stMain"] .stButton > button { border-radius: 6px; font-weight: 600; }
      [data-testid="stMain"] .stButton > button[kind="primary"] { background: #d64545; border-color: #d64545; color: #ffffff !important; }
      [data-testid="stMain"] .stButton > button[kind="primary"] * { color: #ffffff !important; }
      [data-testid="stSidebar"] { background: #102a43; }
      [data-testid="stSidebar"] > div:first-child { background: #102a43; }
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3,
      [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] label { color: #f0f4f8 !important; }
      [data-testid="stSidebar"] .stCaption { color: #b8c7d9 !important; }
      .block-container { max-width: 1440px; padding-top: 2.5rem; padding-bottom: 3rem; }
      .console-hero { border-left: 4px solid #d64545; padding: 0.1rem 0 0.2rem 1rem; margin-bottom: 1.25rem; }
      .console-kicker { color: #d64545 !important; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08rem !important; margin-bottom: 0.25rem; }
      .console-subtitle { color: #627d98 !important; font-size: 1rem; margin: 0.25rem 0 0; }
      .system-strip { background: #e6eff8; border: 1px solid #c9d9e8; border-radius: 6px; padding: 0.8rem 1rem; margin: 1.25rem 0; color: #243b53 !important; }
      div[data-testid="stMetric"] { background: #ffffff; border: 1px solid #d9e2ec; padding: 0.75rem; border-radius: 6px; box-shadow: none; }
      div[data-testid="stMetric"] label { color: #627d98 !important; }
      div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #102a43 !important; }
      [data-testid="stExpander"] { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 6px; }
      .priority-card { background: #ffffff; border: 1px solid #d9e2ec; border-top: 3px solid #2f80ed; border-radius: 6px; padding: 1rem; min-height: 126px; }
      .priority-card h3 { margin: 0 0 0.35rem; font-size: 1rem; }
      .priority-card p { margin: 0; font-size: 0.88rem; color: #627d98 !important; }
      .run-loader { min-height: 300px; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 0.9rem; }
      .run-loader-ring { width: 52px; height: 52px; border: 4px solid #d9e2ec; border-top-color: #d64545; border-radius: 50%; animation: investigation-spin 0.85s linear infinite; }
      .run-loader-label { color: #486581 !important; font-size: 0.95rem; font-weight: 600; }
      @keyframes investigation-spin { to { transform: rotate(360deg); } }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _cases():
    return load_cases()


def _case_label(case):
    marker = "Priority" if case["case_id"] in PRIORITY_CASE_IDS else "Case"
    return f"{marker} | {case['case_id']} | {case['trigger_type']}"


def _queue_case(case_id):
    st.session_state["case_selector"] = case_id
    st.session_state["run_requested"] = True


def _idle_state():
    st.markdown("<div class='system-strip'><strong>Ready for investigation.</strong> Select a case to initiate the production workflow through live TigerGraph MCP. Results are rendered directly from the returned case state.</div>", unsafe_allow_html=True)
    st.subheader("Priority Investigations")
    cards = [
        ("HHG-007", "Region verification", "Region 264 matches the customer baseline, visibly suppressing out_of_region_use."),
        ("HHG-001", "Evidence review", "Shows the returned next-best-action state and any bounded additional-evidence rounds."),
        ("HHG-014", "Cleared-case controls", "A cleared outcome where BLOCK_CARD and FILE_REPORT remain forbidden by PolicyEngine."),
    ]
    columns = st.columns(3)
    for column, (case_id, title, detail) in zip(columns, cards):
        with column:
            st.markdown(f"<div class='priority-card'><h3>{case_id} | {title}</h3><p>{detail}</p></div>", unsafe_allow_html=True)
            st.button(f"Open {case_id}", key=f"open_{case_id}", on_click=_queue_case, args=(case_id,), use_container_width=True)


def main():
    st.markdown(
        """<div class='console-hero'>
        <div class='console-kicker'>Fraud operations / live case review</div>
        <h1>HHGOA Investigation Console</h1>
        <p class='console-subtitle'>Operational case review with grounded evidence, policy controls, and MCP auditability.</p>
        </div>""",
        unsafe_allow_html=True,
    )

    try:
        cases = _cases()
    except Exception as exc:
        st.error(f"Unable to load the existing benchmark case pack: {exc}")
        return

    case_ids = [case["case_id"] for case in cases]
    default = case_ids.index("HHG-007") if "HHG-007" in case_ids else 0
    with st.sidebar:
        st.header("HHGOA")
        st.caption("Fraud investigation operations")
        selected_id = st.selectbox("Case", case_ids, index=default, key="case_selector", format_func=lambda item: _case_label(case_by_id(item, cases)))
        st.caption("Priority cases: HHG-007, HHG-001, HHG-014")
        run = st.button("Run Investigation", type="primary", use_container_width=True)
        st.divider()
        st.success("Live MCP mode")
        st.caption("A graph failure remains visible. This console never replaces it with mock evidence.")

    run = run or st.session_state.pop("run_requested", False)

    selected_case = case_by_id(selected_id, cases)
    if run:
        loader = st.empty()
        try:
            loader.markdown(
                """<div class='run-loader'>
                <div class='run-loader-ring'></div>
                <div class='run-loader-label'>Running live investigation through MCP</div>
                </div>""",
                unsafe_allow_html=True,
            )
            st.session_state["investigation_view"] = run_live_case(selected_case)
            st.session_state.pop("investigation_error", None)
        except Exception as exc:
            st.session_state["investigation_error"] = str(exc)
        finally:
            loader.empty()

    if st.session_state.get("investigation_error"):
        st.error("The live investigation failed. No substitute evidence was generated.")
        st.code(st.session_state["investigation_error"])

    view = st.session_state.get("investigation_view")
    if not view or view["case"]["case_id"] != selected_id:
        _idle_state()
        return

    case_overview.render(view["case"])
    left, right = st.columns((1, 1))
    with left:
        timeline.render(view["timeline"])
        assessment_panel.render(view["assessment"])
        nba_panel.render(view["nba"], view["policy"])
    with right:
        evidence_panel.render(view["evidence"], view["citations"])
        policy_panel.render(view["policy"])
        graph_memory.render(view["graph_memory"])
    explanation_panel.render(view["explanation"], view["citations"])
    trace_panel.render(view["protocol_trace"], view["graph_transport_failures"], view["case"]["reasoning_source"])


if __name__ == "__main__":
    main()
