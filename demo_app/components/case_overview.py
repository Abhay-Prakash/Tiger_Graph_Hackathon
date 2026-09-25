"""Case overview renderer."""

import streamlit as st


def render(case):
    st.subheader("Case Overview")
    first, second, third, fourth = st.columns(4)
    first.metric("Case", case.get("case_id") or "Unavailable")
    second.metric("Outcome", case.get("outcome") or "Pending")
    third.metric("Risk score", f"{(case.get('initial_risk_score') or 0):.2f}")
    fourth.metric("Reasoning", case.get("reasoning_source") or "Unavailable")
    st.caption(case.get("trigger_text") or "No trigger text returned by the runner.")
    left, right = st.columns(2)
    with left:
        st.write("**Trigger type**", case.get("trigger_type") or "Unavailable")
        st.write("**Customer**", case.get("customer_id") or "Unavailable")
    with right:
        st.write("**Card**", case.get("card_id") or "Unavailable")
        st.write("**Flagged transaction**", case.get("flagged_txn_id") or "Unavailable")
    st.write("**Detected pattern**", case.get("pattern") or "None")
