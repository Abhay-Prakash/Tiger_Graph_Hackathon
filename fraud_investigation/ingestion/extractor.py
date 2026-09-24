"""
CSV extraction and transformation for TigerGraph ingestion.

Responsibilities:
- Read HHGOA dataset CSV files.
- Filter transactions/identity to benchmark-scoped customers (or a provided set).
- Transform raw CSV rows into TigerGraph vertex/edge upsert records.
- Handle missing values with documented defaults.
- Compute deterministic device IDs from DeviceInfo strings.

Design constraints:
- Uses stdlib csv only (no pandas dependency).
- Does NOT interpret V1-V339, C3-C14, D2-D15, M1-M3, M7-M9.
- Does NOT invent any values not present in the source data.
- Deterministic: same input → same output.
"""

import csv
import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Generic device strings that are too broad for useful shared-device analysis.
# These would falsely link thousands of unrelated transactions.
# Source: manual inspection of identity.csv DeviceInfo samples.
_GENERIC_DEVICE_INFO = {
    "windows", "macos", "mac os", "linux", "ios device", "android",
    "chrome os", "ubuntu", "unknown", "desktop", "mobile", "",
}

# Minimum DeviceInfo string length to be considered specific enough.
_MIN_DEVICE_INFO_LEN = 9

# Default float for missing numeric CSV fields (addr1, dist1, etc.)
# -1.0 is used because valid addr1 values are always positive region codes.
_MISSING_FLOAT = -1.0

