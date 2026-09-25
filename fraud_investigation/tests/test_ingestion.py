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


class MockIngestionConn:
    def __init__(self):
        self.upserted_vertices = []
        self.upserted_edges = []

    def getVertexTypes(self):
        return ["Customer", "Card", "Transaction", "DeviceProfile", "ClosedCase", "InvestigationCase"]

    def upsertVertices(self, vertex_type, vertices):
        self.upserted_vertices.append((vertex_type, list(vertices)))

    def upsertEdges(self, src_type, edge_type, tgt_type, edges):
        self.upserted_edges.append((src_type, edge_type, tgt_type, list(edges)))


def test_loader_made_with_card_and_case_includes_txn_edges():
    from fraud_investigation.ingestion.loader import load_all

    conn = MockIngestionConn()
    stats = load_all(conn, DATASET_DIR)

    # Verify stats dictionary keys exist
    assert "made_with_card_edges" in stats
    assert "case_includes_txn_edges" in stats

    # Verify MADE_WITH_CARD edges (A, B)
    assert stats["made_with_card_edges"] == 26643
    mwc_calls = [
        call for call in conn.upserted_edges
        if call[1] == "MADE_WITH_CARD"
    ]
    assert len(mwc_calls) > 0
    all_mwc_edges = [edge for call in mwc_calls for edge in call[3]]
    assert len(all_mwc_edges) == 26643
    # Check edge format: (src_txn_id, target_card_id, {})
    first_mwc = all_mwc_edges[0]
    assert isinstance(first_mwc[0], str) and len(first_mwc[0]) > 0  # txn_id
    assert isinstance(first_mwc[1], str) and len(first_mwc[1]) > 0  # card_id (e.g. C09933-K1)

    # Verify CASE_INCLUDES_TXN edges (C, D, E, F)
    assert stats["case_includes_txn_edges"] == 587
    cit_calls = [
        call for call in conn.upserted_edges
        if call[1] == "CASE_INCLUDES_TXN"
    ]
    assert len(cit_calls) == 1
    cit_edges = cit_calls[0][3]
    assert len(cit_edges) == 587

    # Verify no dangling edges: target txn_id in loaded transactions
    all_loaded_txns = set()
    for v_call in conn.upserted_vertices:
        if v_call[0] == "Transaction":
            for v in v_call[1]:
                all_loaded_txns.add(v[0])

    for src_case_id, target_txn_id, attrs in cit_edges:
        assert target_txn_id in all_loaded_txns

