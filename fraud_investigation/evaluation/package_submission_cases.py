"""Create root-level official submission files from verified Phase 3 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from .cases import load_benchmark_cases


ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "docs" / "PHASE3_EVALUATION_RESULTS.json"
CASES_DIR = ROOT / "cases"


def load_authoritative_results(path: Path = RESULTS_PATH) -> Dict[str, Dict[str, Any]]:
    """Load the verified Phase 3 telemetry, indexed by case identifier."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("results", [])
    return {row["case_id"]: row for row in rows}


def submission_record(case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Project authoritative telemetry into the organizer's per-case answer format."""
    evidence = result["evidence_gathered"]
    evidence_ids = {item["evidence_id"] for item in evidence}
    citations = list(result["evidence_citations"])
    writeback_calls = [
        event for event in result["mcp_tool_calls"]
        if event.get("tool") == "tigergraph__add_nodes"
    ]
    return {
        "case_id": case["case_id"],
        "case": {
            "trigger_type": case["trigger_type"],
            "trigger_text": case["trigger_text"],
            "opened_at": case["opened_at"],
            "customer_id": case["customer_id"],
            "card_id": case["card_id"],
            "flagged_txn_id": case["flagged_txn_id"],
            "initial_risk_score": case["risk_score"],
        },
        "investigation": {
            "risk_level": result["risk_level"],
            "confidence": result["confidence"],
            "uncertainty": result["uncertainty"],
            "evidence_sufficient": result["evidence_sufficient"],
            "fraud_hypotheses": result["fraud_hypotheses"],
            "missing_evidence": result["missing_evidence"],
        },
        "evidence": evidence,
        "findings": {
            "outcome": result["outcome"],
            "pattern": result["pattern"],
            "summary": result["explanation"],
        },
        "decisions": {
            "recommended_actions": result["recommended_actions"],
            "approval_route": result["approval_route"],
            "policy_decision": result["policy_decision"],
        },
        "additional_evidence": {
            "rounds": result["additional_evidence_rounds"],
            "requests": result["additional_evidence_requested"],
            "responses": result["additional_evidence_responses"],
            "nba_before": result["nba_before"],
            "nba_after": result["nba_after"],
        },
        "execution": {
            "executed_actions": result["executed_actions"],
            "sar_required": result["sar_requirement"],
        },
        "memory": {
            "written_to_graph": result["writeback_observed"],
            "graph_record_type": "InvestigationCase",
            "mcp_transport": result["mcp_transport"],
            "writeback_tool_calls": writeback_calls,
            "transport_failures": result["mcp_failures"],
        },
        "explanation": {
            "text": result["explanation"],
            "citations": citations,
        },
        "metadata": {
            "reasoning_source": result["reasoning_source"],
            "citation_validity": all(citation in evidence_ids for citation in citations),
            "source_artifact": "docs/PHASE3_EVALUATION_RESULTS.json",
        },
    }


def package_submission_cases(cases_dir: Path = CASES_DIR) -> Iterable[Path]:
    """Write one exact-name JSON answer per verified benchmark case."""
    results = load_authoritative_results()
    cases = load_benchmark_cases()
    case_ids = [case["case_id"] for case in cases]
    if set(results) != set(case_ids):
        raise ValueError("Phase 3 result case IDs do not exactly match case_pack.csv")

    cases_dir.mkdir(exist_ok=True)
    written = []
    for case in cases:
        target = cases_dir / f"{case['case_id']}.json"
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(submission_record(case, results[case["case_id"]]), handle, indent=2)
            handle.write("\n")
        written.append(target)
    return written


if __name__ == "__main__":
    paths = list(package_submission_cases())
    print(f"Wrote {len(paths)} official submission case files to {CASES_DIR}")
