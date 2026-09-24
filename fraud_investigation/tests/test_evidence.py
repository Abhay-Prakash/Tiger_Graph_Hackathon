"""
Unit tests for Evidence dataclass and EvidenceLedger.
"""

import json
import pytest
from fraud_investigation.evidence.ledger import EvidenceLedger
from fraud_investigation.evidence.model import Evidence, EvidenceSource, EvidenceType, make_evidence


def test_evidence_immutability():
    ev = make_evidence(
        source=EvidenceSource.TRANSACTION_DATA,
        source_record_id="3514948",
        evidence_type=EvidenceType.TRANSACTION_CONTEXT,
        description="Test transaction context",
        observed_value={"amount": 111.92},
        provenance="transactions.csv:TransactionAmt",
    )
    assert ev.evidence_id.startswith("EVD-")
    with pytest.raises(Exception):
        ev.description = "Mutated"  # frozen dataclass


def test_evidence_idempotency_and_ledger():
    ledger = EvidenceLedger(case_id="HHG-007")
    ev1 = make_evidence(
        source=EvidenceSource.QUERY_REGION_ANOMALY,
        source_record_id="3514948",
        evidence_type=EvidenceType.REGION_SIGNAL,
        description="Region anomaly detected",
        observed_value={"addr1": 264.0},
        provenance="transactions.csv:addr1",
    )
    ev2 = make_evidence(
        source=EvidenceSource.QUERY_REGION_ANOMALY,
        source_record_id="3514948",
        evidence_type=EvidenceType.REGION_SIGNAL,
        description="Region anomaly detected",
        observed_value={"addr1": 264.0},
        provenance="transactions.csv:addr1",
    )

    # ev1 and ev2 generate the exact same evidence_id from deterministic attributes
    assert ev1.evidence_id == ev2.evidence_id

    added1 = ledger.add(ev1)
    added2 = ledger.add(ev2)

    assert added1 is True
    assert added2 is False  # duplicate skipped
    assert ledger.count == 1


def test_ledger_serialisation():
    ledger = EvidenceLedger(case_id="HHG-007")
    ev = make_evidence(
        source=EvidenceSource.QUERY_CASE_HISTORY,
        source_record_id="C09933",
        evidence_type=EvidenceType.PRIOR_CASE,
        description="Customer C09933 has 19 prior closed cases",
        observed_value={"cases": 19},
        provenance="closed_cases_history.csv:customer_id=C09933",
    )
    ledger.add(ev)

    json_str = ledger.to_json()
    ledger2 = EvidenceLedger.from_json("HHG-007", json_str)

    assert ledger2.count == 1
    assert ledger2.all[0].evidence_id == ev.evidence_id
    assert ledger2.all[0].description == ev.description
