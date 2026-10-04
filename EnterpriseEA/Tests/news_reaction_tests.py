"""News Reaction Recorder: measurement only (TC-NR-01..11)."""
import re
import unittest
from pathlib import Path

from news_reaction_oracle import surprise, path, stats


ROOT = Path(__file__).resolve().parents[1]
T = 1791207900
ATR = 1.0


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


def bars_from(closes_by_minute):
    """closes_by_minute: {minute_offset_from_T: close}; bar opens at T+offset*60."""
    out = []
    for m in sorted(closes_by_minute):
        c = closes_by_minute[m]
        out.append({"t": T + m * 60, "o": c, "h": c + 0.05, "l": c - 0.05, "c": c})
    return out


class ReactionPathTests(unittest.TestCase):
    def test_moves_and_direction(self):  # TC-NR-01
        closes = {m: 100.0 for m in range(-30, 0)}
        closes.update({m: 100.0 + 0.1 * (m + 1) for m in range(0, 240)})
        r = path(bars_from(closes), T, ATR)
        self.assertEqual(r["quality"], "OK")
        self.assertAlmostEqual(r["move"][0], 0.1)        # close of the bar ending at T+1
        self.assertAlmostEqual(r["move"][1], 0.5)
        self.assertAlmostEqual(r["move"][3], 6.0)
        self.assertTrue(all(r["move_ok"]))
        self.assertEqual(r["first_direction"], "UP")
        self.assertFalse(r["reversal_60"])

    def test_reversal_and_missing_data(self):  # TC-NR-01, TC-NR-07
        closes = {m: 100.0 for m in range(-30, 0)}
        closes.update({m: 100.5 for m in range(0, 5)})
        closes.update({m: 99.0 for m in range(5, 70)})
        r = path(bars_from(closes), T, ATR)
        self.assertTrue(r["reversal_60"])
        self.assertFalse(r["move_ok"][4])                # no data for 240 minutes
        no_pre = path(bars_from({m: 100.0 for m in range(0, 70)}), T, ATR)
        self.assertEqual(no_pre["quality"], "INCOMPLETE_NO_PRE_PRICE")
        short = path(bars_from({m: 100.0 for m in range(-30, 20)}), T, ATR)
        self.assertEqual(short["quality"], "INCOMPLETE_NO_60M_PRICE")

    def test_volatility_recovery(self):
        closes = {m: 100.0 for m in range(-30, 0)}
        closes.update({m: 100.0 + (2.0 if m % 2 else 0.0) for m in range(0, 10)})   # wild 10 minutes
        closes.update({m: 100.0 for m in range(10, 70)})
        r = path(bars_from(closes), T, ATR)
        self.assertEqual(r["vol_recovery_min"], 15)


class SurpriseTests(unittest.TestCase):
    def test_missing_values_never_fake_a_surprise(self):  # TC-NR-02 / TC-020
        self.assertEqual(surprise(None, 1.0, 1, [])["quality"], "NO_ACTUAL")
        self.assertEqual(surprise(1.0, None, 1, [])["quality"], "NO_FORECAST")

    def test_history_threshold(self):  # TC-NR-03
        r7 = surprise(3.1, 2.8, 1, [0.1, -0.2, 0.3, 0.0, -0.1, 0.2, -0.3])
        self.assertEqual(r7["quality"], "SURPRISE_HISTORY_INSUFFICIENT")
        self.assertEqual(r7["side"], "ABOVE")
        self.assertIsNone(r7["std"])
        r8 = surprise(3.1, 2.8, 1, [0.1, -0.2, 0.3, 0.0, -0.1, 0.2, -0.3, 0.1])
        self.assertEqual(r8["quality"], "OK")
        self.assertGreater(r8["std"], 1.0)
        self.assertEqual(surprise(2.8, 2.8, 1, [])["side"], "INLINE")


class ReactionStatsTests(unittest.TestCase):
    def test_suggestion_needs_six_samples(self):  # TC-NR-09
        row = {"move15_atr": 1.0, "move60_atr": 2.0, "spread_ratio": 3.0, "recovery_min": 22, "reversal": False}
        self.assertFalse(stats([row] * 5)["has_suggestion"])
        s = stats([row] * 6)
        self.assertTrue(s["has_suggestion"])
        self.assertEqual(s["suggested_post_min"], 25)
        self.assertEqual(s["suggested_pre"], "KEEP")
        quiet = dict(row, move60_atr=0.2)
        self.assertEqual(stats([quiet] * 6)["suggested_pre"], "REDUCE")


class RecorderStaticTests(unittest.TestCase):
    def setUp(self):
        self.rec = read("News/NewsReactionRecorder.mqh")
        self.pure = read("News/NewsReaction.mqh")

    def test_measurement_only(self):  # TC-NR-10
        for text in (self.rec, self.pure):
            for forbidden in ("OrderSend", "EEA_ExecutionSubmit", "EEA_ExecutionModifyProtective",
                              "EEA_ExecutionClosePosition", "EEA_ExecutionCancelPending"):
                self.assertNotIn(forbidden, text)

    def test_idempotent_keys_and_windows(self):  # TC-NR-04, 05
        self.assertIn('const string key=IntegerToString((long)value.id)+"|"+canonical;', self.rec)
        self.assertIn("if(EEA_NrKnown(rt,key)) return 0;", self.rec)
        self.assertIn("#define EEA_NR_LIVE_LOOKBACK_SECONDS (48*3600)", self.rec)
        self.assertIn("#define EEA_NR_SETTLE_SECONDS (4*3600+300)", self.rec)
        self.assertIn("#define EEA_NR_BACKFILL_SECONDS (84*86400)", self.rec)

    def test_spread_falls_back_to_m1(self):  # TC-NR-06
        self.assertIn('r.spread_source="TICKS";', self.rec)
        self.assertIn('r.spread_source="M1";', self.rec)

    def test_backfill_is_budgeted_and_resumable(self):  # TC-NR-11
        update = section(self.rec, "void EEA_NewsReactionUpdate")
        self.assertIn("int budget=EEA_NR_MAX_PER_TIMER;", update)
        self.assertIn("EEA_NrWriteBackfill(rt,root);", update)
        self.assertIn("EEA_NR_MAX_NOT_READY", update)

    def test_direct_and_indirect_impact(self):
        self.assertIn('"DIRECT"', self.rec)
        self.assertIn('"INDIRECT"', self.rec)
        state = read("News/NewsState.mqh")
        sector = section(state, "bool EEA_NewsStrengthSector")
        for token in ("CALENDAR_SECTOR_MONEY", "CALENDAR_SECTOR_PRICES", "CALENDAR_SECTOR_JOBS", "CALENDAR_SECTOR_GDP"):
            self.assertIn(token, sector)
        indirect = section(state, "bool EEA_NewsIndirectAffects")
        self.assertIn("!EEA_NewsAffects(currencies,event_currency)", indirect)

    def test_break_even_value_is_measured(self):  # TC-NR-08
        record = section(self.rec, "int EEA_NrRecord")
        self.assertIn("r.be_would_have_hit_sl++", record)
        self.assertIn("t.initial_sl", record)


if __name__ == "__main__":
    unittest.main()
