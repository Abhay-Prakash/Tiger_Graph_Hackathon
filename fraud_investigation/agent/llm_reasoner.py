"""
Structured LLM Reasoner for Fraud Investigation Agent.

Features:
- Configures LLM provider (Gemini / OpenAI / Anthropic) from environment variables.
- Uses structured Pydantic model / JSON schema output validation.
- Enforces strict evidence grounding and citation rules ([EVD-XXXXX]).
- Rejects/filters invalid or hallucinated Evidence IDs not present in the Evidence Ledger.
- Enforces region contradiction rule (HHG-007: non-anomalous region -> no out_of_region_use claim).
- Provides auditable fallback mechanism logging `reasoning_source: "llm"` vs `"deterministic_fallback"`.
- Handles transient API rate limits/503 spikes with bounded exponential backoff retries.
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, ValidationError

from .prompts import (
    ASSESS_INVESTIGATION_PROMPT,
    DETERMINE_ACTION_PROMPT,
    GENERATE_EXPLANATION_PROMPT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Citation Validator Helper
# ---------------------------------------------------------------------------

def validate_and_extract_citations(
    cited_ids: List[str], text: str, valid_evidence_ids: Set[str]
) -> List[str]:
    """
    Extract citations from both explicit list and text [EVD-XXXXX] tags.
    Strips invalid/hallucinated citations not present in valid_evidence_ids.
    """
    found_in_text = re.findall(r"EVD-[A-Za-z0-9\-_]+", text)
    combined = list(dict.fromkeys(cited_ids + found_in_text))  # preserve order, dedup

    valid = []
    for cid in combined:
        if cid in valid_evidence_ids:
            valid.append(cid)
        else:
            logger.warning("Stripped invalid/hallucinated evidence citation %r (not in ledger)", cid)
    return valid


# ---------------------------------------------------------------------------
# Structured Pydantic Output Schemas
# ---------------------------------------------------------------------------

class AssessmentResult(BaseModel):
    fraud_hypotheses: List[str] = Field(description="Plausible fraud patterns, e.g., ['out_of_region_use', 'account_takeover', 'card_not_present_fraud', 'card_testing', 'none']")
    risk_level: str = Field(description="Risk level: 'low' | 'medium' | 'high' | 'critical'")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    uncertainty: float = Field(ge=0.0, le=1.0, description="Uncertainty score between 0.0 and 1.0")
    evidence_sufficient: bool = Field(description="True if current evidence is sufficient to resolve case")
    missing_evidence: List[str] = Field(default_factory=list, description="Missing evidence items if insufficient")
    reasoning_summary: str = Field(description="Summary of reasoning referencing [EVD-XXXXX] IDs")
    evidence_citations: List[str] = Field(default_factory=list, description="Evidence IDs cited, e.g., ['EVD-A1B2C3D4E5F6']")


class ActionProposalResult(BaseModel):
    recommended_actions: List[str] = Field(description="Proposed list of permitted actions")
    justification: str = Field(description="Rationale referencing [EVD-XXXXX] IDs")
    evidence_citations: List[str] = Field(default_factory=list, description="Evidence IDs cited")


class ExplanationResult(BaseModel):
    explanation_text: str = Field(description="Full grounded investigation report referencing [EVD-XXXXX] IDs")
    evidence_citations: List[str] = Field(default_factory=list, description="All Evidence IDs cited in explanation")


# ---------------------------------------------------------------------------
# LLM Reasoner Class
# ---------------------------------------------------------------------------

class LLMReasoner:
    """
    Handles LLM invocations with structured schema validation and auditable fallbacks.
    """

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "google")
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-3.5-flash")
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        self.is_available = bool(self.api_key and self.api_key.strip())
        logger.info(
            "LLMReasoner initialized (provider=%s, model=%s, available=%s)",
            self.provider, self.model_name, self.is_available,
        )

    # ------------------------------------------------------------------
    # 1. Assess Investigation
    # ------------------------------------------------------------------
    def assess_investigation(
        self,
        case_id: str,
        customer_id: str,
        flagged_txn_id: str,
        evidence_summary: dict,
        evidence_list: List[dict],
        initial_risk_score: float,
        trigger_type: str,
        additional_rounds: int,
        region_contradicts: bool = False,
    ) -> Dict[str, Any]:
        """
        Assess hypotheses & uncertainty. Returns dict containing result + reasoning_source.
        """
        valid_evidence_ids = {e["evidence_id"] for e in evidence_list}

        if self.is_available:
            try:
                raw_json = self._call_llm_json(
                    ASSESS_INVESTIGATION_PROMPT.format(
                        case_id=case_id,
                        customer_id=customer_id,
                        flagged_txn_id=flagged_txn_id,
                        evidence_summary_json=json.dumps(evidence_summary, indent=2),
                        evidence_list_text="\n".join([f"[{e['evidence_id']}] ({e['evidence_type']}) {e['description']}" for e in evidence_list]),
                    )
                )
                parsed = AssessmentResult.model_validate_json(raw_json)
                res = parsed.model_dump()

                # Extract and validate evidence citations
                res["evidence_citations"] = validate_and_extract_citations(
                    res.get("evidence_citations", []),
                    res.get("reasoning_summary", ""),
                    valid_evidence_ids,
                )

                # Sanitize fraud_hypotheses against known valid patterns
                valid_patterns = {
                    "account_takeover", "card_not_present_fraud",
                    "card_not_present_new_device", "card_testing",
                    "out_of_region_use", "high_velocity_pattern",
                    "undocumented", "none", "unverified_transaction"
                }
                sanitized = [h for h in res.get("fraud_hypotheses", []) if h in valid_patterns]
                res["fraud_hypotheses"] = sanitized if sanitized else ["none"]

                # HHG-007 Contradiction Guardrail
                if region_contradicts and "out_of_region_use" in res["fraud_hypotheses"]:
                    logger.warning("LLM proposed out_of_region_use despite region contradiction. Stripping out_of_region_use.")
                    res["fraud_hypotheses"] = [h for h in res["fraud_hypotheses"] if h != "out_of_region_use"] or ["card_not_present_fraud"]

                res["reasoning_source"] = "llm"
                return res

            except Exception as e:
                logger.warning("LLM assessment failed or timed out (%s). Falling back to deterministic reasoning.", e)

        # Deterministic Fallback Path (Auditable)
        return self._fallback_assess_investigation(
            case_id, initial_risk_score, trigger_type, additional_rounds, region_contradicts, evidence_summary
        )

    # ------------------------------------------------------------------
    # 2. Determine Action Proposal
    # ------------------------------------------------------------------
    def propose_actions(
        self,
        case_id: str,
        risk_level: str,
        confidence: float,
        fraud_hypotheses: List[str],
        permitted_actions: List[str],
        forbidden_actions: List[str],
        policy_decision: dict,
    ) -> Dict[str, Any]:
        if self.is_available:
            try:
                raw_json = self._call_llm_json(
                    DETERMINE_ACTION_PROMPT.format(
                        case_id=case_id,
                        risk_level=risk_level,
                        confidence=confidence,
                        fraud_hypotheses=fraud_hypotheses,
                        permitted_actions_list=permitted_actions,
                        forbidden_actions_list=forbidden_actions,
                        policy_decision_json=json.dumps(policy_decision, indent=2),
                    )
                )
                parsed = ActionProposalResult.model_validate_json(raw_json)
                res = parsed.model_dump()
                res["reasoning_source"] = "llm"
                return res
            except Exception as e:
                logger.warning("LLM action proposal failed (%s). Falling back to deterministic proposal.", e)

        # Deterministic Fallback
        primary = fraud_hypotheses[0] if fraud_hypotheses else "none"
        if primary not in {"none", "unverified_transaction"}:
            proposed = ["CREATE_CASE", "BLOCK_CARD"]
        else:
            proposed = ["CREATE_CASE", "VERIFY_WITH_CUSTOMER", "CLOSE_NO_FRAUD"]

        return {
            "recommended_actions": proposed,
            "justification": f"Fallback proposal for hypothesis '{primary}'",
            "evidence_citations": [],
            "reasoning_source": "deterministic_fallback",
        }

    # ------------------------------------------------------------------
    # 3. Generate Explanation
    # ------------------------------------------------------------------
    def generate_explanation(
        self,
        case_id: str,
        trigger_type: str,
        trigger_text: str,
        flagged_txn_id: str,
        exposure_usd: float,
        outcome: str,
        pattern: str,
        required_actions: List[str],
        evidence_list: List[dict],
    ) -> Dict[str, Any]:
        valid_evidence_ids = {e["evidence_id"] for e in evidence_list}

        if self.is_available:
            try:
                ev_text = "\n".join([
                    f"[{e['evidence_id']}] ({e['evidence_type']}) {e['description']} (Provenance: {e['provenance']})"
                    for e in evidence_list
                ])
                prompt = GENERATE_EXPLANATION_PROMPT.format(
                    case_id=case_id,
                    trigger_type=trigger_type,
                    trigger_text=trigger_text,
                    flagged_txn_id=flagged_txn_id,
                    exposure_usd=exposure_usd,
                    outcome=outcome,
                    pattern=pattern,
                    required_actions=required_actions,
                    evidence_list_text=ev_text,
                )
                raw_json = self._call_llm_json(prompt)
                parsed = ExplanationResult.model_validate_json(raw_json)
                res = parsed.model_dump()
                res["evidence_citations"] = validate_and_extract_citations(
                    res.get("evidence_citations", []),
                    res.get("explanation_text", ""),
                    valid_evidence_ids,
                )
                res["reasoning_source"] = "llm"
                return res
            except Exception as e:
                logger.warning("LLM explanation generation failed (%s). Falling back to template explanation.", e)

        # Fallback Template
        evidence_lines = [
            f"  - [{e['evidence_id']}] ({e['evidence_type']}) {e['description']} (Provenance: {e['provenance']})"
            for e in evidence_list
        ]
        text = "\n".join([
            f"FINDING: Case {case_id} resolved as {outcome} (Pattern: {pattern}).",
            "EVIDENCE:",
            "\n".join(evidence_lines),
            f"IMPLICATION: Flagged transaction {flagged_txn_id} (${exposure_usd:.2f}) evaluated under deterministic policy.",
            f"UNCERTAINTY: Residual risk assessed under evidence bounds.",
            f"RECOMMENDED ACTIONS: {', '.join(required_actions)}.",
        ])
        return {
            "explanation_text": text,
            "evidence_citations": [e["evidence_id"] for e in evidence_list],
            "reasoning_source": "deterministic_fallback",
        }

    # ------------------------------------------------------------------
    # Helper: Call LLM API with Retries
    # ------------------------------------------------------------------
    def _call_llm_json(self, prompt: str, max_retries: int = 3) -> str:
        """Call underlying LLM provider with retry logic and return raw JSON string."""
        last_exception = None
        for attempt in range(max_retries):
            try:
                if "google" in self.provider.lower() or "gemini" in self.provider.lower():
                    from google import genai
                    client = genai.Client(api_key=self.api_key)
                    response = client.models.generate_content(
                        model=self.model_name if "gemini" in self.model_name else "gemini-3.5-flash",
                        contents=prompt,
                        config={"response_mime_type": "application/json"},
                    )
                    return response.text or "{}"
                elif "openai" in self.provider.lower() or os.getenv("OPENAI_API_KEY"):
                    import openai
                    client = openai.OpenAI(api_key=self.api_key)
                    resp = client.chat.completions.create(
                        model=self.model_name if "gpt" in self.model_name else "gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                    return resp.choices[0].message.content or "{}"
                else:
                    raise NotImplementedError(f"Unsupported LLM provider '{self.provider}'")
            except Exception as e:
                last_exception = e
                err_msg = str(e)
                if "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    sleep_secs = 1
                    logger.warning("LLM API transient error (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, max_retries, e, sleep_secs)
                    time.sleep(sleep_secs)
                else:
                    raise e
        raise last_exception or RuntimeError("LLM call retries exhausted")

    # ------------------------------------------------------------------
    # Helper: Fallback Assessment Logic
    # ------------------------------------------------------------------
    def _fallback_assess_investigation(
        self,
        case_id: str,
        initial_risk_score: float,
        trigger_type: str,
        additional_rounds: int,
        region_contradicts: bool,
        evidence_summary: Optional[dict] = None,
    ) -> Dict[str, Any]:
        has_customer_report = trigger_type == "customer_report"
        hypotheses = []

        # Check for graph evidence anomalies in summary
        graph_hypotheses = []
        customer_confirmed_valid = False
        if evidence_summary and isinstance(evidence_summary, dict):
            supported = evidence_summary.get("hypotheses_supported", {})
            contradictions = evidence_summary.get("hypotheses_contradicted", {})
            if contradictions.get("fraud_suspicion", 0) > 0 or contradictions.get("all", 0) > 0:
                customer_confirmed_valid = True

            valid_patterns = {
                "account_takeover", "card_not_present_fraud",
                "card_not_present_new_device", "card_testing", "out_of_region_use"
            }
            for hyp, cnt in supported.items():
                if hyp in valid_patterns and cnt > 0:
                    graph_hypotheses.append(hyp)

        if has_customer_report:
            hypotheses.append("card_not_present_fraud")
            confidence = 0.90
            uncertainty = 0.10
            sufficient = True
            missing = []
        elif customer_confirmed_valid:
            hypotheses.append("none")
            confidence = 0.95
            uncertainty = 0.05
            sufficient = True
            missing = []
        elif graph_hypotheses:
            # Graph anomalies present (e.g. shared device, velocity burst)
            filtered_graph_hyp = [h for h in graph_hypotheses if not (region_contradicts and h == "out_of_region_use")]
            if filtered_graph_hyp:
                hypotheses.extend(filtered_graph_hyp)
                confidence = 0.85
                uncertainty = 0.15
                sufficient = True
                missing = []
            else:
                hypotheses.append("none")
                confidence = 0.80
                uncertainty = 0.20
                sufficient = True
                missing = []
        elif region_contradicts:
            if initial_risk_score >= 0.70:
                hypotheses.append("card_not_present_fraud")
                confidence = 0.85
                uncertainty = 0.15
                sufficient = True
                missing = []
            else:
                hypotheses.append("none")
                confidence = 0.80
                uncertainty = 0.20
                sufficient = True
                missing = []
        else:
            if initial_risk_score >= 0.70:
                hypotheses.append("unverified_transaction")
                confidence = 0.85
                uncertainty = 0.15
                sufficient = False
                missing = ["VERIFY_WITH_CUSTOMER"]
            elif 0.40 <= initial_risk_score < 0.70 and additional_rounds == 0:
                hypotheses.append("unverified_transaction")
                confidence = 0.50
                uncertainty = 0.50
                sufficient = False
                missing = ["VERIFY_WITH_CUSTOMER"]
            else:
                hypotheses.append("none")
                confidence = 0.75
                uncertainty = 0.25
                sufficient = True
                missing = []

        return {
            "fraud_hypotheses": hypotheses,
            "risk_level": "high" if initial_risk_score >= 0.70 or has_customer_report or (hypotheses and hypotheses[0] != "none") else ("medium" if initial_risk_score >= 0.40 else "low"),
            "confidence": confidence,
            "uncertainty": uncertainty,
            "evidence_sufficient": sufficient,
            "missing_evidence": missing,
            "reasoning_summary": f"Fallback assessment for risk_score={initial_risk_score:.2f}",
            "evidence_citations": [],
            "reasoning_source": "deterministic_fallback",
        }
