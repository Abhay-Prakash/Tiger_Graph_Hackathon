"""
Unit tests for deterministic PolicyEngine.
"""

import pytest
from fraud_investigation.policy.engine import PolicyEngine


def test_policy_confirmed_fraud_below_sar_threshold():
    engine = PolicyEngine()
    decision = engine.evaluate(
        outcome="confirmed_fraud",
        pattern="out_of_region_use",
        exposure_usd=582.96,
        trigger_type="risk_score",
    )

    assert "CREATE_CASE" in decision.required_actions
    assert "BLOCK_CARD" in decision.required_actions
    assert "FILE_REPORT" not in decision.required_actions
    assert decision.sar_required is False
    assert decision.approval_route == "auto"
    assert "CLOSE_NO_FRAUD" in decision.forbidden_actions


def test_policy_confirmed_fraud_above_sar_threshold():
    engine = PolicyEngine()
    decision = engine.evaluate(
        outcome="confirmed_fraud",
        pattern="account_takeover",
        exposure_usd=1250.00,
        trigger_type="risk_score",
    )

    assert "CREATE_CASE" in decision.required_actions
    assert "BLOCK_CARD" in decision.required_actions
    assert "FILE_REPORT" in decision.required_actions
    assert decision.sar_required is True
    assert decision.approval_route == "auto"


def test_policy_undocumented_pattern_always_files_sar():
    engine = PolicyEngine()
    decision = engine.evaluate(
        outcome="confirmed_fraud",
        pattern="undocumented",
        exposure_usd=150.00,  # below 1000 threshold
        trigger_type="analyst_request",
    )

    assert "FILE_REPORT" in decision.required_actions
    assert decision.sar_required is True
    assert decision.approval_route == "escalation"


def test_policy_cleared_case():
    engine = PolicyEngine()
    decision = engine.evaluate(
        outcome="cleared",
        pattern="none",
        exposure_usd=0.0,
        trigger_type="customer_report",
    )

    assert "VERIFY_WITH_CUSTOMER" in decision.required_actions
    assert "CLOSE_NO_FRAUD" in decision.required_actions
    assert "BLOCK_CARD" in decision.forbidden_actions
    assert "FILE_REPORT" in decision.forbidden_actions
    assert decision.sar_required is False
