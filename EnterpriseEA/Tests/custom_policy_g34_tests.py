"""G34: CUSTOM account policy (daily / overall loss, fixed or trailing floor, balance or equity reference)."""
import unittest
from pathlib import Path

from ftmo_headroom_oracle import calculate, resolve_rules

ROOT = Path(__file__).resolve().parents[1]
POLICY = {
    "policy_id": "CUSTOM", "status": "ACTIVE", "config_version": "v1", "source_version": "v1",
    "source_reference": "operator", "policy_timezone": "Europe/Prague", "account_currency": "USD",
    "initial_capital": 100000.0, "safety_buffer_money": 0.0,
    "custom_rules": {"daily_percent": 4.0, "overall_percent": 8.0, "trailing": False, "daily_from_equity": True},
}
INPUT = {
    "daily_snapshot_config_version": "v1", "daily_snapshot_currency": "USD", "daily_snapshot_quality": "OK",
    "daily_snapshot_id": "d", "daily_reset_at_utc": 1000, "daily_snapshot_valid": True,
    "reset_window_confirmed_by_caller": True, "balance_at_daily_reset": 105000.0, "equity_at_daily_reset": 104000.0,
    "current_balance": 105000.0, "floating_pnl_after_costs": 0.0, "proposed_stress_loss": 500.0,
    "stress_loss_currency": "USD", "high_water_snapshot_valid": True, "high_water_snapshot_quality": "OK",
    "high_water_config_version": "v1", "high_water_as_of_utc": 900, "prior_overall_high_water_balance": 108000.0,
}


def run(rules=None, **inp):
    policy = dict(POLICY, custom_rules=dict(POLICY["custom_rules"], **(rules or {})))
    return calculate(policy, dict(INPUT, **inp))


class RulesTests(unittest.TestCase):
    def test_presets_are_unchanged(self):
        self.assertEqual(resolve_rules("FTMO_1_STEP", None),
                         {"daily_percent": 3.0, "overall_percent": 10.0, "trailing": True, "daily_from_equity": False})
        self.assertEqual(resolve_rules("FTMO_2_STEP", None)["daily_percent"], 5.0)
        self.assertFalse(resolve_rules("FTMO_2_STEP", None)["trailing"])
        self.assertIsNone(resolve_rules("UNSELECTED", None))

    def test_custom_numbers_are_validated(self):
        ok = {"daily_percent": 4.0, "overall_percent": 8.0, "trailing": False, "daily_from_equity": False}
        self.assertEqual(resolve_rules("CUSTOM", ok), ok)
        for bad in ({"daily_percent": 0.0}, {"daily_percent": 9.0}, {"overall_percent": 101.0},
                    {"daily_percent": float("nan")}, {"overall_percent": float("inf")}):
            self.assertIsNone(resolve_rules("CUSTOM", dict(ok, **bad)), bad)
        self.assertIsNone(resolve_rules("CUSTOM", None))


class FloorTests(unittest.TestCase):
    def test_fixed_floor_equity_reference(self):
        r = run()
        self.assertTrue(r["valid"])
        self.assertEqual(r["daily_loss_amount"], 4000.0)
        self.assertEqual(r["daily_floor"], 100000.0)           # equity 104000 - 4000
        self.assertEqual(r["overall_floor"], 92000.0)          # initial 100000 - 8000
        self.assertEqual(r["overall_high_water_balance"], 100000.0)

    def test_balance_reference(self):
        self.assertEqual(run({"daily_from_equity": False})["daily_floor"], 101000.0)   # balance 105000 - 4000

    def test_trailing_floor_uses_high_water(self):
        r = run({"trailing": True})
        self.assertEqual(r["overall_high_water_balance"], 108000.0)
        self.assertEqual(r["overall_floor"], 100000.0)         # 108000 - 8000

    def test_equity_reference_missing_fails_closed(self):
        for value in (0.0, -1.0, float("nan")):
            r = run(equity_at_daily_reset=value)
            self.assertFalse(r["valid"])
            self.assertEqual(r["reason_code"], "DAILY_RESET_EQUITY_MISSING")
        self.assertTrue(run({"daily_from_equity": False}, equity_at_daily_reset=0.0)["valid"])

    def test_trailing_needs_high_water_snapshot(self):
        r = run({"trailing": True}, high_water_snapshot_valid=False)
        self.assertEqual(r["reason_code"], "TRAILING_HIGH_WATER_SNAPSHOT_MISSING_OR_INVALID")

    def test_invalid_custom_numbers_fail_closed(self):
        r = run({"daily_percent": 9.0})
        self.assertFalse(r["valid"])
        self.assertEqual(r["reason_code"], "POLICY_RULESET_UNSUPPORTED")

    def test_ftmo_one_step_matches_custom_equivalent(self):
        one = calculate(dict(POLICY, policy_id="FTMO_1_STEP"), dict(INPUT))
        eq = run({"daily_percent": 3.0, "overall_percent": 10.0, "trailing": True, "daily_from_equity": False})
        for key in ("daily_floor", "overall_floor", "available_headroom", "headroom_status"):
            self.assertEqual(one[key], eq[key], key)


