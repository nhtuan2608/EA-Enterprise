"""Python reference for synthetic closed-bar expected-path examples."""
from copy import deepcopy
import math


def valid_profile(p):
    return (bool(p.get("config_version")) and bool(p.get("setup_id")) and
            p.get("trade_style") in {"SCALP", "SWING"} and
            0 < p.get("proving_bars", 0) < p.get("working_bars", 0) < p.get("horizon_bars", 0) and
            all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k]) and p[k] >= 0
                for k in ("minimum_mfe_at_proving_r", "runner_min_close_r")))


def initialize(seed, profile):
    if (not valid_profile(profile) or not seed.get("trade_id") or
            seed.get("setup_id") != profile["setup_id"] or
            seed.get("config_version") != profile["config_version"] or
            not seed.get("canonical_symbol") or seed.get("filled_at_utc", 0) <= 0 or
            not all(isinstance(seed.get(k), (int, float)) and math.isfinite(seed[k]) and seed[k] > 0
                    for k in ("filled_price", "invalidation_stop")) or
            not ((seed.get("direction") == "LONG" and seed["invalidation_stop"] < seed["filled_price"]) or
                 (seed.get("direction") == "SHORT" and seed["invalidation_stop"] > seed["filled_price"]))):
        return None
    return dict(initialized=True, status="OBSERVING", phase="ENTERED",
                reason_code="FILL_ATTESTED_WAITING_FOR_CLOSED_BAR", trade_id=seed["trade_id"],
                setup_id=seed["setup_id"], config_version=seed["config_version"],
                canonical_symbol=seed["canonical_symbol"], direction=seed["direction"],
                filled_at_utc=seed["filled_at_utc"], filled_price=seed["filled_price"],
                invalidation_stop=seed["invalidation_stop"],
                initial_risk_points=abs(seed["filled_price"] - seed["invalidation_stop"]),
                last_bar_sequence=0, last_bar_fingerprint="", last_bar_closed_at_utc=0,
                bars_held=0, mfe_r=0.0, mae_r=0.0, bars_to_mfe=0, bars_to_mae=0,
                time_to_05r_bars=0, time_to_1r_bars=0, time_to_2r_bars=0)


def apply_closed_bar(state, profile, bar):
    s = deepcopy(state)
    if (not s or s["status"] != "OBSERVING" or not valid_profile(profile) or
            profile["config_version"] != s["config_version"] or profile["setup_id"] != s["setup_id"]):
        return s, False, "PATH_STATE_OR_PROFILE_NOT_READY"
    if (s["last_bar_sequence"] > 0 and bar.get("trade_id") == s["trade_id"] and
            bar.get("config_version") == s["config_version"] and
            bar.get("bar_closed_confirmed") is True and bar.get("data_quality") == "OK" and
            bool(bar.get("bar_fingerprint")) and
            bar.get("bar_sequence") == s["last_bar_sequence"] and
            bar.get("closed_at_utc") == s["last_bar_closed_at_utc"] and
            bar.get("bar_fingerprint") == s["last_bar_fingerprint"]):
        return s, True, "DUPLICATE_CLOSED_BAR_IGNORED"
    if (bar.get("trade_id") != s["trade_id"] or bar.get("config_version") != s["config_version"] or
            bar.get("bar_sequence") != s["last_bar_sequence"] + 1 or not bar.get("bar_fingerprint") or
            bar.get("closed_at_utc", 0) <= max(s["filled_at_utc"], s["last_bar_closed_at_utc"]) or
            bar.get("bar_closed_confirmed") is not True or bar.get("data_quality") != "OK" or
            not all(isinstance(bar.get(k), (int, float)) and math.isfinite(bar[k]) for k in
                    ("open", "high", "low", "close")) or
            bar["low"] <= 0 or bar["low"] > min(bar["open"], bar["close"]) or
            bar["high"] < max(bar["open"], bar["close"], bar["low"]) or
            bar.get("structure_state") not in {"VALID", "INVALID", "UNKNOWN"} or
            bar.get("volatility_state") not in {"NORMAL", "DECAY", "UNKNOWN"} or
            not bar.get("session_state") or not bar.get("news_state")):
        s.update(status="UNKNOWN", reason_code="CLOSED_BAR_MISSING_CONFLICTING_OR_UNTRUSTED")
        return s, False, s["reason_code"]

    s.update(last_bar_sequence=bar["bar_sequence"], last_bar_fingerprint=bar["bar_fingerprint"],
             last_bar_closed_at_utc=bar["closed_at_utc"], bars_held=s["bars_held"] + 1)
    if ((s["direction"] == "LONG" and bar["low"] <= s["invalidation_stop"]) or
            (s["direction"] == "SHORT" and bar["high"] >= s["invalidation_stop"])):
        s.update(status="STOP_TOUCHED_REVIEW", reason_code="INTRABAR_PATH_AMBIGUOUS_STOP_TOUCHED")
        return s, True, s["reason_code"]
    favorable = ((bar["high"] - s["filled_price"]) if s["direction"] == "LONG" else
                 (s["filled_price"] - bar["low"])) / s["initial_risk_points"]
    adverse = ((s["filled_price"] - bar["low"]) if s["direction"] == "LONG" else
               (bar["high"] - s["filled_price"])) / s["initial_risk_points"]
    if not math.isfinite(favorable) or not math.isfinite(adverse):
        s.update(status="UNKNOWN", reason_code="PATH_EXCURSION_INVALID")
        return s, False, s["reason_code"]
    if favorable > s["mfe_r"]:
        s.update(mfe_r=favorable, bars_to_mfe=s["bars_held"])
    if adverse > s["mae_r"]:
        s.update(mae_r=adverse, bars_to_mae=s["bars_held"])
    for threshold, field in ((0.5, "time_to_05r_bars"), (1.0, "time_to_1r_bars"),
                             (2.0, "time_to_2r_bars")):
        if s["mfe_r"] >= threshold and s[field] == 0:
            s[field] = s["bars_held"]

    if bar["structure_state"] == "INVALID":
        s.update(status="INVALIDATED_REVIEW", reason_code="STRUCTURE_INVALIDATED_REVIEW")
    elif bar["structure_state"] == "UNKNOWN" or bar["volatility_state"] == "UNKNOWN":
        s.update(status="UNKNOWN", reason_code="PATH_CONTEXT_UNKNOWN")
    elif s["bars_held"] >= profile["horizon_bars"]:
        close_r = ((bar["close"] - s["filled_price"]) if s["direction"] == "LONG" else
                   (s["filled_price"] - bar["close"])) / s["initial_risk_points"]
        s.update(phase="TIMEOUT_REVIEW", reason_code=(
            "RUNNER_REVIEW_AT_HORIZON" if close_r >= profile["runner_min_close_r"] and
            bar["volatility_state"] == "NORMAL" else "TIMEOUT_REVIEW_REQUIRED"))
    elif (s["bars_held"] >= profile["proving_bars"] and
          s["mfe_r"] < profile["minimum_mfe_at_proving_r"] and
          bar["volatility_state"] == "DECAY"):
        s.update(phase="WORKING" if s["bars_held"] <= profile["working_bars"] else "MATURE",
                 reason_code="UNDERPERFORMING_REVIEW_REQUIRED")
    else:
        phase = ("PROVING" if s["bars_held"] <= profile["proving_bars"] else
                 ("WORKING" if s["bars_held"] <= profile["working_bars"] else "MATURE"))
        s.update(phase=phase, reason_code="PATH_PROGRESS_OBSERVED")
    return s, True, s["reason_code"]
