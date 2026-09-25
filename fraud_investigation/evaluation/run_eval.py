"""
Phase 3 Benchmark Evaluation CLI Entry Point.

Usage:
    python -m fraud_investigation.evaluation.run_eval
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .cases import load_benchmark_cases
from .metrics import calculate_evaluation_metrics
from .report import save_evaluation_report
from .runner import run_benchmark_eval

# Configure clean logging output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Phase3Eval")


def main() -> int:
    """Run the 20-case Phase 3 benchmark evaluation."""
    load_dotenv()
    if os.getenv("LLM_MODEL") in (None, "", "gemini-3.6-flash"):
        os.environ["LLM_MODEL"] = "gemini-3.5-flash"

    root = Path(__file__).resolve().parent.parent.parent
    case_pack_path = root / "dataset" / "case_pack.csv"
    output_json_path = root / "docs" / "PHASE3_EVALUATION_RESULTS.json"
    output_md_path = root / "docs" / "PHASE3_EVALUATION_REPORT.md"

    logger.info("Loading 20 benchmark cases from %s", case_pack_path)
    cases = load_benchmark_cases(case_pack_path)
    logger.info("Loaded %d benchmark cases successfully.", len(cases))

    logger.info("Executing Phase 3 benchmark evaluation across all 20 cases...")
    results = run_benchmark_eval(
        cases, conn=None, delay_between_cases=0.5, live_mcp=True
    )

    logger.info("Calculating evaluation metrics...")
    metrics = calculate_evaluation_metrics(results)

    logger.info("Saving evaluation reports to %s and %s...", output_json_path, output_md_path)
    save_evaluation_report(metrics, results, output_json_path, output_md_path)

    # Print concise terminal summary
    print("\n" + "=" * 65)
    print("PHASE 3 EVALUATION COMPLETE")
    print("=" * 65)
    print(f"Cases Evaluated: {metrics['total_cases']}")
    print(f"Completed Cases: {metrics['completed_cases']}")
    print(f"Failed Cases:    {metrics['failed_cases']}")
    print(f"Ground Truth:    {metrics['ground_truth_available']} (Not pre-packaged)")
    print("-" * 65)
    print(f"Citation Validity Rate:      {metrics['evidence']['citation_validity_rate'] * 100:.2f}%")
    print(f"Forbidden Action Leakage:    {metrics['policy']['forbidden_action_leakage']} (Target: 0)")
    print(f"Mandatory Action Omissions:  {metrics['policy']['mandatory_action_omissions']} (Target: 0)")
    print(f"Direct pyTigerGraph Bypasses: {metrics['mcp']['direct_pytigergraph_bypasses']} (Target: 0)")
    print(f"Additional Evidence Rate:    {metrics['agentic']['additional_evidence_rate'] * 100:.2f}%")
    print(f"Max Additional Ev Rounds:    {metrics['agentic']['max_additional_evidence_rounds']} (Bounded max: 1)")
    print(f"Live LLM Usage Rate:         {metrics['llm']['live_llm_rate'] * 100:.2f}%")
    print(f"Fallback Usage Rate:         {metrics['llm']['fallback_rate'] * 100:.2f}%")
    print(f"Avg Investigation Duration:  {metrics['performance']['avg_duration_seconds']:.4f}s")
    print("-" * 65)
    print(f"HHG-007 Regression Status:   {'PASS' if metrics['hhg007_regression']['passed'] else 'FAIL'}")
    print("=" * 65)
    print(f"Full Report: {output_md_path}")
    print("=" * 65 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
