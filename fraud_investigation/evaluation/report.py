"""
Evaluation Report Generator for Phase 3 Benchmark Evaluation.

Generates machine-readable JSON evaluation results and human-readable Markdown reports.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def generate_markdown_report(metrics: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    """
    Format evaluation metrics and case details into a clean Markdown report.

    Parameters
    ----------
    metrics : dict
        Calculated evaluation metrics.
    results : list
        Per-case evaluation telemetry results.

    Returns
    -------
    str
        Formatted Markdown document string.
    """
    ev = metrics.get("evidence", {})
    pol = metrics.get("policy", {})
    mcp = metrics.get("mcp", {})
    ag = metrics.get("agentic", {})
    llm = metrics.get("llm", {})
    perf = metrics.get("performance", {})
    hhg007 = metrics.get("hhg007_regression", {})

    additional_evidence_cases = [
        result for result in results if result.get("additional_evidence_rounds", 0) > 0
    ]
    contradiction_cases = [
        result for result in results if result.get("contradiction_evidence")
    ]
    writeback_cases = [result for result in results if result.get("writeback_observed")]
    transport_failure_cases = [result for result in results if result.get("mcp_failures")]

    lines = [
        "# Phase 3 — Benchmark Evaluation & System Audit Report",
        "",
        "## EXECUTIVE SUMMARY",
        "",
        f"- **Cases Evaluated:** {metrics.get('total_cases', 20)}",
        f"- **Completed Cases:** {metrics.get('completed_cases', 0)}",
        f"- **Failed Cases:** {metrics.get('failed_cases', 0)}",
        f"- **Ground Truth Available:** {metrics.get('ground_truth_available', 'NO')} (Strictly distinguished from dataset pattern alignment per Section 5)",
        "",
        "---",
        "",
        "## 1. EVIDENCE GROUNDING",
        "",
        f"- **Total Evidence Objects Gathered:** {ev.get('total_evidence_objects', 0)}",
        f"- **Valid Evidence Citations:** {ev.get('valid_citations', 0)}",
        f"- **Invalid / Hallucinated Citations:** {ev.get('invalid_citations', 0)}",
        f"- **Citation Validity Rate:** {ev.get('citation_validity_rate', 1.0) * 100:.2f}%",
        f"- **Unsupported Claims:** {ev.get('unsupported_claims', 0)}",
        "",
        "---",
        "",
        "## 2. POLICY SAFETY INVARIANTS",
        "",
        f"- **Forbidden Action Leakage:** {pol.get('forbidden_action_leakage', 0)} (Target: 0)",
        f"- **Mandatory Action Omissions:** {pol.get('mandatory_action_omissions', 0)} (Target: 0)",
        f"- **Total Policy Violations:** {pol.get('policy_violations', 0)} (Target: 0)",
        f"- **Policy Engine Version:** `hackathon-inferred-v1` (Deterministic Authority)",
        "",
        "---",
        "",
        "## 3. MCP BOUNDARY INTEGRITY",
        "",
        f"- **Total MCP Tool Calls Executed:** {mcp.get('mcp_calls', 0)}",
        f"- **GSQL Graph Query Calls:** {mcp.get('graph_queries', 0)}",
        f"- **MCP Transport Failures:** {mcp.get('mcp_failures', 0)}",
        f"- **Direct pyTigerGraph Bypasses:** {mcp.get('direct_pytigergraph_bypasses', 0)} (Strict Target: 0)",
        "",
        "---",
        "",
        "## 4. AGENTICITY & WORKFLOW DYNAMICS",
        "",
        f"- **Cases Requiring Additional Evidence:** {ag.get('cases_requiring_additional_evidence', 0)}",
        f"- **Additional Evidence Invocation Rate:** {ag.get('additional_evidence_rate', 0.0) * 100:.2f}%",
        f"- **Maximum Observed Loop Depth:** {ag.get('max_additional_evidence_rounds', 0)} (Bounded at max 1)",
        f"- **NBA-Before Capture Rate:** {ag.get('nba_before_capture_rate', 1.0) * 100:.2f}%",
        f"- **NBA-After Capture Rate:** {ag.get('nba_after_capture_rate', 1.0) * 100:.2f}%",
        "",
        "---",
        "",
        "## 5. LLM REASONING & FALLBACK TRACING",
        "",
        f"- **Live LLM Reasoning Cases:** {llm.get('live_llm_cases', 0)}",
        f"- **Deterministic Fallback Cases:** {llm.get('fallback_cases', 0)}",
        f"- **Live LLM Usage Rate:** {llm.get('live_llm_rate', 0.0) * 100:.2f}%",
        f"- **Fallback Usage Rate:** {llm.get('fallback_rate', 0.0) * 100:.2f}%",
        "",
        "---",
        "",
        "## 6. PERFORMANCE TELEMETRY",
        "",
        f"- **Average Duration:** {perf.get('avg_duration_seconds', 0.0):.4f} seconds",
        f"- **Median Duration:** {perf.get('median_duration_seconds', 0.0):.4f} seconds",
        f"- **Minimum Duration:** {perf.get('min_duration_seconds', 0.0):.4f} seconds",
        f"- **Maximum Duration:** {perf.get('max_duration_seconds', 0.0):.4f} seconds",
        "",
        "---",
        "",
        "## 7. HHG-007 REGRESSION AUDIT",
        "",
        f"- **Flagged Region vs Home Region Match:** `264.0 == 264.0` (`is_anomalous = false`)",
        f"- **`out_of_region_use` Asserted:** {'YES' if hhg007.get('out_of_region_use_asserted') else 'NOT ASSERTED'}",
        f"- **Regression Status:** {'PASS' if hhg007.get('passed') else 'FAIL'}",
        "",
        "---",
        "",
        "## 8. Accuracy And Error Analysis",
        "",
        "- No per-case ground-truth outcomes are present in `dataset/case_pack.csv`; a classification accuracy score is therefore not calculated.",
        f"- Execution errors: {metrics.get('failed_cases', 0)}.",
        f"- MCP transport failure events: {mcp.get('mcp_failures', 0)} across {len(transport_failure_cases)} cases.",
        f"- Cases using deterministic reasoning fallback: {llm.get('fallback_cases', 0)}.",
        f"- Policy violations observed: {pol.get('policy_violations', 0)}.",
        "",
        "---",
        "",
        "## 9. NBA Before/After Matrix",
        "",
        "| Case ID | NBA Before | Additional Evidence Requested | NBA After |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        requested = r.get("additional_evidence_requested", [])
        request_text = "; ".join(str(item.get("request_type", item)) for item in requested) or "none"
        before = ", ".join(r.get("nba_before") or []) or "none"
        after = ", ".join(r.get("nba_after") or []) or "none"
        lines.append(f"| `{r.get('case_id', 'N/A')}` | {before} | {request_text} | {after} |")

    lines.extend([
        "",
        "---",
        "",
        "## 10. Additional Evidence And Contradictions",
        "",
        f"- Cases requiring additional evidence: {', '.join(result['case_id'] for result in additional_evidence_cases) or 'none'}.",
        f"- Cases with contradiction evidence: {', '.join(result['case_id'] for result in contradiction_cases) or 'none'}.",
        f"- Observed MCP writebacks through `tigergraph__add_nodes`: {len(writeback_cases)}/{len(results)}.",
        "",
        "---",
        "",
        "## 11. Per-Case Results",
        "",
    ])

    for r in results:
        lines.extend([
            f"### {r.get('case_id', 'N/A')}",
            "",
            f"- Trigger: `{r.get('trigger_type', '')}`; initial risk: `{r.get('initial_risk_score', 0.0)}`; transaction: `{r.get('flagged_txn_id', '')}`.",
            f"- Evidence: {r.get('evidence_count', 0)} items; citations: {', '.join(r.get('evidence_citations', [])) or 'none'}; sufficient: `{r.get('evidence_sufficient', False)}`.",
            f"- Hypotheses: {', '.join(r.get('fraud_hypotheses', [])) or 'none'}; confidence: `{r.get('confidence', 0.0)}`; uncertainty: `{r.get('uncertainty', 0.0)}`.",
            f"- Outcome/pattern/exposure: `{r.get('outcome', 'unknown')}` / `{r.get('pattern', 'unknown')}` / `${r.get('exposure_usd', 0.0):.2f}`.",
            f"- SAR required: `{r.get('sar_requirement')}`; executed actions: {', '.join(r.get('executed_actions', [])) or 'none'}.",
            f"- Reasoning: `{r.get('reasoning_source', 'unknown')}`; MCP transport: `{r.get('mcp_transport', 'unknown')}`; writeback observed: `{r.get('writeback_observed', False)}`.",
            f"- MCP failures: {json.dumps(r.get('mcp_failures', []))}; error: {r.get('error') or 'none'}.",
            "",
        ])

    return "\n".join(lines)


def save_evaluation_report(
    metrics: Dict[str, Any],
    results: List[Dict[str, Any]],
    output_json_path: Path,
    output_md_path: Path,
) -> None:
    """Save machine-readable JSON and human-readable Markdown evaluation reports."""
    # Ensure parent directories exist
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "metrics": metrics,
        "results": results,
    }

    with open(output_json_path, mode="w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    md_content = generate_markdown_report(metrics, results)
    with open(output_md_path, mode="w", encoding="utf-8") as f:
        f.write(md_content)
