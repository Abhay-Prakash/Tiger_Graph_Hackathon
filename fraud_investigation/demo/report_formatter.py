"""
InvestigationReportFormatter - Phase 4 Demo.

Converts a final InvestigationState into a structured, section-organized
human-readable report string.

Design invariants:
- Presentation-only: does NOT re-run any workflow or recompute policy.
- Uses actual state field values; invents nothing.
- Clearly labels [LLM REASONING] vs [FALLBACK REASONING] from state field.
- Shows CONTRADICTION HANDLING section only when guardrail actually fired.
- Shows NBA section only when additional evidence loop actually ran.
- ASCII-safe output for cross-platform compatibility (Windows CMD/PowerShell).
"""

from typing import Any, Dict, List, Optional
from ..evidence.ledger import EvidenceLedger


SEPARATOR = "=" * 66
SUBSEP = "-" * 66


class InvestigationReportFormatter:
    """
    Converts InvestigationState -> structured human-readable report.

    Usage:
        formatter = InvestigationReportFormatter()
        report_text = formatter.format(final_state)
    """

    def format(self, state: Dict[str, Any]) -> str:
        """Return the full structured investigation report string."""
        sections = [
            self._header(state),
            self._section_case(state),
            self._section_evidence(state),
            self._section_reasoning(state),
            self._section_contradiction(state),
            self._section_nba(state),
            self._section_policy(state),
            self._section_outcome(state),
            self._section_explanation(state),
            SEPARATOR,
        ]
        return "\n".join(s for s in sections if s is not None)

    def _header(self, state: Dict[str, Any]) -> str:
        case_id = state.get("case_id", "UNKNOWN")
        return (
            "\n" + SEPARATOR + "\n"
            f"  HHGOA FRAUD INVESTIGATION AGENT - Case {case_id}\n"
            + SEPARATOR
        )

    def _section_case(self, state: Dict[str, Any]) -> str:
        trigger_type = state.get("trigger_type", "unknown")
        risk_score = state.get("initial_risk_score", 0.0)
        score_str = f" (Score: {risk_score:.2f})" if risk_score > 0 else ""
        lines = [
            "\n[CASE]",
            f"  Case ID:       {state.get('case_id', 'UNKNOWN')}",
            f"  Customer:      {state.get('customer_id', 'UNKNOWN')}",
            f"  Card:          {state.get('card_id', 'UNKNOWN')}",
            f"  Flagged TXN:   {state.get('flagged_txn_id', 'UNKNOWN')}",
            f"  Trigger:       {trigger_type}{score_str}",
            f"  Case Status:   {state.get('case_status', 'unknown')}",
            f"  Opened:        {state.get('opened_at', 'N/A')}",
        ]
        transport = self._extract_transport(state)
        lines.append(f"  MCP Transport: {transport}")
        return "\n".join(lines)

    def _extract_transport(self, state: Dict[str, Any]) -> str:
        try:
            ledger = EvidenceLedger.from_json(
                state.get("case_id", "UNKNOWN"),
                state.get("evidence_ledger_json", "[]"),
            )
            for ev in ledger.all:
                if "live_mcp" in ev.description:
                    return "live_mcp"
                if "mock_mcp" in ev.description:
                    return "mock_mcp"
        except Exception:
            pass
        return "mock_mcp (offline)"

    def _section_evidence(self, state: Dict[str, Any]) -> str:
        try:
            ledger = EvidenceLedger.from_json(
                state.get("case_id", "UNKNOWN"),
                state.get("evidence_ledger_json", "[]"),
            )
            items = ledger.all
        except Exception:
            items = []

        lines = [f"\n[GRAPH EVIDENCE]   ({len(items)} items in EvidenceLedger)"]
        if not items:
            lines.append("  (No evidence gathered - all MCP queries returned empty)")
        else:
            for ev in items:
                lines.append(f"  [{ev.evidence_id}]  ({ev.evidence_type.value})")
                lines.append(f"    {ev.description}")
                lines.append(f"    Provenance: {ev.provenance}")
                if ev.supports and ev.supports not in ("none", "", None):
                    lines.append(f"    Supports:   {ev.supports}")
                if ev.contradicts and ev.contradicts not in ("none", "", None):
                    lines.append(f"    Contradicts: {ev.contradicts}  <- GUARDRAIL SIGNAL")
                lines.append(f"    Confidence: {ev.confidence:.2f}")
        return "\n".join(lines)

    def _section_reasoning(self, state: Dict[str, Any]) -> str:
        source = state.get("reasoning_source", "deterministic_fallback")
        if source == "llm":
            source_label = "[LLM REASONING]   <- reasoning_source: llm (Gemini)"
        else:
            source_label = "[FALLBACK REASONING]   <- reasoning_source: deterministic_fallback"

        hypotheses = state.get("fraud_hypotheses", [])
        confidence = state.get("confidence", 0.0)
        uncertainty = state.get("uncertainty", 0.0)
        sufficient = state.get("evidence_sufficient", True)
        missing = state.get("missing_evidence", [])
        citations = state.get("evidence_citations", [])

        lines = [
            f"\n{source_label}",
            f"  Hypotheses:    {', '.join(hypotheses) if hypotheses else 'none'}",
            f"  Confidence:    {confidence:.2f}",
            f"  Uncertainty:   {uncertainty:.2f}",
            f"  Sufficient:    {'YES' if sufficient else 'NO'}",
        ]
        if missing:
            lines.append(f"  Missing:       {', '.join(missing)}")
        if citations:
            lines.append(f"  Citations:     {', '.join(citations)}")
        else:
            lines.append("  Citations:     (from explanation text - see GROUNDED EXPLANATION)")
        return "\n".join(lines)

    def _section_contradiction(self, state: Dict[str, Any]) -> Optional[str]:
        try:
            ledger = EvidenceLedger.from_json(
                state.get("case_id", "UNKNOWN"),
                state.get("evidence_ledger_json", "[]"),
            )
            region_contradictions = [
                ev for ev in ledger.all
                if ev.contradicts == "out_of_region_use"
            ]
        except Exception:
            region_contradictions = []

        hypotheses = state.get("fraud_hypotheses", [])
        if region_contradictions and "out_of_region_use" not in hypotheses:
            ev = region_contradictions[0]
            obs = ev.observed_value or {}
            flagged = obs.get("flagged_addr1", "?")
            home = obs.get("home_region", "?")
            is_anomalous = obs.get("is_anomalous", False)
            lines = [
                "\n[CONTRADICTION GUARDRAIL FIRED]",
                "  out_of_region_use SUPPRESSED",
                f"  Reason: region {flagged} == home_region {home}",
                f"          is_anomalous = {str(is_anomalous).lower()}",
                f"  Evidence: [{ev.evidence_id}]",
            ]
            return "\n".join(lines)
        return None

    def _section_nba(self, state: Dict[str, Any]) -> Optional[str]:
        rounds = state.get("additional_evidence_rounds", 0)
        nba_before = state.get("nba_before_additional_evidence")
        nba_after = state.get("nba_after_additional_evidence")

        if rounds == 0:
            return None

        requests = state.get("evidence_requests", [])
        req_type = requests[0].get("request_type", "VERIFY_WITH_CUSTOMER") if requests else "VERIFY_WITH_CUSTOMER"

        lines = [
            "\n[NEXT-BEST-ACTION]   (additional evidence loop ran)",
            f"  NBA Before:    {', '.join(nba_before) if nba_before else 'N/A'}",
            f"  Evidence Req:  {req_type}",
            f"  NBA After:     {', '.join(nba_after) if nba_after else 'N/A'}",
            f"  Loop Rounds:   {rounds} (max: 1)",
        ]
        return "\n".join(lines)

    def _section_policy(self, state: Dict[str, Any]) -> str:
        pol = state.get("policy_decision") or {}
        required = pol.get("required_actions", [])
        permitted = pol.get("permitted_actions", [])
        forbidden = pol.get("forbidden_actions", [])
        route = pol.get("approval_route", state.get("approval_route", "unknown"))
        sar = pol.get("sar_required", False)
        rules = pol.get("policy_rules_applied", [])
        reasoning = pol.get("reasoning", "")

        lines = [
            "\n[POLICY DECISION]   (hackathon-inferred-v1 - deterministic authority)",
            f"  Required:      {', '.join(required) if required else 'none'}",
            f"  Permitted:     {', '.join(permitted) if permitted else 'none'}",
            f"  Forbidden:     {', '.join(forbidden) if forbidden else 'none'}",
            f"  Approval:      {route}",
            f"  SAR Required:  {'YES' if sar else 'NO'}",
        ]
        if rules:
            lines.append(f"  Rules Applied: {', '.join(rules)}")
        if reasoning:
            for rline in reasoning.split("\n"):
                if rline.strip():
                    lines.append(f"    {rline}")
        return "\n".join(lines)

    def _section_outcome(self, state: Dict[str, Any]) -> str:
        outcome = state.get("outcome", "unknown")
        pattern = state.get("pattern", "none")
        executed = state.get("executed_actions", [])
        exposure = state.get("exposure_usd", 0.0)

        lines = [
            "\n[FINAL OUTCOME]",
            f"  Outcome:       {outcome}",
            f"  Pattern:       {pattern}",
            f"  Exposure USD:  ",
            "  Executed:",
        ]
        for action in executed:
            lines.append(f"    [x] {action}")
        if not executed:
            lines.append("    (none)")
        return "\n".join(lines)

    def _section_explanation(self, state: Dict[str, Any]) -> str:
        explanation = state.get("explanation", "")
        lines = ["\n[GROUNDED EXPLANATION]"]
        if explanation:
            for line in explanation.split("\n"):
                lines.append(f"  {line}" if line else "")
        else:
            lines.append("  (no explanation generated)")
        return "\n".join(lines)