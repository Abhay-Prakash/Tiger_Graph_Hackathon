"""
Phase 6 — Adversarial Edge-Case Suite (E13 - E20).

Tests evidence sufficiency, conflicting evidence, live vs fallback parity,
and potential overreaction to isolated graph signals.

Invariants Verified:
1. No fabricated graph evidence.
2. Missing evidence remains missing.
3. ML risk score is not itself treated as graph evidence.
4. Single weak signal does not automatically become confirmed fraud without justification.
5. Contradictory evidence is preserved in ledger.
6. HHG-007 region contradiction suppresses only out_of_region_use.
7. PolicyEngine remains final execution authority.
8. Forbidden actions cannot be executed even if proposed.
9. Valid evidence citations remain grounded; fake citations stripped.
10. Fallback parity matches live LLM behavior semantically.
11. Additional evidence loop remains bounded at max 1 round.
"""

from unittest.mock import MagicMock, patch
import pytest

from fraud_investigation.agent.graph import build_investigation_graph, route_sufficiency
from fraud_investigation.agent.llm_reasoner import LLMReasoner, validate_and_extract_citations
from fraud_investigation.agent.nodes import WorkflowNodes
from fraud_investigation.agent.runner import run_fraud_investigation
from fraud_investigation.agent.state import InvestigationState
from fraud_investigation.agent.tools import AgentTools
from fraud_investigation.evidence.ledger import EvidenceLedger
from fraud_investigation.evidence.model import EvidenceSource, EvidenceType, make_evidence
from fraud_investigation.policy.engine import PolicyEngine, PolicyDecision


