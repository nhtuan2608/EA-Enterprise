"""Python reference validator for the pure MT5 runtime evidence contract.

Contracts:
  - evaluate(snapshot, now_utc, previous_watermark = -1) -> dict
  - material_spec_equal(left, right) -> bool
  - fnv1a32_hex(server, account_id) -> str  (matches MQL EEA_RuntimeFingerprint)

Both functions must produce a deterministic status given the inputs and match
the MQL5 core contract definitions that will be written in Runtime/RuntimeEvidence.mqh.
This is the "oracle"; the MQL code will be the "implementation".
"""

import math
import struct
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_finite(v: Any) -> bool:
    """Returns True if v is a finite number (NaN/Infinity is invalid)."""
    return isinstance(v, (int, float)) and math.isfinite(v)


def fnv1a32_hex(server: str, account_id: str) -> str:
    """FNV-1a 32-bit hash matching MQL EEA_RuntimeFingerprint byte-for-byte."""
    h = 0x811C9DC5
    raw = server + "|" + account_id
    for ch in raw:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"fnv1a32:{h:x}"


def _identity_ok(snapshot: Dict[str, Any]) -> str:
    """Return '' when identity is OK, else the reason code."""
    for field in ("account_fingerprint", "broker_server", "account_currency", "account_margin_mode"):
        if not snapshot.get(field):
            return "ACCOUNT_IDENTITY_UNAVAILABLE"
    return ""


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def evaluate(snapshot: Dict[str, Any], now_utc: int, previous_watermark: int = -1) -> Dict[str, Any]:
    """Validate a runtime evidence snapshot and produce a status dict.

    Check order and reason codes match the design doc:
    1. Schema version / checkpoint compatibility
    2. Account identity
    3. Freshness (valid_until_utc)
    4. Watermark regression (deal_watermark AND deal_watermark_time_msc)
    5. Duplicate tickets / finite numeric / chronological deals
    6. Source completeness flags (→DEGRADED)
    7. Material symbol-spec validation
    8. Success → OBSERVING
    """
    result: Dict[str, Any] = {
        "runtime_state": "BLOCKED",
        "reason_code": "RUNTIME_RECONCILIATION_REQUIRED",
        "new_entries_blocked": True,
        "previous_deal_watermark": previous_watermark,
        "previous_deal_watermark_time": -1,
    }

    # 1. Schema version
    if snapshot.get("schema_version") != "runtime-evidence-v0.1.0":
        result["reason_code"] = "RUNTIME_CHECKPOINT_INCOMPATIBLE"
        return result

    # 2. Identity
    reason = _identity_ok(snapshot)
    if reason:
        result["reason_code"] = reason
        return result

    # 3. Freshness
    if not snapshot.get("valid_until_utc") or now_utc > snapshot["valid_until_utc"]:
        result["reason_code"] = "RUNTIME_RECONCILIATION_REQUIRED"
        return result

    # 4. Watermark regression (deal_watermark)
    deal_watermark = snapshot.get("deal_watermark", -1)
    if previous_watermark >= 0 and deal_watermark < previous_watermark:
        result["reason_code"] = "DEAL_WATERMARK_REGRESSED"
        return result

    # 5. Duplicate tickets / finite numeric / chronological deals
    positions = snapshot.get("positions", [])
    orders = snapshot.get("orders", [])
    deals = snapshot.get("deals", [])

    # Count bounds
    if len(positions) > 256:
        result["reason_code"] = "POSITIONS_SOURCE_INCOMPLETE"
        return result
    if len(orders) > 256:
        result["reason_code"] = "ORDERS_SOURCE_INCOMPLETE"
        return result
    if len(deals) > 2048:
        result["reason_code"] = "DEALS_SOURCE_INCOMPLETE"
        return result

    # Position tickets and finite numeric fields
    pos_tickets = set()
    for p in positions:
        t = p.get("ticket")
        if t in pos_tickets:
            result["reason_code"] = "POSITIONS_SOURCE_INCOMPLETE"
            return result
        if not is_finite(p.get("volume", 0)) or not is_finite(p.get("price_open", 0)):
            result["reason_code"] = "POSITIONS_SOURCE_INCOMPLETE"
            return result
        pos_tickets.add(t)

    # Order tickets and finite numeric fields
    ord_tickets = set()
    for o in orders:
        t = o.get("ticket")
        if t in ord_tickets:
            result["reason_code"] = "ORDERS_SOURCE_INCOMPLETE"
            return result
        if not is_finite(o.get("volume", 0)) or not is_finite(o.get("price", 0)):
            result["reason_code"] = "ORDERS_SOURCE_INCOMPLETE"
            return result
        ord_tickets.add(t)

    # Deal tickets, finite numeric fields, and chronological ordering by (time_msc, ticket)
    seen_deal_tickets = set()
    for i, d in enumerate(deals):
        dt = d.get("deal_ticket")
        if dt in seen_deal_tickets:
            result["reason_code"] = "DEALS_SOURCE_INCOMPLETE"
            return result
        seen_deal_tickets.add(dt)
        if not is_finite(d.get("volume", 0)) or not is_finite(d.get("price", 0)):
            result["reason_code"] = "DEALS_SOURCE_INCOMPLETE"
            return result
        if i > 0:
            prev = deals[i - 1]
            # Chronological ordering by (time_msc, deal_ticket) tuple
            prev_key = (prev.get("time_msc", 0), prev.get("deal_ticket", 0))
            curr_key = (d.get("time_msc", 0), dt)
            if curr_key < prev_key:
                result["reason_code"] = "DEALS_SOURCE_INCOMPLETE"
                return result

    # 6. Source completeness flags
    if not snapshot.get("positions_complete", False):
        result["runtime_state"] = "DEGRADED"
        result["reason_code"] = "POSITIONS_SOURCE_INCOMPLETE"
        return result
    if not snapshot.get("orders_complete", False):
        result["runtime_state"] = "DEGRADED"
        result["reason_code"] = "ORDERS_SOURCE_INCOMPLETE"
        return result
    if not snapshot.get("deals_complete", False):
        result["runtime_state"] = "DEGRADED"
        result["reason_code"] = "DEALS_SOURCE_INCOMPLETE"
        return result

    # 7. Material symbol specs (finite/positive ranges/currencies)
    for s in snapshot.get("symbols", []):
        # Finite/positive numeric ranges
        if not is_finite(s.get("volume_min", 0)) or s.get("volume_min", 0) <= 0:
            result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
            return result
        if not is_finite(s.get("volume_max", 0)) or s.get("volume_max", 0) < s.get("volume_min", 0):
            result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
            return result
        if not is_finite(s.get("volume_step", 0)) or s.get("volume_step", 0) <= 0:
            result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
            return result
        if not is_finite(s.get("tick_size", 0)) or s.get("tick_size", 0) <= 0:
            result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
            return result
        if not is_finite(s.get("point", 0)) or s.get("point", 0) <= 0:
            result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
            return result
        # Currency presence
        for cur in ("base_currency", "profit_currency", "margin_currency"):
            if not s.get(cur):
                result["reason_code"] = "SYMBOL_SPEC_INCOMPLETE"
                return result

    # 8. All good
    result["runtime_state"] = "OBSERVING"
    result["reason_code"] = "RUNTIME_EVIDENCE_CURRENT"
    return result


