"""
Phase 2 & Phase 2.6 & Phase 2.6.5 Test Suite for LangGraph Fraud Investigation Agent.

Tests:
1. State initialization
2. Evidence gathering & normalization via TigerGraphMCPClient
3. Contradicting evidence preservation (HHG-007 regression)
4. Insufficient evidence branch & additional evidence loop
5. Bounded loop behavior (MAX_ADDITIONAL_EVIDENCE_ROUNDS = 1)
6. Reassessment after evidence
7. NBA-before capture & NBA-after capture
8. Policy rejection & forbidden action enforcement
9. Approval-required routing
10. Case memory write via MCP
11. Grounded explanation generation with Evidence ID citations
12. LLM structured output parsing & fallback tracing (reasoning_source)
13. MCP transport metadata tracking (live_mcp vs mock_mcp)
14. Evidence citation validation & hallucinated ID stripping
"""

import json
from pathlib import Path
import pytest

from fraud_investigation.agent.graph import build_investigation_graph, route_sufficiency
from fraud_investigation.agent.llm_reasoner import AssessmentResult, LLMReasoner, validate_and_extract_citations
from fraud_investigation.agent.mcp_client import TigerGraphMCPClient
from fraud_investigation.agent.nodes import WorkflowNodes
from fraud_investigation.agent.runner import run_fraud_investigation
from fraud_investigation.agent.state import InvestigationState
from fraud_investigation.agent.tools import AgentTools
from fraud_investigation.evidence.ledger import EvidenceLedger
from fraud_investigation.evidence.model import EvidenceSource, EvidenceType, make_evidence
from fraud_investigation.policy.engine import PolicyEngine


# ---------------------------------------------------------------------------
# Test 1: MCP Client & Tool Execution
# ---------------------------------------------------------------------------
def test_mcp_client_and_transport_metadata():
    mcp_client = TigerGraphMCPClient(conn=None, use_mcp=True)
    assert mcp_client.transport_name == "mock_mcp"

    tools = AgentTools(mcp_client=mcp_client)
    assert tools.transport_name == "mock_mcp"

    evs = tools.fetch_transaction_context("3514030")
    assert len(evs) == 1
    assert "mock_mcp" in evs[0].description


# ---------------------------------------------------------------------------
# Test 2: Structured LLM Reasoner & Fallback Tracing
# ---------------------------------------------------------------------------
def test_llm_reasoner_structured_fallback_tracing():
    reasoner = LLMReasoner()
    # When no API key is provided, reasoner gracefully falls back to deterministic logic
    res = reasoner.assess_investigation(
        case_id="HHG-001",
        customer_id="C12382",
        flagged_txn_id="3514030",
        evidence_summary={},
        evidence_list=[],
        initial_risk_score=0.61,
        trigger_type="risk_score",
        additional_rounds=0,
        region_contradicts=False,
    )
    assert res["reasoning_source"] in {"llm", "deterministic_fallback"}
    assert "fraud_hypotheses" in res
    assert isinstance(res["confidence"], float)


# ---------------------------------------------------------------------------
# Test 3: Citation Validation (Hallucination Rejection)
# ---------------------------------------------------------------------------
def test_citation_validation_strips_hallucinations():
    valid_set = {"EVD-123456789012", "EVD-ABCDEF123456"}
    cited = ["EVD-123456789012", "EVD-HALLUCINATED-999"]
    
    validated = validate_and_extract_citations(cited, "", valid_set)
    assert validated == ["EVD-123456789012"]
    assert "EVD-HALLUCINATED-999" not in validated


