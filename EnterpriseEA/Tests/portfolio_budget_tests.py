"""Fixed synthetic budget examples; does not execute the MQL5 module."""
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/portfolio-budget-v0.1.0.json").read_text(encoding="utf-8"))


def calculate_budget(i):
    if (not i["config_version"] or not i["account_currency"] or i["data_quality"] != "OK" or
            i["account_scope"] != "ACCOUNT_WIDE" or i["reconciliation_status"] != "RECONCILED" or
            not i["policy_floor_calculation_valid"] or i["policy_headroom_quality"] != "OK" or
            i["policy_config_version"] != i["config_version"] or
            i["policy_headroom_currency"] != i["account_currency"] or not i["external_orders_included"] or
            not i["account_mode_reconciled"] or not i["portfolio_limits_confirmed"]):
        return {"valid": False, "budget_status": "UNKNOWN", "reason_code": "ACCOUNT_WIDE_EVIDENCE_INCOMPLETE"}
    numbers = [i[k] for k in ("equity_after_costs", "base_risk_fraction", "per_trade_cap_money",
                              "portfolio_remaining_money", "policy_headroom_after_buffer_money",
                              "existing_stress_loss_money")]
    if (not all(math.isfinite(x) for x in numbers) or numbers[0] <= 0 or not 0 < numbers[1] <= 1 or
            any(x < 0 for x in numbers[2:])):
        return {"valid": False, "budget_status": "UNKNOWN", "reason_code": "INVALID_BUDGET_INPUT"}
    base_risk = numbers[0] * numbers[1]
    floor_remaining = numbers[4] - numbers[5]
    budget = max(0, min(base_risk, numbers[2], numbers[3], floor_remaining))
    if not all(math.isfinite(x) for x in (base_risk, floor_remaining, budget)):
        return {"valid": False, "budget_status": "UNKNOWN", "reason_code": "BUDGET_CALCULATION_INVALID"}
    return {"valid": True, "budget_status": "BUDGET_AVAILABLE" if budget > 0 else "BLOCK",
            "base_risk_money": base_risk, "floor_remaining_money": floor_remaining, "budget_money": budget}


class PortfolioBudgetExamples(unittest.TestCase):
    def test_fixed_account_wide_budget_examples(self):
        for row in FIXTURE["cases"]:
            with self.subTest(name=row["name"]):
                actual = calculate_budget(FIXTURE["base"] | row["overrides"])
                for key, expected in row["expected"].items():
                    self.assertEqual(actual[key], expected)

    def test_module_is_isolated_and_has_no_order_permission(self):
        source = (ROOT / "Risk/PortfolioBudget.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_CalculatePortfolioBudget", source)
        self.assertNotIn('"ALLOW"', source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("PortfolioBudget.mqh", shell)


if __name__ == "__main__":
    unittest.main()
