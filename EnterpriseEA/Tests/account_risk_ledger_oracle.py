"""Pure snapshot reducer for synthetic account-wide risk ledger fixtures."""
from copy import deepcopy
import math

ORIGINS = {"EA", "MANUAL", "OTHER_EA"}
MODES = {"HEDGING", "NETTING"}


def defaults():
    return {"initialized": False, "reconciliation_valid": False, "new_entries_blocked": True,
            "protect_existing_positions": True, "ledger_status": "POLICY_DATA_UNKNOWN",
            "last_transition": "NONE", "reason_code": "ACCOUNT_WIDE_SNAPSHOT_REQUIRED",
            "config_version": "", "account_id": "", "broker_server": "", "account_currency": "",
            "account_mode": "", "last_event_id": "", "last_snapshot_id": "",
            "last_content_fingerprint": "",
            "last_captured_at_utc": 0, "last_event_sequence": 0, "last_deal_watermark": 0,
            "position_count": 0, "working_order_count": 0, "deal_count": 0,
            "initial_risk_money": 0.0, "projected_loss_to_sl_money": 0.0,
            "remaining_loss_to_sl_money": 0.0, "floating_pnl_after_costs": 0.0,
            "locked_profit_money": 0.0, "equity_after_costs": 0.0,
            "equity_floor_headroom_money": 0.0, "floor_headroom_after_ledger_risk_money": 0.0}


def _finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def _unknown(ledger, reason, transition="REJECTED"):
    ledger.update(reconciliation_valid=False, new_entries_blocked=True,
                  protect_existing_positions=True, ledger_status="POLICY_DATA_UNKNOWN",
                  last_transition=transition, reason_code=reason)
    return False


def _validate(s, positions, orders, deals, now):
    required = ("config_version", "account_id", "broker_server", "account_currency", "event_id",
                "source_snapshot_id", "positions_snapshot_id", "orders_snapshot_id", "deals_snapshot_id",
                "policy_snapshot_id", "content_fingerprint")
    if (any(not s.get(k) for k in required) or s.get("account_mode") not in MODES or
            s.get("event_sequence", 0) <= 0 or s.get("captured_at_utc", 0) <= 0 or
            s.get("max_age_seconds", 0) <= 0 or now < s["captured_at_utc"] or
            now - s["captured_at_utc"] > s["max_age_seconds"] or
            s.get("data_quality") != "OK" or s.get("reconciliation_status") != "RECONCILED" or
            s.get("account_scope") != "ACCOUNT_WIDE" or
            not all(s.get(k) for k in ("positions_complete", "orders_complete", "deals_complete",
                                        "manual_activity_included", "other_ea_activity_included",
                                        "cash_flows_reconciled", "costs_reconciled",
                                        "account_mode_reconciled", "policy_headroom_valid")) or
            s.get("policy_quality") != "OK" or s.get("policy_config_version") != s.get("config_version") or
            s.get("policy_currency") != s.get("account_currency")):
        return "ACCOUNT_WIDE_SNAPSHOT_OR_POLICY_EVIDENCE_MISSING"
    if (not _finite(s.get("equity_after_costs")) or s["equity_after_costs"] <= 0 or
            not _finite(s.get("equity_floor_headroom_money"))):
        return "ACCOUNT_EQUITY_OR_FLOOR_HEADROOM_INVALID"

    ids, net_symbols = set(), set()
    sums = [0.0, 0.0, 0.0, 0.0, 0.0]
    for p in positions:
        if (not p.get("position_id") or p.get("origin") not in ORIGINS or
                not p.get("canonical_symbol") or not p.get("broker_symbol") or
                p.get("direction") not in {"LONG", "SHORT"} or
                p.get("config_version") != s["config_version"] or
                p.get("account_currency") != s["account_currency"] or
                p.get("risk_lineage_valid") is not True or
                not _finite(p.get("volume")) or p["volume"] <= 0 or
                not _finite(p.get("initial_risk_money")) or p["initial_risk_money"] <= 0 or
                not _finite(p.get("projected_loss_to_sl")) or p["projected_loss_to_sl"] <= 0 or
                not _finite(p.get("remaining_loss_to_sl")) or p["remaining_loss_to_sl"] < 0 or
                not _finite(p.get("floating_pnl_after_costs")) or
                not _finite(p.get("locked_profit_money")) or p["locked_profit_money"] < 0):
            return "POSITION_ROW_INVALID"
        if p["position_id"] in ids:
            return "DUPLICATE_POSITION_ID"
        ids.add(p["position_id"])
        if s["account_mode"] == "NETTING" and p["broker_symbol"] in net_symbols:
            return "NETTING_DUPLICATE_SYMBOL_POSITION"
        net_symbols.add(p["broker_symbol"])
        for n, key in enumerate(("initial_risk_money", "projected_loss_to_sl", "remaining_loss_to_sl",
                                 "floating_pnl_after_costs", "locked_profit_money")):
            sums[n] += p[key]

    order_ids = set()
    for row in orders:
        if (not row.get("order_id") or row.get("origin") not in ORIGINS or
                not row.get("canonical_symbol") or not row.get("broker_symbol") or
                row.get("order_status") not in {"WORKING", "PARTIAL"} or
                row.get("config_version") != s["config_version"] or
                row.get("account_currency") != s["account_currency"] or
                not _finite(row.get("remaining_volume")) or row["remaining_volume"] <= 0 or
                not _finite(row.get("projected_loss_to_sl")) or row["projected_loss_to_sl"] <= 0 or
                not _finite(row.get("remaining_loss_to_sl")) or row["remaining_loss_to_sl"] < 0):
            return "WORKING_ORDER_ROW_INVALID"
        if row["order_id"] in order_ids:
            return "DUPLICATE_WORKING_ORDER_ID"
        order_ids.add(row["order_id"])
        sums[1] += row["projected_loss_to_sl"]
        sums[2] += row["remaining_loss_to_sl"]

    deal_ids, previous_seq = set(), 0
    for d in deals:
        if (not d.get("deal_id") or d.get("origin") not in ORIGINS or
                d.get("config_version") != s["config_version"] or
                d.get("account_currency") != s["account_currency"] or
                d.get("deal_kind") not in {"TRADE", "COMMISSION", "SWAP", "FEE", "DEPOSIT", "WITHDRAWAL"} or
                d.get("sequence", 0) <= previous_seq or d["sequence"] > s.get("deal_watermark", -1) or
                not _finite(d.get("money"))):
            return "DEAL_HISTORY_INVALID_OR_OUT_OF_ORDER"
        if d["deal_id"] in deal_ids:
            return "DUPLICATE_DEAL_ID"
        deal_ids.add(d["deal_id"])
        previous_seq = d["sequence"]
    if s.get("deal_watermark", -1) < max((d["sequence"] for d in deals), default=0) or s.get("deal_watermark", -1) < 0:
        return "DEAL_WATERMARK_INVALID"
    if not all(math.isfinite(v) for v in sums):
        return "LEDGER_TOTAL_OVERFLOW"
    return None


