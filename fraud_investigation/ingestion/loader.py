"""
Idempotent TigerGraph loader for the HHGOA Fraud Investigation dataset.

Idempotency guarantees:
- Schema creation: checks graph existence before applying DDL.
- Data loading: uses upsertVertices / upsertEdges (UPSERT semantics by PK).
- Re-running load_all() on the same data produces no duplicate vertices/edges.
- The --reset flag drops the graph first for a clean slate.

Loading scope:
- closed_cases_history.csv: ALL 5,565 rows (not benchmark-scoped).
- case_pack.csv:            All 20 benchmark cases.
- transactions.csv:         Benchmark customers only (or supplied customer_ids).
- identity.csv:             Transactions in benchmark scope that have specific device info.

Does NOT modify the tigergraph-mcp package source.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Graph name — must match fraud_schema.gsql
GRAPH_NAME = "HHGOA_Fraud"

_SCHEMA_FILE = Path(__file__).parent.parent / "schema" / "fraud_schema.gsql"
_QUERIES_DIR = Path(__file__).parent.parent / "queries"


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------

def apply_schema(conn: Any, reset: bool = False) -> None:
    """
    Apply the FraudInvestigation graph schema idempotently.

    Parameters
    ----------
    conn  : pyTigerGraph TigerGraphConnection instance.
    reset : If True, DROP the graph first (complete clean slate).
            WARNING: all data is lost on reset.
    """
    if reset:
        logger.warning("--reset flag: dropping graph %s", GRAPH_NAME)
        try:
            conn.gsql(f"DROP GRAPH {GRAPH_NAME} CASCADE")
            logger.info("Dropped graph %s", GRAPH_NAME)
        except Exception as e:
            logger.warning("Drop graph failed (may not exist): %s", e)

    # Check if graph schema already exists
    try:
        existing_types = conn.getVertexTypes()
        if existing_types:
            logger.info(
                "Graph %s already exists (%d vertex types found) — skipping schema creation. "
                "Use reset=True to recreate.", GRAPH_NAME, len(existing_types),
            )
            return
    except Exception as e:
        logger.warning("Could not check vertex types: %s", e)

    # Apply schema DDL
    gsql_text = _SCHEMA_FILE.read_text(encoding="utf-8")
    logger.info("Applying schema from %s", _SCHEMA_FILE)
    result = conn.gsql(gsql_text)
    logger.info("Schema result: %s", str(result)[:200])


# ---------------------------------------------------------------------------
# Query installation
# ---------------------------------------------------------------------------

def install_queries(conn: Any) -> None:
    """
    Install all 5 investigation GSQL queries on the FraudInvestigation graph.
    Idempotent: CREATE OR REPLACE QUERY re-installs if already present.
    """
    for query_file in sorted(_QUERIES_DIR.glob("*.gsql")):
        logger.info("Installing query from %s", query_file.name)
        gsql_text = query_file.read_text(encoding="utf-8")
        try:
            result = conn.gsql(f"USE GRAPH {GRAPH_NAME}\n" + gsql_text)
            logger.info("Installed %s: %s", query_file.name, str(result)[:100])
        except Exception as e:
            logger.error("Failed to install %s: %s", query_file.name, e)
            raise


# ---------------------------------------------------------------------------
# Batch upsert helpers
# ---------------------------------------------------------------------------

def _upsert_vertices(
    conn: Any,
    vertex_type: str,
    records: List[Dict[str, Any]],
    id_field: str,
    batch_size: int = 500,
) -> int:
    """
    Upsert a list of vertex records in batches.
    Returns total count of upserted vertices.
    """
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        vertices = [(r[id_field], {k: v for k, v in r.items() if k != id_field})
                    for r in batch]
        conn.upsertVertices(vertex_type, vertices)
        total += len(batch)
    return total


def _upsert_edges(
    conn: Any,
    src_type: str,
    edge_type: str,
    tgt_type: str,
    edges: List[tuple],   # [(src_id, tgt_id, {attrs}), ...]
    batch_size: int = 500,
) -> int:
    """
    Upsert a list of edges in batches.
    Returns total count of upserted edges.
    """
    total = 0
    for i in range(0, len(edges), batch_size):
        batch = edges[i : i + batch_size]
        conn.upsertEdges(src_type, edge_type, tgt_type, batch)
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_all(
    conn: Any,
    dataset_dir: Path,
    customer_ids: Optional[Set[str]] = None,
    batch_size: int = 500,
) -> dict:
    """
    Load all HHGOA dataset entities into TigerGraph FraudInvestigation graph.

    Parameters
    ----------
    conn         : pyTigerGraph TigerGraphConnection (must be connected to GRAPH_NAME).
    dataset_dir  : Directory containing the 4 CSV files.
    customer_ids : Optional set of customer_ids to scope transaction/identity loading.
                   If None, loads the 20 benchmark customers from case_pack.csv.
    batch_size   : Vertices/edges per upsert call.

    Returns
    -------
    dict with loading statistics.
    """
    from .extractor import (
        load_benchmark_customer_ids,
        extract_closed_cases,
        extract_case_pack,
        extract_transactions,
        extract_identity,
    )

    t0 = time.time()
    stats: dict = {}

    # File paths
    case_pack_path    = dataset_dir / "case_pack.csv"
    closed_cases_path = dataset_dir / "closed_cases_history.csv"
    transactions_path = dataset_dir / "transactions.csv"
    identity_path     = dataset_dir / "identity.csv"

    # Resolve customer scope
    if customer_ids is None:
        customer_ids = load_benchmark_customer_ids(case_pack_path)
    logger.info("Loading scope: %d customers", len(customer_ids))

    # ------------------------------------------------------------------
    # 1. Load Customers
    # ------------------------------------------------------------------
    logger.info("Step 1/7 — Loading Customer vertices")
    customer_vertices = [
        (cid, {"customer_id": cid}) for cid in sorted(customer_ids)
    ]
    # Also add customers from closed_cases (for case memory edges)
    all_case_customers: Set[str] = set()
    for rec in extract_closed_cases(closed_cases_path):
        all_case_customers.add(rec["customer_id"])
    for cid in all_case_customers:
        customer_vertices.append((cid, {"customer_id": cid}))

    # Deduplicate
    seen = set()
    deduped = []
    for cv in customer_vertices:
        if cv[0] not in seen:
            seen.add(cv[0])
            deduped.append(cv)

    conn.upsertVertices("Customer", deduped)
    stats["customers"] = len(deduped)
    logger.info("Upserted %d Customer vertices", len(deduped))

    # ------------------------------------------------------------------
    # 2. Load ClosedCases (ALL 5,565 rows)
    # ------------------------------------------------------------------
    logger.info("Step 2/7 — Loading ClosedCase vertices and edges")
    case_vertices = []
    card_vertices_from_cases = []   # cards seen in closed cases
    case_customer_edges = []
    case_card_edges = []
    closed_case_txns = []           # (case_id, txn_ids_list) for CASE_INCLUDES_TXN edges

    for rec in extract_closed_cases(closed_cases_path):
        cid = rec["case_id"]
        attrs = {
            k: v for k, v in rec.items()
            if k not in {"case_id", "_txn_ids_list", "_connected_cards_list"}
            and not (k in {"closed_at", "opened_at"} and v == "")
        }
        case_vertices.append((cid, attrs))
        case_customer_edges.append((rec["customer_id"], cid, {}))
        if rec["_txn_ids_list"]:
            closed_case_txns.append((cid, rec["_txn_ids_list"]))
        if rec["card_id"]:
            case_card_edges.append((cid, rec["card_id"], {}))
            # Register card vertex
            card_vertices_from_cases.append((rec["card_id"], {
                "card_id":      rec["card_id"],
                "customer_id":  rec["customer_id"],
                "card_network": "",
                "card_type":    "",
                "card_token":   "",
            }))

    n_cases = _upsert_vertices(conn, "ClosedCase", [], "case_id")  # use direct below
    conn.upsertVertices("ClosedCase", case_vertices)
    stats["closed_cases"] = len(case_vertices)
    logger.info("Upserted %d ClosedCase vertices", len(case_vertices))

    # ------------------------------------------------------------------
    # 3. Load Card vertices (from closed cases first; transactions will enrich)
    # ------------------------------------------------------------------
    logger.info("Step 3/7 — Loading Card vertices")
    # Deduplicate cards
    card_seen: Set[str] = set()
    card_deduped = []
    for cv in card_vertices_from_cases:
        if cv[0] not in card_seen:
            card_seen.add(cv[0])
            card_deduped.append(cv)
    conn.upsertVertices("Card", card_deduped)
    stats["cards_from_cases"] = len(card_deduped)
    logger.info("Upserted %d Card vertices from closed cases", len(card_deduped))

    # ------------------------------------------------------------------
    # 4. Load benchmark InvestigationCase vertices
    # ------------------------------------------------------------------
    logger.info("Step 4/7 — Loading InvestigationCase vertices")
    inv_vertices = []
    inv_customer_edges = []
    for rec in extract_case_pack(case_pack_path):
        case_id = rec["case_id"]
        attrs = {
            k: v for k, v in rec.items()
            if k != "case_id"
            and not (k in {"closed_at", "opened_at"} and v == "")
        }
        inv_vertices.append((case_id, attrs))
        inv_customer_edges.append((case_id, rec["customer_id"], {}))

    conn.upsertVertices("InvestigationCase", inv_vertices)
    stats["investigation_cases"] = len(inv_vertices)
    logger.info("Upserted %d InvestigationCase vertices", len(inv_vertices))

    # ------------------------------------------------------------------
    # 5. Load Transactions (benchmark-scoped)
    # ------------------------------------------------------------------
    logger.info("Step 5/7 — Loading Transaction vertices (scoped to %d customers)", len(customer_ids))
    txn_vertices = []
    txn_customer_edges = []      # Customer → Transaction
    made_with_card_edges = []    # Transaction → Card
    loaded_txn_ids: Set[str] = set()
    total_made_with_card = 0

    # card1_token → card_id mapping (built during transaction scan)
    # card_id format: {customer_id}-K{n} — we derive this by grouping card1 values
    customer_card_tokens: dict = {}  # customer_id → {card1_token → card_id}
    customer_card_counters: dict = {}  # customer_id → counter

    for rec in extract_transactions(transactions_path, customer_ids):
        txn_id = rec["txn_id"]
        cid    = rec["customer_id"]
        loaded_txn_ids.add(txn_id)

        # Assign card_id: group card1_token per customer
        card1_tok = rec["card1_token"]
        if cid not in customer_card_tokens:
            customer_card_tokens[cid] = {}
            customer_card_counters[cid] = 0
        if card1_tok and card1_tok not in customer_card_tokens[cid]:
            customer_card_counters[cid] += 1
            customer_card_tokens[cid][card1_tok] = (
                f"{cid}-K{customer_card_counters[cid]}"
            )
        card_id = customer_card_tokens[cid].get(card1_tok, "")

        txn_attrs = {
            "amount":         rec["amount"],
            "txn_timestamp":  rec["txn_timestamp"],
            "channel":        rec["channel"],
            "product_cd":     rec["product_cd"],
            "addr1":          rec["addr1"],
            "dist1":          rec["dist1"],
            "p_email_domain": rec["p_email_domain"],
            "r_email_domain": rec["r_email_domain"],
            "card1_token":    card1_tok,
            "card_network":   rec["card_network"],
            "card_type":      rec["card_type"],
            "c1":             rec["c1"],
            "c2":             rec["c2"],
            "d1":             rec["d1"],
            "m4":             rec["m4"],
            "m5":             rec["m5"],
            "m6":             rec["m6"],
            "risk_score":     rec["risk_score"],
            "transaction_dt": rec["transaction_dt"],
        }
        txn_vertices.append((txn_id, txn_attrs))
        txn_customer_edges.append((cid, txn_id, {}))
        if card_id:
            made_with_card_edges.append((txn_id, card_id, {}))

        if len(txn_vertices) >= batch_size:
            conn.upsertVertices("Transaction", list(txn_vertices))
            conn.upsertEdges("Customer", "HAS_TRANSACTION", "Transaction", list(txn_customer_edges))
            if made_with_card_edges:
                conn.upsertEdges("Transaction", "MADE_WITH_CARD", "Card", list(made_with_card_edges))
                total_made_with_card += len(made_with_card_edges)
            txn_vertices.clear()
            txn_customer_edges.clear()
            made_with_card_edges.clear()

    # Flush remaining
    if txn_vertices:
        conn.upsertVertices("Transaction", list(txn_vertices))
        conn.upsertEdges("Customer", "HAS_TRANSACTION", "Transaction", list(txn_customer_edges))
        if made_with_card_edges:
            conn.upsertEdges("Transaction", "MADE_WITH_CARD", "Card", list(made_with_card_edges))
            total_made_with_card += len(made_with_card_edges)

    stats["transactions"] = len(loaded_txn_ids)
    stats["made_with_card_edges"] = total_made_with_card
    logger.info("Upserted %d Transaction vertices, %d MADE_WITH_CARD edges", len(loaded_txn_ids), total_made_with_card)

    # Upsert enriched Card vertices (with network/type from transactions)
    enriched_cards = []
    for cid, token_map in customer_card_tokens.items():
        for token, card_id in token_map.items():
            enriched_cards.append((card_id, {
                "card_id":     card_id,
                "customer_id": cid,
                "card_token":  token,
                "card_network": "",  # will be set per-transaction if available
                "card_type":   "",
            }))
    if enriched_cards:
        conn.upsertVertices("Card", enriched_cards)
        stats["cards_from_txns"] = len(enriched_cards)

    # ------------------------------------------------------------------
    # 6. Load DeviceProfile vertices and HAS_IDENTITY edges
    # ------------------------------------------------------------------
    logger.info("Step 6/7 — Loading DeviceProfile vertices")
    device_vertices = []
    has_identity_edges = []
    seen_device_ids: Set[str] = set()

    for rec in extract_identity(identity_path, loaded_txn_ids):
        did = rec["device_id"]
        txn_id = rec["txn_id"]
        if did not in seen_device_ids:
            device_vertices.append((did, {
                "device_type":          rec["device_type"],
                "device_info":          rec["device_info"],
                "device_info_normalized": rec["device_info_normalized"],
            }))
            seen_device_ids.add(did)
        has_identity_edges.append((txn_id, did, {}))

    if device_vertices:
        conn.upsertVertices("DeviceProfile", device_vertices)
        stats["device_profiles"] = len(device_vertices)
    if has_identity_edges:
        conn.upsertEdges("Transaction", "HAS_IDENTITY", "DeviceProfile", has_identity_edges)
    stats["has_identity_edges"] = len(has_identity_edges)
    logger.info(
        "Upserted %d DeviceProfile vertices, %d HAS_IDENTITY edges",
        len(device_vertices), len(has_identity_edges),
    )

    # ------------------------------------------------------------------
    # 7. Create remaining edges
    # ------------------------------------------------------------------
    logger.info("Step 7/7 — Creating relationship edges")

    # Customer → ClosedCase
    conn.upsertEdges("Customer", "CUSTOMER_HAS_CASE", "ClosedCase", case_customer_edges)
    stats["customer_has_case_edges"] = len(case_customer_edges)

    # ClosedCase → Card
    if case_card_edges:
        conn.upsertEdges("ClosedCase", "CASE_ON_CARD", "Card", case_card_edges)
    stats["case_on_card_edges"] = len(case_card_edges)

    # Customer → Card (OWNS_CARD) — for benchmark customers
    owns_card_edges = []
    for cid, token_map in customer_card_tokens.items():
        for token, card_id in token_map.items():
            owns_card_edges.append((cid, card_id, {}))
    if owns_card_edges:
        conn.upsertEdges("Customer", "OWNS_CARD", "Card", owns_card_edges)
    stats["owns_card_edges"] = len(owns_card_edges)

    # InvestigationCase → Customer
    conn.upsertEdges(
        "InvestigationCase", "INVESTIGATION_FOR_CUSTOMER", "Customer", inv_customer_edges
    )

    # InvestigationCase → Transaction (flagged txn)
    inv_txn_edges = []
    for rec in extract_case_pack(case_pack_path):
        ftxn = rec["flagged_txn_id"]
        if ftxn in loaded_txn_ids:
            inv_txn_edges.append((rec["case_id"], ftxn, {}))
    if inv_txn_edges:
        conn.upsertEdges(
            "InvestigationCase", "INVESTIGATION_FLAGS_TXN", "Transaction", inv_txn_edges
        )
    stats["investigation_flags_txn_edges"] = len(inv_txn_edges)

    # ClosedCase → Transaction (CASE_INCLUDES_TXN) — benchmark-scoped transactions only
    case_includes_txn_edges = []
    seen_case_txn: Set[tuple] = set()
    for case_id, txn_list in closed_case_txns:
        for tid in txn_list:
            if tid in loaded_txn_ids:
                pair = (case_id, tid)
                if pair not in seen_case_txn:
                    seen_case_txn.add(pair)
                    case_includes_txn_edges.append((case_id, tid, {}))
    if case_includes_txn_edges:
        conn.upsertEdges("ClosedCase", "CASE_INCLUDES_TXN", "Transaction", case_includes_txn_edges)
    stats["case_includes_txn_edges"] = len(case_includes_txn_edges)

    elapsed = time.time() - t0
    stats["elapsed_seconds"] = round(elapsed, 1)
    logger.info("Load complete in %.1fs. Stats: %s", elapsed, stats)
    return stats
