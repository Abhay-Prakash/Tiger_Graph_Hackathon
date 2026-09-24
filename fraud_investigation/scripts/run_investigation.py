"""
Script to execute the reference investigation for HHG-007 (or any benchmark case)
and output the complete evidence ledger, policy decision, and findings bundle.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fraud_investigation.ingestion.loader import GRAPH_NAME
from fraud_investigation.investigation.context import InvestigationContextAssembler
from fraud_investigation.policy.engine import PolicyEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reference fraud investigation.")
    parser.add_argument("--case-id", type=str, default="HHG-007", help="Benchmark case ID (default: HHG-007).")
    parser.add_argument("--case-pack", type=str, default="dataset/case_pack.csv", help="Path to case_pack.csv.")
    parser.add_argument("--host", type=str, default=os.getenv("TG_HOST", "http://127.0.0.1"), help="TigerGraph host URL.")
    parser.add_argument("--username", type=str, default=os.getenv("TG_USERNAME", "tigergraph"), help="TigerGraph username.")
    parser.add_argument("--password", type=str, default=os.getenv("TG_PASSWORD", "tigergraph"), help="TigerGraph password.")
    parser.add_argument("--mock", action="store_true", help="Run in mock offline mode using local dataset files.")

    args = parser.parse_args()

    # Find case in case_pack
    import csv
    case_row = None
    with open(args.case_pack, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["case_id"] == args.case_id:
                case_row = row
                break

    if not case_row:
        print(f"Error: case {args.case_id} not found in {args.case_pack}")
        sys.exit(1)

    print(f"=== HHGOA Reference Investigation: {args.case_id} ===")
    print(f"Trigger: {case_row['trigger_type']} ('{case_row['trigger_text']}')")
    print(f"Customer: {case_row['customer_id']} | Card: {case_row['card_id']} | Flagged TXN: {case_row['flagged_txn_id']}")

    if args.mock:
        print("\n[Mock Mode] Assembling investigation from local CSV dataset...")
        # Create mock connection or offline context
        from fraud_investigation.tests.mock_investigation import run_mock_investigation
        res = run_mock_investigation(args.case_id, case_row, Path("dataset"))
    else:
        try:
            import pyTigerGraph as tg
            conn = tg.TigerGraphConnection(
                host=args.host,
                username=args.username,
                password=args.password,
                graphname=GRAPH_NAME,
            )
            assembler = InvestigationContextAssembler(conn)
            res = assembler.assemble_case_investigation(
                case_id=case_row["case_id"],
                customer_id=case_row["customer_id"],
                flagged_txn_id=case_row["flagged_txn_id"],
                trigger_type=case_row["trigger_type"],
                trigger_text=case_row["trigger_text"],
                initial_risk_score=float(case_row["risk_score"] or 0.0),
            )
        except Exception as e:
            print(f"Live TigerGraph connection failed ({e}). Falling back to mock offline mode...")
            from fraud_investigation.tests.mock_investigation import run_mock_investigation
            res = run_mock_investigation(args.case_id, case_row, Path("dataset"))

    print("\n--- Evidence Ledger ---")
    ledger = res["evidence_ledger"]
    for ev in ledger.all:
        print(f"[{ev.evidence_id}] ({ev.evidence_type.value}) {ev.description}")
        print(f"    Source: {ev.provenance} | Supports: {ev.supports} | Confidence: {ev.confidence}")

    print("\n--- Policy Evaluation ---")
    policy = res["policy_decision"]
    print(f"Required Actions: {policy['required_actions']}")
    print(f"Permitted Actions: {policy['permitted_actions']}")
    print(f"Forbidden Actions: {policy['forbidden_actions']}")
    print(f"SAR Required:      {policy['sar_required']}")
    print(f"Approval Route:    {policy['approval_route']}")
    print(f"Rules Applied:     {policy['policy_rules_applied']}")

    print("\n--- Investigation Decision ---")
    print(f"Outcome:       {res['outcome']}")
    print(f"Pattern:       {res['pattern']}")
    print(f"Exposure USD:  ${res['exposure_usd']:.2f}")


if __name__ == "__main__":
    main()
