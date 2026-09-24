"""
Trace Renderer - Phase 4 Demo.

Maps agent_trace entries (from InvestigationState) to labeled,
human-readable output sections for the hackathon demo.

Design invariants:
- Presentation-only: does NOT modify agent_trace semantics.
- Does NOT fabricate trace entries for absent nodes.
- Derives reasoning label from actual state["reasoning_source"].
"""

import re
from typing import Any, Dict, List


_NODE_LABELS = {
    "initialize_case":             "[CASE INITIALIZATION]",
    "gather_initial_evidence":     "[MCP TOOL CALL]",
    "retrieve_case_memory":        "[MCP TOOL CALL]",
    "build_evidence_ledger":       "[EVIDENCE LEDGER]",
    "assess_investigation":        None,
    "identify_missing_evidence":   "[EVIDENCE GAP IDENTIFIED]",
    "request_additional_evidence": "[CONTROLLED EVIDENCE REQUEST]",
    "incorporate_response":        "[EVIDENCE INCORPORATED]",
    "reassess_investigation":      "[REASSESSMENT]",
    "determine_next_action":       "[NBA PROPOSAL]",
    "policy_gate":                 "[POLICY DECISION]",
    "approval_gate":               "[APPROVAL ROUTING]",
    "execute_or_simulate":         "[ACTION EXECUTED]",
    "write_case_memory":           "[CASE MEMORY]",
    "generate_explanation":        "[GROUNDED EXPLANATION]",
}


def render_trace(state: Dict[str, Any]) -> str:
    """
    Render the agent_trace list into a labeled, human-readable string.

    Parameters
    ----------
    state : InvestigationState

    Returns
    -------
    str - formatted trace output, ready to print.
    """
    trace_entries: List[str] = state.get("agent_trace", [])
    reasoning_source = state.get("reasoning_source", "deterministic_fallback")

    if not trace_entries:
        return "\n[AGENT TRACE]\n  (no trace entries recorded)"

    output_lines = ["\n[AGENT TRACE]"]
    for entry in trace_entries:
        node_label, detail = _parse_entry(entry, reasoning_source)
        output_lines.append(f"  {node_label}")
        if detail:
            for detail_line in detail.split("\n"):
                output_lines.append(f"    {detail_line}")

    return "\n".join(output_lines)


def _parse_entry(entry: str, reasoning_source: str) -> tuple:
    """
    Parse a single trace entry string into (label, detail) pair.

    Trace entries have format: "[HH:MM:SS] [node_name] detail text"
    """
    match = re.match(r"\[(\d{2}:\d{2}:\d{2})\] \[([\w_]+)\] (.*)", entry, re.DOTALL)
    if not match:
        return (f"[TRACE]  {entry}", "")

    timestamp = match.group(1)
    node_name = match.group(2)
    detail = match.group(3)

    label = _NODE_LABELS.get(node_name)

    if node_name == "assess_investigation":
        if reasoning_source == "llm":
            label = "[LLM REASONING]"
        else:
            label = "[FALLBACK REASONING]"

    if label is None:
        label = f"[{node_name.upper()}]"

    return (f"{timestamp}  {label}  {detail}", "")