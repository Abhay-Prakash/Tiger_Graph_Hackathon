"""
Deterministic Robustness & Failure Test Suite — Phase 3 + Phase 4.

Phase 3 Tests (1-5):
1. Gemini failure -> deterministic fallback (reasoning_source = "deterministic_fallback")
2. Hallucinated Evidence ID -> rejected & stripped cleanly
3. Forbidden action -> filtered out by PolicyEngine
4. Additional evidence loop -> strictly bounded at max 1 round
5. HHG-007 region contradiction -> out_of_region_use suppressed when is_anomalous = false

Phase 4 Tests (6-10):
6. Empty EvidenceLedger (all MCP queries return []) -> agent completes safely
7. Malformed LLM JSON -> Pydantic validation fails -> deterministic fallback
8. MCP tool call failure (success=False) -> graceful degradation, no crash
9. analyst_request trigger -> cleared outcome -> BLOCK_CARD forbidden
10. Missing device data (fetch_shared_device returns []) -> no crash, no fake evidence
"""

from unittest.mock import MagicMock, patch
import pytest

from fraud_investigation.agent.graph import route_sufficiency
from fraud_investigation.agent.llm_reasoner import LLMReasoner, validate_and_extract_citations
from fraud_investigation.agent.nodes import WorkflowNodes
from fraud_investigation.agent.runner import run_fraud_investigation
from fraud_investigation.agent.state import InvestigationState
from fraud_investigation.agent.tools import AgentTools
from fraud_investigation.evidence.ledger import EvidenceLedger
from fraud_investigation.evidence.model import EvidenceSource, EvidenceType, make_evidence
from fraud_investigation.policy.engine import PolicyEngine


# ---------------------------------------------------------------------------
# Test 1: Gemini Failure / Unavailable -> Graceful Deterministic Fallback
# ---------------------------------------------------------------------------
def test_gemini_failure_fallback_tracing():
    """
    Verify that when Gemini API call raises an Exception, LLMReasoner catches it
    and falls back cleanly to deterministic reasoning with reasoning_source='deterministic_fallback'.
    """
    reasoner = LLMReasoner()
    # Force API key presence to trigger API attempt path
    reasoner.api_key = "fake_key_for_testing"
    reasoner.is_available = True

    with patch.object(reasoner, "_call_llm_json", side_effect=RuntimeError("Simulated Gemini 503 Spike")):
        res = reasoner.assess_investigation(
            case_id="HHG-FAIL-01",
            customer_id="C99999",
            flagged_txn_id="9999999",
            evidence_summary={},
            evidence_list=[],
            initial_risk_score=0.85,
            trigger_type="risk_score",
            additional_rounds=0,
            region_contradicts=False,
        )

    assert res["reasoning_source"] == "deterministic_fallback"
    assert "fraud_hypotheses" in res
    assert isinstance(res["confidence"], float)


# ---------------------------------------------------------------------------
# Test 2: Hallucinated Evidence ID Rejection
# ---------------------------------------------------------------------------
def test_hallucinated_citation_stripping():
    """
    Verify that validate_and_extract_citations strips hallucinated/unrecognized Evidence IDs
    that do not exist in the EvidenceLedger valid set.
    """
    valid_ledger_ids = {"EVD-75D480F6F6FF", "EVD-940B92FE1731"}
    raw_citations = ["EVD-75D480F6F6FF", "EVD-HALLUCINATED-999", "EVD-FAKE-123"]
    text = "The transaction was flagged [EVD-75D480F6F6FF] but fake [EVD-HALLUCINATED-999] was cited."

    cleaned = validate_and_extract_citations(raw_citations, text, valid_ledger_ids)
    assert cleaned == ["EVD-75D480F6F6FF"]
    assert "EVD-HALLUCINATED-999" not in cleaned
    assert "EVD-FAKE-123" not in cleaned


