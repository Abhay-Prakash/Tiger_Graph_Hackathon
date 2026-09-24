"""
Deterministic policy evaluation engine.

Critical invariant:
    This module NEVER calls an LLM. Policy evaluation is fully deterministic
    given input facts. The LLM reads PolicyDecision objects; it does not
    create or modify them.

Policy source: fraud_investigation/config/policy_rules.json (hackathon-inferred-v1)
Derivation:    docs/POLICY_MODEL.md
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_POLICY_PATH = Path(__file__).parent.parent / "config" / "policy_rules.json"

# SAR threshold inferred from data: max unfiled confirmed_fraud exposure = USD 999.95
_SAR_EXPOSURE_THRESHOLD_USD = 1_000.0

# Patterns that always require SAR regardless of exposure (from data: undocumented = 9/9 filed)
_ALWAYS_SAR_PATTERNS = {"undocumented"}

# Threshold above which to escalate (high-value fraud)
_ESCALATION_THRESHOLD_USD = 5_000.0


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDecision:
    """
    Deterministic, immutable output of the policy engine.

    All fields are populated by the engine from policy_rules.json +
    the current investigation state facts.  No LLM involvement.

    Attributes
    ----------
    required_actions     : Actions that MUST be taken per inferred policy.
    permitted_actions    : Actions that are allowed but not mandatory.
    forbidden_actions    : Actions explicitly prohibited for this outcome.
    sar_required         : True if a SAR must be filed.
    approval_route       : "auto" | "analyst_review" | "escalation"
    policy_rules_applied : Rule IDs that were triggered (e.g. ["POL-001","POL-002"])
    reasoning            : Human-readable trace of which rules fired and why.
                           Suitable for inclusion in case findings.
    """
    required_actions:     tuple
    permitted_actions:    tuple
    forbidden_actions:    tuple
    sar_required:         bool
    approval_route:       str
    policy_rules_applied: tuple
    reasoning:            str

    def as_dict(self) -> dict:
        return {
            "required_actions":     list(self.required_actions),
            "permitted_actions":    list(self.permitted_actions),
            "forbidden_actions":    list(self.forbidden_actions),
            "sar_required":         self.sar_required,
            "approval_route":       self.approval_route,
            "policy_rules_applied": list(self.policy_rules_applied),
            "reasoning":            self.reasoning,
        }

    def all_recommended_actions(self) -> List[str]:
        """Required + permitted actions, deduped, in order."""
        seen = set()
        out = []
        for a in list(self.required_actions) + list(self.permitted_actions):
            if a not in seen:
                seen.add(a)
                out.append(a)
        return out


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """
    Deterministic policy evaluator for fraud investigation decisions.

    Usage
    -----
    engine = PolicyEngine()

    # Case closed as confirmed fraud, exposure = $1250, pattern = account_takeover
    decision = engine.evaluate(
        outcome="confirmed_fraud",
        pattern="account_takeover",
        exposure_usd=1250.00,
    )
    print(decision.required_actions)  # ('CREATE_CASE', 'BLOCK_CARD', 'FILE_REPORT')
    print(decision.sar_required)      # True

    # Cleared case
    decision = engine.evaluate(outcome="cleared")
    print(decision.required_actions)  # ('CREATE_CASE', 'VERIFY_WITH_CUSTOMER', 'CLOSE_NO_FRAUD')
    print(decision.forbidden_actions) # ('BLOCK_CARD', 'FILE_REPORT')
    """

    def __init__(self, policy_path: Path = _DEFAULT_POLICY_PATH) -> None:
        with open(policy_path, encoding="utf-8") as f:
            self._policy = json.load(f)
        self._rules = {r["rule_id"]: r for r in self._policy["rules"]}
        logger.info(
            "PolicyEngine loaded version=%s from %s",
            self._policy["_meta"]["version"],
            policy_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        return self._policy["_meta"]["version"]

    def evaluate(
        self,
        outcome:       Optional[str]  = None,   # "confirmed_fraud" | "cleared" | None
        pattern:       Optional[str]  = None,   # fraud pattern label
        exposure_usd:  float          = 0.0,
        trigger_type:  str            = "risk_score",
    ) -> PolicyDecision:
        """
        Evaluate policy given the current investigation state.

        Parameters
        ----------
        outcome      : Final case outcome; None means investigation still pending.
        pattern      : Fraud pattern if identified (e.g. "account_takeover").
        exposure_usd : Total confirmed USD exposure.
        trigger_type : What triggered the case ("risk_score"|"customer_report"|"analyst_request").

        Returns
        -------
        PolicyDecision  — fully deterministic, no LLM involved.
        """
        required_actions:     List[str] = []
        permitted_actions:    List[str] = []
        forbidden_actions:    List[str] = []
        rules_applied:        List[str] = []
        reasoning_lines:      List[str] = []

        # ---- POL-001: Case creation is always mandatory ----
        required_actions.append("CREATE_CASE")
        rules_applied.append("POL-001")
        reasoning_lines.append(
            f"POL-001: trigger_type={trigger_type!r} → CREATE_CASE required"
        )

        # ---- Pending (outcome not yet determined) ----
        if outcome is None:
            permitted_actions.append("VERIFY_WITH_CUSTOMER")
            sar_required = False
            approval_route = "analyst_review"
            reasoning_lines.append("Outcome pending — investigation in progress.")

        # ---- Confirmed fraud ----
        elif outcome == "confirmed_fraud":
            # POL-002: Block card is mandatory
            required_actions.append("BLOCK_CARD")
            rules_applied.append("POL-002")
            reasoning_lines.append("POL-002: confirmed_fraud → BLOCK_CARD mandatory")

            # POL-003: SAR filing
            sar_exposure = exposure_usd >= _SAR_EXPOSURE_THRESHOLD_USD
            sar_pattern  = (pattern or "") in _ALWAYS_SAR_PATTERNS
            sar_required = sar_exposure or sar_pattern

            if sar_required:
                required_actions.append("FILE_REPORT")
                rules_applied.append("POL-003")
                if sar_exposure:
                    reasoning_lines.append(
                        f"POL-003: exposure_usd={exposure_usd:.2f} >= "
                        f"{_SAR_EXPOSURE_THRESHOLD_USD:.0f} → FILE_REPORT mandatory"
                    )
                if sar_pattern:
                    reasoning_lines.append(
                        f"POL-003: pattern={pattern!r} always requires FILE_REPORT"
                    )
            else:
                reasoning_lines.append(
                    f"POL-003: exposure_usd={exposure_usd:.2f} < "
                    f"{_SAR_EXPOSURE_THRESHOLD_USD:.0f} and pattern={pattern!r} "
                    f"→ SAR not required"
                )

            # Forbidden on confirmed fraud
            forbidden_actions.append("CLOSE_NO_FRAUD")

            # Approval routing
            if exposure_usd >= _ESCALATION_THRESHOLD_USD or sar_pattern:
                approval_route = "escalation"
                reasoning_lines.append(
                    f"High exposure (≥${_ESCALATION_THRESHOLD_USD:,.0f}) "
                    f"or undocumented pattern → escalation"
                )
            else:
                approval_route = "auto"

        # ---- Cleared ----
        elif outcome == "cleared":
            # POL-004: Cleared protocol
            required_actions.extend(["VERIFY_WITH_CUSTOMER", "CLOSE_NO_FRAUD"])
            forbidden_actions.extend(["BLOCK_CARD", "FILE_REPORT"])
            rules_applied.append("POL-004")
            sar_required = False
            approval_route = "auto"
            reasoning_lines.append(
                "POL-004: cleared → VERIFY_WITH_CUSTOMER + CLOSE_NO_FRAUD; "
                "BLOCK_CARD and FILE_REPORT forbidden"
            )

        else:
            raise ValueError(
                f"Unknown outcome {outcome!r}. "
                "Expected: 'confirmed_fraud', 'cleared', or None (pending)."
            )

        return PolicyDecision(
            required_actions     = tuple(required_actions),
            permitted_actions    = tuple(permitted_actions),
            forbidden_actions    = tuple(forbidden_actions),
            sar_required         = sar_required,
            approval_route       = approval_route,
            policy_rules_applied = tuple(rules_applied),
            reasoning            = "\n".join(reasoning_lines),
        )

    def is_action_permitted(
        self,
        action:       str,
        outcome:      Optional[str],
        exposure_usd: float = 0.0,
        pattern:      Optional[str] = None,
    ) -> bool:
        """
        Convenience check: is this action permitted for the given outcome?
        Returns False if the action is in forbidden_actions.
        """
        decision = self.evaluate(
            outcome=outcome, exposure_usd=exposure_usd, pattern=pattern
        )
        if action in decision.forbidden_actions:
            return False
        return action in decision.required_actions or action in decision.permitted_actions

    def pattern_info(self, pattern: str) -> dict:
        """Retrieve statistical metadata about a known fraud pattern."""
        return self._policy.get("fraud_patterns", {}).get(pattern, {})

    def all_patterns(self) -> List[str]:
        """Return all known fraud pattern labels from policy data."""
        return list(self._policy.get("fraud_patterns", {}).keys())

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"PolicyEngine(version={self.version!r})"
