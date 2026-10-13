"""G111 step 1 (research/long/g111_levels.py): Fibonacci levels, zone tests, the reversal trade T, no look-ahead."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g109_zones as gz  # noqa: E402
import g111_levels as gl  # noqa: E402


def synthetic(days=45, seed=12):
    rng = np.random.default_rng(seed)
    n = days * 288
    t = int(pd.Timestamp("2025-02-03").timestamp()) + 300 * np.arange(n)
    c = 3000 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.9, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.9, n)
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c,
                         "tickvol": rng.integers(50, 500, n).astype(float), "spread": 5, "sp": 0.05})


class G111LevelsTests(unittest.TestCase):
    def test_fib_levels(self):
        up = dict(gl.fib_levels(100.0, 200.0, True, (0.382, 0.5, 0.618)))
        self.assertAlmostEqual(up[0.5], 150.0); self.assertAlmostEqual(up[0.382], 161.8); self.assertAlmostEqual(up[0.618], 138.2)
        dn = dict(gl.fib_levels(100.0, 200.0, False, (0.382,)))
        self.assertAlmostEqual(dn[0.382], 138.2)                          # retracement up from the low of a down leg

    def test_find_test(self):
        # level 105 +/- 0.5 above the price: a touch closing inside the band is a test
        h = np.array([104.0, 104.7, 105.2]); l = h - 1; c = np.array([103.8, 104.6, 104.9])
        self.assertEqual(gl.find_test(1, 105.0, 0.5, h, l, c), 1)
        c2 = np.array([103.8, 105.7, 105.0]); h2 = np.array([104.0, 105.9, 105.2])
        self.assertIsNone(gl.find_test(1, 105.0, 0.5, h2, h2 - 1, c2))   # first reach closes beyond: a break
        self.assertIsNone(gl.find_test(1, 105.0, 0.5, np.array([104.0]), np.array([103.0]), np.array([103.5])))
        l3 = np.array([96.0, 95.3]); self.assertEqual(gl.find_test(-1, 95.0, 0.5, l3 + 1, l3, l3 + 0.5), 1)
        # a buy limit at 95.5 fills only when the ask (bid + spread) reaches it
        l4 = np.array([96.0, 95.45, 95.2]); sp4 = np.array([0.1, 0.1, 0.1])
        self.assertEqual(gl.find_test(-1, 95.0, 0.5, l4 + 1, l4, l4 + 0.5, sp4), 2)   # bar 1: ask 95.55 > 95.5

    def test_trade_t_fill_bar_only_stops(self):
        sp = np.zeros(3)
        # sell at 104.5, stop 106: the fill bar's low reaching the target does not count; bar 1 hits it
        r = gl.trade_t(-1, 104.5, 106.0, 101.5, np.array([104.8, 104.0, 102.0]), np.array([101.0, 101.4, 101.0]), np.array([104.6, 102.0, 101.5]), sp)
        self.assertEqual(r["a"], 2.0)
        r2 = gl.trade_t(-1, 104.5, 106.0, 101.5, np.array([106.1, 104.0]), np.array([104.0, 101.0]), np.array([105.0, 101.5]), np.zeros(2))
        self.assertEqual(r2["a"], -1.0)                                   # stopped on the fill bar

    def test_no_look_ahead(self):
        df = synthetic(days=45, seed=12)
        Z, C, D = gz.build(df, None, "XAUUSD")
        LV, TS = gl.build(df, Z, D)
        self.assertGreater(len(TS), 30)
        cut = int(len(df) * 0.85)
        part = df.iloc[:cut].reset_index(drop=True)
        Zp, Cp, Dp = gz.build(part, None, "XAUUSD")
        LVp, TSp = gl.build(part, Zp, Dp)
        feats = ["w", "side", "d", "entry", "stop", "risk", "conf", "rv6", "rv12", "rv_slope", "speed", "delta12",
                 "diverg", "adx_h1", "d1_with", "h4_side", "dist_open"]
        m = TS.merge(TSp, on=["time", "fam", "ratio", "center"], suffixes=("", "_p"))
        m = m[m["k"] < cut - 13]
        self.assertGreater(len(m), 10)
        for f in feats:
            self.assertTrue(np.allclose(m[f].to_numpy(float), m[f + "_p"].to_numpy(float), equal_nan=True), f)

    def test_rules(self):
        df = synthetic(days=45, seed=12)
        Z, C, D = gz.build(df, None, "XAUUSD")
        LV, TS = gl.build(df, Z, D)
        self.assertTrue((TS["d"] == -TS["side"]).all())
        self.assertTrue(np.allclose(TS["entry"], TS["center"] - TS["side"] * TS["w"]))
        self.assertTrue(((TS["Ra"] >= -1 - 1e-9) & (TS["Ra"] <= gl.RR + 1e-9)).all())
        self.assertTrue((TS["conf"] >= 0).all())
        self.assertTrue(set(TS["fam"]) <= {"PFIB", "PFAKE", "AFIB", "AFAKE", "DFIB", "DFAKE", "ZONE", "ZFAKE"})


if __name__ == "__main__":
    unittest.main()