def apply_snapshot(ledger, snapshot, positions, orders, deals, now_utc):
    reason = _validate(snapshot, positions, orders, deals, now_utc)
    if reason:
        return _unknown(ledger, reason)
    if ledger["initialized"]:
        if (snapshot["event_id"] == ledger["last_event_id"] and
                snapshot["source_snapshot_id"] == ledger["last_snapshot_id"] and
                snapshot["event_sequence"] == ledger["last_event_sequence"]):
            if snapshot["content_fingerprint"] != ledger["last_content_fingerprint"]:
                return _unknown(ledger, "SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT")
            if not ledger["reconciliation_valid"]:
                ledger.update(last_transition="DUPLICATE_IGNORED",
                              reason_code="DUPLICATE_SNAPSHOT_WHILE_LEDGER_UNKNOWN")
                return False
            ledger.update(last_transition="DUPLICATE_IGNORED", reason_code="DUPLICATE_SNAPSHOT_NO_STATE_CHANGE")
            return True
        if snapshot["event_id"] == ledger["last_event_id"] or snapshot["source_snapshot_id"] == ledger["last_snapshot_id"]:
            return _unknown(ledger, "SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT")
        if any(snapshot[k] != ledger[lk] for k, lk in (
                ("config_version", "config_version"), ("account_id", "account_id"),
                ("broker_server", "broker_server"), ("account_currency", "account_currency"),
                ("account_mode", "account_mode"))):
            return _unknown(ledger, "ACCOUNT_IDENTITY_OR_MODE_CHANGED")
        if (snapshot["event_sequence"] <= ledger["last_event_sequence"] or
                snapshot["captured_at_utc"] <= ledger["last_captured_at_utc"] or
                snapshot["deal_watermark"] < ledger["last_deal_watermark"]):
            return _unknown(ledger, "OUT_OF_ORDER_ACCOUNT_SNAPSHOT")

    initial = sum(p["initial_risk_money"] for p in positions)
    projected = sum(p["projected_loss_to_sl"] for p in positions) + sum(o["projected_loss_to_sl"] for o in orders)
    remaining = sum(p["remaining_loss_to_sl"] for p in positions) + sum(o["remaining_loss_to_sl"] for o in orders)
    floating = sum(p["floating_pnl_after_costs"] for p in positions)
    locked = sum(p["locked_profit_money"] for p in positions)
    after_floor = snapshot["equity_floor_headroom_money"] - remaining
    if not all(math.isfinite(v) for v in (initial, projected, remaining, floating, locked, after_floor)):
        return _unknown(ledger, "LEDGER_TOTAL_OVERFLOW")
    ledger.update(initialized=True, reconciliation_valid=True,
                  new_entries_blocked=after_floor <= 0, protect_existing_positions=True,
                  ledger_status="RECONCILED", last_transition="SNAPSHOT_APPLIED",
                  reason_code="RECONCILED_BUT_FLOOR_HEADROOM_EXHAUSTED" if after_floor <= 0 else "ACCOUNT_WIDE_SNAPSHOT_RECONCILED",
                  config_version=snapshot["config_version"], account_id=snapshot["account_id"],
                  broker_server=snapshot["broker_server"], account_currency=snapshot["account_currency"],
                  account_mode=snapshot["account_mode"], last_event_id=snapshot["event_id"],
                  last_snapshot_id=snapshot["source_snapshot_id"], last_captured_at_utc=snapshot["captured_at_utc"],
                  last_content_fingerprint=snapshot["content_fingerprint"],
                  last_event_sequence=snapshot["event_sequence"], last_deal_watermark=snapshot["deal_watermark"],
                  position_count=len(positions), working_order_count=len(orders), deal_count=len(deals),
                  initial_risk_money=initial, projected_loss_to_sl_money=projected,
                  remaining_loss_to_sl_money=remaining, floating_pnl_after_costs=floating,
                  locked_profit_money=locked, equity_after_costs=snapshot["equity_after_costs"],
                  equity_floor_headroom_money=snapshot["equity_floor_headroom_money"],
                  floor_headroom_after_ledger_risk_money=after_floor)
    return True