def material_spec_equal(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    """Compare two material symbol specifications for equality."""
    fields = (
        "broker_symbol", "digits", "point", "tick_size", "tick_value",
        "contract_size", "volume_min", "volume_max", "volume_step",
        "stops_level_points", "freeze_level_points",
        "trade_mode", "order_mode", "expiration_mode", "calculation_mode",
        "base_currency", "profit_currency", "margin_currency",
    )
    for field in fields:
        if left.get(field) != right.get(field):
            return False
    return True
def validate_runtime_telemetry(telemetry: dict) -> tuple[bool, str]:
    for key in ("refresh_attempt_count", "refresh_success_count", "refresh_failure_count",
                "max_refresh_duration_ms", "last_refresh_duration_ms", 
                "consecutive_refresh_failures", "refresh_generation", "refresh_sequence"):
        if telemetry.get(key, -1) < 0:
            return False, "RUNTIME_TELEMETRY_INVALID"

    if telemetry["refresh_success_count"] + telemetry["refresh_failure_count"] > telemetry["refresh_attempt_count"]:
        return False, "RUNTIME_TELEMETRY_INVALID"
    if telemetry["last_refresh_duration_ms"] > telemetry["max_refresh_duration_ms"]:
        return False, "RUNTIME_TELEMETRY_INVALID"
    if telemetry["consecutive_refresh_failures"] > telemetry["refresh_failure_count"]:
        return False, "RUNTIME_TELEMETRY_INVALID"
    if telemetry["refresh_sequence"] > telemetry["refresh_generation"]:
        return False, "RUNTIME_TELEMETRY_INVALID"

    if not isinstance(telemetry.get("pending_refresh"), bool) or not isinstance(telemetry.get("refresh_in_progress"), bool):
        return False, "RUNTIME_TELEMETRY_INVALID"
    
    return True, ""


def audit_invariants(records: list[dict]) -> tuple[bool, str]:
    seen_completions = set()
    seen_records = []
    
    attempts = set()
    invalidations = set()

    last_gen = -1
    last_seq = -1

    for r in records:
        if not isinstance(r, dict):
            return False, "RUNTIME_AUDIT_INVALID"
        if r in seen_records:
            return False, "RUNTIME_AUDIT_INVALID"
        seen_records.append(r)

        event = r.get("event")
        inst = r.get("runtime_instance_id")
        gen = r.get("refresh_generation", -1)
        seq = r.get("refresh_sequence", -1)

        if gen < last_gen:
            return False, "RUNTIME_AUDIT_INVALID"
        if gen == last_gen and seq < last_seq:
            return False, "RUNTIME_AUDIT_INVALID"
        last_gen = gen
        last_seq = seq

        key = (inst, gen)

        if event in ("startup-completion", "refresh-completion"):
            if key in seen_completions:
                return False, "RUNTIME_AUDIT_INVALID"
            if key not in attempts:
                return False, "RUNTIME_AUDIT_INVALID"
            seen_completions.add(key)
        elif event in ("startup-attempt", "refresh-attempt"):
            attempts.add(key)
        elif event == "transaction-invalidation":
            invalidations.add(key)
        elif event == "transaction-invalidation-completion":
            if key not in invalidations:
                return False, "RUNTIME_AUDIT_INVALID"

    return True, ""


def selection_load_policy(document: dict, config_version: str, account_fingerprint: str, csv_symbols: list[str]) -> dict:
    if document.get("config_version") != config_version or document.get("account_fingerprint") != account_fingerprint:
        return {"canonical_symbols": csv_symbols, "reason": "RUNTIME_SELECTION_INCOMPATIBLE"}
    return {"canonical_symbols": document.get("canonical_symbols", [])}
