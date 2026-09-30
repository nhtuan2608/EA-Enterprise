"""Synthetic expected-path scenarios, not MQL5 runtime or broker fills."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from expected_path_oracle import apply_closed_bar, initialize

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "Tests/Fixtures/expected-path-v0.1.0.json").read_text(encoding="utf-8"))


def long_bar(sequence, **changes):
    bar = dict(DATA["defaults_for_bars"], bar_sequence=sequence,
               bar_fingerprint=f"synthetic-{sequence}", closed_at_utc=1000 + sequence * 60,
               open=100.0, high=100.2, low=99.8, close=100.1,
               structure_state="VALID", volatility_state="NORMAL")
    bar.update(changes)
    return bar


class ExpectedPathExamples(unittest.TestCase):
    def test_long_path_tracks_mfe_mae_and_time_to_r_milestones(self):
        state = initialize(DATA["long_seed"], DATA["profile"])
        self.assertIsNotNone(state)
        for example in DATA["long_bars"]:
            bar = dict(DATA["defaults_for_bars"], **example)
            state, ok, _ = apply_closed_bar(state, DATA["profile"], bar)
            self.assertTrue(ok)
        expected = DATA["expected_after_long_bars"]
        for key in ("bars_held", "bars_to_mfe", "bars_to_mae", "time_to_05r_bars",
                    "time_to_1r_bars", "time_to_2r_bars", "phase", "status"):
            self.assertEqual(state[key], expected[key], key)
        self.assertAlmostEqual(state["mfe_r"], expected["mfe_r"])
        self.assertAlmostEqual(state["mae_r"], expected["mae_r"])

    def test_short_direction_uses_low_for_favorable_excursion(self):
        state = initialize(DATA["short_seed"], DATA["profile"])
        bar = long_bar(1, trade_id="virtual-short-1", open=100.0, high=100.2,
                       low=99.5, close=99.7)
        state, ok, _ = apply_closed_bar(state, DATA["profile"], bar)
        self.assertTrue(ok)
        self.assertAlmostEqual(state["mfe_r"], 0.5)
        self.assertAlmostEqual(state["mae_r"], 0.2)
        self.assertEqual(state["time_to_05r_bars"], 1)

    def test_underperformance_requires_slow_mfe_and_volatility_decay(self):
        state = initialize(DATA["long_seed"], DATA["profile"])
        for n in range(1, 4):
            state, ok, reason = apply_closed_bar(
                state, DATA["profile"], long_bar(n, high=100.1 + n * 0.05,
                                                  volatility_state="DECAY" if n == 3 else "NORMAL"))
            self.assertTrue(ok)
        self.assertEqual(reason, "UNDERPERFORMING_REVIEW_REQUIRED")
        self.assertEqual(state["status"], "OBSERVING")
        self.assertEqual(state["phase"], "WORKING")

    def test_stop_touch_does_not_invent_intrabar_path_or_fill(self):
        state = initialize(DATA["long_seed"], DATA["profile"])
        state, ok, reason = apply_closed_bar(
            state, DATA["profile"], long_bar(1, high=102.2, low=98.8, close=100.2))
        self.assertTrue(ok)
        self.assertEqual(reason, "INTRABAR_PATH_AMBIGUOUS_STOP_TOUCHED")
        self.assertEqual(state["status"], "STOP_TOUCHED_REVIEW")
        self.assertEqual(state["mfe_r"], 0)
        self.assertEqual(state["time_to_2r_bars"], 0)
        self.assertFalse(apply_closed_bar(state, DATA["profile"], long_bar(2))[1])

    def test_duplicate_is_idempotent_but_revised_bar_fails_closed(self):
        state = initialize(DATA["long_seed"], DATA["profile"])
        first = long_bar(1)
        state, _, _ = apply_closed_bar(state, DATA["profile"], first)
        same, ok, reason = apply_closed_bar(state, DATA["profile"], first)
        self.assertTrue(ok)
        self.assertEqual(reason, "DUPLICATE_CLOSED_BAR_IGNORED")
        self.assertEqual(same, state)
        revised = deepcopy(first)
        revised["bar_fingerprint"] = "different-content"
        unknown, ok, _ = apply_closed_bar(state, DATA["profile"], revised)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "UNKNOWN")
        foreign = deepcopy(first)
        foreign["trade_id"] = "another-trade"
        unknown, ok, _ = apply_closed_bar(state, DATA["profile"], foreign)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "UNKNOWN")

    def test_bar_gap_or_unclosed_bar_fails_closed(self):
        for bar in (long_bar(2), long_bar(1, bar_closed_confirmed=False)):
            with self.subTest(bar=bar):
                state = initialize(DATA["long_seed"], DATA["profile"])
                unknown, ok, _ = apply_closed_bar(state, DATA["profile"], bar)
                self.assertFalse(ok)
                self.assertEqual(unknown["status"], "UNKNOWN")

    def test_horizon_is_review_only(self):
        state = initialize(DATA["long_seed"], DATA["profile"])
        for n in range(1, 16):
            state, ok, reason = apply_closed_bar(state, DATA["profile"], long_bar(n))
            self.assertTrue(ok)
        self.assertEqual(state["phase"], "TIMEOUT_REVIEW")
        self.assertEqual(reason, "TIMEOUT_REVIEW_REQUIRED")
        self.assertEqual(state["status"], "OBSERVING")

    def test_invalid_fill_geometry_and_structure_invalidation(self):
        bad_seed = deepcopy(DATA["long_seed"])
        bad_seed["invalidation_stop"] = 101.0
        self.assertIsNone(initialize(bad_seed, DATA["profile"]))
        state = initialize(DATA["long_seed"], DATA["profile"])
        state, ok, reason = apply_closed_bar(state, DATA["profile"],
                                              long_bar(1, structure_state="INVALID"))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "INVALIDATED_REVIEW")
        self.assertEqual(reason, "STRUCTURE_INVALIDATED_REVIEW")

    def test_module_is_isolated_from_orders_and_ea_shell(self):
        source = (ROOT / "TradeManager/ExpectedPath.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for forbidden in ("OrderSend", "CTrade", "WebRequest", "FileOpen"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("ExpectedPath.mqh", shell)


if __name__ == "__main__":
    unittest.main()