# ---------------------------------------------------------------------------
# Test 3: Forbidden Action Filtered by PolicyEngine
# ---------------------------------------------------------------------------
def test_policy_engine_filters_forbidden_action():
    """
    Verify that PolicyEngine strictly filters out forbidden actions (e.g. BLOCK_CARD on cleared case)
    even if proposed by the LLM or agent nodes.
    """
    policy_engine = PolicyEngine()
    
    # Evaluate a cleared case where BLOCK_CARD is proposed
    evaluated = policy_engine.evaluate(
        outcome="cleared",
        pattern="none",
        exposure_usd=49.00,
    )

    # BLOCK_CARD is forbidden for cleared cases per policy_rules.json
    assert "BLOCK_CARD" in evaluated.forbidden_actions
    assert "BLOCK_CARD" not in evaluated.permitted_actions
    assert "CLOSE_NO_FRAUD" in evaluated.permitted_actions or "CLOSE_NO_FRAUD" in evaluated.required_actions


# ---------------------------------------------------------------------------
# Test 4: Additional Evidence Loop Bounded at Max 1 Round
# ---------------------------------------------------------------------------
def test_additional_evidence_loop_max_depth_bound():
    """
    Verify that after additional_evidence_rounds reaches 1, route_sufficiency
    returns 'sufficient' to enforce the MAX_ADDITIONAL_EVIDENCE_ROUNDS = 1 bound.
    """
    state_round_0: InvestigationState = {
        "evidence_sufficient": False,
        "additional_evidence_rounds": 0,
    }
    assert route_sufficiency(state_round_0) == "insufficient"

    state_round_1: InvestigationState = {
        "evidence_sufficient": False,
        "additional_evidence_rounds": 1,
    }
    # Once rounds == 1, route_sufficiency MUST override and return 'sufficient'
    assert route_sufficiency(state_round_1) == "sufficient"


# ---------------------------------------------------------------------------
# Test 5: HHG-007 Region Contradiction Guardrail
# ---------------------------------------------------------------------------
def test_hhg007_region_contradiction_suppression():
    """
    HHG-007 Regression Test:
    When is_anomalous = false (flagged region 264.0 == home region 264.0),
    out_of_region_use MUST NOT be asserted in hypotheses.
    """
    tools = AgentTools(conn=None)
    nodes = WorkflowNodes(tools=tools)

    ledger = EvidenceLedger(case_id="HHG-007")
    ledger.add(
        make_evidence(
            source=EvidenceSource.QUERY_REGION_ANOMALY,
            source_record_id="3514948",
            evidence_type=EvidenceType.REGION_SIGNAL,
            description="Transaction region 264.0 matches customer primary home region 264.0.",
            observed_value={"flagged_addr1": 264.0, "home_region": 264.0},
            provenance="transactions.csv:addr1 (txn=3514948)",
            contradicts="out_of_region_use",
            confidence=0.9,
        )
    )

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
    assert "out_of_region_use" not in assessed["fraud_hypotheses"]


# ===========================================================================
# PHASE 4 ROBUSTNESS TESTS (6-10)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 6: Empty EvidenceLedger — all MCP queries return []
# ---------------------------------------------------------------------------
def test_empty_evidence_ledger_does_not_crash():
    """
    Invariant: If every MCP evidence query returns [], the agent must:
    - complete the full LangGraph workflow without crashing
    - produce a structurally valid final state
    - not fabricate any evidence citations
    - remain in deterministic fallback mode safely
    """
    case_data = {
        "case_id": "HHG-EMPTY-01",
        "customer_id": "C99000",
        "card_id": "C99000-K1",
        "flagged_txn_id": "9000001",
        "trigger_type": "risk_score",
        "trigger_text": "Risk score 0.80 on empty evidence test",
        "risk_score": 0.80,
        "amount": 50.00,
    }

    tools = AgentTools(conn=None)
    # Patch all five evidence-fetching methods to return []
    with patch.object(tools, "fetch_transaction_context", return_value=[]), \
         patch.object(tools, "fetch_region_anomaly", return_value=[]), \
         patch.object(tools, "fetch_shared_device", return_value=[]), \
         patch.object(tools, "fetch_velocity_burst", return_value=[]), \
         patch.object(tools, "fetch_customer_case_history", return_value=[]):

        from fraud_investigation.agent.graph import build_investigation_graph
        from fraud_investigation.agent.nodes import WorkflowNodes
        from fraud_investigation.policy.engine import PolicyEngine

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": case_data["case_id"],
            "customer_id": case_data["customer_id"],
            "card_id": case_data["card_id"],
            "flagged_txn_id": case_data["flagged_txn_id"],
            "trigger_type": case_data["trigger_type"],
            "trigger_text": case_data["trigger_text"],
            "initial_risk_score": 0.80,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 50.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    # Workflow must complete without error
    assert final_state is not None
    assert "outcome" in final_state
    assert final_state.get("outcome") in {"confirmed_fraud", "cleared"}
    assert "executed_actions" in final_state
    assert isinstance(final_state["executed_actions"], list)
    # Explanation must exist
    assert "explanation" in final_state
    # No hallucinated citations: all cited EVD IDs must be in the ledger
    from fraud_investigation.evidence.ledger import EvidenceLedger as EL
    ledger = EL.from_json(case_data["case_id"], final_state.get("evidence_ledger_json", "[]"))
    valid_ids = {e.evidence_id for e in ledger.all}
    citations = final_state.get("evidence_citations", [])
    for cid in citations:
        assert cid in valid_ids, f"Hallucinated citation {cid!r} not in ledger"


