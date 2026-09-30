"""Fixed synthetic price examples; no MQL5 or broker runtime is executed."""
import json
import unittest
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "Tests/Fixtures/structural-levels-v0.1.0.json").read_text(encoding="utf-8"))["cases"]


def check_case(row):
    d = lambda key: Decimal(str(row[key]))
    direction = row["direction"]
    entry, invalidation, target = d("entry"), d("invalidation"), d("target")
    buffer, tick = d("stop_buffer"), d("tick_size")
    if direction not in (1, -1) or min(entry, invalidation, target, buffer, tick) <= 0:
        return {"reason": "INVALID_LEVEL_INPUT"}
    if direction == 1 and not (invalidation < entry < target):
        return {"reason": "INVALID_LONG_GEOMETRY"}
    if direction == -1 and not (target < entry < invalidation):
        return {"reason": "INVALID_SHORT_GEOMETRY"}
    rounding = ROUND_FLOOR if direction == 1 else ROUND_CEILING
    raw_sl = invalidation - buffer if direction == 1 else invalidation + buffer
    sl = (raw_sl / tick).to_integral_value(rounding=rounding) * tick
    tp = (target / tick).to_integral_value(rounding=rounding) * tick
    if (direction == 1 and (sl <= 0 or sl >= invalidation or tp <= entry)) or (direction == -1 and (sl <= invalidation or tp >= entry)):
        return {"reason": "LEVELS_COLLAPSED_AFTER_TICK_ROUNDING"}
    return {"reason": "PROPOSED_LEVELS_ONLY", "sl": sl, "tp": tp}


class StructuralLevelsExamples(unittest.TestCase):
    def test_fixed_geometry_examples(self):
        for row in CASES:
            with self.subTest(name=row["name"]):
                result = check_case(row)
                if "expected_reason" in row:
                    self.assertEqual(result["reason"], row["expected_reason"])
                else:
                    self.assertEqual(result["reason"], "PROPOSED_LEVELS_ONLY")
                    self.assertEqual(result["sl"], Decimal(str(row["expected_sl"])))
                    self.assertEqual(result["tp"], Decimal(str(row["expected_tp"])))

    def test_proposal_has_no_order_permission_or_broker_calls(self):
        source = (ROOT / "Risk/StructuralLevels.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_ProposeStructuralLevels", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("StructuralLevels.mqh", shell)


if __name__ == "__main__":
    unittest.main()
