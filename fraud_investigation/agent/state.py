"""
Canonical TypedDict InvestigationState for LangGraph Fraud Investigation Agent.

Source of truth: docs/INVESTIGATION_STATE.md
Maintains complete evidence ledger, provenance, policy decisions, audit trace, and reasoning_source tracking.
"""

from typing import Any, Dict, List, Optional, TypedDict


class InvestigationState(TypedDict, total=False):
    # Case Identification & Trigger Facts
    case_id: str                          # e.g. "HHG-007"
    customer_id: str                      # e.g. "C09933"
    card_id: str                          # e.g. "C09933-K2"
    flagged_txn_id: str                   # e.g. "3514948"
    trigger_type: str                     # "risk_score" | "customer_report" | "analyst_request"
    trigger_text: str                     # Human-readable trigger description
    initial_risk_score: float             # Pre-computed ML model score (0.0 if report/request)
    opened_at: str                        # Case open timestamp

    # Investigation Lifecycle Status
    case_status: str                      # "open" | "investigating" | "pending_evidence" | "closed_fraud" | "closed_cleared"

    # Evidence & Memory (Canonical evidence held in EvidenceLedger JSON format)
    evidence_ledger_json: str             # Serialized EvidenceLedger JSON
    gathered_evidence_summary: dict       # Summary stats of evidence ledger

    # Assessment & Reasoning
    fraud_hypotheses: List[str]           # Candidate patterns (e.g. ["out_of_region_use"])
    risk_level: str                       # "low" | "medium" | "high" | "critical"
    confidence: float                     # 0.0 - 1.0 confidence score
    uncertainty: float                    # 0.0 - 1.0 uncertainty score
    evidence_sufficient: bool             # Gate boolean for decision readiness
    missing_evidence: List[str]           # Specific evidence gaps identified
    reasoning_source: str                 # "llm" | "deterministic_fallback"
    evidence_citations: List[str]         # Evidence IDs cited by reasoner, e.g. ["EVD-XXXXX"]

    # Controlled Additional Evidence Loop (Bounded: MAX_ADDITIONAL_EVIDENCE_ROUNDS = 1)
    additional_evidence_rounds: int       # Loop counter
    evidence_requests: List[dict]         # Requests sent (e.g. VERIFY_WITH_CUSTOMER)
    evidence_responses: List[dict]        # Mocked/simulated responses received

    # Next Best Action (NBA) Tracking — Explicit separation required by brief
    nba_before_additional_evidence: Optional[List[str]] # NBA recommendation prior to round 1
    nba_after_additional_evidence: Optional[List[str]]  # NBA recommendation post round 1

    # Action Selection & Policy Gate
    recommended_actions: List[str]        # Actions proposed by agent reasoning
    policy_decision: Optional[dict]       # Deterministic result from PolicyEngine.evaluate()
    approval_route: str                   # "auto" | "analyst_review" | "escalation"
    executed_actions: List[str]           # Actions permitted & executed/simulated

    # Final Findings & Outcome
    outcome: Optional[str]                # "confirmed_fraud" | "cleared"
    pattern: str                          # Final assigned fraud pattern
    exposure_usd: float                   # Calculated USD exposure
    explanation: str                      # Grounded finding summary referencing Evidence IDs

    # Observability & Audit Trail
    decision_history: List[dict]          # Timestamped decision events
    agent_trace: List[str]                # Detailed execution step log
    mcp_protocol_trace: List[dict]        # initialize/tools-list/tools-call records
    graph_transport_failures: List[dict]  # Explicit unavailable/failed graph reads