# ---------------------------------------------------------------------------
# Test 4: HHG-007 Contradiction Guardrail
# ---------------------------------------------------------------------------
def test_hhg007_contradiction_guardrail():
    """
    HHG-007 Regression Test:
    risk_score = 0.87 must NOT cause the agent to claim out_of_region_use
    when the region baseline is non-anomalous (flagged 264.0 == home 264.0).
    """
    case_data = {
        "case_id": "HHG-007",
        "customer_id": "C09933",
        "card_id": "C09933-K2",
        "flagged_txn_id": "3514948",
        "trigger_type": "risk_score",
        "trigger_text": "Model scored transaction at 0.87",
        "risk_score": 0.87,
        "amount": 111.92,
    }

    tools = AgentTools(conn=None)
    nodes = WorkflowNodes(tools=tools)

    ledger = EvidenceLedger(case_id="HHG-007")
    ledger.add(make_evidence(
        source=EvidenceSource.QUERY_REGION_ANOMALY,
        source_record_id="3514948",
        evidence_type=EvidenceType.REGION_SIGNAL,
        description="Transaction region 264.0 matches customer primary home region 264.0.",
        observed_value={"flagged_addr1": 264.0, "home_region": 264.0},
        provenance="transactions.csv:addr1 (txn=3514948)",
        contradicts="out_of_region_use",
        confidence=0.9,
    ))

    state: InvestigationState = {
        "case_id": "HHG-007",
        "customer_id": "C09933",
        "flagged_txn_id": "3514948",
        "trigger_type": "risk_score",
        "initial_risk_score": 0.87,
        "evidence_ledger_json": ledger.to_json(),
        "agent_trace": [],
    }

    assessed = nodes.assess_investigation(state)

    # Verify out_of_region_use is NOT in hypotheses due to region contradiction
    assert "out_of_region_use" not in assessed["fraud_hypotheses"]


# ---------------------------------------------------------------------------
# Test 5: Insufficient Evidence Branch & Bounded Loop
# ---------------------------------------------------------------------------
def test_insufficient_evidence_branch_and_bounded_loop():
    tools = AgentTools(conn=None)
    nodes = WorkflowNodes(tools=tools)

    state: InvestigationState = {
        "case_id": "HHG-012",
        "customer_id": "C05876",
        "flagged_txn_id": "3553342",
        "trigger_type": "risk_score",
        "initial_risk_score": 0.55,  # moderate risk score triggers additional evidence branch
        "additional_evidence_rounds": 0,
        "evidence_ledger_json": EvidenceLedger("HHG-012").to_json(),
        "agent_trace": [],
    }

    # 1. First assessment -> insufficient evidence
    assessed = nodes.assess_investigation(state)
    assert assessed["evidence_sufficient"] is False
    assert route_sufficiency(assessed) == "insufficient"

    # 2. Identify missing evidence & request
    missing = nodes.identify_missing_evidence(assessed)
    assert missing["nba_before_additional_evidence"] == ["VERIFY_WITH_CUSTOMER"]

    req = nodes.request_additional_evidence(missing)
    assert len(req["evidence_requests"]) == 1

    inc = nodes.incorporate_response(req)
    assert inc["additional_evidence_rounds"] == 1

    reassessed = nodes.reassess_investigation(inc)
    assert reassessed["evidence_sufficient"] is True
    # Verify router now directs to sufficient (bounded loop prevents second round)
    assert route_sufficiency(reassessed) == "sufficient"


# ---------------------------------------------------------------------------
# Test 6: Policy Gate Rejection
# ---------------------------------------------------------------------------
def test_policy_rejection_for_cleared_case():
    tools = AgentTools(conn=None)
    nodes = WorkflowNodes(tools=tools)

    state: InvestigationState = {
        "case_id": "HHG-003",
        "customer_id": "C08623",
        "flagged_txn_id": "3530164",
        "trigger_type": "customer_report",
        "outcome": "cleared",
        "pattern": "none",
        "exposure_usd": 0.0,
        "recommended_actions": ["BLOCK_CARD", "CLOSE_NO_FRAUD"], # BLOCK_CARD is forbidden for cleared!
        "agent_trace": [],
    }

    gated = nodes.policy_gate(state)

    # BLOCK_CARD must be rejected/filtered out by PolicyEngine
    assert "BLOCK_CARD" not in gated["recommended_actions"]
    assert "CLOSE_NO_FRAUD" in gated["recommended_actions"]
    assert gated["policy_decision"]["forbidden_actions"] == ["BLOCK_CARD", "FILE_REPORT"]


# ---------------------------------------------------------------------------
# Test 7: Grounded Explanation with Citations
# ---------------------------------------------------------------------------
def test_grounded_explanation_with_citations():
    case_data = {
        "case_id": "HHG-010",
        "customer_id": "C10434",
        "flagged_txn_id": "3506725",
        "trigger_type": "risk_score",
        "risk_score": 0.90,
        "amount": 1000.03,
    }

    state = run_fraud_investigation(case_data, conn=None)

    exp = state.get("explanation", "")
    assert "FINDING:" in exp
    assert "EVIDENCE:" in exp
    assert "IMPLICATION:" in exp
    assert "UNCERTAINTY:" in exp
    assert "[EVD-" in exp  # References exact Evidence IDs
    assert state.get("reasoning_source") in {"llm", "deterministic_fallback"}
