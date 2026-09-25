"""Actual agent trace timeline renderer."""

import streamlit as st


def render(entries):
    st.subheader("Investigation Timeline")
    if not entries:
        st.info("No agent trace was returned for this investigation.")
        return
    for index, entry in enumerate(entries, start=1):
        st.markdown(f"**{index:02d}. {entry['label']}**")
        st.caption(entry["detail"])
