"""Collapsed technical observability renderer."""

import streamlit as st


def render(protocol_trace, failures, reasoning_source):
    with st.expander("Technical Trace", expanded=False):
        st.write("**Reasoning source**", reasoning_source or "Unavailable")
        st.write("**MCP protocol trace**")
        st.json(protocol_trace)
        st.write("**Graph transport failures**")
        st.json(failures)
