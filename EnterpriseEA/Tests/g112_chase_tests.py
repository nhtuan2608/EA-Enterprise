"""G112 step 1 (research/long/g112_chase.py): position engine (exits, adds, stop-adding, random adds), first-touch
levels, and signals / features without look-ahead."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g109_zones as gz  # noqa: E402
import g112_chase as gc  # noqa: E402


def path(closes, wick=0.05):
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    return o, np.maximum(o, c) + wick, np.minimum(o, c) - wick, c


def run(closes, d=1, entry=100.0, stop=99.0, exit_mode="none", target=None, add_mode="none", stop_add=None, rand=None, swing=None):
    o, h, l, c = path(closes)
    n = len(c)
    sa = np.zeros(n, bool) if stop_add is None else stop_add
    sw = np.full(n, np.nan) if swing is None else swing
    return gc.run_position(d, entry, stop, 1.0, o, h, l, c, np.zeros(n), sw, sa, exit_mode, target, add_mode, rand)


class G112ChaseTests(unittest.TestCase):
    def test_tp_and_stop(self):
        self.assertAlmostEqual(run([100.2, 101.0, 102.1], exit_mode="X1", target=102.0)["R"], 2.0)
        self.assertAlmostEqual(run([100.2, 99.5, 98.0], exit_mode="X1", target=102.0)["R"], -1.0)

    # rise to +1.2R, pull back 0.4, new high at bar 7 -> add at the open of bar 8, stop to break-even
    UP = [100.3, 100.6, 100.9, 101.2, 100.8, 100.9, 101.0, 101.5, 101.6, 101.8, 99.0]

    def test_rule_add_and_break_even(self):
        r = run(self.UP, add_mode="rule")
        self.assertEqual(r["adds"], 1)
        add_px = 101.5                                                    # open of bar 8 = close of bar 7
        self.assertAlmostEqual(r["R"], (100.0 - 100.0) + (100.0 - add_px))  # both units out at the first entry
        self.assertEqual(run(self.UP, add_mode="none")["adds"], 0)

    def test_stop_adding_blocks_rule_not_random(self):
        sa = np.ones(len(self.UP), bool)
        self.assertEqual(run(self.UP, add_mode="rule", stop_add=sa)["adds"], 0)
        self.assertEqual(run(self.UP, add_mode="random", stop_add=sa, rand=[7])["adds"], 1)

    def test_no_add_before_one_r_or_without_pullback(self):
        self.assertEqual(run([100.2, 100.4, 100.6, 100.8, 100.9, 100.95, 100.97, 100.99, 100.6, 100.98], add_mode="rule")["adds"], 0)
        straight = [100.3, 100.6, 100.9, 101.2, 101.4, 101.6, 101.8, 102.0, 102.2]   # no pullback
        self.assertEqual(run(straight, add_mode="rule")["adds"], 0)

    def test_trailing_ratchets(self):
        sw = np.array([np.nan, 99.5, 100.4, 100.2, 100.2, 100.2])
        r = run([100.3, 100.8, 101.3, 101.0, 100.3, 100.0], exit_mode="X2", swing=sw)
        self.assertAlmostEqual(r["R"], 0.4)                               # out at the 100.4 swing; it never moved down
        r3 = run([100.5, 101.0, 102.0, 101.0, 100.4], exit_mode="X3")
        self.assertAlmostEqual(r3["R"], (102.05 - 1.5) - 100.0)            # 1.5 ATR under the best bid high

    def test_time_exit(self):
        r = run([100.2] * (gc.MAX_BARS + 5))
        self.assertEqual(r["bars"], gc.MAX_BARS)
        self.assertAlmostEqual(r["R"], 0.2)

    def test_first_touch(self):
        o, h, l, c = path([100.5, 101.2, 102.3, 101.0, 98.5])
        ft = gc.first_touch_r(1, 100.0, 1.0, h, l, np.zeros(5))
        self.assertEqual((ft["hit1"], ft["hit2"], ft["hit3"]), (1, 1, 0))

    def test_signals_without_look_ahead(self):
        rng = np.random.default_rng(21)
        n = 30 * 288
        t = int(pd.Timestamp("2025-02-03").timestamp()) + 300 * np.arange(n)
        c = 3000 + np.cumsum(rng.normal(0, 1.5, n))
        o = np.r_[c[0], c[:-1]]
        df = pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) + rng.uniform(0, 1, n),
                           "low": np.minimum(o, c) - rng.uniform(0, 1, n), "close": c,
                           "tickvol": rng.integers(50, 500, n).astype(float), "spread": 5, "sp": 0.05})
        Z, _, D = gz.build(df, None, "XAUUSD")
        C = gc.build(df, Z, D, None)
        self.assertGreater(len(C), 30)
        cut = int(n * 0.8)
        p = df.iloc[:cut].reset_index(drop=True)
        Zp, _, Dp = gz.build(p, None, "XAUUSD")
        Cp = gc.build(p, Zp, Dp, None)
        feats = ["entry", "stop", "risk", "adx_h1", "adx_up", "d1_with", "h4_side", "rv1", "rv6", "delta12", "diverg",
                 "move6", "body", "void_ahead", "zone_ahead", "compress", "day_pos"]
        m = C.merge(Cp, on=["time", "typ", "d"], suffixes=("", "_p"))
        m = m[m["e"] < cut - 13]
        self.assertGreater(len(m), 10)
        for f in feats:
            self.assertTrue(np.allclose(m[f].to_numpy(float), m[f + "_p"].to_numpy(float), equal_nan=True), f)
        self.assertTrue((C["risk"] > 0).all())
        self.assertTrue(((C["X1_none"] >= -1 - 1e-9) & (C["X1_none"] <= 2 + 1e-9)).all())

    def test_random_control_avoids_the_signal_day(self):
        import g108_data as g8
        rng = np.random.default_rng(3)
        n = 6 * 288
        t = int(pd.Timestamp("2025-02-03").timestamp()) + 300 * np.arange(n)
        c = np.r_[np.full(288, 100.0), 100 + np.cumsum(np.full(n - 288, 0.05))]   # day 1 flat, then a steady rise
        df = pd.DataFrame({"time": t, "open": c, "high": c + 0.01, "low": c - 0.01, "close": c, "sp": 0.0})
        sig_day = int(t[300] // 86400)
        C = pd.DataFrame({"day": [int(t[288] // 86400)], "d": [1], "risk": [1000.0], "period": ["train"]})
        # with only the flat first day and rising days available, a fair control never draws from the signal day
        orig = gc.gs.simulate
        seen = []
        def spy(d, en, st, tg, h, l, c2, sp):
            seen.append(en); return orig(d, en, st, tg, h, l, c2, sp)
        gc.gs.simulate = spy
        try:
            gc.random_control(df, C, draws=50)
        finally:
            gc.gs.simulate = orig
        days_drawn = {int(t[np.nonzero(np.isclose(df["open"].to_numpy(), e))[0][0]] // 86400) for e in seen if e != 100.0}
        self.assertNotIn(int(C["day"][0]), days_drawn)
        self.assertTrue(len(seen) == 50)


if __name__ == "__main__":
    unittest.main()
