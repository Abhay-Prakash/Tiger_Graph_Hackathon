"""
Evidence model for the HHGOA Fraud Investigation system.

Core invariant:
    CLAIM → EVIDENCE → SOURCE (data field or named query)

The LLM may synthesize and reason over Evidence objects.
The LLM NEVER creates, modifies, or authors Evidence objects.
Provenance always points to a dataset file+field or named GSQL query.

Source of truth: docs/EVIDENCE_MODEL.md
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EvidenceSource(str, Enum):
    """The originating system that produced this evidence piece."""
    TRANSACTION_DATA     = "transaction_data"                # transactions.csv
    IDENTITY_DATA        = "identity_data"                   # identity.csv
    CASE_HISTORY         = "case_history"                    # closed_cases_history.csv
    BENCHMARK_CASE       = "benchmark_case"                  # case_pack.csv
    QUERY_TXN_CONTEXT    = "query_get_transaction_context"   # GSQL query 01
    QUERY_CASE_HISTORY   = "query_get_customer_case_history" # GSQL query 02
    QUERY_REGION_ANOMALY = "query_detect_region_anomaly"     # GSQL query 03
    QUERY_SHARED_DEVICE  = "query_detect_shared_device"      # GSQL query 04
    QUERY_VELOCITY       = "query_detect_velocity_burst"     # GSQL query 05
    POLICY_ENGINE        = "policy_engine"                   # config/policy_rules.json


class EvidenceType(str, Enum):
    """Classification of what investigative dimension this evidence addresses."""
    TRANSACTION_CONTEXT  = "transaction_context"  # basic transaction details
    CUSTOMER_HISTORY     = "customer_history"     # customer baseline / prior behaviour
    PRIOR_CASE           = "prior_case"           # closed historical fraud case
    REGION_SIGNAL        = "region_signal"        # geographic / billing region analysis
    DEVICE_SIGNAL        = "device_signal"        # device or identity signal
    VELOCITY_SIGNAL      = "velocity_signal"      # transaction velocity or burst
    CUSTOMER_REPORT      = "customer_report"      # explicit customer dispute statement
    MODEL_SCORE          = "model_score"          # pre-computed ML risk score
    POLICY_CONSTRAINT    = "policy_constraint"    # deterministic policy rule evaluation


# ---------------------------------------------------------------------------
# Evidence dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """
    An immutable, provenance-carrying unit of investigation evidence.

    frozen=True enforces immutability: once created, evidence cannot change.
    The evidence_id is generated deterministically from content — identical
    evidence gathered twice produces the same ID, enabling deduplication.

    Fields
    ------
    source            : Which dataset or query produced this evidence.
    source_record_id  : The primary-key identifier in that source
                        (TransactionID, case_id, query name, etc.)
    evidence_type     : Investigative dimension this addresses.
    description       : One-sentence human-readable statement of the finding.
    observed_value    : The raw value retrieved from the data source.
    supports          : Fraud hypothesis this evidence supports, e.g.
                        "out_of_region_use", or "none".
    contradicts       : Fraud hypothesis this evidence contradicts, or "none".
    confidence        : How strongly this evidence contributes (0.0–1.0).
    timestamp         : UTC ISO-8601 string: when evidence was gathered.
    provenance        : Exact data path: "transactions.csv:addr1",
                        "closed_cases_history.csv:outcome", etc.
    evidence_id       : SHA-256–derived deterministic ID (auto-generated).
    """

    source:           EvidenceSource
    source_record_id: str
    evidence_type:    EvidenceType
    description:      str
    observed_value:   Any
    supports:         str
    contradicts:      str
    confidence:       float
    timestamp:        str
    provenance:       str
    evidence_id:      str = field(default="", compare=False)

    def __post_init__(self) -> None:
        # Validate confidence range
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be 0–1, got {self.confidence}")
        # Generate deterministic evidence_id if not supplied
        if not self.evidence_id:
            raw = "|".join([
                self.source.value,
                self.source_record_id,
                self.evidence_type.value,
                self.provenance,
            ])
            digest = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
            object.__setattr__(self, "evidence_id", f"EVD-{digest}")

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["evidence_type"] = self.evidence_type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        d = dict(d)
        d["source"] = EvidenceSource(d["source"])
        d["evidence_type"] = EvidenceType(d["evidence_type"])
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "Evidence":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def make_evidence(
    source:           EvidenceSource,
    source_record_id: str,
    evidence_type:    EvidenceType,
    description:      str,
    observed_value:   Any,
    provenance:       str,
    supports:         str = "none",
    contradicts:      str = "none",
    confidence:       float = 0.5,
) -> Evidence:
    """
    Convenience factory.  Sets timestamp to current UTC.

    Example
    -------
    >>> ev = make_evidence(
    ...     source=EvidenceSource.TRANSACTION_DATA,
    ...     source_record_id="3514948",
    ...     evidence_type=EvidenceType.TRANSACTION_CONTEXT,
    ...     description="Transaction in billing region 264.0 (customer home region).",
    ...     observed_value={"addr1": 264.0},
    ...     provenance="transactions.csv:addr1",
    ...     supports="none",
    ...     contradicts="out_of_region_use",
    ...     confidence=0.9,
    ... )
    """
    return Evidence(
        source=source,
        source_record_id=source_record_id,
        evidence_type=evidence_type,
        description=description,
        observed_value=observed_value,
        supports=supports,
        contradicts=contradicts,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provenance=provenance,
    )
