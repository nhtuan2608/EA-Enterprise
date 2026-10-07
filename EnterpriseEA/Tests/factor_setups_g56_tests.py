"""G56 B + C: the trade walk of research/long/factor_setups.py and the walk-forward bookkeeping."""
import os
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
sys.path.insert(0, str(ROOT / "research" / "g10"))

_old = os.environ.get("EEA_RESEARCH_DATA")
import factor_setups as fs  # noqa: E402
if _old is None:
    os.environ.pop("EEA_RESEARCH_DATA", None)
else:
    os.environ["EEA_RESEARCH_DATA"] = _old


def data(path, atr=1.0, spread=0.0):
    o = np.array([p[0] for p in path], float)
    return {"open": o, "high": np.array([p[1] for p in path], float), "low": np.array([p[2] for p in path], float),
            "close": np.array([p[3] for p in path], float), "spread": np.full(len(path), spread),
            "atr": np.full(len(path), atr), "point": 1.0, "commission": 0.0}


class WalkTests(unittest.TestCase):
    def test_stop_before_target_in_the_same_bar(self):
        d = data([(100, 100, 100, 100), (100, 103, 98, 101)])
        self.assertEqual(fs.simulate(d, 0, 1, 1.0, "TP2R", 24, 240), (-1.0, 1))

    def test_targets(self):
        d = data([(100, 100, 100, 100), (100, 102.5, 99.5, 102), (102, 103.5, 101.5, 103)])
        self.assertEqual(fs.simulate(d, 0, 1, 1.0, "TP2R", 24, 240), (2.0, 1))
        self.assertEqual(fs.simulate(d, 0, 1, 1.0, "TP3R", 24, 240), (3.0, 2))

    def test_time_exit_at_the_close(self):
        d = data([(100, 100, 100, 100), (100, 100.5, 99.5, 100.4), (100.4, 100.6, 100.1, 100.3)])
        r, x = fs.simulate(d, 0, 1, 1.0, "TIME", 2, 240)
        self.assertEqual(x, 2)
        self.assertAlmostEqual(r, 0.3)

    def test_gap_fills_at_the_open(self):
        d = data([(100, 100, 100, 100), (97, 97.5, 96, 97)])
        self.assertAlmostEqual(fs.simulate(d, 0, 1, 1.0, "TRAIL3", 24, 240)[0], -3.0)

    def test_runner_banks_half_and_breaks_even(self):
        d = data([(100, 100, 100, 100), (100, 101.2, 99.8, 101), (101, 101.1, 99.9, 100)])
        r, x = fs.simulate(d, 0, 1, 1.0, "RUNNER", 24, 240)
        self.assertEqual(x, 2)
        self.assertAlmostEqual(r, 0.5)                   # half at +1R, the rest out at break-even

    def test_short_pays_the_spread_and_commission(self):
        d = data([(100, 100, 100, 100), (100, 100.2, 99.4, 99.5)], spread=0.1)
        d["commission"] = 0.1
        r, _ = fs.simulate(d, 0, -1, 1.0, "TIME", 1, 240)
        self.assertAlmostEqual(r, (100 - 99.6) / 1.0 - 0.1)


class BookkeepingTests(unittest.TestCase):
    def block(self):
        ev = []
        for i, y, res in ((10, 2020, (1.0, 30)), (20, 2020, (-1.0, 25)), (40, 2021, (2.0, 50)), (45, 2021, (1.0, 60))):
            ev.append({"i": i, "dir": 1, "year": y, "hour": 9, "macd": i != 40,
                       "res": {(s, k): res for s in fs.STOPS for k in fs.EXITS}})
        return {"symbol": "EURUSD", "d": None, "events": ev}

    def test_one_position_at_a_time_and_filters(self):
        b = self.block()
        got = fs.trades(b, 1.0, "TIME", False, {2020, 2021})
        self.assertEqual([t["i"] for t in got], [10, 40])            # 20 inside the first trade, 45 inside the third
        self.assertEqual([t["i"] for t in fs.trades(b, 1.0, "TIME", True, {2020, 2021})], [10, 45])
        self.assertEqual([t["i"] for t in fs.trades(b, 1.0, "TIME", False, {2021})], [40])

    def test_train_window_never_holds_the_test_year(self):
        spec = fs.SETUPS["SW1"]
        self.assertEqual(fs.train_years(spec, 2014, []), {2010, 2011, 2012, 2013})
        blk = [{"events": [{"year": 2021}]}]
        self.assertEqual(fs.train_years(fs.SETUPS["SC1"], 2025, blk), {2021, 2022, 2023, 2024})


if __name__ == "__main__":
    unittest.main()
