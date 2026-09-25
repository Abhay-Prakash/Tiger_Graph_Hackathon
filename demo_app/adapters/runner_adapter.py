"""Translate existing investigation state into display-only UI data."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from fraud_investigation.agent.runner import run_fraud_investigation
from fraud_investigation.evaluation.cases import load_benchmark_cases
from fraud_investigation.evidence.ledger import EvidenceLedger


PRIORITY_CASE_IDS = ("HHG-007", "HHG-001", "HHG-014")
MAX_ADDITIONAL_EVIDENCE_ROUNDS = 1


def load_cases() -> List[Dict[str, Any]]:
    """Load the existing benchmark case pack without adding UI fixture data."""
    return load_benchmark_cases()


def case_by_id(case_id: str, cases: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise KeyError(f"Case {case_id!r} was not found in the benchmark case pack")


def _evidence_from_state(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = state.get("evidence_ledger_json", "")
    if not raw:
        return []
    return [item.to_dict() for item in EvidenceLedger.from_json(state["case_id"], raw).all]


def _timeline(trace: Iterable[str]) -> List[Dict[str, str]]:
    """Keep actual agent trace lines intact while exposing a compact UI label."""
    labels = {
        "initialize_case": "Trigger",
        "gather_initial_evidence": "Evidence Retrieval",
        "retrieve_case_memory": "Case Memory",
        "build_evidence_ledger": "Evidence Ledger",
        "assess_investigation": "Risk Assessment",
        "identify_missing_evidence": "Evidence Sufficiency",
        "request_additional_evidence": "Additional Evidence",
        "incorporate_response": "Additional Evidence",
        "reassess_investigation": "Reassessment",
        "determine_next_action": "Next Best Action",
        "policy_gate": "Policy Gate",
        "approval_gate": "Approval",
        "execute_or_simulate": "Execution / Simulation",
        "write_case_memory": "Case Writeback",
        "generate_explanation": "Grounded Explanation",
    }
    entries = []
    for line in trace:
        node = next((name for name in labels if f"] [{name}]" in line), "")
        entries.append({"label": labels.get(node, "Agent Trace"), "detail": line})
    return entries


def present_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return a display model composed only from authoritative runner output."""
    evidence = _evidence_from_state(state)
    policy = dict(state.get("policy_decision") or {})
    protocol_trace = list(state.get("mcp_protocol_trace") or [])
    executed = list(state.get("executed_actions") or [])
    forbidden = list(policy.get("forbidden_actions") or [])
    writeback_event = next(
        (event for event in protocol_trace if event.get("tool") == "tigergraph__add_nodes"),
        None,
    )

    return {
        "case": {
            "case_id": state.get("case_id"),
            "trigger_type": state.get("trigger_type"),
            "trigger_text": state.get("trigger_text"),
            "customer_id": state.get("customer_id"),
            "card_id": state.get("card_id"),
            "flagged_txn_id": state.get("flagged_txn_id"),
            "initial_risk_score": state.get("initial_risk_score"),
            "outcome": state.get("outcome"),
            "pattern": state.get("pattern"),
            "reasoning_source": state.get("reasoning_source"),
        },
        "evidence": evidence,
        "timeline": _timeline(state.get("agent_trace") or []),
        "assessment": {
            "hypotheses": list(state.get("fraud_hypotheses") or []),
            "supported": list((state.get("gathered_evidence_summary") or {}).get("hypotheses_supported", {}).keys()),
            "contradicted": list((state.get("gathered_evidence_summary") or {}).get("hypotheses_contradicted", {}).keys()),
            "confidence": state.get("confidence"),
            "uncertainty": state.get("uncertainty"),
            "evidence_sufficient": state.get("evidence_sufficient"),
            "missing_evidence": list(state.get("missing_evidence") or []),
            "additional_rounds": state.get("additional_evidence_rounds", 0),
            "max_additional_rounds": MAX_ADDITIONAL_EVIDENCE_ROUNDS,
        },
        "nba": {
            "before": state.get("nba_before_additional_evidence"),
            "requests": list(state.get("evidence_requests") or []),
            "responses": list(state.get("evidence_responses") or []),
            "after": state.get("nba_after_additional_evidence"),
        },
        "policy": {
            **policy,
            "executed_actions": executed,
            "reported_violations": [action for action in executed if action in forbidden],
        },
        "graph_memory": {
            "case_id": state.get("case_id"),
            "flagged_txn_id": state.get("flagged_txn_id"),
            "customer_id": state.get("customer_id"),
            "writeback_observed_via_mcp": writeback_event is not None,
            "writeback_trace": writeback_event,
        },
        "explanation": state.get("explanation", ""),
        "citations": list(state.get("evidence_citations") or []),
        "protocol_trace": protocol_trace,
        "graph_transport_failures": list(state.get("graph_transport_failures") or []),
        "raw_state": state,
    }


def run_live_case(
    case_data: Dict[str, Any],
    runner: Callable[..., Dict[str, Any]] = run_fraud_investigation,
) -> Dict[str, Any]:
    """Run one selected benchmark case through the existing live MCP workflow."""
    return present_state(runner(case_data, live_mcp=True))
