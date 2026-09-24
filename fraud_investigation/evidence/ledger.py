"""
Evidence ledger: ordered, append-only collection of Evidence objects for one case.

Invariants:
- Once added, evidence cannot be removed or modified (Evidence is frozen).
- Duplicate evidence_ids are silently skipped (idempotent append).
- Evidence is ordered by insertion order (investigation sequence).
- The ledger serialises to/from JSON for persistence in TigerGraph.
"""

import json
import logging
from typing import Dict, Iterable, List

from .model import Evidence, EvidenceSource, EvidenceType

logger = logging.getLogger(__name__)


class EvidenceLedger:
    """
    Append-only, indexed evidence store for a single investigation case.

    Usage
    -----
    ledger = EvidenceLedger(case_id="HHG-007")
    ledger.add(some_evidence)
    ledger.add_all(list_of_evidence)

    # Query
    region_evidence = ledger.by_type(EvidenceType.REGION_SIGNAL)
    fraud_support   = ledger.supporting("out_of_region_use")

    # Persist
    json_str = ledger.to_json()
    ledger2  = EvidenceLedger.from_json("HHG-007", json_str)
    """

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self._evidence: List[Evidence] = []
        self._id_index: Dict[str, int] = {}  # evidence_id → list index

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, evidence: Evidence) -> bool:
        """
        Append evidence.  Returns True if added, False if duplicate (skipped).
        Idempotent: adding the same evidence twice is safe.
        """
        if evidence.evidence_id in self._id_index:
            logger.debug("Skipping duplicate evidence %s", evidence.evidence_id)
            return False
        idx = len(self._evidence)
        self._evidence.append(evidence)
        self._id_index[evidence.evidence_id] = idx
        return True

    def add_all(self, evidence_list: Iterable[Evidence]) -> int:
        """Add a collection; return count of newly added items."""
        return sum(1 for e in evidence_list if self.add(e))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def all(self) -> List[Evidence]:
        return list(self._evidence)

    @property
    def count(self) -> int:
        return len(self._evidence)

    def by_type(self, evidence_type: EvidenceType) -> List[Evidence]:
        return [e for e in self._evidence if e.evidence_type == evidence_type]

    def by_source(self, source: EvidenceSource) -> List[Evidence]:
        return [e for e in self._evidence if e.source == source]

    def supporting(self, hypothesis: str) -> List[Evidence]:
        """Return evidence that supports the named fraud hypothesis."""
        return [e for e in self._evidence
                if e.supports and e.supports != "none" and hypothesis in e.supports]

    def contradicting(self, hypothesis: str) -> List[Evidence]:
        """Return evidence that contradicts the named fraud hypothesis."""
        return [e for e in self._evidence
                if e.contradicts and e.contradicts != "none"
                and hypothesis in e.contradicts]

    def get(self, evidence_id: str) -> Evidence:
        idx = self._id_index.get(evidence_id)
        if idx is None:
            raise KeyError(f"Evidence {evidence_id!r} not in ledger {self.case_id!r}")
        return self._evidence[idx]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self._evidence], default=str)

    @classmethod
    def from_json(cls, case_id: str, json_str: str) -> "EvidenceLedger":
        ledger = cls(case_id)
        for d in json.loads(json_str):
            ledger.add(Evidence.from_dict(d))
        return ledger

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """
        Structured summary of ledger contents.
        Used by the investigation context assembler.
        """
        hypothesis_support: Dict[str, int] = {}
        hypothesis_contradict: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}

        for e in self._evidence:
            # Type distribution
            t = e.evidence_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            # Support counts
            if e.supports and e.supports != "none":
                hypothesis_support[e.supports] = hypothesis_support.get(e.supports, 0) + 1
            # Contradiction counts
            if e.contradicts and e.contradicts != "none":
                hypothesis_contradict[e.contradicts] = (
                    hypothesis_contradict.get(e.contradicts, 0) + 1
                )

        # Strongest hypothesis (most supporting evidence)
        top_hypothesis = (
            max(hypothesis_support, key=hypothesis_support.get)
            if hypothesis_support else "unknown"
        )

        return {
            "case_id":            self.case_id,
            "total_evidence":     self.count,
            "by_type":            type_counts,
            "hypotheses_supported":   hypothesis_support,
            "hypotheses_contradicted": hypothesis_contradict,
            "top_hypothesis":     top_hypothesis,
        }

    def __repr__(self) -> str:
        return f"EvidenceLedger(case_id={self.case_id!r}, count={self.count})"
