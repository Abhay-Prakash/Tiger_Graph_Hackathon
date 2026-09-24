"""
Unit tests for data extraction and ingestion transformation rules.
"""

from pathlib import Path
import pytest
from fraud_investigation.ingestion.extractor import (
    _device_id,
    _is_specific_device,
    extract_case_pack,
    extract_closed_cases,
    load_benchmark_customer_ids,
)

DATASET_DIR = Path("dataset")


def test_device_id_generation_and_filtering():
    # Specific devices generate valid IDs
    d1 = _device_id("SAMSUNG SM-G892A Build/NRD90M")
    assert d1.startswith("DEV-")

    # Generic devices return empty string (filtered out)
    assert _device_id("Windows") == ""
    assert _device_id("MacOS") == ""
    assert _device_id("iOS Device") == ""
    assert _device_id("") == ""


def test_load_benchmark_customer_ids():
    cids = load_benchmark_customer_ids(DATASET_DIR / "case_pack.csv")
    assert len(cids) == 20
    assert "C09933" in cids  # HHG-007 customer
    assert "C12382" in cids  # HHG-001 customer


def test_extract_case_pack():
    cases = extract_case_pack(DATASET_DIR / "case_pack.csv")
    assert len(cases) == 20
    hhg007 = next(c for c in cases if c["case_id"] == "HHG-007")
    assert hhg007["customer_id"] == "C09933"
    assert hhg007["flagged_txn_id"] == "3514948"
    assert hhg007["trigger_type"] == "risk_score"


def test_extract_closed_cases():
    closed = list(extract_closed_cases(DATASET_DIR / "closed_cases_history.csv"))
    assert len(closed) == 5565
    sample = closed[0]
    assert "case_id" in sample
    assert "customer_id" in sample
    assert "outcome" in sample
