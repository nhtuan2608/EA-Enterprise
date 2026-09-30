"""Reference state gate for synthetic dry-run composition cases only."""
from copy import deepcopy
import math

STAGES = ("SYMBOL", "CANDIDATE", "LEVELS", "ECONOMICS", "FTMO", "PORTFOLIO", "VOLUME")


def evaluate(ctx):
    stable_candidate_id = ""
    def finish(status, reason):
        return {"decision_status": status, "reason_codes": [reason],
                "candidate_id": stable_candidate_id, "final_volume": 0, "projected_loss": 0, "net_reward_risk": 0}

    if any(not ctx.get(k) for k in ("config_version", "setup_config_version", "account_currency",
                                     "canonical_symbol", "broker_symbol", "broker_server",
                                     "levels_snapshot_id", "portfolio_snapshot_id",
                                     "volume_quote_snapshot_id")) or ctx.get("evaluated_at_utc", 0) <= 0:
        return finish("UNKNOWN", "DRY_RUN_CONTEXT_INCOMPLETE")

    by_stage = {}
    reasons = []
    blocked = False
    if len(ctx.get("evidence", [])) != len(STAGES) or any(r.get("stage") not in STAGES for r in ctx.get("evidence", [])):
        return finish("UNKNOWN", "EVIDENCE_STAGE_SET_INVALID")
    for stage in STAGES:
        records = [r for r in ctx.get("evidence", []) if r.get("stage") == stage]
        if len(records) != 1:
            reasons.append(f"{stage}_EVIDENCE_MISSING_OR_DUPLICATE")
            continue
        ev = records[0]
        by_stage[stage] = ev
        age = ctx["evaluated_at_utc"] - ev.get("captured_at_utc", 0)
        if (ev.get("quality") != "OK" or not ev.get("source_version") or
                not ev.get("source_snapshot_id") or ev.get("max_age_seconds", 0) <= 0 or
                age < 0 or age > ev["max_age_seconds"]):
            reasons.append("EVIDENCE_STALE_OR_INCOMPLETE")
            continue
        if any(ev.get(k) != ctx.get(ctx_key) for k, ctx_key in (
                ("config_version", "config_version"), ("account_currency", "account_currency"),
                ("canonical_symbol", "canonical_symbol"), ("broker_symbol", "broker_symbol"),
                ("broker_server", "broker_server"))):
            reasons.append("EVIDENCE_BINDING_MISMATCH")
            blocked = True
    if reasons:
        return {**finish("BLOCKED" if blocked else "UNKNOWN", reasons[0]), "reason_codes": reasons}

    sym = ctx["symbol"]
    if (not sym.get("resolved") or sym.get("status") != "RESOLVED" or
            any(sym.get(k) != ctx.get(k) for k in ("canonical_symbol", "broker_symbol", "broker_server")) or
            not sym.get("source_version") or not sym.get("metadata_version") or
            not sym.get("metadata_fingerprint")):
        return finish("BLOCKED", "SYMBOL_MAPPING_NOT_RESOLVED_OR_STALE")
    ev = by_stage["SYMBOL"]
    if ev["source_version"] != sym["source_version"] or ev["source_snapshot_id"] != sym["metadata_fingerprint"]:
        return finish("BLOCKED", "SYMBOL_SOURCE_SNAPSHOT_MISMATCH")

    c = ctx["candidate"]
    if c.get("canonical_symbol") != ctx["canonical_symbol"] or c.get("config_version") != ctx["setup_config_version"]:
        return finish("BLOCKED", "CANDIDATE_IDENTITY_OR_CONFIG_MISMATCH")
    stable_candidate_id = c.get("candidate_id", "")
    if (c.get("state") != "TRIGGERED" or c.get("setup_id") != "S02" or not c.get("candidate_id") or
            not c.get("timeframe") or c.get("expires_after_bars", 0) <= 0 or
            c.get("age_after_trigger_bars", -1) < 0 or
            c.get("age_after_trigger_bars", -1) >= c["expires_after_bars"] or
            c.get("direction") not in {"LONG", "SHORT"}):
        return finish("REJECTED", "CANDIDATE_NOT_FRESH_TRIGGERED_S02")
    ev = by_stage["CANDIDATE"]
    if ev["captured_at_utc"] < c.get("triggered_at_utc", 0):
        return finish("BLOCKED", "CANDIDATE_EVIDENCE_PREDATES_TRIGGER")
    if ev["source_version"] != c["config_version"] or ev["source_snapshot_id"] != c["candidate_id"]:
        return finish("BLOCKED", "CANDIDATE_SOURCE_SNAPSHOT_MISMATCH")
    if (c.get("triggered_at_utc", 0) <= 0 or c["triggered_at_utc"] > ctx["evaluated_at_utc"] or
            ctx["evaluated_at_utc"] - c["triggered_at_utc"] > ev["max_age_seconds"]):
        return finish("REJECTED", "CANDIDATE_TRIGGER_STALE_OR_INVALID")

    econ_i, econ = ctx["economics_input"], ctx["economics"]
    if econ_i.get("direction") not in {1, -1} or c["direction"] != ("LONG" if econ_i["direction"] == 1 else "SHORT"):
        return finish("BLOCKED", "CANDIDATE_DIRECTION_MISMATCH")
    levels = ctx["levels"]
    if (not levels.get("valid") or not _close(levels.get("stop_loss"), econ_i.get("stop_loss")) or
            not _close(levels.get("take_profit"), econ_i.get("take_profit"))):
        return finish("REJECTED", "STRUCTURAL_LEVELS_INVALID_OR_MISMATCHED")
    ev = by_stage["LEVELS"]
    if ev["source_version"] != ctx["setup_config_version"] or ev["source_snapshot_id"] != ctx["levels_snapshot_id"]:
        return finish("BLOCKED", "LEVELS_SOURCE_SNAPSHOT_MISMATCH")

    if (econ_i.get("config_version") != ctx["config_version"] or
            econ_i.get("account_currency") != ctx["account_currency"] or
            econ_i.get("quote_config_version") != ctx["config_version"] or
            econ_i.get("quote_currency") != ctx["account_currency"] or
            not econ_i.get("pricing_snapshot_id") or econ_i.get("quote_quality") != "OK" or
            not econ_i.get("target_space_confirmed") or not econ_i.get("execution_constraints_confirmed")):
        return finish("BLOCKED", "ECONOMICS_CONFIG_CURRENCY_OR_SNAPSHOT_MISMATCH")
    if not econ.get("valid") or econ.get("economics_status") == "UNKNOWN":
        return finish("UNKNOWN", "TRADE_ECONOMICS_UNKNOWN")
    if (not _positive_finite(econ_i.get("final_volume")) or
            not _positive_finite(econ_i.get("net_loss_at_sl_money")) or
            not _positive_finite(econ_i.get("net_gain_at_tp_money")) or
            not _positive_finite(econ_i.get("minimum_net_rr")) or
            not _positive_finite(econ.get("net_reward_risk"))):
        return finish("UNKNOWN", "ECONOMICS_FINAL_VOLUME_OR_LOSS_INVALID")
    ratio = econ_i["net_gain_at_tp_money"] / econ_i["net_loss_at_sl_money"]
    if (not _close(econ["net_reward_risk"], ratio) or
            not _close(econ.get("net_loss_at_sl_money"), econ_i["net_loss_at_sl_money"]) or
            not _close(econ.get("net_gain_at_tp_money"), econ_i["net_gain_at_tp_money"]) or
            not _close(econ_i.get("quote_volume"), econ_i["final_volume"]) or
            (econ.get("economics_status") == "ECONOMICS_ACCEPTABLE" and
             econ["net_reward_risk"] < econ_i["minimum_net_rr"])):
        return finish("BLOCKED", "ECONOMICS_RESULT_INPUT_MISMATCH")
    if econ.get("economics_status") != "ECONOMICS_ACCEPTABLE":
        return finish("REJECTED", "TRADE_ECONOMICS_REJECTED")
    ev = by_stage["ECONOMICS"]
    if ev["source_version"] != econ_i["quote_config_version"] or ev["source_snapshot_id"] != econ_i["pricing_snapshot_id"]:
        return finish("BLOCKED", "ECONOMICS_SOURCE_SNAPSHOT_MISMATCH")

    h = ctx["headroom"]
    if h.get("config_version") != ctx["config_version"] or not h.get("snapshot_id"):
        return finish("BLOCKED", "FTMO_CONFIG_OR_SNAPSHOT_MISMATCH")
    if (not h.get("calculation_valid") or h.get("calculation_status") != "OK" or
            h.get("headroom_status") == "POLICY_DATA_UNKNOWN" or
            not _positive_finite(h.get("proposed_stress_loss")) or
            not _positive_finite(h.get("available_headroom"))):
        return finish("UNKNOWN", "FTMO_HEADROOM_UNKNOWN")
    if h.get("headroom_status") != "SUFFICIENT":
        return finish("REJECTED", "FTMO_HEADROOM_INSUFFICIENT")
    ev = by_stage["FTMO"]
    if ev["source_version"] != h["source_version"] or ev["source_snapshot_id"] != h["snapshot_id"]:
        return finish("BLOCKED", "FTMO_SOURCE_SNAPSHOT_MISMATCH")

    pi, p = ctx["portfolio_input"], ctx["portfolio"]
    if (pi.get("config_version") != ctx["config_version"] or
            pi.get("account_currency") != ctx["account_currency"] or
            pi.get("policy_config_version") != ctx["config_version"] or
            pi.get("policy_headroom_currency") != ctx["account_currency"] or
            not _close(pi.get("policy_headroom_after_buffer_money"), h.get("available_headroom"))):
        return finish("BLOCKED", "PORTFOLIO_CONFIG_CURRENCY_OR_HEADROOM_MISMATCH")
    if (not p.get("valid") or p.get("budget_status") == "UNKNOWN" or
            not _positive_finite(p.get("budget_money")) or pi.get("data_quality") != "OK" or
            pi.get("account_scope") != "ACCOUNT_WIDE" or pi.get("reconciliation_status") != "RECONCILED" or
            not pi.get("external_orders_included") or not pi.get("account_mode_reconciled") or
            not pi.get("portfolio_limits_confirmed") or not pi.get("policy_floor_calculation_valid") or
            pi.get("policy_headroom_quality") != "OK"):
        return finish("UNKNOWN", "ACCOUNT_WIDE_RECONCILIATION_EVIDENCE_UNKNOWN")
    if p.get("budget_status") != "BUDGET_AVAILABLE":
        return finish("REJECTED", "ACCOUNT_WIDE_BUDGET_REJECTED")
    ev = by_stage["PORTFOLIO"]
    if ev["source_version"] != pi["config_version"] or ev["source_snapshot_id"] != ctx["portfolio_snapshot_id"]:
        return finish("BLOCKED", "PORTFOLIO_SOURCE_SNAPSHOT_MISMATCH")

    vi, s = ctx["sizing_input"], ctx["sizing"]
    if vi.get("config_version") != ctx["config_version"] or vi.get("account_currency") != ctx["account_currency"]:
        return finish("BLOCKED", "VOLUME_CONFIG_OR_CURRENCY_MISMATCH")
    if not s.get("valid") or s.get("sizing_status") != "SIZED":
        status = "REJECTED" if s.get("sizing_status") == "BLOCKED" else "UNKNOWN"
        return finish(status, "VOLUME_SIZING_UNKNOWN_OR_REJECTED")
    if (not _positive_finite(s.get("volume")) or not _positive_finite(s.get("projected_loss")) or
            not vi.get("loss_quote_valid") or vi.get("loss_quote_quality") != "OK" or
            vi.get("loss_quote_version") != ctx["config_version"] or vi.get("loss_quote_currency") != ctx["account_currency"] or
            not vi.get("final_loss_quote_valid") or vi.get("final_loss_quote_quality") != "OK" or
            vi.get("final_loss_quote_version") != ctx["config_version"] or vi.get("final_loss_quote_currency") != ctx["account_currency"] or
            not vi.get("margin_quote_valid") or vi.get("margin_quote_quality") != "OK" or
            vi.get("margin_quote_version") != ctx["config_version"] or vi.get("margin_quote_currency") != ctx["account_currency"] or
            not _finite(s.get("required_margin")) or not _finite(s.get("available_margin")) or
            s["required_margin"] > s["available_margin"]):
        return finish("UNKNOWN", "VOLUME_OR_MARGIN_QUOTE_EVIDENCE_INVALID")
    if (not _positive_finite(vi.get("risk_budget")) or vi["risk_budget"] > p["budget_money"] or
            not _close(econ_i.get("final_volume"), s.get("volume")) or
            not _close(s.get("volume"), vi.get("final_loss_quote_volume")) or
            not _close(s.get("volume"), vi.get("margin_quote_volume")) or
            not _close(s.get("projected_loss"), econ_i.get("net_loss_at_sl_money")) or
            not _close(s.get("projected_loss"), h.get("proposed_stress_loss")) or
            s["projected_loss"] > vi["risk_budget"] or s["projected_loss"] > p["budget_money"] or
            pi.get("existing_stress_loss_money", math.inf) + s["projected_loss"] > h["available_headroom"]):
        return finish("BLOCKED", "FINAL_VOLUME_LOSS_BUDGET_OR_STRESS_MISMATCH")
    ev = by_stage["VOLUME"]
    if ev["source_version"] != vi["config_version"] or ev["source_snapshot_id"] != ctx["volume_quote_snapshot_id"]:
        return finish("BLOCKED", "VOLUME_SOURCE_SNAPSHOT_MISMATCH")

    return {"decision_status": "REVIEWABLE_CANDIDATE",
            "reason_codes": ["ALL_OFFLINE_GATES_PASSED_FOR_REVIEW_ONLY"],
            "candidate_id": c["candidate_id"], "final_volume": s["volume"],
            "projected_loss": s["projected_loss"], "net_reward_risk": econ["net_reward_risk"]}


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def _positive_finite(value):
    return _finite(value) and value > 0


def _close(a, b):
    return _finite(a) and _finite(b) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def mutate(base, path, value):
    """Return a deep copy with one dotted/indexed fixture path changed."""
    copy = deepcopy(base)
    parts = path.split(".")
    target = copy
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = value
    elif value == "__DELETE__":
        del target[last]
    else:
        target[last] = value
    return copy
