"""
Offline mock investigation runner for local testing and CI/CD without live TigerGraph instance.
"""

import csv
from pathlib import Path
from typing import Any, Dict
from ..evidence.ledger import EvidenceLedger
from ..evidence.model import EvidenceSource, EvidenceType, make_evidence
from ..policy.engine import PolicyEngine


def run_mock_investigation(case_id: str, case_row: dict, dataset_dir: Path) -> Dict[str, Any]:
    ledger = EvidenceLedger(case_id=case_id)
    cid = case_row["customer_id"]
    flagged_txn_id = case_row["flagged_txn_id"]
    trigger_type = case_row["trigger_type"]
    trigger_text = case_row["trigger_text"]
    risk_score = float(case_row.get("risk_score") or 0.0)

    # 1. Trigger Evidence
    ledger.add(
        make_evidence(
            source=EvidenceSource.BENCHMARK_CASE,
            source_record_id=case_id,
            evidence_type=EvidenceType.CUSTOMER_REPORT if trigger_type == "customer_report" else EvidenceType.MODEL_SCORE,
            description=f"Case {case_id} triggered by {trigger_type}: '{trigger_text}'",
            observed_value={"trigger_type": trigger_type, "risk_score": risk_score},
            provenance=f"case_pack.csv:case_id={case_id}",
            supports="high_risk_fraud" if risk_score >= 0.5 else "none",
            confidence=0.9,
        )
    )

    # 2. Parse transactions.csv for flagged txn and customer history
    flagged_txn = None
    cust_txns = []
    with open(dataset_dir / "transactions.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["customer_id"] == cid:
                cust_txns.append(row)
                if row["TransactionID"] == flagged_txn_id:
                    flagged_txn = row

    if flagged_txn:
        amt = float(flagged_txn["TransactionAmt"])
        ch = flagged_txn["channel"]
        addr1 = float(flagged_txn["addr1"] or -1.0)
        risk = float(flagged_txn["risk_score"] or 0.0)

        ledger.add(
            make_evidence(
                source=EvidenceSource.QUERY_TXN_CONTEXT,
                source_record_id=flagged_txn_id,
                evidence_type=EvidenceType.MODEL_SCORE,
                description=f"Transaction {flagged_txn_id} pre-computed ML risk score is {risk:.2f}.",
                observed_value={"risk_score": risk, "amount": amt, "channel": ch},
                provenance=f"transactions.csv:risk_score (txn={flagged_txn_id})",
                supports="high_risk_fraud" if risk >= 0.5 else "none",
                confidence=min(1.0, max(0.1, risk)),
            )
        )

        ledger.add(
            make_evidence(
                source=EvidenceSource.QUERY_TXN_CONTEXT,
                source_record_id=flagged_txn_id,
                evidence_type=EvidenceType.TRANSACTION_CONTEXT,
                description=f"Flagged transaction of ${amt:.2f} via {ch} channel at region code {addr1}.",
                observed_value={"amount": amt, "channel": ch, "addr1": addr1},
                provenance=f"transactions.csv:TransactionAmt,channel,addr1 (txn={flagged_txn_id})",
                confidence=0.9,
            )
        )

        # Region anomaly mock calculation
        past_addrs = [float(t["addr1"]) for t in cust_txns if t["TransactionID"] != flagged_txn_id and t["addr1"]]
        if past_addrs:
            from collections import Counter
            counts = Counter(past_addrs)
            home = counts.most_common(1)[0][0]
            if addr1 > 0 and home > 0 and addr1 != home:
                ledger.add(
                    make_evidence(
                        source=EvidenceSource.QUERY_REGION_ANOMALY,
                        source_record_id=flagged_txn_id,
                        evidence_type=EvidenceType.REGION_SIGNAL,
                        description=f"Out-of-region activity detected: flagged region {addr1} differs from customer home region {home}.",
                        observed_value={"flagged_addr1": addr1, "home_region": home},
                        provenance=f"transactions.csv:addr1 (txn={flagged_txn_id})",
                        supports="out_of_region_use",
                        confidence=0.85,
                    )
                )

    # 3. Parse closed_cases_history.csv
    prior_cases = []
    with open(dataset_dir / "closed_cases_history.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["customer_id"] == cid:
                prior_cases.append(row)

    if prior_cases:
        confirmed = sum(1 for c in prior_cases if c["outcome"] == "confirmed_fraud")
        tot_exp = sum(float(c["exposure_usd"]) for c in prior_cases if c["outcome"] == "confirmed_fraud")
        patterns = list(set(c["pattern"] for c in prior_cases))
        ledger.add(
            make_evidence(
                source=EvidenceSource.QUERY_CASE_HISTORY,
                source_record_id=cid,
                evidence_type=EvidenceType.PRIOR_CASE,
                description=f"Customer {cid} has {len(prior_cases)} prior closed cases ({confirmed} confirmed fraud, total exposure ${tot_exp:.2f}).",
                observed_value={"total_cases": len(prior_cases), "confirmed_fraud": confirmed, "patterns": patterns},
                provenance=f"closed_cases_history.csv:customer_id={cid}",
                supports="repeat_offender",
                confidence=0.95,
            )
        )

    # 4. Identity mock calculation
    device_info = None
    with open(dataset_dir / "identity.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["TransactionID"] == flagged_txn_id:
                device_info = row.get("DeviceInfo")
                break

    if device_info:
        ledger.add(
            make_evidence(
                source=EvidenceSource.QUERY_SHARED_DEVICE,
                source_record_id=flagged_txn_id,
                evidence_type=EvidenceType.DEVICE_SIGNAL,
                description=f"Device profile record found: '{device_info}'.",
                observed_value={"device_info": device_info},
                provenance=f"identity.csv:DeviceInfo (txn={flagged_txn_id})",
                confidence=0.8,
            )
        )

    # Outcome & Policy
    exposure_usd = float(flagged_txn["TransactionAmt"]) if flagged_txn else 0.0
    outcome = "confirmed_fraud" if (risk_score >= 0.5 or len(prior_cases) > 5) else "cleared"
    pattern = "out_of_region_use" if outcome == "confirmed_fraud" else "none"

    engine = PolicyEngine()
    policy_decision = engine.evaluate(outcome=outcome, pattern=pattern, exposure_usd=exposure_usd, trigger_type=trigger_type)

    return {
        "case_id": case_id,
        "customer_id": cid,
        "flagged_txn_id": flagged_txn_id,
        "trigger_type": trigger_type,
        "trigger_text": trigger_text,
        "initial_risk_score": risk_score,
        "outcome": outcome,
        "pattern": pattern,
        "exposure_usd": exposure_usd,
        "evidence_ledger": ledger,
        "policy_decision": policy_decision.as_dict(),
    }
