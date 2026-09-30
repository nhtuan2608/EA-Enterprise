"""Synthetic fixtures for the isolated Phase 3 volume sizing prototype."""
import json
import unittest
from pathlib import Path

from volume_sizing_oracle import calculate

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "Tests/Fixtures/volume-sizing-v0.1.0.json").read_text(encoding="utf-8"))["cases"]


class VolumeSizingExamples(unittest.TestCase):
    def test_fixed_cases(self):
        for row in CASES:
            with self.subTest(name=row["name"]):
                actual = calculate(row["input"])
                for key, expected in row["expected"].items():
                    self.assertEqual(actual[key], expected)

    def test_untrusted_loss_and_margin_inputs_fail_closed(self):
        base = dict(CASES[0]["input"])
        for changes, reason in (
            ({"loss_quote_quality": "STALE"}, "LOSS_QUOTE_OR_VOLUME_SPEC_INVALID"),
            ({"loss_quote_currency": "EUR"}, "LOSS_QUOTE_OR_VOLUME_SPEC_INVALID"),
            ({"final_loss_quote_valid": False}, "FINAL_VOLUME_LOSS_QUOTE_MISSING_OR_MISMATCHED"),
            ({"final_loss_quote_quality": "STALE"}, "FINAL_VOLUME_LOSS_QUOTE_MISSING_OR_MISMATCHED"),
            ({"final_loss_quote_volume": 0.41}, "FINAL_VOLUME_LOSS_QUOTE_MISSING_OR_MISMATCHED"),
            ({"margin_quote_valid": False}, "MARGIN_QUOTE_MISSING_OR_INVALID"),
            ({"margin_quote_version": "old"}, "MARGIN_QUOTE_MISSING_OR_INVALID"),
            ({"margin_quote_volume": 0.41}, "MARGIN_QUOTE_VOLUME_MISMATCH"),
        ):
            data = dict(base)
            data.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(calculate(data)["reason_code"], reason)

    def test_rounding_near_maximum_never_exceeds_maximum(self):
        data = dict(CASES[1]["input"])
        data.update(risk_budget=1000, loss_per_lot_at_sl=100,
                    volume_max=2.999999999999999, volume_step=0.1,
                    final_loss_quote_volume=2.9, final_loss_at_sl=290,
                    margin_quote_volume=2.9)
        result = calculate(data)
        self.assertEqual(result["volume"], 2.9)
        self.assertLessEqual(result["volume"], data["volume_max"])

    def test_finite_inputs_that_overflow_double_range_are_unknown(self):
        data = dict(CASES[0]["input"])
        data["risk_budget"] = 1e308
        data["loss_per_lot_at_sl"] = 1e-308
        self.assertEqual(calculate(data)["reason_code"], "CALCULATION_OVERFLOW_OR_INVALID_RESULT")

    def test_module_is_isolated_and_does_not_guess_contract_value(self):
        source = (ROOT / "Risk/VolumeSizing.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("loss_per_lot_at_sl", source)
        self.assertNotIn("tick_value", source.lower())
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("VolumeSizing.mqh", shell)


if __name__ == "__main__":
    unittest.main()