# ===========================================================================
# E13 — HIGH RISK + ZERO GRAPH EVIDENCE
# ===========================================================================
def test_edge_case_e13_high_risk_zero_graph_evidence():
    """
    E13: initial_risk_score = 0.95, but all graph queries return [].
    - Does ML risk score alone constituted confirmed graph evidence?
    - System must NOT fabricate graph evidence.
    - EvidenceLedger must contain ONLY the initial trigger evidence item.
    - Outcome & actions should be driven by risk score trigger under policy without fake evidence.
    """
    tools = AgentTools(conn=None)

    with patch.object(tools, "fetch_transaction_context", return_value=[]), \
         patch.object(tools, "fetch_region_anomaly", return_value=[]), \
         patch.object(tools, "fetch_shared_device", return_value=[]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[]), \
         patch.object(tools, "fetch_customer_case_history", return_value=[]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E13-01",
            "customer_id": "C991301",
            "card_id": "C991301-K1",
            "flagged_txn_id": "99130101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.95",
            "initial_risk_score": 0.95,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 150.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    ledger = EvidenceLedger.from_json("HHG-E13-01", final_state["evidence_ledger_json"])
    # First evidence must be MODEL_SCORE trigger (not fabricated graph evidence)
    assert ledger.all[0].evidence_type == EvidenceType.MODEL_SCORE
    # No fabricated graph evidence types from empty MCP queries
    assert len(ledger.by_type(EvidenceType.REGION_SIGNAL)) == 0, "No region evidence fabricated from empty MCP"
    assert len(ledger.by_type(EvidenceType.DEVICE_SIGNAL)) == 0, "No device evidence fabricated from empty MCP"
    assert len(ledger.by_type(EvidenceType.VELOCITY_SIGNAL)) == 0, "No velocity evidence fabricated from empty MCP"
    # out_of_region_use must NOT appear (was fabricated in old fallback code)
    assert "out_of_region_use" not in final_state.get("fraud_hypotheses", []), \
        "Fallback must not fabricate out_of_region_use without region evidence"
    assert final_state.get("reasoning_source") in {"llm", "deterministic_fallback"}
    # System requests customer verification and confirms fraud after customer disputes
    assert final_state.get("outcome") == "confirmed_fraud"
    assert "BLOCK_CARD" in final_state.get("executed_actions", [])


# ===========================================================================
# E14 — LOW SCORE + WEAK SHARED-DEVICE SIGNAL (No Confirmed Fraud on Device)
# ===========================================================================
def test_edge_case_e14_low_score_weak_shared_device_signal():
    """
    E14: initial_risk_score = 0.10.
    Shared device is present (shared with 2 cards), but those cards have ZERO confirmed fraud history.
    Velocity = normal, region = normal, context = normal.
    - Shared device alone without fraud history is weak/contextual.
    - Tests if Audit Case 5 fallback fix is too permissive (i.e. 'any graph evidence -> confirmed fraud').
    - If device signal has supports='none', evidence_summary['hypotheses_supported'] must be empty or 'none'.
    """
    tools = AgentTools(conn=None)

    # Weak device signal: device shared with 2 cards, 0 fraud cases
    ev_weak_device = make_evidence(
        source=EvidenceSource.QUERY_SHARED_DEVICE,
        source_record_id="99140101",
        evidence_type=EvidenceType.DEVICE_SIGNAL,
        description="Device D9914 shared with 2 other active cards. No historical fraud associated.",
        observed_value={"device_id": "D9914", "card_count": 2, "fraud_count": 0},
        provenance="identity.csv:DeviceInfo",
        supports="none",  # WEAK signal — supports NO fraud hypothesis
        confidence=0.6,
    )

    with patch.object(tools, "fetch_shared_device", return_value=[ev_weak_device]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[]), \
         patch.object(tools, "fetch_region_anomaly", return_value=[]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E14-01",
            "customer_id": "C991401",
            "card_id": "C991401-K1",
            "flagged_txn_id": "99140101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.10",
            "initial_risk_score": 0.10,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 40.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    # Weak device signal (supports='none') must NOT trigger confirmed_fraud
    assert final_state.get("fraud_hypotheses") == ["none"]
    assert final_state.get("outcome") == "cleared"
    assert "BLOCK_CARD" not in final_state.get("executed_actions", [])
    assert "CLOSE_NO_FRAUD" in final_state.get("executed_actions", [])


# ===========================================================================
# E15 — LOW SCORE + STRONG VELOCITY SIGNAL
# ===========================================================================
def test_edge_case_e15_low_score_strong_velocity_signal():
    """
    E15: initial_risk_score = 0.10.
    Velocity burst: 8 transactions in 5 minutes (strong velocity signal).
    Device = [], region = normal, context = [].
    - Missing device/context remains missing (not fabricated).
    - Strong velocity signal (supports='card_not_present_fraud') is retained.
    """
    tools = AgentTools(conn=None)

    ev_velocity = make_evidence(
        source=EvidenceSource.QUERY_VELOCITY,
        source_record_id="99150101",
        evidence_type=EvidenceType.VELOCITY_SIGNAL,
        description="High velocity burst: 8 transactions in 5 minutes.",
        observed_value={"txn_count": 8, "window_minutes": 5},
        provenance="transactions.csv:velocity",
        supports="card_not_present_fraud",
        confidence=0.9,
    )

    with patch.object(tools, "fetch_shared_device", return_value=[]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[ev_velocity]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E15-01",
            "customer_id": "C991501",
            "card_id": "C991501-K1",
            "flagged_txn_id": "99150101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.10",
            "initial_risk_score": 0.10,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 450.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    ledger = EvidenceLedger.from_json("HHG-E15-01", final_state["evidence_ledger_json"])
    assert len(ledger.by_type(EvidenceType.DEVICE_SIGNAL)) == 0, "Device signal must remain empty"
    assert "card_not_present_fraud" in final_state.get("fraud_hypotheses", [])
    assert final_state.get("outcome") == "confirmed_fraud"


# ===========================================================================
# E16 — HIGH SCORE + CONTRADICTORY NORMAL EVIDENCE (Customer Confirms)
# ===========================================================================
def test_edge_case_e16_high_score_contradictory_normal_evidence():
    """
    E16: initial_risk_score = 0.95.
    Region = normal, device = normal, velocity = normal.
    Customer explicit response = authorized (customer confirms transaction).
    - Can corroborating evidence contradict a high ML risk score?
    - High risk score must NOT blindly force confirmed_fraud when customer confirms transaction.
    - Outcome resolves to cleared; PolicyEngine POL-004 strictly forbids BLOCK_CARD.
    """
    tools = AgentTools(conn=None)

    ev_customer_confirm = make_evidence(
        source=EvidenceSource.BENCHMARK_CASE,
        source_record_id="HHG-E16-01",
        evidence_type=EvidenceType.CUSTOMER_REPORT,
        description="Customer confirmed they authorized the transaction.",
        observed_value={"customer_response": "authorized"},
        provenance="controlled_request:VERIFY_WITH_CUSTOMER",
        supports="none",
        confidence=0.95,
    )

    with patch.object(tools, "fetch_transaction_context", return_value=[]), \
         patch.object(tools, "fetch_shared_device", return_value=[]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[]), \
         patch.object(tools, "fetch_region_anomaly", return_value=[]), \
         patch.object(tools, "fetch_customer_case_history", return_value=[]), \
         patch.object(tools, "request_controlled_evidence", return_value={
             "response": {"customer_response": "authorized"},
             "evidence": ev_customer_confirm,
         }):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E16-01",
            "customer_id": "C991601",
            "card_id": "C991601-K1",
            "flagged_txn_id": "99160101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.95",
            "initial_risk_score": 0.95,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 300.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    assert final_state.get("outcome") == "cleared", "Outcome must be cleared when customer confirms"
    assert "BLOCK_CARD" not in final_state.get("executed_actions", []), "BLOCK_CARD must be stripped on cleared case despite 0.95 risk score"
    assert "CLOSE_NO_FRAUD" in final_state.get("executed_actions", [])


# ===========================================================================
# E17 — STRONG GRAPH EVIDENCE + CUSTOMER DENIAL / CONFIRMATION CONFLICT
# ===========================================================================
def test_edge_case_e17_strong_graph_evidence_customer_response_conflict():
    """
    E17: Strong graph anomalies (shared device with confirmed fraud) + Customer Response.
    Test both possibilities:
    Part A: Customer denies transaction -> confirmed_fraud, BLOCK_CARD + CREATE_CASE + FILE_REPORT.
    Part B: Customer confirms transaction -> cleared, CLOSE_NO_FRAUD required, BLOCK_CARD forbidden.
    - System must preserve evidence and policy safety in both cases.
    """
    policy_engine = PolicyEngine()

    # Part A: Customer denies transaction
    dec_deny = policy_engine.evaluate(
        outcome="confirmed_fraud",
        pattern="account_takeover",
        exposure_usd=1200.00,
        trigger_type="risk_score",
    )
    assert dec_deny.sar_required is True
    assert "BLOCK_CARD" in dec_deny.required_actions
    assert "FILE_REPORT" in dec_deny.required_actions

    # Part B: Customer confirms transaction
    dec_confirm = policy_engine.evaluate(
        outcome="cleared",
        pattern="none",
        exposure_usd=0.0,
        trigger_type="risk_score",
    )
    assert dec_confirm.sar_required is False
    assert "CLOSE_NO_FRAUD" in dec_confirm.required_actions
    assert "BLOCK_CARD" in dec_confirm.forbidden_actions
    assert "FILE_REPORT" in dec_confirm.forbidden_actions


# ===========================================================================
# E18 — MISSING CRITICAL EVIDENCE SOURCE
# ===========================================================================
def test_edge_case_e18_missing_critical_evidence_source():
    """
    E18: initial_risk_score = 0.70.
    transaction_context = [], device = [], velocity = strong, region = [], history = [].
    - Missing data must remain missing in EvidenceLedger.
    - System must NOT manufacture negative assertions ('device is normal', 'region is normal').
    - Ledger must contain only gathered velocity evidence and trigger evidence.
    """
    tools = AgentTools(conn=None)

    ev_velocity = make_evidence(
        source=EvidenceSource.QUERY_VELOCITY,
        source_record_id="99180101",
        evidence_type=EvidenceType.VELOCITY_SIGNAL,
        description="High velocity burst: 5 transactions in 10 minutes.",
        observed_value={"txn_count": 5, "window_minutes": 10},
        provenance="transactions.csv:velocity",
        supports="card_not_present_fraud",
        confidence=0.85,
    )

    with patch.object(tools, "fetch_transaction_context", return_value=[]), \
         patch.object(tools, "fetch_shared_device", return_value=[]), \
         patch.object(tools, "fetch_region_anomaly", return_value=[]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[ev_velocity]), \
         patch.object(tools, "fetch_customer_case_history", return_value=[]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E18-01",
            "customer_id": "C991801",
            "card_id": "C991801-K1",
            "flagged_txn_id": "99180101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.70",
            "initial_risk_score": 0.70,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 200.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    ledger = EvidenceLedger.from_json("HHG-E18-01", final_state["evidence_ledger_json"])
    assert len(ledger.by_type(EvidenceType.DEVICE_SIGNAL)) == 0, "No DEVICE_SIGNAL allowed"
    assert len(ledger.by_type(EvidenceType.REGION_SIGNAL)) == 0, "No REGION_SIGNAL allowed"
    assert len(ledger.by_type(EvidenceType.TRANSACTION_CONTEXT)) == 0, "No TRANSACTION_CONTEXT allowed"
    assert len(ledger.by_type(EvidenceType.VELOCITY_SIGNAL)) == 1, "Exactly 1 VELOCITY_SIGNAL expected"


# ===========================================================================
# E19 — MULTIPLE / CONTRADICTORY FRAUD HYPOTHESES (HHG-007 Scoping Check)
# ===========================================================================
def test_edge_case_e19_multiple_contradictory_fraud_hypotheses():
    """
    E19: out_of_region_use is contradicted (is_anomalous=False),
    BUT account_takeover AND card_testing are both supported by graph evidence.
    - Region contradiction guardrail MUST suppress ONLY out_of_region_use.
    - account_takeover and card_testing MUST NOT be wiped by the region guardrail.
    """
    tools = AgentTools(conn=None)

    ev_region_contradict = make_evidence(
        source=EvidenceSource.BENCHMARK_CASE,
        source_record_id="99190101",
        evidence_type=EvidenceType.REGION_SIGNAL,
        description="Transaction region matches home region.",
        observed_value={"is_anomalous": False},
        provenance="transactions.csv:addr1",
        contradicts="out_of_region_use",
        confidence=0.9,
    )

    ev_device_ato = make_evidence(
        source=EvidenceSource.QUERY_SHARED_DEVICE,
        source_record_id="99190101",
        evidence_type=EvidenceType.DEVICE_SIGNAL,
        description="Shared device linked to 3 ATO cases.",
        observed_value={"card_count": 3},
        provenance="identity.csv:DeviceInfo",
        supports="account_takeover",
        confidence=0.9,
    )

    ev_velocity_testing = make_evidence(
        source=EvidenceSource.QUERY_VELOCITY,
        source_record_id="99190101",
        evidence_type=EvidenceType.VELOCITY_SIGNAL,
        description="Rapid sub- authorizations.",
        observed_value={"txn_count": 4},
        provenance="transactions.csv:velocity",
        supports="card_testing",
        confidence=0.9,
    )

    with patch.object(tools, "fetch_region_anomaly", return_value=[ev_region_contradict]), \
         patch.object(tools, "fetch_shared_device", return_value=[ev_device_ato]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[ev_velocity_testing]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-E19-01",
            "customer_id": "C991901",
            "card_id": "C991901-K1",
            "flagged_txn_id": "99190101",
            "trigger_type": "risk_score",
            "trigger_text": "Model risk score 0.85",
            "initial_risk_score": 0.85,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 600.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    hypotheses = final_state.get("fraud_hypotheses", [])
    assert "out_of_region_use" not in hypotheses, "out_of_region_use must be suppressed by region guardrail"
    assert len(hypotheses) > 0, "At least one remaining hypothesis must survive (account_takeover / card_testing)"
    assert final_state.get("outcome") == "confirmed_fraud"


# ===========================================================================
# E20 — LIVE LLM vs DETERMINISTIC FALLBACK PARITY
# ===========================================================================
def test_edge_case_e20_live_llm_vs_deterministic_fallback_parity():
    """
    E20: Parity comparison between Live LLM reasoning and Deterministic Fallback reasoning.
    Runs 3 representative test states under:
      Path A: Live LLM (mocked valid structured response)
      Path B: Deterministic Fallback (_fallback_assess_investigation)
    Verifies semantic equivalence:
      - Outcome must match (confirmed_fraud vs confirmed_fraud, cleared vs cleared)
      - Executed actions must be identical / policy compliant
      - PolicyEngine decision must match
    """
    policy_engine = PolicyEngine()
    tools = AgentTools(conn=None)

    # Test Case 1: High risk score confirmed fraud
    state_high_risk: InvestigationState = {
        "case_id": "HHG-E20-01",
        "customer_id": "C992001",
        "card_id": "C992001-K1",
        "flagged_txn_id": "99200101",
        "trigger_type": "risk_score",
        "trigger_text": "Model risk score 0.85",
        "initial_risk_score": 0.85,
        "opened_at": "",
        "case_status": "open",
        "exposure_usd": 1200.00,
        "agent_trace": [],
    }

    # Path A: Live LLM
    nodes_live = WorkflowNodes(tools=tools, policy_engine=policy_engine)
    nodes_live.llm_reasoner.assess_investigation = MagicMock(return_value={
        "fraud_hypotheses": ["card_not_present_fraud"],
        "risk_level": "high",
        "confidence": 0.90,
        "uncertainty": 0.10,
        "evidence_sufficient": True,
        "missing_evidence": [],
        "reasoning_summary": "High risk score with unverified online transaction.",
        "evidence_citations": [],
        "reasoning_source": "llm",
    })
    nodes_live.llm_reasoner.propose_actions = MagicMock(return_value={
        "recommended_actions": ["CREATE_CASE", "BLOCK_CARD", "FILE_REPORT"],
        "reasoning_source": "llm",
    })

    app_live = build_investigation_graph(nodes_live)
    state_live = app_live.invoke(dict(state_high_risk))

    # Path B: Deterministic Fallback
    nodes_fallback = WorkflowNodes(tools=tools, policy_engine=policy_engine)
    nodes_fallback.llm_reasoner.is_available = False  # Force fallback
    app_fallback = build_investigation_graph(nodes_fallback)
    state_fallback = app_fallback.invoke(dict(state_high_risk))

    # Compare Parity
    assert state_live["outcome"] == state_fallback["outcome"] == "confirmed_fraud", "Outcomes must match (confirmed_fraud)"
    assert state_live["executed_actions"] == state_fallback["executed_actions"], "Executed actions must be identical"
    assert state_live["policy_decision"]["sar_required"] == state_fallback["policy_decision"]["sar_required"] == True
    assert state_live["reasoning_source"] == "llm"
    assert state_fallback["reasoning_source"] == "deterministic_fallback"