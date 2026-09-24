"""
Script to load HHGOA dataset into TigerGraph and install GSQL queries.
Supports --reset for clean re-ingestion and idempotency testing.
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fraud_investigation.ingestion.loader import GRAPH_NAME, apply_schema, install_queries, load_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Load HHGOA dataset into TigerGraph.")
    parser.add_argument("--reset", action="store_true", help="Drop graph before loading.")
    parser.add_argument("--dataset-dir", type=str, default="dataset", help="Directory containing dataset CSVs.")
    parser.add_argument("--host", type=str, default=os.getenv("TG_HOST", "http://127.0.0.1"), help="TigerGraph host URL.")
    parser.add_argument("--username", type=str, default=os.getenv("TG_USERNAME", "tigergraph"), help="TigerGraph username.")
    parser.add_argument("--password", type=str, default=os.getenv("TG_PASSWORD", "tigergraph"), help="TigerGraph password.")
    parser.add_argument("--dry-run", action="store_true", help="Parse files without pushing to TigerGraph.")

    args = parser.parse_args()

    dataset_path = Path(args.dataset_dir)
    if not dataset_path.exists():
        print(f"Error: dataset directory {dataset_path} does not exist.")
        sys.exit(1)

    if args.dry_run:
        print(f"Dry-run mode: Parsing files in {dataset_path}...")
        from fraud_investigation.ingestion.extractor import (
            extract_case_pack,
            extract_closed_cases,
            load_benchmark_customer_ids,
        )
        cids = load_benchmark_customer_ids(dataset_path / "case_pack.csv")
        cases = extract_case_pack(dataset_path / "case_pack.csv")
        closed = list(extract_closed_cases(dataset_path / "closed_cases_history.csv"))
        print(f"Dry-run succeeded: {len(cids)} benchmark customers, {len(cases)} benchmark cases, {len(closed)} closed cases.")
        return

    try:
        import pyTigerGraph as tg
    except ImportError:
        print("Error: pyTigerGraph is required. Install via pip install pyTigerGraph.")
        sys.exit(1)

    print(f"Connecting to TigerGraph at {args.host}...")
    conn = tg.TigerGraphConnection(
        host=args.host,
        username=args.username,
        password=args.password,
    )

    # 1. Schema
    apply_schema(conn, reset=args.reset)
    conn.graphname = GRAPH_NAME

    # 2. Queries
    install_queries(conn)

    # 3. Load Data
    stats = load_all(conn, dataset_path)
    print("\nData loading complete!")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
