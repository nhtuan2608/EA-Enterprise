"""Standard-library reference oracle for FTMO floor arithmetic, not a trading engine."""
from __future__ import annotations

import math


def calculate(policy: dict, inputs: dict) -> dict:
    def unknown(reason: str) -> dict:
        return {"valid": False, "headroom_status": "POLICY_DATA_UNKNOWN", "reason_code": reason}

    if policy["status"] != "ACTIVE" or policy["policy_id"] not in {"FTMO_1_STEP", "FTMO_2_STEP"}:
        return unknown("POLICY_NOT_SELECTED_OR_UNSUPPORTED")
    if (not policy["config_version"] or not policy["source_version"] or not policy["source_reference"] or
            policy["policy_timezone"] != "Europe/Prague" or not policy["account_currency"] or
            not math.isfinite(policy["initial_capital"]) or policy["initial_capital"] <= 0 or
            not math.isfinite(policy["safety_buffer_money"]) or policy["safety_buffer_money"] < 0):
        return unknown("POLICY_CONFIGURATION_INCOMPLETE")
    if (not inputs["daily_snapshot_valid"] or inputs["daily_snapshot_quality"] != "OK" or
            not inputs["reset_window_confirmed_by_caller"] or inputs["daily_reset_at_utc"] <= 0 or
            not inputs["daily_snapshot_id"] or inputs["daily_snapshot_config_version"] != policy["config_version"] or
            inputs["daily_snapshot_currency"] != policy["account_currency"] or
            not math.isfinite(inputs["balance_at_daily_reset"])):
        return unknown("DAILY_RESET_SNAPSHOT_MISSING_OR_MISMATCHED")
    if (not math.isfinite(inputs["current_balance"]) or
            not math.isfinite(inputs["floating_pnl_after_costs"]) or
            not math.isfinite(inputs["proposed_stress_loss"]) or inputs["proposed_stress_loss"] <= 0 or
            inputs["stress_loss_currency"] != policy["account_currency"]):
        return unknown("CURRENT_EQUITY_OR_STRESS_INPUT_INVALID")

    initial = policy["initial_capital"]
    if policy["policy_id"] == "FTMO_1_STEP":
        if (not inputs["high_water_snapshot_valid"] or inputs["high_water_snapshot_quality"] != "OK" or
                inputs["high_water_config_version"] != policy["config_version"] or
                inputs["high_water_as_of_utc"] <= 0 or inputs["high_water_as_of_utc"] > inputs["daily_reset_at_utc"] or
                not math.isfinite(inputs["prior_overall_high_water_balance"]) or
                inputs["prior_overall_high_water_balance"] < initial):
            return unknown("TRAILING_HIGH_WATER_SNAPSHOT_MISSING_OR_INVALID")
        daily_percent, overall_percent = 3.0, 10.0
        high_water = max(initial, inputs["prior_overall_high_water_balance"], inputs["balance_at_daily_reset"])
    else:
        daily_percent, overall_percent = 5.0, 10.0
        high_water = initial

    equity = inputs["current_balance"] + inputs["floating_pnl_after_costs"]
    daily_loss = initial * daily_percent / 100.0
    daily_floor = inputs["balance_at_daily_reset"] - daily_loss
    overall_floor = (high_water if policy["policy_id"] == "FTMO_1_STEP" else initial) - initial * overall_percent / 100.0
    daily_room = equity - daily_floor
    overall_room = equity - overall_floor
    available = min(daily_room, overall_room) - policy["safety_buffer_money"]
    stress = inputs["proposed_stress_loss"]
    computed = (equity, daily_loss, daily_floor, overall_floor, high_water, daily_room,
                overall_room, available, stress, equity - stress, available - stress)
    if not all(math.isfinite(value) for value in computed):
        return unknown("CALCULATION_OVERFLOW_OR_INVALID_RESULT")
    if daily_room <= 0 or overall_room <= 0 or available <= 0:
        headroom_status, reason = "BLOCK_NEW_ENTRY", "FLOOR_OR_SAFETY_BUFFER_EXHAUSTED"
    elif stress >= available:
        headroom_status = "REDUCE_OR_WAIT"
        reason = ("STRESS_LOSS_CONSUMES_AVAILABLE_HEADROOM" if stress == available
                  else "STRESS_LOSS_EXCEEDS_AVAILABLE_HEADROOM")
    else:
        headroom_status, reason = "SUFFICIENT", "STRESS_LOSS_WITHIN_AVAILABLE_HEADROOM"
    return {
        "valid": True,
        "headroom_status": headroom_status,
        "reason_code": reason,
        "equity_after_costs": equity,
        "daily_loss_amount": daily_loss,
        "daily_floor": daily_floor,
        "overall_high_water_balance": high_water,
        "overall_floor": overall_floor,
        "daily_floor_headroom": daily_room,
        "overall_floor_headroom": overall_room,
        "available_headroom": available,
        "proposed_stress_loss": stress,
        "stress_equity": equity - stress,
        "post_stress_available_headroom": available - stress,
    }
