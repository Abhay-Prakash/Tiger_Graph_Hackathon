"""
HHGOA Fraud Investigation Agent - Hackathon Demo CLI.

Usage:
    python -m fraud_investigation.demo --case HHG-007
    python -m fraud_investigation.demo --case HHG-001
    python -m fraud_investigation.demo --case HHG-014

The demo:
  1. Loads the case from dataset/case_pack.csv
  2. Runs it through the verified LangGraph workflow (run_fraud_investigation)
  3. Renders a labeled observability trace
  4. Renders a structured investigation report
  5. Saves the report to docs/demo/<CASE_ID>_investigation_report.txt

LLM behavior:
  - Attempts live Gemini when GEMINI_API_KEY is set and quota is available
  - Falls back to deterministic reasoning on quota/API failure
  - Clearly displays which mode was used (reasoning_source)
  - Never fabricates LLM output
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

# Force stdout/stderr UTF-8 encoding on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv

load_dotenv()
if os.getenv("LLM_MODEL") in (None, "", "gemini-3.6-flash"):
    os.environ["LLM_MODEL"] = "gemini-3.5-flash"

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("FraudDemo")

from fraud_investigation.agent.runner import run_fraud_investigation
from fraud_investigation.demo.report_formatter import InvestigationReportFormatter
from fraud_investigation.demo.trace_renderer import render_trace

SEPARATOR = "=" * 66
SUBSEP = "-" * 66


def safe_print(text: str) -> None:
    """Print text safely across all operating systems and console encodings."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def load_case(case_pack_path: Path, case_id: str) -> dict:
    with open(case_pack_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["case_id"] == case_id:
                return {
                    "case_id": row["case_id"],
                    "customer_id": row["customer_id"],
                    "card_id": row.get("card_id", f"{row['customer_id']}-K1"),
                    "flagged_txn_id": row["flagged_txn_id"],
                    "trigger_type": row.get("trigger_type", "risk_score"),
                    "trigger_text": row.get("trigger_text", ""),
                    "risk_score": float(row.get("risk_score") or 0.0),
                    "amount": float(row.get("amount") or 0.0),
                    "opened_at": row.get("opened_at", ""),
                }
    return None


def print_banner(case_id: str) -> None:
    safe_print("")
    safe_print(SEPARATOR)
    safe_print(f"  HHGOA FRAUD INVESTIGATION AGENT - Hackathon Demo")
    safe_print(f"  Case: {case_id}")
    safe_print(SEPARATOR)


def run_demo(case_id: str) -> int:
    root = Path(__file__).resolve().parent.parent.parent
    case_pack_path = root / "dataset" / "case_pack.csv"

    if not case_pack_path.exists():
        safe_print(f"ERROR: case_pack.csv not found at {case_pack_path}")
        return 1

    case_data = load_case(case_pack_path, case_id)
    if case_data is None:
        safe_print(f"ERROR: Case '{case_id}' not found in {case_pack_path}")
        safe_print("Available cases: HHG-001 through HHG-020")
        return 1

    print_banner(case_id)
    safe_print(f"\n  Running LangGraph investigation for case {case_id}...")
    safe_print(f"  Customer: {case_data['customer_id']}  |  TXN: {case_data['flagged_txn_id']}")
    safe_print(f"  Trigger:  {case_data['trigger_type']}  |  Risk score: {case_data['risk_score']:.2f}")
    safe_print("")

    try:
        final_state = run_fraud_investigation(case_data, conn=None)
    except Exception as exc:
        safe_print(f"ERROR: Investigation workflow failed: {exc}")
        logger.exception("Investigation workflow exception")
        return 1

    reasoning_source = final_state.get("reasoning_source", "deterministic_fallback")
    safe_print(SEPARATOR)
    if reasoning_source == "llm":
        safe_print("  REASONING MODE: [LLM REASONING]  (Gemini API - live)")
    else:
        safe_print("  REASONING MODE: [FALLBACK REASONING]  (deterministic_fallback)")
        safe_print("  Gemini API quota exhausted or unavailable.")
        safe_print("  Deterministic fallback is auditable and evidence-grounded.")
    safe_print(SEPARATOR)

    trace_output = render_trace(final_state)
    safe_print(trace_output)

    formatter = InvestigationReportFormatter()
    report_text = formatter.format(final_state)
    safe_print(report_text)

    demo_dir = root / "docs" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    report_path = demo_dir / f"{case_id}_investigation_report.txt"
    report_path.write_text(report_text, encoding="utf-8")

    safe_print("")
    safe_print(SEPARATOR)
    safe_print(f"  Report saved: {report_path}")
    safe_print(SEPARATOR)
    safe_print("")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HHGOA Fraud Investigation Agent - Hackathon Demo CLI"
    )
    parser.add_argument(
        "--case",
        type=str,
        required=True,
        help="Case ID to investigate (e.g. HHG-007, HHG-001, HHG-014)",
    )
    args = parser.parse_args()
    return run_demo(args.case.upper())


if __name__ == "__main__":
    sys.exit(main())