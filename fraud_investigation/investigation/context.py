"""
Investigation Context Assembler.

Runs all 5 queries for a case, populates an EvidenceLedger, evaluates policy,
and packages the investigation bundle.
"""

import logging
from typing import Any, Dict, Optional
from ..evidence.ledger import EvidenceLedger
from ..evidence.model import EvidenceSource, EvidenceType, make_evidence
from ..policy.engine import PolicyEngine
from .queries import InvestigationQueries

logger = logging.getLogger(__name__)


class InvestigationContextAssembler:
    """
    Coordinates gathering evidence for a benchmark case.
    """

    def __init__(self, conn: Any, policy_engine: Optional[PolicyEngine] = None) -> None:
        self.queries = InvestigationQueries(conn)
        self.policy_engine = policy_engine or PolicyEngine()

    def assemble_case_investigation(
        self,
        case_id: str,
        customer_id: str,
        flagged_txn_id: str,
        trigger_type: str,
        trigger_text: str = "",
        initial_risk_score: float = 0.0,
        forced_outcome: Optional[str] = None,
        forced_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        ledger = EvidenceLedger(case_id=case_id)

        # 1. Trigger Evidence
        ledger.add(
            make_evidence(
                source=EvidenceSource.BENCHMARK_CASE,
                source_record_id=case_id,
                evidence_type=EvidenceType.CUSTOMER_REPORT if trigger_type == "customer_report" else EvidenceType.MODEL_SCORE,
                description=f"Case {case_id} triggered by {trigger_type}: '{trigger_text}'",
                observed_value={"trigger_type": trigger_type, "trigger_text": trigger_text, "initial_risk_score": initial_risk_score},
                provenance=f"case_pack.csv:case_id={case_id}",
                supports="customer_dispute" if trigger_type == "customer_report" else "high_risk_flag",
                confidence=0.9,
            )
        )

        # 2. Run Query 01 — Transaction Context
        q1_res = self.queries.get_transaction_context(flagged_txn_id)
        ledger.add_all(self.queries.extract_context_evidence(q1_res, flagged_txn_id))

        # 3. Run Query 02 — Customer Case History
        q2_res = self.queries.get_customer_case_history(customer_id)
        ledger.add_all(self.queries.extract_history_evidence(q2_res, customer_id))

        # 4. Run Query 03 — Region Anomaly
        q3_res = self.queries.detect_region_anomaly(customer_id, flagged_txn_id)
        ledger.add_all(self.queries.extract_region_evidence(q3_res, flagged_txn_id))

        # 5. Run Query 04 — Shared Device
        q4_res = self.queries.detect_shared_device(flagged_txn_id)
        ledger.add_all(self.queries.extract_device_evidence(q4_res, flagged_txn_id))

        # 6. Run Query 05 — Velocity Burst
        q5_res = self.queries.detect_velocity_burst(customer_id, flagged_txn_id)
        ledger.add_all(self.queries.extract_velocity_evidence(q5_res, flagged_txn_id))

        # 7. Evaluate Evidence & Determine Outcome/Pattern if not forced
        summary = ledger.summary()
        top_hyp = summary.get("top_hypothesis", "none")

        outcome = forced_outcome
        pattern = forced_pattern
        exposure_usd = 0.0

        flagged_txn_data = q1_res.get("FlaggedTxn", []) if isinstance(q1_res, dict) else []
        if flagged_txn_data:
            exposure_usd = flagged_txn_data[0].get("attributes", {}).get("amount", 0.0)

        if outcome is None:
            # Deterministic assessment logic for manual walkthrough / evaluation
            if top_hyp != "none" and top_hyp != "unknown":
                outcome = "confirmed_fraud"
                pattern = top_hyp
            elif initial_risk_score >= 0.70 or trigger_type == "customer_report":
                outcome = "confirmed_fraud"
                pattern = "out_of_region_use" if q3_res.get("is_anomalous") else "card_not_present_fraud"
            else:
                outcome = "cleared"
                pattern = "none"
                exposure_usd = 0.0

        # 8. Deterministic Policy Evaluation
        policy_decision = self.policy_engine.evaluate(
            outcome=outcome,
            pattern=pattern,
            exposure_usd=exposure_usd,
            trigger_type=trigger_type,
        )

        return {
            "case_id": case_id,
            "customer_id": customer_id,
            "flagged_txn_id": flagged_txn_id,
            "trigger_type": trigger_type,
            "trigger_text": trigger_text,
            "initial_risk_score": initial_risk_score,
            "outcome": outcome,
            "pattern": pattern,
            "exposure_usd": exposure_usd,
            "evidence_ledger": ledger,
            "policy_decision": policy_decision.as_dict(),
            "query_results": {
                "q1_context": q1_res,
                "q2_history": q2_res,
                "q3_region": q3_res,
                "q4_device": q4_res,
                "q5_velocity": q5_res,
            },
        }
