"""
Python wrappers for running the 5 installed GSQL investigation queries
and normalizing their outputs into immutable Evidence objects.
"""

import logging
from typing import Any, Dict, List
from ..evidence.model import Evidence, EvidenceSource, EvidenceType, make_evidence

logger = logging.getLogger(__name__)


class InvestigationQueries:
    """
    Executes GSQL queries on TigerGraph via pyTigerGraph connection
    and returns raw query results or Evidence lists.
    """

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # 01. get_transaction_context
    # ------------------------------------------------------------------
    def get_transaction_context(self, flagged_txn_id: str, lookback_days: int = 30) -> Dict[str, Any]:
        params = {"flagged_txn_id": flagged_txn_id, "lookback_days": lookback_days}
        res = self.conn.runInstalledQuery("get_transaction_context", params)
        if isinstance(res, list):
            res_data = {}
            for item in res:
                if isinstance(item, dict):
                    res_data.update(item)
            return res_data
        return res

    def extract_context_evidence(self, query_res: Dict[str, Any], flagged_txn_id: str) -> List[Evidence]:
        evidence = []
        flagged_txn = query_res.get("FlaggedTxn", [])
        if flagged_txn:
            t = flagged_txn[0].get("attributes", {})
            amt = t.get("amount", 0.0)
            ch = t.get("channel", "")
            risk = t.get("risk_score", 0.0)
            addr1 = t.get("addr1", -1.0)
            
            # Model score evidence
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_TXN_CONTEXT,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.MODEL_SCORE,
                    description=f"Transaction {flagged_txn_id} pre-computed ML risk score is {risk:.2f}.",
                    observed_value={"risk_score": risk, "amount": amt, "channel": ch},
                    provenance=f"transactions.csv:risk_score (txn={flagged_txn_id})",
                    supports="high_risk_fraud" if risk >= 0.5 else "none",
                    contradicts="high_risk_fraud" if risk < 0.3 else "none",
                    confidence=min(1.0, max(0.1, risk)),
                )
            )

            # Transaction context evidence
            evidence.append(
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

        return evidence

    # ------------------------------------------------------------------
    # 02. get_customer_case_history
    # ------------------------------------------------------------------
    def get_customer_case_history(self, customer_id: str) -> Dict[str, Any]:
        params = {"customer_id": customer_id}
        res = self.conn.runInstalledQuery("get_customer_case_history", params)
        if isinstance(res, list):
            res_data = {}
            for item in res:
                if isinstance(item, dict):
                    res_data.update(item)
            return res_data
        return res

    def extract_history_evidence(self, query_res: Dict[str, Any], customer_id: str) -> List[Evidence]:
        evidence = []
        cases = query_res.get("cases", [])
        confirmed_count = query_res.get("confirmed_fraud_count", 0)
        total_exp = query_res.get("total_historical_exposure_usd", 0.0)
        patterns = query_res.get("distinct_patterns_seen", [])

        if cases:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_CASE_HISTORY,
                    source_record_id=customer_id,
                    evidence_type=EvidenceType.PRIOR_CASE,
                    description=f"Customer {customer_id} has {len(cases)} prior closed cases ({confirmed_count} confirmed fraud, total exposure ${total_exp:.2f}).",
                    observed_value={
                        "total_cases": len(cases),
                        "confirmed_fraud_count": confirmed_count,
                        "total_exposure_usd": total_exp,
                        "patterns": patterns,
                    },
                    provenance=f"closed_cases_history.csv:customer_id={customer_id}",
                    supports="account_takeover" if "account_takeover" in patterns else "repeat_offender",
                    confidence=0.95 if confirmed_count > 0 else 0.5,
                )
            )
        else:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_CASE_HISTORY,
                    source_record_id=customer_id,
                    evidence_type=EvidenceType.PRIOR_CASE,
                    description=f"Customer {customer_id} has no prior historical closed cases.",
                    observed_value={"total_cases": 0},
                    provenance=f"closed_cases_history.csv:customer_id={customer_id}",
                    confidence=0.9,
                )
            )

        return evidence

    # ------------------------------------------------------------------
    # 03. detect_region_anomaly
    # ------------------------------------------------------------------
    def detect_region_anomaly(self, customer_id: str, flagged_txn_id: str) -> Dict[str, Any]:
        params = {"customer_id": customer_id, "flagged_txn_id": flagged_txn_id}
        res = self.conn.runInstalledQuery("detect_region_anomaly", params)
        if isinstance(res, list):
            res_data = {}
            for item in res:
                if isinstance(item, dict):
                    res_data.update(item)
            return res_data
        return res

    def extract_region_evidence(self, query_res: Dict[str, Any], flagged_txn_id: str) -> List[Evidence]:
        evidence = []
        is_anomalous = query_res.get("is_anomalous", False)
        flagged_addr1 = query_res.get("flagged_addr1", -1.0)
        home_region = query_res.get("home_region", -1.0)

        if is_anomalous:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_REGION_ANOMALY,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.REGION_SIGNAL,
                    description=f"Out-of-region activity detected: flagged region {flagged_addr1} differs from customer primary home region {home_region}.",
                    observed_value={"flagged_addr1": flagged_addr1, "home_region": home_region},
                    provenance=f"transactions.csv:addr1 (txn={flagged_txn_id})",
                    supports="out_of_region_use",
                    confidence=0.85,
                )
            )
        else:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_REGION_ANOMALY,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.REGION_SIGNAL,
                    description=f"Transaction region {flagged_addr1} matches customer primary home region {home_region}.",
                    observed_value={"flagged_addr1": flagged_addr1, "home_region": home_region},
                    provenance=f"transactions.csv:addr1 (txn={flagged_txn_id})",
                    contradicts="out_of_region_use",
                    confidence=0.8,
                )
            )

        return evidence

    # ------------------------------------------------------------------
    # 04. detect_shared_device
    # ------------------------------------------------------------------
    def detect_shared_device(self, flagged_txn_id: str) -> Dict[str, Any]:
        params = {"flagged_txn_id": flagged_txn_id}
        res = self.conn.runInstalledQuery("detect_shared_device", params)
        if isinstance(res, list):
            res_data = {}
            for item in res:
                if isinstance(item, dict):
                    res_data.update(item)
            return res_data
        return res

    def extract_device_evidence(self, query_res: Dict[str, Any], flagged_txn_id: str) -> List[Evidence]:
        evidence = []
        has_device = query_res.get("has_device", False)
        shared_cust_count = query_res.get("shared_customer_count", 0)
        shared_txn_count = query_res.get("shared_transaction_count", 0)
        device_info = query_res.get("device_info", "")

        if has_device:
            if shared_cust_count > 0:
                evidence.append(
                    make_evidence(
                        source=EvidenceSource.QUERY_SHARED_DEVICE,
                        source_record_id=flagged_txn_id,
                        evidence_type=EvidenceType.DEVICE_SIGNAL,
                        description=f"Device ring detected: device '{device_info}' is shared across {shared_cust_count} other customers ({shared_txn_count} transactions).",
                        observed_value={
                            "device_info": device_info,
                            "shared_customers": shared_cust_count,
                            "shared_txns": shared_txn_count,
                        },
                        provenance=f"identity.csv:DeviceInfo (txn={flagged_txn_id})",
                        supports="card_not_present_new_device",
                        confidence=0.9,
                    )
                )
            else:
                evidence.append(
                    make_evidence(
                        source=EvidenceSource.QUERY_SHARED_DEVICE,
                        source_record_id=flagged_txn_id,
                        evidence_type=EvidenceType.DEVICE_SIGNAL,
                        description=f"Device record exists ('{device_info}'), no multi-customer device sharing detected.",
                        observed_value={"device_info": device_info},
                        provenance=f"identity.csv:DeviceInfo (txn={flagged_txn_id})",
                        confidence=0.7,
                    )
                )
        else:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_SHARED_DEVICE,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.DEVICE_SIGNAL,
                    description=f"No identity/device record available for transaction {flagged_txn_id}.",
                    observed_value={"has_device": False},
                    provenance=f"identity.csv (txn={flagged_txn_id})",
                    confidence=0.5,
                )
            )

        return evidence

    # ------------------------------------------------------------------
    # 05. detect_velocity_burst
    # ------------------------------------------------------------------
    def detect_velocity_burst(self, customer_id: str, flagged_txn_id: str, window_hours: int = 24) -> Dict[str, Any]:
        params = {"customer_id": customer_id, "flagged_txn_id": flagged_txn_id, "window_hours": window_hours}
        res = self.conn.runInstalledQuery("detect_velocity_burst", params)
        if isinstance(res, list):
            res_data = {}
            for item in res:
                if isinstance(item, dict):
                    res_data.update(item)
            return res_data
        return res

    def extract_velocity_evidence(self, query_res: Dict[str, Any], flagged_txn_id: str) -> List[Evidence]:
        evidence = []
        burst = query_res.get("has_velocity_burst", False)
        cnt = query_res.get("txn_count_in_window", 0)
        amt = query_res.get("total_amount_in_window", 0.0)
        d1_zero = query_res.get("has_same_day_d1", False)

        if burst:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_VELOCITY,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.VELOCITY_SIGNAL,
                    description=f"High velocity burst: {cnt} transactions totaling ${amt:.2f} within {query_res.get('window_hours', 24)}h window.",
                    observed_value={"txn_count": cnt, "total_amount": amt, "has_same_day_d1": d1_zero},
                    provenance=f"transactions.csv:ts,C2,D1 (txn={flagged_txn_id})",
                    supports="card_testing",
                    confidence=0.85,
                )
            )
        elif d1_zero:
            evidence.append(
                make_evidence(
                    source=EvidenceSource.QUERY_VELOCITY,
                    source_record_id=flagged_txn_id,
                    evidence_type=EvidenceType.VELOCITY_SIGNAL,
                    description=f"Same-day card activity detected (D1=0.0) with {cnt} transactions.",
                    observed_value={"txn_count": cnt, "has_same_day_d1": True},
                    provenance=f"transactions.csv:D1 (txn={flagged_txn_id})",
                    confidence=0.6,
                )
            )

        return evidence
