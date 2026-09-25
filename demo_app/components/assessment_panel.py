"""Assessment, hypothesis, and uncertainty renderer."""

import streamlit as st


def _items(values):
    return ", ".join(values) if values else "None returned"


def render(assessment):
    st.subheader("Hypotheses And Uncertainty")
    left, right, third = st.columns(3)
    left.metric("Confidence", "Unavailable" if assessment.get("confidence") is None else f"{assessment['confidence']:.0%}")
    right.metric("Uncertainty", "Unavailable" if assessment.get("uncertainty") is None else f"{assessment['uncertainty']:.0%}")
    third.metric("Evidence sufficient", str(assessment.get("evidence_sufficient")))
    st.write("**Proposed hypotheses**", _items(assessment.get("hypotheses", [])))
    st.write("**Supported hypotheses**", _items(assessment.get("supported", [])))
    st.write("**Contradicted hypotheses**", _items(assessment.get("contradicted", [])))
    if "out_of_region_use" in assessment.get("contradicted", []):
        st.info("Region evidence contradicts `out_of_region_use`; the runner suppresses that hypothesis.")
    st.write("**Missing evidence**", _items(assessment.get("missing_evidence", [])))
    st.caption(
        f"Additional evidence rounds: {assessment.get('additional_rounds', 0)} / {assessment.get('max_additional_rounds', 1)}"
    )
