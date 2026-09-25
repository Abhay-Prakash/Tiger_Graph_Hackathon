"""Grounded explanation renderer."""

import streamlit as st


def render(explanation, citations):
    st.subheader("Grounded Explanation")
    if explanation:
        st.markdown(explanation)
    else:
        st.warning("The runner did not return an explanation.")
    st.caption("Returned citations: " + (", ".join(citations) if citations else "None"))
