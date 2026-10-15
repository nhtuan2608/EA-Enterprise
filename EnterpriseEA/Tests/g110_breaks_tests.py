"""G110 step 1 (research/long/g110_breaks.py): relative volume from earlier days only, close location, break and
hold labels, events built without look-ahead."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g109_zones as gz  # noqa: E402
import g110_breaks as gb  # noqa: E402


def synthetic(days=40, seed=8):
    rng = np.random.default_rng(seed)
    n = days * 288
    t = int(pd.Timestamp("2025-02-03").timestamp()) + 300 * np.arange(n)
    c = 3000 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.9, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.9, n)
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c,
                         "tickvol": rng.integers(50, 500, n).astype(float), "spread": 5, "sp": 0.05})


class G110BreaksTests(unittest.TestCase):
    def test_rel_volume_uses_earlier_days_only(self):
        t = np.arange(15) * 86400                                         # the same minute on 15 days
        tv = np.arange(1, 16, dtype=float)
        rv = gb.rel_volume(t, tv, days=20)
        self.assertTrue(np.isnan(rv[:10]).all())                         # fewer than 10 earlier days
        self.assertAlmostEqual(rv[10], 11 / np.median(np.arange(1, 11)))  # median of the 10 earlier values
        tv2 = tv.copy(); tv2[14] = 1e6                                   # a later spike does not change earlier values
        self.assertTrue(np.allclose(gb.rel_volume(t, tv2, 20)[:14], rv[:14], equal_nan=True))

    def test_clv(self):
        o = np.array([1.0, 1.0, 1.0]); h = np.array([2.0, 2.0, 1.0]); l = np.array([0.0, 0.0, 1.0]); c = np.array([2.0, 0.0, 1.0])
        self.assertEqual(gb.clv(o, h, l, c).tolist(), [1.0, -1.0, 0.0])

    def test_break_and_hold(self):
        c = np.array([99.0, 100.6, 100.4, 100.7, 100.9])
        self.assertEqual(gb.break_event(1, 100.5, c), 4)
        self.assertEqual(gb.hold_and_reclaim(1, 100.5, np.array([100.8, 100.6, 100.9])), (True, None))
        self.assertEqual(gb.hold_and_reclaim(1, 100.5, np.array([100.8, 100.5, 101.0])), (False, 1))
        self.assertEqual(gb.hold_and_reclaim(-1, 99.5, np.array([99.0, 99.7])), (False, 1))

    def test_events_without_look_ahead(self):
        df = synthetic()
        Z, C, D = gz.build(df, None, "XAUUSD")
        E = gb.build(df, Z, D)
        self.assertGreater(len(E), 50)
        feats = ["tv_break", "tv_appr", "tv_slope", "body", "effort", "delta6", "delta12", "price12", "diverg", "wick",
                 "beyond", "compress", "adx_h1", "di_h1", "d1_with", "h4_side", "open_dist",
                 "nr7", "expand", "void_ahead", "void_size", "zone_ahead", "bos_h1", "bos_dist", "struct_m5", "pole",
                 "cons_rng", "cons_slope", "flag_pat", "wedge_hi", "wedge_lo", "wedge_conv", "wedge_type", "wedge_with", "pa_close"]
        cut = int(len(df) * 0.8)
        part = df.iloc[:cut].reset_index(drop=True)
        Zp, Cp, Dp = gz.build(part, None, "XAUUSD")
        Ep = gb.build(part, Zp, Dp)
        key = ["time", "type", "s", "center"]
        m = E.merge(Ep, on=key, suffixes=("", "_p"))
        m = m[m["j"] < cut - 13]                                         # the cut data's last H1 bar is partial
        self.assertGreater(len(m), 20)
        for f in feats:
            a, b = m[f].to_numpy(float), m[f + "_p"].to_numpy(float)
            self.assertTrue(np.allclose(a, b, equal_nan=True), f)

    def test_trades_rules(self):
        df = synthetic()
        Z, C, D = gz.build(df, None, "XAUUSD")
        E = gb.build(df, Z, D)
        fo = E[E["fo_Ra"].notna()]
        fa = E[E["fa_Ra"].notna()]
        self.assertGreater(len(fo) + len(fa), 5)
        self.assertTrue((fo["fo_i"] > fo["j"]).all() and (fo["fo_i"] <= fo["j"] + gb.LIMIT_BARS).all())
        self.assertTrue((fa["hold"] == 0).all())                         # a fade needs a close back inside
        self.assertTrue((fa["fa_i"] <= fa["j"] + gb.HOLD_BARS + 1).all())
        self.assertTrue(((E["fo_Ra"].dropna() >= -1.0 - 1e-9) & (E["fo_Ra"].dropna() <= gb.RR + 1e-9)).all())

    def test_flag_pattern(self):
        n = 60; j = 50; a30 = 1.0
        c = np.zeros(n); c[:14] = 100.0
        c[14:38] = np.linspace(100, 102, 24)                            # pole j-36 .. j-12: +2 ATR
        c[37:49] = np.linspace(102.0, 101.7, 12)                         # tight consolidation drifting down
        c[49:] = 102.3
        h = c + 0.05; l = c - 0.05
        pole, rng, cons, flag = gb.flag_feats(c, h, l, j, 1, a30)
        self.assertGreaterEqual(pole, 1.5); self.assertLessEqual(rng, 1.0); self.assertLessEqual(cons, 0)
        self.assertEqual(flag, 1)
        self.assertEqual(gb.flag_feats(c, h, l, j, -1, a30)[3], 0)       # a down break is not this flag

    def test_wedges(self):
        n = 40; j = 30; x = np.arange(n, dtype=float)
        h = 100 + 0.10 * x; l = 99 + 0.15 * x                             # both rising, lows faster: rising wedge
        sh, sl, conv, wt, ww = gb.wedge_feats(h, l, j, -1, 1.0)
        self.assertEqual(wt, 1); self.assertEqual(ww, 1)                 # broken down: the classic side
        self.assertEqual(gb.wedge_feats(h, l, j, 1, 1.0)[4], -1)
        h2 = 100 - 0.15 * x; l2 = 99 - 0.10 * x                           # falling wedge
        self.assertEqual(gb.wedge_feats(h2, l2, j, 1, 1.0)[3:], (-1, 1))
        h3 = 100 + 0.10 * x; l3 = 99 + 0.10 * x                           # parallel channel: no wedge
        self.assertEqual(gb.wedge_feats(h3, l3, j, 1, 1.0)[3], 0)

    def test_nr7_and_void(self):
        h = np.array([10, 10, 10, 10, 10, 10, 9.6, 10, 10.0]); l = np.array([9, 9, 9, 9, 9, 9, 9.5, 9, 9.0])
        self.assertEqual(gb.nr7(h, l, 8), 1)                              # bar 6 (j-2) is the narrowest of 7
        # a bearish gap above the price (bars 0..2), never filled, is the void ahead of an up break
        h2 = np.array([105.0, 104.0, 102.0, 101.0, 101.5]); l2 = np.array([104.0, 102.5, 101.0, 100.0, 100.5])
        fv = gb.m5_fvgs(h2, l2)
        import g108_data as g8
        d, size = gb.void_ahead(4, 1, 101.0, fv, g8.RangeExt(h2, np.maximum), g8.RangeExt(l2, np.minimum), 1.0)
        self.assertAlmostEqual(d, 1.0); self.assertAlmostEqual(size, 2.0)  # gap 102 .. 104, 1 ATR above 101
        self.assertEqual(gb.void_ahead(4, -1, 101.0, fv, g8.RangeExt(h2, np.maximum), g8.RangeExt(l2, np.minimum), 1.0)[0], 9.0)


if __name__ == "__main__":
    unittest.main()
