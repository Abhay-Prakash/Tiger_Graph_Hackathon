"""
Benchmark Case Loader for Phase 3 Evaluation.

Loads the 20 benchmark cases from dataset/case_pack.csv.
Validates required benchmark fields: case_id, customer_id, flagged_txn_id, trigger_type.
"""

import csv
import os
from pathlib import Path
from typing import Any, Dict, List


def get_dataset_dir() -> Path:
    """Resolve absolute path to dataset directory."""
    root = Path(__file__).resolve().parent.parent.parent
    dataset_dir = root / "dataset"
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found at {dataset_dir}")
    return dataset_dir


def load_benchmark_cases(case_pack_path: Path = None) -> List[Dict[str, Any]]:
    """
    Load and parse the 20 benchmark cases from dataset/case_pack.csv.

    Returns
    -------
    List[Dict[str, Any]]
        List of parsed benchmark case dictionary records.
    """
    if case_pack_path is None:
        case_pack_path = get_dataset_dir() / "case_pack.csv"

    if not case_pack_path.exists():
        raise FileNotFoundError(f"Case pack CSV file missing at {case_pack_path}")

    cases = []
    required_fields = {"case_id", "customer_id", "flagged_txn_id", "trigger_type"}

    with open(case_pack_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            missing = required_fields - set(row.keys())
            if missing:
                raise ValueError(f"Invalid case_pack.csv: missing required fields {missing}")

            # Parse risk score cleanly
            raw_risk = row.get("risk_score", "").strip()
            risk_score = float(raw_risk) if raw_risk else 0.0

            case_item = {
                "case_id": row["case_id"].strip(),
                "opened_at": row.get("opened_at", "").strip(),
                "trigger_type": row["trigger_type"].strip(),
                "trigger_text": row.get("trigger_text", "").strip(),
                "flagged_txn_id": row["flagged_txn_id"].strip(),
                "card_id": row.get("card_id", "").strip() or f"{row['customer_id'].strip()}-K1",
                "customer_id": row["customer_id"].strip(),
                "risk_score": risk_score,
            }
            cases.append(case_item)

    if not cases:
        raise ValueError(f"No benchmark cases found in {case_pack_path}")

    return cases
