"""Evidence ledger renderer."""

import json
import streamlit as st


def render(evidence, citations):
    st.subheader("Grounded Evidence")
    if not evidence:
        st.warning("No graph evidence was returned. Review the technical trace for MCP failures.")
        return
    citation_set = set(citations)
    for item in evidence:
        heading = f"{item.get('evidence_type', 'evidence')} | {item.get('source', 'unknown source')}"
        with st.expander(heading, expanded=False):
            st.write(item.get("description") or "No factual summary returned.")
            st.caption(f"Evidence ID: {item.get('evidence_id', 'Unavailable')}")
            st.caption(f"Provenance: {item.get('provenance', 'Unavailable')}")
            st.json(item.get("observed_value", {}))
            left, right = st.columns(2)
            left.write("**Supports**", item.get("supports") or "none")
            right.write("**Contradicts**", item.get("contradicts") or "none")
            if item.get("evidence_id") in citation_set:
                st.success("Cited by the returned explanation")