# ---------------------------------------------------------------------------
# Test 7: Malformed LLM JSON -> Pydantic validation fails -> fallback
# ---------------------------------------------------------------------------
def test_malformed_llm_json_falls_back():
    """
    Invariant: When the LLM returns malformed JSON (not parseable by Pydantic),
    LLMReasoner must catch the error and fall back to deterministic reasoning.
    reasoning_source must equal "deterministic_fallback".
    The workflow must not crash.
    """
    reasoner = LLMReasoner()
    reasoner.api_key = "fake_key_for_malformed_json_test"
    reasoner.is_available = True

    # _call_llm_json returns a non-JSON string — Pydantic model_validate_json will fail
    with patch.object(reasoner, "_call_llm_json", return_value="not valid json {{ broken"):
        res = reasoner.assess_investigation(
            case_id="HHG-MALFORM-01",
            customer_id="C99001",
            flagged_txn_id="9000002",
            evidence_summary={},
            evidence_list=[],
            initial_risk_score=0.75,
            trigger_type="risk_score",
            additional_rounds=0,
            region_contradicts=False,
        )

    assert res["reasoning_source"] == "deterministic_fallback"
    assert "fraud_hypotheses" in res
    assert isinstance(res["confidence"], float)
    assert 0.0 <= res["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Test 8: MCP tool call returns success=False -> graceful degradation
# ---------------------------------------------------------------------------
def test_mcp_tool_failure_graceful_degradation():
    """
    Invariant: When TigerGraphMCPClient.call_mcp_tool returns success=False,
    the agent must not crash. Evidence gathering must degrade safely
    (returning empty lists or offline stubs), and no fabricated evidence
    must be introduced.
    """
    from fraud_investigation.agent.mcp_client import TigerGraphMCPClient

    # Create a mock conn so that is_live() returns True, but call_mcp_tool fails
    mock_conn = MagicMock()
    mock_conn.runInstalledQuery.side_effect = RuntimeError("Simulated GSQL query failure")

    tools = AgentTools(conn=mock_conn)
    # Even with a live conn but failing query, the MCP client wraps and returns error
    result = tools.mcp_client.call_mcp_tool(
        "run_installed_query",
        {"query_name": "get_transaction_context", "params": {"flagged_txn_id": "9000003"}},
    )
    # Must return a structured error response, not raise an exception
    assert result is not None
    assert result.get("success") is False
    assert "error" in result

    # The agent's evidence fetch methods must not crash even with a failing conn
    # fetch_transaction_context falls back to offline mock when live query fails
    # (tools.py catches exceptions at the query-runner level via mcp_client)
    # Here we verify the tools layer does NOT propagate the exception upward:
    try:
        evs = tools.fetch_transaction_context("9000003")
        # Either returns evidence (offline stub path) or empty list — never raises
        assert isinstance(evs, list)
    except Exception as exc:
        pytest.fail(f"fetch_transaction_context raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Test 9: analyst_request trigger -> cleared outcome -> BLOCK_CARD forbidden
# ---------------------------------------------------------------------------
def test_analyst_request_trigger_yields_cleared():
    """
    Invariant: For a case with trigger_type='analyst_request' and no
    supporting fraud hypothesis, the PolicyEngine must:
    - produce outcome = "cleared"
    - include BLOCK_CARD in forbidden_actions
    - NOT include BLOCK_CARD in executed_actions
    PolicyEngine remains the deterministic authority over this decision.
    """
    from fraud_investigation.policy.engine import PolicyEngine

    policy_engine = PolicyEngine()

    # Evaluate a cleared analyst_request case
    decision = policy_engine.evaluate(
        outcome="cleared",
        pattern="none",
        exposure_usd=0.0,
        trigger_type="analyst_request",
    )

    assert "BLOCK_CARD" in decision.forbidden_actions, \
        "BLOCK_CARD must be forbidden for a cleared case"
    assert "CLOSE_NO_FRAUD" in decision.required_actions, \
        "CLOSE_NO_FRAUD must be required for a cleared case"
    assert "BLOCK_CARD" not in decision.required_actions
    assert "BLOCK_CARD" not in decision.permitted_actions

    # Now run a full investigation to confirm agent-level enforcement
    case_data = {
        "case_id": "HHG-014",
        "customer_id": "C13487",
        "card_id": "C13487-K1",
        "flagged_txn_id": "3534791",
        "trigger_type": "analyst_request",
        "trigger_text": "Analyst flagged for manual review — no model score",
        "risk_score": 0.0,
        "amount": 0.0,
    }

    final_state = run_fraud_investigation(case_data, conn=None)

    # Confirmed: outcome is cleared and BLOCK_CARD not executed
    assert final_state.get("outcome") == "cleared", \
        f"Expected 'cleared', got {final_state.get('outcome')!r}"
    assert "BLOCK_CARD" not in final_state.get("executed_actions", []), \
        "BLOCK_CARD must not be executed on a cleared case"


# ---------------------------------------------------------------------------
# Test 10: Missing device data (fetch_shared_device returns []) -> no crash
# ---------------------------------------------------------------------------
def test_missing_device_data_no_crash():
    """
    Invariant: When fetch_shared_device returns [], indicating no device
    fingerprint data is available for the flagged transaction:
    - workflow must complete without exception
    - no fabricated DEVICE_SIGNAL evidence must be added to the ledger
    - the absence of device data must not cause the investigation to crash
    """
    from fraud_investigation.agent.graph import build_investigation_graph
    from fraud_investigation.agent.nodes import WorkflowNodes
    from fraud_investigation.policy.engine import PolicyEngine
    from fraud_investigation.evidence.model import EvidenceType

    tools = AgentTools(conn=None)

    # Patch only fetch_shared_device to return [] (device data absent)
    with patch.object(tools, "fetch_shared_device", return_value=[]):

        nodes = WorkflowNodes(tools=tools, policy_engine=PolicyEngine())
        app = build_investigation_graph(nodes)

        initial_state: InvestigationState = {
            "case_id": "HHG-NODEV-01",
            "customer_id": "C99002",
            "card_id": "C99002-K1",
            "flagged_txn_id": "9000004",
            "trigger_type": "customer_report",
            "trigger_text": "Customer reported unauthorized transaction",
            "initial_risk_score": 0.0,
            "opened_at": "",
            "case_status": "open",
            "exposure_usd": 150.00,
            "agent_trace": [],
        }

        final_state = app.invoke(initial_state)

    # Workflow must complete
    assert final_state is not None
    assert "outcome" in final_state

    # Inspect ledger: no DEVICE_SIGNAL evidence must exist (since we patched it to [])
    from fraud_investigation.evidence.ledger import EvidenceLedger as EL
    ledger = EL.from_json("HHG-NODEV-01", final_state.get("evidence_ledger_json", "[]"))
    device_evs = ledger.by_type(EvidenceType.DEVICE_SIGNAL)
    assert len(device_evs) == 0, \
        f"No DEVICE_SIGNAL evidence expected when fetch_shared_device returns []; found {len(device_evs)}"
