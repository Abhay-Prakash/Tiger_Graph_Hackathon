"""
Evaluation Runner for Phase 3 Benchmark Evaluation.

Invokes the existing agent runner (`run_fraud_investigation`) for each benchmark case,
capturing telemetry, timing, citations, policy decisions, and execution metadata.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from ..agent.runner import run_fraud_investigation
from ..evidence.ledger import EvidenceLedger

logger = logging.getLogger(__name__)


def evaluate_single_case(case_data: Dict[str, Any], conn: Optional[Any] = None) -> Dict[str, Any]:
    """
    Evaluate a single benchmark case using the production agent workflow.

    Parameters
    ----------
    case_data : dict
        Case data from load_benchmark_cases().
    conn : Optional pyTigerGraph connection.

    Returns
    -------
    dict
        Telemetry dictionary recording all investigation states and metrics.
    """
    case_id = case_data["case_id"]
    start_time = time.time()
    error_msg = None
    final_state = {}

    try:
        final_state = run_fraud_investigation(case_data, conn=conn)
    except Exception as e:
        logger.error("Error investigating case %s: %s", case_id, e, exc_info=True)
        error_msg = str(e)

    duration = time.time() - start_time

    # Extract ledger stats & IDs
    evidence_ids = []
    evidence_count = 0
    if "evidence_ledger_json" in final_state:
        raw = final_state["evidence_ledger_json"]
        try:
            # evidence_ledger_json is always a JSON string (ledger.to_json())
            if isinstance(raw, str) and raw.strip():
                ledger = EvidenceLedger.from_json(case_id, raw)
            elif isinstance(raw, list):
                # Defensive: already parsed by LangGraph state serialisation
                import json as _json
                ledger = EvidenceLedger.from_json(case_id, _json.dumps(raw))
            else:
                raise ValueError(f"Unexpected evidence_ledger_json type: {type(raw)}")
            evidence_ids = [e.evidence_id for e in ledger.all]
            evidence_count = len(ledger.all)
        except Exception as _exc:
            logger.warning("Could not deserialise evidence ledger for %s: %s", case_id, _exc)
            # Fall back: use evidence_citations (populated from ledger in assess_investigation)
            evidence_ids = list(final_state.get("evidence_citations", []))

    # Extract policy decision details
    policy_dec = final_state.get("policy_decision") or {}
    permitted_actions = policy_dec.get("permitted_actions", [])
    forbidden_actions = policy_dec.get("forbidden_actions", [])
    policy_version = policy_dec.get("policy_version", "hackathon-inferred-v1")

    # Extract citations
    citations = final_state.get("evidence_citations", [])

    telemetry = {
        "case_id": case_id,
        "customer_id": case_data["customer_id"],
        "card_id": case_data.get("card_id", ""),
        "flagged_txn_id": case_data["flagged_txn_id"],
        "trigger_type": case_data.get("trigger_type", ""),
        "initial_risk_score": case_data.get("risk_score", 0.0),
        "outcome": final_state.get("outcome", "unknown"),
        "pattern": final_state.get("pattern", "unknown"),
        "fraud_hypotheses": final_state.get("fraud_hypotheses", []),
        "risk_level": final_state.get("risk_level", "unknown"),
        "confidence": final_state.get("confidence", 0.0),
        "uncertainty": final_state.get("uncertainty", 0.0),
        "evidence_ids": evidence_ids,
        "evidence_count": evidence_count,
        "evidence_citations": citations,
        "reasoning_source": final_state.get("reasoning_source", "unknown"),
        "recommended_actions": final_state.get("recommended_actions", []),
        "permitted_actions": permitted_actions,
        "forbidden_actions": forbidden_actions,
        "executed_actions": final_state.get("executed_actions", []),
        "approval_route": final_state.get("approval_route", "unknown"),
        "additional_evidence_rounds": final_state.get("additional_evidence_rounds", 0),
        "nba_before": final_state.get("nba_before_additional_evidence"),
        "nba_after": final_state.get("nba_after_additional_evidence"),
        "policy_version": policy_version,
        "explanation": final_state.get("explanation", ""),
        "duration_seconds": round(duration, 4),
        "error": error_msg,
    }

    return telemetry


def run_benchmark_eval(
    cases: List[Dict[str, Any]], conn: Optional[Any] = None, delay_between_cases: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Run evaluation across all benchmark cases.

    Parameters
    ----------
    cases : List[Dict[str, Any]]
        List of benchmark case objects.
    conn : Optional pyTigerGraph connection.
    delay_between_cases : float
        Inter-case delay in seconds to prevent API rate limiting.

    Returns
    -------
    List[Dict[str, Any]]
        List of telemetry dictionaries for all evaluated cases.
    """
    results = []
    total = len(cases)

    for i, case in enumerate(cases, 1):
        logger.info("Evaluating benchmark case [%d/%d]: %s", i, total, case["case_id"])
        res = evaluate_single_case(case, conn=conn)
        results.append(res)

        if delay_between_cases > 0 and i < total:
            time.sleep(delay_between_cases)

    return results