class SourceTests(unittest.TestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_mql_resolves_rules_in_one_place(self):
        rules = self.read("Risk/PolicyRules.mqh")
        self.assertIn('policy_id=="CUSTOM"', rules)
        self.assertIn("r.daily_percent<=r.overall_percent", rules)
        head = self.read("Risk/FtmoHeadroom.mqh")
        self.assertIn("EEA_PolicyRulesResolve(p.policy_id,p.custom_rules,rules)", head)
        self.assertNotIn("3.0", head)
        self.assertIn("DAILY_RESET_EQUITY_MISSING", head)
        self.assertIn("EEA_PolicyRulesResolve(policy_id,g_custom_policy_rules,rules)", self.read("Risk/RiskLimitsProfile.mqh"))

    def test_session_signs_the_custom_numbers(self):
        self.assertIn("EEA_PolicySignedId", self.read("Risk/PolicyRules.mqh"))
        for rel in ("EnterpriseEA.mq5", "Integration/ControlledLiveRuntime.mqh", "Integration/S06BPyramidRuntime.mqh"):
            self.assertIn("EEA_PolicySignedId(policy.committed_policy)", self.read(rel), rel)
        self.assertNotIn("account_margin_mode,policy.committed_policy,", self.read("Integration/ControlledLiveRuntime.mqh"))
        self.assertNotIn("account_margin_mode,policy.committed_policy,", self.read("Integration/S06BPyramidRuntime.mqh"))

    def test_daily_reference_is_used_for_every_daily_loss_check(self):
        live = self.read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn("EEA_LedgerDailyReference(ledger,policy_id)-equity", live)
        self.assertNotIn("ledger.last_reset_balance-equity", live)
        self.assertIn("EEA_LedgerDailyReference(ledger,policy.committed_policy),observer.account.equity", live)
        self.assertIn("EEA_LedgerDailyReference(ledger,policy.committed_policy),observer.account.equity",
                      self.read("Integration/S06BPyramidRuntime.mqh"))

    def test_equity_sample_only_when_the_reset_was_seen(self):
        store = self.read("Storage/RiskLedgerStore.mqh")
        self.assertIn("EEA_RESET_EQUITY_SAMPLE_WINDOW", store)
        self.assertIn("(now_utc-latest)<=EEA_RESET_EQUITY_SAMPLE_WINDOW && current_equity>0.0", store)
        self.assertIn("last_reset_equity", store)
        self.assertIn("return l.last_reset_balance;", store)

    def test_custom_is_an_accepted_policy_id_and_has_inputs(self):
        self.assertIn('policy=="CUSTOM"', self.read("Storage/PolicySettingsStore.mqh"))
        shell = self.read("EnterpriseEA.mq5")
        for name in ("InpCustomDailyLossPercent", "InpCustomOverallLossPercent",
                     "InpCustomTrailingFloor", "InpCustomDailyFromEquity"):
            self.assertIn(name, shell)
        self.assertIn("g_custom_policy_rules.daily_from_equity=InpCustomDailyFromEquity", shell)
        self.assertIn("Btn_Policy_CUSTOM", self.read("Runtime/SymbolSelectionPanel.mqh"))


if __name__ == "__main__":
    unittest.main()
