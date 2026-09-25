"""MCP graph writeback renderer."""

import streamlit as st


def render(memory):
    st.subheader("Graph Memory")
    if memory.get("writeback_observed_via_mcp"):
        st.success("InvestigationCase writeback observed through MCP.")
    else:
        st.warning("No successful `tigergraph__add_nodes` event was returned in the MCP trace.")
    st.write("**Case**", memory.get("case_id") or "Unavailable")
    st.write("**Flagged transaction**", memory.get("flagged_txn_id") or "Unavailable")
    st.write("**Customer relationship**", memory.get("customer_id") or "Unavailable")