# Columns kept from transactions.csv (all others discarded at extraction time)
_TXN_KEEP_COLS = {
    "TransactionID", "TransactionDT", "TransactionAmt", "ProductCD",
    "card1", "card4", "card6",
    "addr1", "dist1",
    "P_emaildomain", "R_emaildomain",
    "C1", "C2", "D1",
    "M4", "M5", "M6",
    "customer_id", "ts", "channel", "risk_score",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float(val: str, default: float = _MISSING_FLOAT) -> float:
    """Parse CSV string to float; return default for empty/invalid."""
    try:
        return float(val) if val.strip() else default
    except (ValueError, TypeError):
        return default


def _int(val: str, default: int = 0) -> int:
    """Parse CSV string to int; return default for empty/invalid."""
    try:
        f = float(val)
        return int(f)
    except (ValueError, TypeError):
        return default


def _bool(val: str) -> bool:
    """Parse 'Yes'/'No'/'True'/'False'/'T'/'F' etc. to bool."""
    return val.strip().lower() in {"yes", "true", "t", "1"}


def _str(val: str) -> str:
    """Strip whitespace from string field."""
    return val.strip()


def _device_id(device_info: str) -> str:
    """
    Compute a deterministic, collision-resistant device ID.
    Returns empty string if the device info is too generic.
    """
    normalized = device_info.strip().lower()
    if normalized in _GENERIC_DEVICE_INFO or len(normalized) < _MIN_DEVICE_INFO_LEN:
        return ""
    return "DEV-" + hashlib.sha256(normalized.encode()).hexdigest()[:16].upper()


def _is_specific_device(device_info: str) -> bool:
    """True if DeviceInfo is specific enough to create a DeviceProfile vertex."""
    return bool(_device_id(device_info))


# ---------------------------------------------------------------------------
# Customer set loading
# ---------------------------------------------------------------------------

def load_benchmark_customer_ids(case_pack_path: Path) -> Set[str]:
    """
    Extract the 20 benchmark customer IDs from case_pack.csv.
    Returns a set of customer_id strings (e.g. {'C12382', 'C11891', ...}).
    """
    ids: Set[str] = set()
    with open(case_pack_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["customer_id"].strip()
            if cid:
                ids.add(cid)
    logger.info("Loaded %d benchmark customer IDs from %s", len(ids), case_pack_path)
    return ids


# ---------------------------------------------------------------------------
# Closed cases extraction (ALL rows — no customer filter)
# ---------------------------------------------------------------------------

def extract_closed_cases(
    closed_cases_path: Path,
) -> Iterator[dict]:
    """
    Yield one record dict per closed case.
    ALL 5,565 rows are extracted (not benchmark-scoped).
    """
    with open(closed_cases_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                # Vertex attributes
                "case_id":            _str(row["case_id"]),
                "customer_id":        _str(row["customer_id"]),
                "card_id":            _str(row["card_id"]),
                "opened_at":          _str(row["opened_at"]),
                "closed_at":          _str(row["closed_at"]),
                "outcome":            _str(row["outcome"]),
                "pattern":            _str(row["pattern"]),
                "first_fraud_txn_id": _str(row["first_fraud_txn_id"]),
                "txn_ids":            _str(row["txn_ids"]),         # pipe-separated
                "n_txns":             _int(row["n_txns"]),
                "exposure_usd":       _float(row["exposure_usd"], 0.0),
                "connected_card_ids": _str(row["connected_card_ids"]),
                "actions_taken":      _str(row["actions_taken"]),
                "report_filed":       _bool(row["report_filed"]),
                "analyst_notes":      _str(row["analyst_notes"]),
                # Derived
                "_txn_ids_list": [
                    t.strip() for t in row["txn_ids"].split("|") if t.strip()
                ],
                "_connected_cards_list": [
                    c.strip() for c in row["connected_card_ids"].split("|") if c.strip()
                ],
            }


# ---------------------------------------------------------------------------
# Case pack extraction
# ---------------------------------------------------------------------------

def extract_case_pack(case_pack_path: Path) -> List[dict]:
    """
    Extract all 20 benchmark investigation cases from case_pack.csv.
    """
    records = []
    with open(case_pack_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            records.append({
                "case_id":         _str(row["case_id"]),
                "opened_at":       _str(row["opened_at"]),
                "trigger_type":    _str(row["trigger_type"]),
                "trigger_text":    _str(row["trigger_text"]),
                "flagged_txn_id":  _str(row["flagged_txn_id"]),
                "card_id":         _str(row["card_id"]),
                "customer_id":     _str(row["customer_id"]),
                "initial_risk_score": _float(row["risk_score"], 0.0),
                # Initial status fields (will be updated by investigation)
                "case_status":     "open",
                "outcome":         "pending",
                "pattern":         "",
                "exposure_usd":    0.0,
                "actions_taken":   "",
                "sar_required":    False,
                "findings_summary": "",
                "evidence_json":   "[]",
                "nba_before_evidence": "",
                "nba_after_evidence":  "",
                "closed_at":       "",
            })
    logger.info("Extracted %d benchmark cases from %s", len(records), case_pack_path)
    return records


# ---------------------------------------------------------------------------
# Transaction extraction (benchmark-scoped)
# ---------------------------------------------------------------------------

def extract_transactions(
    transactions_path: Path,
    customer_ids: Set[str],
    progress_every: int = 50_000,
) -> Iterator[dict]:
    """
    Yield transaction records for the given customer_ids only.
    Scans the full transactions.csv but discards rows not in customer_ids.
    
    Only investigation-relevant columns are retained; V1-V339, C3-C14,
    D2-D15, M1-M3, M7-M9, and other undocumented columns are discarded.
    """
    total = 0
    matched = 0
    with open(transactions_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if total % progress_every == 0:
                logger.info(
                    "Scanned %d transactions, matched %d for %d customers",
                    total, matched, len(customer_ids),
                )
            cid = row["customer_id"].strip()
            if cid not in customer_ids:
                continue
            matched += 1
            txn_id = _str(row["TransactionID"])
            yield {
                "txn_id":         txn_id,
                "customer_id":    cid,
                "amount":         _float(row["TransactionAmt"], 0.0),
                "txn_timestamp":  _str(row["ts"]),         # "YYYY-MM-DD HH:MM:SS"
                "channel":        _str(row["channel"]),    # online | in_person
                "product_cd":     _str(row["ProductCD"]),  # H/W/C/S/R
                "addr1":          _float(row["addr1"], _MISSING_FLOAT),
                "dist1":          _float(row["dist1"], _MISSING_FLOAT),
                "p_email_domain": _str(row["P_emaildomain"]),
                "r_email_domain": _str(row["R_emaildomain"]),
                "card1_token":    _str(row["card1"]),
                "card_network":   _str(row["card4"]),      # visa/mastercard/amex/discover
                "card_type":      _str(row["card6"]),      # credit/debit
                "c1":             _float(row["C1"]),
                "c2":             _float(row["C2"]),
                "d1":             _float(row["D1"]),
                "m4":             _str(row["M4"]),
                "m5":             _str(row["M5"]),
                "m6":             _str(row["M6"]),
                "risk_score":     _float(row["risk_score"], 0.0),
                "transaction_dt": _int(row["TransactionDT"]),
            }
    logger.info(
        "Extraction complete: %d total rows scanned, %d matched for %d customers",
        total, matched, len(customer_ids),
    )


# ---------------------------------------------------------------------------
# Identity extraction (benchmark-scoped, with device specificity filter)
# ---------------------------------------------------------------------------

def extract_identity(
    identity_path: Path,
    txn_id_set: Set[str],
) -> Iterator[dict]:
    """
    Yield identity records for the given TransactionID set only.
    Filters out generic device strings (see _GENERIC_DEVICE_INFO).
    
    Note: Only transactions that pass the specificity filter get a
    DeviceProfile vertex. Others are silently skipped.
    """
    matched = 0
    skipped_generic = 0
    with open(identity_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_id = row["TransactionID"].strip()
            if txn_id not in txn_id_set:
                continue
            device_info = _str(row["DeviceInfo"])
            device_type = _str(row["DeviceType"])
            did = _device_id(device_info)
            if not did:
                skipped_generic += 1
                continue
            matched += 1
            yield {
                "txn_id":               txn_id,
                "device_id":            did,
                "device_type":          device_type,
                "device_info":          device_info,
                "device_info_normalized": device_info.strip().lower(),
            }
    logger.info(
        "Identity extraction: %d specific devices matched, %d generic skipped",
        matched, skipped_generic,
    )
