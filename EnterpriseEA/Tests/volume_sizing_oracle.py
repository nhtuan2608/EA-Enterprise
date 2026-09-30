"""Standard-library Decimal oracle for offline volume sizing, not broker logic."""
from decimal import Decimal, ROUND_FLOOR
import math


def calculate(data: dict) -> dict:
    def unknown(reason):
        return {"valid": False, "sizing_status": "INPUT_UNKNOWN", "reason_code": reason}

    def d(name):
        try:
            value = Decimal(str(data[name]))
        except Exception:
            return None
        return value if value.is_finite() else None

    numeric = {name: d(name) for name in (
        "risk_budget", "loss_per_lot_at_sl", "volume_min", "volume_max", "volume_step",
        "final_loss_quote_volume", "final_loss_at_sl", "margin_quote_volume",
        "required_margin", "available_margin")}
    if (not data.get("config_version") or not data.get("account_currency") or
            any(value is None for value in numeric.values()) or
            numeric["risk_budget"] <= 0 or numeric["loss_per_lot_at_sl"] <= 0 or
            numeric["volume_min"] <= 0 or numeric["volume_max"] < numeric["volume_min"] or
            numeric["volume_step"] <= 0 or not data.get("loss_quote_valid") or
            data.get("loss_quote_quality") != "OK" or
            data.get("loss_quote_version") != data["config_version"] or
            data.get("loss_quote_currency") != data["account_currency"]):
        return unknown("LOSS_QUOTE_OR_VOLUME_SPEC_INVALID")
    if (not data.get("margin_quote_valid") or data.get("margin_quote_quality") != "OK" or
            data.get("margin_quote_version") != data["config_version"] or
            data.get("margin_quote_currency") != data["account_currency"] or
            numeric["margin_quote_volume"] <= 0 or numeric["required_margin"] < 0 or
            numeric["available_margin"] < 0):
        return unknown("MARGIN_QUOTE_MISSING_OR_INVALID")

    raw = numeric["risk_budget"] / numeric["loss_per_lot_at_sl"]
    if not math.isfinite(float(raw)):
        return unknown("CALCULATION_OVERFLOW_OR_INVALID_RESULT")
    capped = min(raw, numeric["volume_max"])
    volume = (capped / numeric["volume_step"]).to_integral_value(rounding=ROUND_FLOOR) * numeric["volume_step"]
    if not math.isfinite(float(volume)):
        return unknown("CALCULATION_OVERFLOW_OR_INVALID_RESULT")
    result = {"valid": False, "sizing_status": "INPUT_UNKNOWN", "reason_code": "INPUT_UNKNOWN",
              "raw_volume": float(raw), "volume": float(volume)}
    if volume < numeric["volume_min"]:
        result.update(sizing_status="BLOCKED", reason_code="RISK_BUDGET_BELOW_MINIMUM_VOLUME")
        return result
    if volume > numeric["volume_max"]:
        return unknown("ROUNDED_VOLUME_EXCEEDS_MAXIMUM")
    if (not data.get("final_loss_quote_valid") or data.get("final_loss_quote_quality") != "OK" or
            data.get("final_loss_quote_version") != data["config_version"] or
            data.get("final_loss_quote_currency") != data["account_currency"] or
            abs(numeric["final_loss_quote_volume"] - volume) > numeric["volume_step"] * Decimal("1e-8") or
            numeric["final_loss_at_sl"] <= 0):
        return unknown("FINAL_VOLUME_LOSS_QUOTE_MISSING_OR_MISMATCHED")
    projected = numeric["final_loss_at_sl"]
    result.update(projected_loss=float(projected), required_margin=float(numeric["required_margin"]),
                  available_margin=float(numeric["available_margin"]))
    if projected > numeric["risk_budget"]:
        result.update(sizing_status="BLOCKED", reason_code="FINAL_VOLUME_LOSS_EXCEEDS_RISK_BUDGET")
        return result
    tolerance = numeric["volume_step"] * Decimal("1e-8")
    if abs(numeric["margin_quote_volume"] - volume) > tolerance:
        result.update(sizing_status="INPUT_UNKNOWN", reason_code="MARGIN_QUOTE_VOLUME_MISMATCH")
        return result
    if numeric["required_margin"] > numeric["available_margin"]:
        result.update(sizing_status="BLOCKED", reason_code="INSUFFICIENT_AVAILABLE_MARGIN")
        return result
    result.update(valid=True, sizing_status="SIZED",
                  reason_code="ROUNDED_VOLUME_WITHIN_RISK_AND_MARGIN_BUDGETS")
    return result
