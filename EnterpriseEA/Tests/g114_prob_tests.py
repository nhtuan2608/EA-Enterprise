"""G114 (research/long/g114_prob.py): probabilities from earlier months only, shrinkage, LR, isotonic calibration,
Wilson lower bound, EV decision, capped Kelly, one trade at a time, random control on other days."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g114_prob as gp  # noqa: E402


def synthetic(n=1800, seed=3):
    """One family over ~14 months: factor f_a = 1 raises the win rate (0.55 vs 0.30); f_b is noise."""
    rng = np.random.default_rng(seed)
    t0 = int(pd.Timestamp("2024-07-01").timestamp())
    t = np.sort(t0 + rng.integers(0, 420 * 86400, n)).astype(np.int64)
    a = rng.integers(0, 2, n)
    b = rng.integers(0, 3, n)
    win = rng.random(n) < np.where(a == 1, 0.55, 0.30)
    R = np.where(win, 2.0, -1.0)
    return pd.DataFrame({"fam": "T", "day": t // 86400, "i": np.arange(n) * 10, "bars": 6, "d": 1, "R": R, "win": win,
                         "time": t, "exit_t": t + 1800, "kind": "rev", "period": "train", "f_a": a, "f_b": b})


class G114ProbTests(unittest.TestCase):
    def test_wilson_lower(self):
        self.assertAlmostEqual(gp.wilson_lower(0.5, 100), 0.4189, places=3)     # z = 1.645
        self.assertLess(gp.wilson_lower(0.5, 20), gp.wilson_lower(0.5, 200))    # fewer trades -> lower bound lower
        self.assertEqual(gp.wilson_lower(0.4, 0), 0.0)
        self.assertGreaterEqual(gp.wilson_lower(0.0, 10), 0.0)

    def test_pav_monotone_and_counts(self):
        s = np.array([1, 2, 3, 4, 5, 6], float)
        y = np.array([0, 1, 0, 1, 1, 1], float)
        b = gp.pav_fit(s, y)
        ps = [x[1] for x in b]
        self.assertTrue(all(ps[k] < ps[k + 1] for k in range(len(ps) - 1)))   # strictly increasing after pooling
        self.assertEqual(sum(x[2] for x in b), 6)
        self.assertAlmostEqual(b[0][1], 0.0)
        self.assertAlmostEqual(b[1][1], 0.5)                                  # 2 and 3 pooled
        p, n = gp.pav_predict(b, np.array([0.0, 2.5, 3.0, 9.0]))
        self.assertEqual(list(p), [0.0, 0.5, 0.5, 1.0])                       # step function, clipped at both ends
        self.assertEqual(list(n), [1, 2, 2, 3])

    def test_pav_pools_equal_scores(self):
        s = np.array([1, 1, 1, 1, 2, 2], float)
        b = gp.pav_fit(s, np.array([0, 1, 0, 1, 1, 1], float))             # ties never split by their order
        self.assertEqual([(x[0], x[1], x[2]) for x in b], [(1.0, 0.5, 4.0), (2.0, 1.0, 2.0)])
        b2 = gp.pav_fit(s, np.array([1, 1, 0, 0, 1, 1], float))
        self.assertEqual(b, b2)

    def test_nb_table_and_score(self):
        F = pd.DataFrame({"f_a": [1] * 40 + [0] * 40})
        win = np.array([True] * 30 + [False] * 10 + [True] * 10 + [False] * 30)
        p0, tab = gp.nb_table(F, win)
        self.assertAlmostEqual(p0, 41 / 82)
        self.assertAlmostEqual(tab[("f_a", 1)], math.log((31 / 42) / (11 / 42)))   # Laplace counts, K = 2 levels
        s = gp.nb_score(F.iloc[[0, 79]], p0, tab)
        self.assertGreater(s[0], 0)
        self.assertLess(s[1], 0)
        # a level seen fewer than 30 times is left out (LR 1)
        p0b, tab_b = gp.nb_table(pd.DataFrame({"f_a": [1] * 10 + [0] * 70}), np.array([True] * 40 + [False] * 40))
        self.assertNotIn(("f_a", 1), tab_b)
        self.assertIn(("f_a", 0), tab_b)

    def test_shrinkage(self):
        self.assertAlmostEqual(gp.shrunk_p(5, 5, 0.3), (5 + 9) / 35)            # 5 of 5 wins -> pulled to the base
        self.assertAlmostEqual(gp.shrunk_p(600, 1000, 0.3), (600 + 9) / 1030)

    def test_ev_and_kelly_cap(self):
        self.assertAlmostEqual(gp.ev_lower(0.4, 2.0, 1.0), 0.2)
        self.assertEqual(gp.kelly_size(-0.1, 2.0), 0.0)
        self.assertAlmostEqual(gp.kelly_size(0.2, 2.0), 0.025)
        self.assertEqual(gp.kelly_size(50.0, 1.0), 1.0)                         # capped at 1 R

    def test_one_at_a_time(self):
        i = np.array([0, 0, 5, 12, 20])
        bars = np.array([10, 10, 3, 5, 5])
        key = np.array([0.1, 0.3, 9.0, 0.2, 0.2])
        k = gp.one_at_a_time(i, bars, key)
        self.assertEqual(list(k), [1, 3, 4])                                  # tie at i=0 -> higher key; 5 is blocked

    def test_dedupe_same_trade(self):
        P = pd.DataFrame({"fam": ["G110A", "G110A", "G110A", "C1"], "i": [5, 5, 5, 5], "d": [1, 1, -1, 1],
                          "bars": [3, 3, 3, 3], "R": [2.0, 2.0, -1.0, 2.0], "f_type": [0, 1, 0, 0]})
        Q = gp.dedupe(P)
        self.assertEqual(len(Q), 3)                                           # same family / bar / side / result once
        self.assertEqual(int(Q["f_type"].iloc[0]), 0)

    def test_band(self):
        self.assertEqual(list(gp.band([10, 20, 25, 30, np.nan], [20, 30])), [0, 1, 1, 2, -1])

    def test_lr_ci(self):
        lr, lo, hi = gp.lr_ci(60, 100, 20, 100)
        self.assertGreater(lr, 2.5)
        self.assertTrue(lo < lr < hi and lo > 1)

    def test_walk_uses_earlier_results_only(self):
        X = gp.walk_family(synthetic())
        self.assertTrue(X["nb_ev"].notna().any())
        target = X[X["nb_ev"].notna()].iloc[-50]
        cut = int(pd.Timestamp(int(target["time"]), unit="s").to_period("M").to_timestamp().timestamp())
        # the same month recomputed when nothing after it exists, and with future results scrambled
        base = synthetic()
        trunc = base[base["time"] < cut + 31 * 86400].copy()
        Y = gp.walk_family(trunc)
        scr = base.copy()
        late = scr["time"] >= cut
        scr.loc[late, "win"] = ~scr.loc[late, "win"]
        scr.loc[late, "R"] = np.where(scr.loc[late, "win"], 2.0, -1.0)
        Z = gp.walk_family(scr)
        for M in (Y, Z):
            row = M[(M["time"] == target["time"]) & (M["i"] == target["i"])].iloc[0]
            for c in ("nb_raw", "nb_p", "nb_ev", "logit_raw", "logit_ev", "lgbm_raw", "W", "L"):
                self.assertTrue(np.isclose(row[c], target[c], equal_nan=True), c)

    def test_calibrated_and_selects_good_factor(self):
        X = gp.walk_family(synthetic(4000, seed=9))
        x = X[X["nb_p"].notna()]
        self.assertGreater(x.loc[x["f_a"] == 1, "nb_p"].mean(), x.loc[x["f_a"] == 0, "nb_p"].mean() + 0.15)
        sel = gp.select(X, "nb")
        self.assertGreater((sel["f_a"] == 1).mean(), 0.9)                     # EV_lo > 0 only on the good factor
        self.assertGreater(sel["R"].mean(), 0.4)

    def test_random_control_other_days(self):
        S = synthetic(600, seed=4)
        taken = S.iloc[::7]
        rc = gp.random_control(S, taken, n_draw=20)
        self.assertEqual(len(rc), 20)
        # monkey-check: with every day taken it falls back to the month pool, never empty
        self.assertTrue(np.isfinite(gp.random_control(S, S, n_draw=3)).all())


if __name__ == "__main__":
    unittest.main()
