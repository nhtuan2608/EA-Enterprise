"""Synthetic net reward/risk oracle, not MQL5 or broker execution."""
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/trade-economics-v0.1.0.json").read_text(encoding="utf-8"))


def evaluate(i):
    if (not i["config_version"] or not i["account_currency"] or
            i["quote_config_version"] != i["config_version"] or
            i["quote_currency"] != i["account_currency"] or i["quote_quality"] != "OK" or
            not i["pricing_snapshot_id"] or not i["loss_quote_valid"] or
            not i["reward_quote_valid"] or not i["execution_constraints_confirmed"]):
        return {"valid": False, "economics_status": "UNKNOWN", "reason_code": "PRICING_OR_EXECUTION_EVIDENCE_MISSING"}
    if i["direction"] not in (-1, 1):
        return {"valid": False, "economics_status": "UNKNOWN", "reason_code": "INVALID_DIRECTION"}
    fields = ("entry_reference", "stop_loss", "take_profit", "final_volume", "quote_volume",
              "net_loss_at_sl_money", "net_gain_at_tp_money", "minimum_net_rr")
    if (not all(math.isfinite(i[k]) for k in fields) or
            any(i[k] <= 0 for k in fields if k != "net_gain_at_tp_money") or
            i["quote_volume"] != i["final_volume"]):
        return {"valid": False, "economics_status": "UNKNOWN", "reason_code": "INVALID_ECONOMICS_INPUT"}
    if (i["direction"] == 1 and not i["stop_loss"] < i["entry_reference"] < i["take_profit"]) or (
            i["direction"] == -1 and not i["take_profit"] < i["entry_reference"] < i["stop_loss"]):
        return {"valid": False, "economics_status": "UNKNOWN", "reason_code": "INVALID_PRICE_GEOMETRY"}
    rr = i["net_gain_at_tp_money"] / i["net_loss_at_sl_money"]
    if not math.isfinite(rr):
        return {"valid": False, "economics_status": "UNKNOWN", "reason_code": "ECONOMICS_CALCULATION_INVALID"}
    if not i["target_space_confirmed"]:
        status, reason = "REJECTED", "TARGET_SPACE_INSUFFICIENT"
    elif i["net_gain_at_tp_money"] <= 0:
        status, reason = "REJECTED", "NONPOSITIVE_NET_REWARD"
    elif rr < i["minimum_net_rr"]:
        status, reason = "REJECTED", "NET_REWARD_RISK_BELOW_PROFILE_MINIMUM"
    else:
        status, reason = "ECONOMICS_ACCEPTABLE", "NET_REWARD_RISK_AND_TARGET_SPACE_ACCEPTABLE"
    return {"valid": True, "economics_status": status, "reason_code": reason, "net_reward_risk": rr}


class TradeEconomicsExamples(unittest.TestCase):
    def test_fixed_net_reward_risk_examples(self):
        for row in FIXTURE["cases"]:
            with self.subTest(name=row["name"]):
                observed = evaluate(FIXTURE["base"] | row["overrides"])
                for key, expected in row["expected"].items():
                    self.assertEqual(observed[key], expected)

    def test_module_is_isolated(self):
        source = (ROOT / "Risk/TradeEconomics.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_CheckTradeEconomics", source)
        self.assertNotIn('"ALLOW"', source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("TradeEconomics.mqh", shell)


if __name__ == "__main__":
    unittest.main()
