"""G108 step 1 (research/long/g108_data.py): swings, liquidity targets, first-touch labels and no look-ahead."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g108_data as g  # noqa: E402
import g108_patterns as gp  # noqa: E402
import g108_features as gf  # noqa: E402
import g108_models as gm  # noqa: E402


def synthetic(days=4, seed=7):
    """Random-walk M5 bars, server time, with a weekend-free run of `days` days."""
    rng = np.random.default_rng(seed)
    n = days * 288
    t = int(pd.Timestamp("2025-03-03").timestamp()) + 300 * np.arange(n)
    c = 3000 + np.cumsum(rng.normal(0, 1.0, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.8, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.8, n)
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "spread": 25, "sp": 0.25})


class G108PathTests(unittest.TestCase):
    def test_fractals_two_bars_each_side(self):
        h = np.array([1, 2, 3, 5, 4, 3, 2, 3, 4, 6, 5, 4], float)
        l = h - 1
        sh, sl = g.fractals(h, l)
        self.assertEqual(sh.tolist(), [3, 9])
        self.assertEqual(sl.tolist(), [6])

    def test_swing_known_only_after_confirmation(self):
        idx = np.array([3]); lev = np.arange(10, dtype=float)
        last, prev = g.last_two_confirmed(idx, lev, 8)
        self.assertTrue(np.isnan(last[4]))                 # bar 3 confirmed at the close of bar 5
        self.assertEqual(last[5], 3.0)
        self.assertTrue(np.isnan(prev[7]))

    def test_range_ext_matches_brute_force(self):
        x = np.random.default_rng(1).normal(size=300)
        mx, mn = g.RangeExt(x, np.maximum), g.RangeExt(x, np.minimum)
        for a, b in ((0, 0), (5, 77), (100, 299), (17, 18)):
            self.assertEqual(mx.q(a, b), x[a:b + 1].max())
            self.assertEqual(mn.q(a, b), x[a:b + 1].min())

    def test_first_touch_buy(self):
        sp = np.zeros(3)
        h = np.array([101, 103, 104.0]); l = np.array([99.5, 100, 100.0])
        self.assertEqual(g.first_touch(1, 100, 98, 104, h, l, sp, 100, 0), (2.0, 1, 2))    # target first
        l2 = np.array([99.5, 97.9, 100.0])
        self.assertEqual(g.first_touch(1, 100, 98, 104, h, l2, sp, 100, 0), (-1.0, -1, 1))  # stop first
        h3 = np.array([101, 104.5, 104.0]); l3 = np.array([99.5, 97.0, 100.0])
        self.assertEqual(g.first_touch(1, 100, 98, 104, h3, l3, sp, 100, 0), (-1.0, -1, 1))  # same bar: stop
        R, out, k = g.first_touch(1, 100, 98, 110, h, l, sp, 101, 0)
        self.assertEqual((R, out, k), (0.5, 0, 2))                                                 # day end at the close

    def test_first_touch_sell_uses_ask(self):
        sp = np.full(2, 0.5)
        h = np.array([100.2, 100.0]); l = np.array([96.6, 95.0])
        # sell entry 100 (bid), stop 102, target 96: ask low = 96.6 + 0.5 = 97.1 > 96, then 95.5 <= 96
        self.assertEqual(g.first_touch(-1, 100, 102, 96, h, l, sp, 99, 0.5), (2.0, 1, 1))
        h2 = np.array([101.6, 100.0])                          # ask high 102.1 >= 102 -> stop
        self.assertEqual(g.first_touch(-1, 100, 102, 96, h2, l, sp, 99, 0.5), (-1.0, -1, 0))
        R, _, _ = g.first_touch(-1, 100, 102, 90, np.array([100.0]), np.array([99.0]), np.array([0.5]), 99, 0.5)
        self.assertAlmostEqual(R, 0.25)                         # exit at ask 99.5

    def test_nearest_target_skips_taken_and_behind(self):
        cands = [(105.0, 1), (103.0, 2), (99.0, 3), (102.0, 4)]
        taken = lambda d, lev, last: lev == 102.0
        self.assertEqual(g.nearest_target(1, 100.0, cands, taken), 103.0)
        self.assertEqual(g.nearest_target(-1, 100.0, cands, taken), 99.0)
        self.assertTrue(np.isnan(g.nearest_target(1, 106.0, cands, taken)))

    def test_plans_respect_rules(self):
        D = g.build(synthetic(), start=0)
        self.assertGreater(len(D), 50)
        self.assertTrue((D["rr"] >= g.MIN_RR - 1e-9).all())
        self.assertTrue((D["risk"] >= g.MIN_RISK_SPREADS * 0.25 - 1e-9).all())
        self.assertTrue((D["d"] * (D["target"] - D["entry"]) > 0).all())
        self.assertTrue((D["d"] * (D["entry"] - D["stop"]) > 0).all())
        win = D[D["outcome"] == 1]
        self.assertTrue(np.allclose(win["R"], win["rr"]))
        self.assertTrue((D.loc[D["outcome"] == -1, "R"] == -1).all())
        self.assertTrue(((D["exit_i"] > D["i"]) & (D["exit_i"] <= D["i"] + g.HORIZON)).all())

    def test_no_look_ahead(self):
        df = synthetic(days=5, seed=11)
        full = g.build(df, start=0)
        cols = ["time", "d", "pos", "sess", "band", "m30_up", "struct", "slope", "entry", "stop", "target", "rr", "atr30"]
        for cut in (800, 1000, 1300):
            part = g.build(df.iloc[:cut].reset_index(drop=True), start=0)
            # same plans with identical features / levels; the cut data has no plan within 24 h of its end
            a = full[full["i"] <= cut - 1 - g.HORIZON][cols].reset_index(drop=True)
            b = part[cols].reset_index(drop=True)
            with self.subTest(cut=cut):
                self.assertGreater(len(a), 20)
                pd.testing.assert_frame_equal(a, b)

    def test_no_plan_without_a_full_horizon(self):
        df = synthetic(days=3, seed=5)
        D = g.build(df, start=0)
        self.assertTrue((D["i"] + g.HORIZON <= len(df) - 1).all())
        self.assertEqual(int(D["i"].max()), len(df) - 1 - g.HORIZON)

    def test_periods_and_sealed_test(self):
        ts = pd.Series([g.START, g.TRAIN_END, g.VALID_END])
        self.assertEqual(g.period(ts).tolist(), ["train", "validate", "test"])
        self.assertEqual(pd.Timestamp(g.VALID_END, unit="s"), pd.Timestamp("2026-01-01"))

    def test_pattern_table_hides_test_and_dedupes(self):
        D = pd.DataFrame({"period": ["train", "train", "validate", "test"], "d": [1, 1, 1, -1],
                          "stop": [99.0, 99.0, 98.0, 101.0], "target": [104.0, 104.0, 103.0, 96.0],
                          "time": [86400 * 10 + 300, 86400 * 10 + 600, 86400 * 20, 86400 * 30],
                          "struct": [1, 1, -1, 1], "band": [1, 1, 0, -1], "m30_up": [1, -1, 1, 1],
                          "slope": [0.1, 0.2, -0.3, 0.5], "R": [2.0, -1.0, -1.0, 3.0]})
        U = gp.usable(D)
        self.assertFalse((U["period"] == "test").any())
        self.assertEqual(len(gp.usable(D, open_test=True)), 4)
        X = gp.dedupe(U)
        self.assertEqual(X["time"].tolist(), [86400 * 10 + 300, 86400 * 20])     # the repeat of plan 1 dropped
        Y = gp.relative(X)
        lo, hi = Y.attrs["slope_cuts"]
        self.assertAlmostEqual(lo, 0.1); self.assertAlmostEqual(hi, 0.1)       # cuts from the train row only
        self.assertEqual(Y["struct"].tolist(), [1, -1])

    def test_features_no_look_ahead_and_direction(self):
        df = synthetic(days=6, seed=3)
        full = g.build(df, start=0)
        F = gf.features(df, full)
        self.assertEqual(list(F.columns), gf.FEATS)
        cut = 1300
        part_df = df.iloc[:cut].reset_index(drop=True)
        part = g.build(part_df, start=0)
        Fp = gf.features(part_df, part)
        merged = full.reset_index(drop=True)
        keys = pd.MultiIndex.from_frame(part[["i", "d"]])
        sel = pd.MultiIndex.from_frame(merged[["i", "d"]]).isin(keys)
        pd.testing.assert_frame_equal(F[sel].reset_index(drop=True), Fp.reset_index(drop=True))
        # direction: a buy and a sell at the same bar see mirrored path moves
        both = full.groupby("i").filter(lambda x: len(x) == 2)
        if len(both):
            fb = gf.features(df, both).reset_index(drop=True)
            r = both.reset_index(drop=True)
            buy, sell = fb[r["d"] == 1].reset_index(drop=True), fb[r["d"] == -1].reset_index(drop=True)
            self.assertTrue(np.allclose(buy["p1"], -sell["p1"]))
            self.assertTrue(np.allclose(buy["e200"], -sell["e200"]))

    def test_weekday(self):
        D = pd.DataFrame({"i": [50], "d": [1], "pos": [1], "sess": [0], "risk": [1.0], "rr": [2.0], "struct": [0], "band": [0]})
        df = synthetic(days=1)
        F = gf.features(df, D)
        self.assertEqual(int(F["dow"].iloc[0]), pd.Timestamp(int(df["time"].iloc[50]), unit="s").dayofweek)

    def test_walk_forward_mask_and_past_threshold(self):
        X = pd.DataFrame({"time": [100, 200, 300, 400], "exit_time": [150, 450, 350, 500]})
        self.assertEqual(gm.train_mask(X, 400).tolist(), [True, False, True, False])
        n = 1200
        X2 = pd.DataFrame({"month": ["2025-01"] * 600 + ["2025-02"] * 600})
        evp = np.r_[np.linspace(0, 1, 600), np.full(600, 0.95)]
        sel = gm.select(X2, evp, "top 10%")
        self.assertFalse(sel[:600].any())                               # no earlier month -> no threshold
        self.assertTrue(sel[600:].all())                                # 0.95 >= 90th pct of January (0.9)

    def test_nearest_target_min_distance(self):
        cands = [(101.0, 1), (102.0, 2), (104.0, 3)]
        never = lambda d, lev, last: False
        self.assertEqual(g.nearest_target(1, 100.0, cands, never, min_dist=1.5), 102.0)
        self.assertEqual(g.nearest_target(1, 100.0, cands, never, min_dist=2.0), 104.0)

    def test_label_variants(self):
        df = synthetic(days=4, seed=9)
        L = g.build(df, start=0, label="liq15")
        self.assertGreater(len(L), 20)
        self.assertTrue(((L["rr"] >= 1.5 - 1e-9) & (L["rr"] <= 3.0 + 1e-9)).all())
        for lab, k in g.FIXED_RR.items():
            X = g.build(df, start=0, label=lab)
            with self.subTest(label=lab):
                self.assertTrue(np.allclose(X["rr"], k))
                self.assertTrue(np.allclose(X["target"], X["entry"] + X["d"] * k * X["risk"]))
                win = X[X["outcome"] == 1]
                self.assertTrue(np.allclose(win["R"], k))
        # fixed RR: the same stop on the same day is one plan even though the target moves with the entry
        old = g.LABEL
        try:
            g.LABEL = "rr2"
            D = pd.DataFrame({"d": [1, 1], "stop": [99.0, 99.0], "target": [103.0, 103.4], "time": [86400 * 5, 86400 * 5 + 300]})
            self.assertEqual(len(gp.dedupe(D)), 1)
            g.LABEL = "liq"
            self.assertEqual(len(gp.dedupe(D)), 2)
        finally:
            g.LABEL = old

    def test_raw_utc_files_converted_to_server_time(self):
        ts = pd.Series(pd.to_datetime(["2025-07-15 12:00", "2025-01-15 12:00"]))
        srv = g.utc_to_server(ts)
        self.assertEqual(srv.iloc[0], pd.Timestamp("2025-07-15 15:00"))        # US summer time: +3 h
        self.assertEqual(srv.iloc[1], pd.Timestamp("2025-01-15 14:00"))        # winter: +2 h
        self.assertEqual(g.RAW_UTC, {"EURUSD", "GBPUSD"})


if __name__ == "__main__":
    unittest.main()
