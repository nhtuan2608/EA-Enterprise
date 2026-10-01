"""Synthetic FTMO floor/headroom fixtures and fail-closed oracle checks."""
import json
import unittest
from pathlib import Path

from ftmo_headroom_oracle import calculate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/ftmo-headroom-v0.1.0.json").read_text(encoding="utf-8"))


class FtmoHeadroomExamples(unittest.TestCase):
    def test_fixed_scenarios(self):
        for row in FIXTURE["scenarios"]:
            with self.subTest(name=row["name"]):
                actual = calculate(row["policy"], row["input"])
                for key, expected in row["expected"].items():
                    self.assertEqual(actual[key], expected)

    def test_stale_or_unattested_daily_snapshot_is_unknown(self):
        row = FIXTURE["scenarios"][0]
        for key, value in (("daily_snapshot_quality", "STALE"), ("reset_window_confirmed_by_caller", False)):
            bad = dict(row["input"])
            bad[key] = value
            self.assertEqual(calculate(row["policy"], bad)["headroom_status"], "POLICY_DATA_UNKNOWN")

    def test_stress_equal_to_available_headroom_is_reduce_or_wait(self):
        row = FIXTURE["scenarios"][0]
        data = dict(row["input"])
        data["proposed_stress_loss"] = 6000
        result = calculate(row["policy"], data)
        self.assertEqual(result["headroom_status"], "REDUCE_OR_WAIT")
        self.assertEqual(result["reason_code"], "STRESS_LOSS_CONSUMES_AVAILABLE_HEADROOM")

    def test_negative_balance_is_valid_input_but_blocks(self):
        row = FIXTURE["scenarios"][2]
        data = dict(row["input"])
        data["current_balance"] = -1
        result = calculate(row["policy"], data)
        self.assertTrue(result["valid"])
        self.assertEqual(result["headroom_status"], "BLOCK_NEW_ENTRY")

    def test_finite_inputs_that_overflow_computation_are_unknown(self):
        row = FIXTURE["scenarios"][2]
        policy, data = dict(row["policy"]), dict(row["input"])
        policy["initial_capital"] = 1e308
        data["balance_at_daily_reset"] = 1e308
        data["current_balance"] = 1e308
        data["floating_pnl_after_costs"] = 1e308
        result = calculate(policy, data)
        self.assertFalse(result["valid"])
        self.assertEqual(result["headroom_status"], "POLICY_DATA_UNKNOWN")
        self.assertEqual(result["reason_code"], "CALCULATION_OVERFLOW_OR_INVALID_RESULT")

    def test_balance_based_policy_calculation(self):
        policy = {
            "policy_id": "BALANCE_BASED_FTMO_V1",
            "status": "ACTIVE",
            "config_version": "v1",
            "source_version": "v1",
            "source_reference": "https://ftmo.com",
            "policy_timezone": "Europe/Prague",
            "account_currency": "USD",
            "initial_capital": 100000.0,
            "safety_buffer_money": 1000.0,
            "continue_after_daily_profit_target": True,
            "continue_after_overall_profit_target": True
        }
        input_data = {
            "daily_snapshot_config_version": "v1",
            "daily_snapshot_currency": "USD",
            "daily_snapshot_quality": "OK",
            "daily_snapshot_id": "day-1",
            "daily_reset_at_utc": 1000,
            "daily_snapshot_valid": True,
            "reset_window_confirmed_by_caller": True,
            "balance_at_daily_reset": 105000.0,
            "current_balance": 106000.0,
            "floating_pnl_after_costs": 500.0,
            "proposed_stress_loss": 2000.0,
            "stress_loss_currency": "USD",
            "high_water_snapshot_valid": False,
            "high_water_snapshot_quality": "UNKNOWN",
            "high_water_config_version": "",
            "high_water_as_of_utc": 0,
            "prior_overall_high_water_balance": 0.0
        }
        result = calculate(policy, input_data)
        self.assertTrue(result["valid"])
        self.assertEqual(result["daily_loss_amount"], 5000.0)
        self.assertEqual(result["daily_floor"], 100000.0)
        self.assertEqual(result["overall_floor"], 90000.0)
        self.assertEqual(result["headroom_status"], "SUFFICIENT")

    def test_policy_is_not_entry_permission_and_module_is_isolated(self):
        source = (ROOT / "Risk/FtmoHeadroom.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("headroom_status", source)
        self.assertNotIn('"ALLOW"', source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("FtmoHeadroom.mqh", shell)


if __name__ == "__main__":
    unittest.main()
