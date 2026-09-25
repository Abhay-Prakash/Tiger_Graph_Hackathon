"""Authoritative policy decision renderer."""

import streamlit as st


def _actions(actions):
    return ", ".join(actions) if actions else "None"


def render(policy):
    st.subheader("Policy Gate")
    left, right = st.columns(2)
    left.write("**Mandatory actions**", _actions(policy.get("required_actions")))
    left.write("**Permitted actions**", _actions(policy.get("permitted_actions")))
    right.write("**Forbidden actions**", _actions(policy.get("forbidden_actions")))
    right.write("**Executed actions**", _actions(policy.get("executed_actions")))
    st.write("**Rules applied**", _actions(policy.get("policy_rules_applied")))
    st.write("**SAR required**", str(policy.get("sar_required")))
    violations = policy.get("reported_violations") or []
    if violations:
        st.error(f"Reported forbidden executed actions: {_actions(violations)}")
    else:
        st.success("No forbidden action appears in the runner's executed action list.")
    if policy.get("reasoning"):
        st.caption(policy["reasoning"])
