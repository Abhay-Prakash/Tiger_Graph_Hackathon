"""Validate root-level official case answers against frozen Phase 3 results."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .cases import load_benchmark_cases
from .package_submission_cases import CASES_DIR, load_authoritative_results


TOP_LEVEL_FIELDS = {
    "case_id", "case", "investigation", "evidence", "findings", "decisions",
    "additional_evidence", "execution", "memory", "explanation", "metadata",
}
ALLOWED_OUTCOMES = {"confirmed_fraud", "cleared", "unknown"}


def _error(errors: List[str], case_id: str, message: str) -> None:
    errors.append(f"{case_id}: {message}")


def validate_submission_cases(cases_dir: Path = CASES_DIR) -> List[str]:
    """Return all validation errors; an empty list means complete parity."""
    expected_cases = {case["case_id"]: case for case in load_benchmark_cases()}
    expected_names = {f"{case_id}.json" for case_id in expected_cases}
    actual_paths = sorted(cases_dir.glob("*.json")) if cases_dir.exists() else []
    actual_names = {path.name for path in actual_paths}
    errors: List[str] = []

    if actual_names != expected_names:
        errors.append(f"case filenames differ; missing={sorted(expected_names - actual_names)}, extra={sorted(actual_names - expected_names)}")
    if len(actual_paths) != 20:
        errors.append(f"expected exactly 20 JSON files, found {len(actual_paths)}")

    results = load_authoritative_results()
    for case_id, case in expected_cases.items():
        path = cases_dir / f"{case_id}.json"
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                record: Dict[str, Any] = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            _error(errors, case_id, f"invalid JSON: {exc}")
            continue

        if set(record) != TOP_LEVEL_FIELDS:
            _error(errors, case_id, "top-level fields are missing, extra, or fabricated")
            continue
        if record["case_id"] != case_id:
            _error(errors, case_id, "case_id does not match filename")
        if record["case"] != {
            "trigger_type": case["trigger_type"], "trigger_text": case["trigger_text"],
            "opened_at": case["opened_at"], "customer_id": case["customer_id"],
            "card_id": case["card_id"], "flagged_txn_id": case["flagged_txn_id"],
            "initial_risk_score": case["risk_score"],
        }:
            _error(errors, case_id, "case identity differs from case_pack.csv")

        result = results.get(case_id)
        if result is None:
            _error(errors, case_id, "missing Phase 3 benchmark result")
            continue
        if record["findings"]["outcome"] not in ALLOWED_OUTCOMES:
            _error(errors, case_id, "outcome is invalid")
        comparisons = {
            "investigation.risk_level": (record["investigation"]["risk_level"], result["risk_level"]),
            "investigation.confidence": (record["investigation"]["confidence"], result["confidence"]),
            "investigation.uncertainty": (record["investigation"]["uncertainty"], result["uncertainty"]),
            "investigation.evidence_sufficient": (record["investigation"]["evidence_sufficient"], result["evidence_sufficient"]),
            "investigation.fraud_hypotheses": (record["investigation"]["fraud_hypotheses"], result["fraud_hypotheses"]),
            "investigation.missing_evidence": (record["investigation"]["missing_evidence"], result["missing_evidence"]),
            "evidence": (record["evidence"], result["evidence_gathered"]),
            "outcome": (record["findings"]["outcome"], result["outcome"]),
            "pattern": (record["findings"]["pattern"], result["pattern"]),
            "summary": (record["findings"]["summary"], result["explanation"]),
            "recommended_actions": (record["decisions"]["recommended_actions"], result["recommended_actions"]),
            "approval_route": (record["decisions"]["approval_route"], result["approval_route"]),
            "policy_decision": (record["decisions"]["policy_decision"], result["policy_decision"]),
            "rounds": (record["additional_evidence"]["rounds"], result["additional_evidence_rounds"]),
            "requests": (record["additional_evidence"]["requests"], result["additional_evidence_requested"]),
            "responses": (record["additional_evidence"]["responses"], result["additional_evidence_responses"]),
            "nba_before": (record["additional_evidence"]["nba_before"], result["nba_before"]),
            "nba_after": (record["additional_evidence"]["nba_after"], result["nba_after"]),
            "executed_actions": (record["execution"]["executed_actions"], result["executed_actions"]),
            "sar_required": (record["execution"]["sar_required"], result["sar_requirement"]),
            "written_to_graph": (record["memory"]["written_to_graph"], result["writeback_observed"]),
            "mcp_transport": (record["memory"]["mcp_transport"], result["mcp_transport"]),
            "transport_failures": (record["memory"]["transport_failures"], result["mcp_failures"]),
            "explanation.text": (record["explanation"]["text"], result["explanation"]),
            "explanation.citations": (record["explanation"]["citations"], result["evidence_citations"]),
            "reasoning_source": (record["metadata"]["reasoning_source"], result["reasoning_source"]),
        }
        for field, (actual, expected) in comparisons.items():
            if actual != expected:
                _error(errors, case_id, f"{field} differs from Phase 3 result")

        evidence_ids = {item.get("evidence_id") for item in record["evidence"]}
        if not all(item.get("provenance") for item in record["evidence"]):
            _error(errors, case_id, "evidence item missing provenance")
        if any(item.get("source") == "llm" for item in record["evidence"]):
            _error(errors, case_id, "LLM was represented as evidence provenance")
        if not all(citation in evidence_ids for citation in record["explanation"]["citations"]):
            _error(errors, case_id, "citation does not reference an evidence ID")
        if record["metadata"]["citation_validity"] is not True:
            _error(errors, case_id, "citation_validity must be true")
        if record["memory"]["graph_record_type"] != "InvestigationCase":
            _error(errors, case_id, "graph record type is invalid")
        if record["memory"]["written_to_graph"] and not record["memory"]["writeback_tool_calls"]:
            _error(errors, case_id, "writeback observed without MCP writeback call")

    return errors


def main() -> int:
    errors = validate_submission_cases()
    if errors:
        print("SUBMISSION VALIDATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("CASE FILE COUNT: 20")
    print("MISSING FILES: none")
    print("INVALID JSON: none")
    print("CASE ID MISMATCHES: none")
    print("CITATION ERRORS: none")
    print("POLICY DATA ERRORS: none")
    print("NBA DATA ERRORS: none")
    print("GRAPH WRITEBACK DATA ERRORS: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
