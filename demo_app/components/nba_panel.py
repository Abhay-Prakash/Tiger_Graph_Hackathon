"""Next-best-action renderer."""

import streamlit as st


def _actions(actions):
    return ", ".join(actions) if actions else "No action list returned"


def render(nba, policy):
    st.subheader("Next Best Action")
    before, response, after = st.columns(3)
    before.write("**NBA before**")
    before.write(_actions(nba.get("before")))
    response.write("**Additional evidence**")
    requests = nba.get("requests") or []
    responses = nba.get("responses") or []
    response.write(_actions([str(item.get("request_type", item)) for item in requests]))
    if responses:
        response.json(responses)
    after.write("**NBA after**")
    after.write(_actions(nba.get("after")))
    st.caption(f"Approval route returned by PolicyEngine: {policy.get('approval_route', 'Unavailable')}")
