"""G51: the News Guard break-even on T2 trades (research/g10/t2_news_be.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidates_eval as ce  # noqa: E402
import pyramid  # noqa: E402
import t2_news_be as nb  # noqa: E402

H4 = 4 * 3600


def bars(path, atr=1.0):
    """H4 bars from (open, high, low, close); spread 0, ATR fixed."""
    return [{"time": k * H4, "open": o, "high": h, "low": lo, "close": c, "spread": 0, "atr": atr}
            for k, (o, h, lo, c) in enumerate(path)]


class WalkTests(unittest.TestCase):
    def setUp(self):
        # long from 100, stop 98 (risk 2): up to 101.5 (+0.75R), back to 99.9, then up to 106
        self.c = {"entry": bars([(100, 100, 100, 100), (100, 101.5, 99.9, 101.5), (101.5, 101.6, 99.9, 100.5),
                                 (100.5, 106, 100.4, 105.5), (105.5, 106, 105, 105.8)]), "point": 0.01, "symbol": "X"}
        self.t = {"symbol": "X", "i": 0, "dir": 1, "entry": 100.0, "stop": 98.0, "target": 0.0, "zl": 0.0, "zh": 0.0}

    def test_without_events_it_is_the_research_walk(self):
        mine = nb.walk(self.c, self.t, ce.T2_RULE)
        ref = pyramid.walk(self.c, self.t, ce.T2_RULE, 0, 100.0, 98.0, None)
        self.assertAlmostEqual(mine[0], ref[0])
        self.assertEqual(mine[1], ref[1])
        self.assertFalse(mine[2])

    def test_break_even_before_an_event_cuts_the_trade(self):
        event = 2 * H4 + 3600                 # inside bar 2, whose open (101.5) is +0.75R
        r, exit_i, used = nb.walk(self.c, self.t, ce.T2_RULE, [event], 0)
        self.assertTrue(used)
        self.assertEqual(exit_i, 2)           # bar 2 dips to 99.9 < entry
        self.assertAlmostEqual(r, 0.0)
        self.assertGreater(nb.walk(self.c, self.t, ce.T2_RULE)[0], 2.0)    # without it the trade runs on

    def test_no_break_even_below_the_minimum_r(self):
        event = 1 * H4 + 3600                 # bar 1 opens at entry: 0R < 0.3R
        r, _, used = nb.walk(self.c, self.t, ce.T2_RULE, [event], 0)
        self.assertFalse(used)
        self.assertAlmostEqual(r, nb.walk(self.c, self.t, ce.T2_RULE)[0])

    def test_trigger_is_fifteen_minutes_before_the_event_in_server_time(self):
        event = 2 * H4 + 10 * 60              # trigger 5 min before bar 2 -> falls in bar 1 (open 0R): nothing
        self.assertFalse(nb.walk(self.c, self.t, ce.T2_RULE, [event], 0)[2])
        self.assertTrue(nb.walk(self.c, self.t, ce.T2_RULE, [event], 3600)[2])     # UTC+1 server: trigger in bar 2


    def test_g52_tightened_trail_instead_of_break_even(self):
        event = 2 * H4 + 3600                 # bar 2 opens at 101.5 (+0.75R), dips to 99.9
        # k=1: stop 100.5 (above entry) -> out at +0.25R; k=2: stop 99.5 -> survives the dip and runs on
        r1, exit1, used1 = nb.walk(self.c, self.t, ce.T2_RULE, [event], 0, news_k=1.0)
        self.assertTrue(used1)
        self.assertEqual(exit1, 2)
        self.assertAlmostEqual(r1, 0.25)
        r2, _, used2 = nb.walk(self.c, self.t, ce.T2_RULE, [event], 0, news_k=2.0)
        self.assertTrue(used2)
        self.assertGreater(r2, 2.0)
        # looser than the current stop: nothing changes
        self.assertFalse(nb.walk(self.c, self.t, ce.T2_RULE, [event], 0, news_k=5.0)[2])
        self.assertEqual(nb.TRAIL_K, (1.0, 1.5, 2.0))


class EventTests(unittest.TestCase):
    def test_direct_events_of_the_symbol_without_ignored_names(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "news.jsonl"
            ok = {"time_rule": "calendar_now_offset"}
            rows = [dict(ok, symbol="EURUSD", impact="DIRECT", event="CPI y/y", event_utc=10),
                    dict(ok, symbol="EURUSD", impact="DIRECT", event="CPI y/y", event_utc=10),
                    {"symbol": "EURUSD", "impact": "DIRECT", "event": "PPI m/m", "event_utc": 15},   # before G54: unused
                    dict(ok, symbol="EURUSD", impact="INDIRECT", event="GDP q/q", event_utc=20),
                    dict(ok, symbol="EURUSD", impact="DIRECT", event="Initial Jobless Claims", event_utc=30),
                    dict(ok, symbol="XAUUSD", impact="DIRECT", event="CPI y/y", event_utc=40)]
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            self.assertEqual(nb.news_times(p, "EURUSD", ["initial jobless claims"]), [10])

    def test_keywords_and_guard_values_follow_the_ea(self):
        self.assertIn("initial jobless claims", nb.ignore_keywords())
        state = (ROOT / "News" / "NewsState.mqh").read_text(encoding="utf-8")
        self.assertIn(f"c.be_before_min={nb.BE_BEFORE_MIN}; c.be_min_r={nb.BE_MIN_R};", state)

    def test_paired_interval(self):
        lo, hi = nb.paired_ci([0.0] * 10 + [-1.0])
        self.assertLessEqual(lo, -0.09)
        self.assertGreaterEqual(hi, -0.1)


if __name__ == "__main__":
    unittest.main()
