"""Python reference validator for a versioned ledger checkpoint contract."""
import hashlib
import json
import math

VERSION = "ledger-checkpoint-v1.0.0"


def fingerprint(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def defaults():
    return {"initialized": False, "sequence": 0, "fingerprint": "", "daily_status": "UNKNOWN",
            "risk_status": "POLICY_DATA_UNKNOWN", "new_entries_blocked": True,
            "protect_existing_positions": True, "daily": {}, "risk": {}}


def _fail(state, reason):
    state["daily_status"] = "UNKNOWN"
    state["risk_status"] = "POLICY_DATA_UNKNOWN"
    state["new_entries_blocked"] = True
    state["protect_existing_positions"] = True
    state["reason"] = reason
    return False, "CHECKPOINT_REJECTED"


def restore(state, checkpoint, expected, now_utc):
    p = checkpoint.get("payload", {})
    required = ("config_version", "account_epoch_id", "account_id", "broker_server", "account_currency",
                "checkpoint_sequence", "captured_at_utc", "max_age_seconds", "daily_snapshot_id",
                "risk_source_snapshot_id", "risk_content_fingerprint", "policy_id", "initial_capital",
                "reset_status", "prague_day_id", "day_index", "reset_at_utc", "balance_at_reset",
                "highest_reset_balance", "daily_floor", "overall_floor", "account_mode",
                "reconciliation_valid", "new_entries_blocked", "protect_existing_positions",
                "risk_status", "risk_captured_at_utc", "risk_event_sequence", "deal_watermark",
                "position_count", "working_order_count", "deal_count", "initial_risk_money",
                "projected_loss_to_sl_money", "remaining_loss_to_sl_money", "floating_pnl_after_costs",
                "locked_profit_money", "equity_after_costs", "equity_floor_headroom_money",
                "floor_headroom_after_ledger_risk_money")
    if (checkpoint.get("schema_version") != VERSION or checkpoint.get("integrity_marker") != "CHECKPOINT_OK" or
            not checkpoint.get("fingerprint") or fingerprint(p) != checkpoint.get("fingerprint") or
            any(k not in p for k in required) or
            any(not p.get(k) or p.get(k) != expected.get(k) for k in
                ("config_version", "account_epoch_id", "account_id", "broker_server", "account_currency")) or
            p.get("checkpoint_sequence", 0) <= 0 or p.get("captured_at_utc", 0) <= 0 or
            p.get("max_age_seconds", 0) <= 0 or now_utc < p["captured_at_utc"] or
            now_utc - p["captured_at_utc"] > p["max_age_seconds"] or
            not p.get("daily_snapshot_id") or not p.get("risk_source_snapshot_id") or
            not p.get("risk_content_fingerprint") or p.get("reset_status") != "OK" or
            p.get("risk_status") != "RECONCILED" or p.get("reconciliation_valid") is not True or
            p.get("protect_existing_positions") is not True or
            p.get("account_mode") not in {"HEDGING", "NETTING"} or
            p.get("policy_id") not in {"FTMO_1_STEP", "FTMO_2_STEP"} or
            p.get("day_index", -1) < 0 or p.get("reset_at_utc", 0) > p.get("captured_at_utc", 0) or
            not all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k]) for k in
                    ("initial_capital", "balance_at_reset", "highest_reset_balance", "daily_floor", "overall_floor",
                     "initial_risk_money", "projected_loss_to_sl_money", "remaining_loss_to_sl_money",
                     "floating_pnl_after_costs", "locked_profit_money", "equity_after_costs",
                     "equity_floor_headroom_money", "floor_headroom_after_ledger_risk_money")) or
            p["initial_capital"] <= 0 or p["equity_after_costs"] <= 0 or
            any(p[k] < 0 for k in ("initial_risk_money", "projected_loss_to_sl_money",
                                   "remaining_loss_to_sl_money", "locked_profit_money")) or
            p["new_entries_blocked"] != (p["floor_headroom_after_ledger_risk_money"] <= 0) or
            not math.isclose(p["equity_floor_headroom_money"] - p["remaining_loss_to_sl_money"],
                             p["floor_headroom_after_ledger_risk_money"], rel_tol=0, abs_tol=1e-7)):
        return _fail(state, "CHECKPOINT_MISSING_TORN_STALE_OR_INCOMPATIBLE")

    seq, fp = p["checkpoint_sequence"], checkpoint["fingerprint"]
    if state["initialized"]:
        if seq == state["sequence"] and fp == state["fingerprint"]:
            return True, "CHECKPOINT_REPLAY_IGNORED"
        if seq <= state["sequence"]:
            return _fail(state, "CHECKPOINT_REPLAY_OR_SEQUENCE_REGRESSION")
    state.update(initialized=True, sequence=seq, fingerprint=fp, daily_status="UNKNOWN",
                 risk_status="POLICY_DATA_UNKNOWN", new_entries_blocked=True,
                 protect_existing_positions=True,
                 reason="CURRENT_RESET_AND_BROKER_RECONCILIATION_REQUIRED_AFTER_RESTART",
                 daily={k: p[k] for k in ("policy_id", "config_version", "account_epoch_id", "account_currency",
                                          "initial_capital", "daily_snapshot_id", "prague_day_id", "day_index",
                                          "reset_at_utc", "balance_at_reset", "highest_reset_balance", "daily_floor",
                                          "overall_floor")},
                 risk={k: p[k] for k in ("account_id", "broker_server", "account_currency", "account_mode",
                                         "risk_source_snapshot_id", "risk_content_fingerprint", "risk_captured_at_utc",
                                         "risk_event_sequence", "deal_watermark", "position_count", "working_order_count",
                                         "deal_count", "initial_risk_money", "projected_loss_to_sl_money",
                                         "remaining_loss_to_sl_money", "floating_pnl_after_costs", "locked_profit_money",
                                         "equity_after_costs", "equity_floor_headroom_money",
                                         "floor_headroom_after_ledger_risk_money")})
    return True, "CHECKPOINT_RESTORED_PENDING_RESET_AND_BROKER_RECONCILIATION"


def reattest_daily(state, fresh, current_prague_day_id):
    historical = state["daily"]
    fields = ("config_version", "account_epoch_id", "account_currency", "prague_day_id",
              "day_index", "reset_at_utc", "balance_at_reset")
    if (state["daily_status"] != "UNKNOWN" or state.get("reason") not in
            {"CURRENT_RESET_AND_BROKER_RECONCILIATION_REQUIRED_AFTER_RESTART",
             "CURRENT_PRAGUE_RESET_REATTESTATION_FAILED"}):
        return False
    if (not current_prague_day_id or
            fresh.get("prague_day_id") != current_prague_day_id or
            fresh.get("snapshot_id") != historical.get("daily_snapshot_id") or
            any(fresh.get(k) != historical.get(k) for k in fields) or
            fresh.get("prague_midnight_confirmed") is not True or fresh.get("data_quality") != "OK"):
        state["daily_status"] = "UNKNOWN"
        state["reason"] = "CURRENT_PRAGUE_RESET_REATTESTATION_FAILED"
        return False
    state["daily_status"] = "OK"
    state["reason"] = "CURRENT_PRAGUE_RESET_REATTESTED"
    return True
