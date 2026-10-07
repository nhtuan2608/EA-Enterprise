"""G56: factor atlas — no look-ahead in any factor, and the statistics."""
import os
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
sys.path.insert(0, str(ROOT / "research" / "g10"))

_old = os.environ.get("EEA_RESEARCH_DATA")
import factor_atlas as fa  # noqa: E402
if _old is None:
    os.environ.pop("EEA_RESEARCH_DATA", None)
else:
    os.environ["EEA_RESEARCH_DATA"] = _old


def synthetic(n=3000, seed=3):
    rng = np.random.default_rng(seed)
    c = 1.1 + np.cumsum(rng.normal(0, 0.001, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + abs(rng.normal(0, 0.0005, n))
    l = np.minimum(o, c) - abs(rng.normal(0, 0.0005, n))
    t = 1_600_000_000 - 1_600_000_000 % 86400 + np.arange(n) * 3600
    d = {"symbol": "EURUSD", "tf": "H1", "time": t, "utc": t, "open": o, "high": h, "low": l, "close": c,
         "spread": np.full(n, 10.0), "hour": (t % 86400) // 3600, "day": t // 86400}
    d["dow"] = (d["day"] + 3) % 7
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    d["atr"] = fa.sma(tr, 14)
    d["cost"] = d["spread"] * 0.00001 / d["atr"]
    d["tickvol"] = rng.integers(100, 1000, n).astype(float)
    return d


class NoLookAheadTests(unittest.TestCase):
    def test_changing_the_future_never_changes_a_past_event(self):
        d = synthetic()
        cut = 2000
        base = fa.factors(d)
        e = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in d.items()}
        rng = np.random.default_rng(9)
        for key in ("open", "high", "low", "close"):
            e[key][cut:] = e[key][cut:] + rng.normal(0, 0.01, len(e[key]) - cut)
        e["high"] = np.maximum.reduce([e["high"], e["open"], e["close"]])
        e["low"] = np.minimum.reduce([e["low"], e["open"], e["close"]])
        e["tickvol"][cut:] = 5000.0
        pc = np.r_[e["close"][0], e["close"][:-1]]
        tr = np.maximum(e["high"] - e["low"], np.maximum(abs(e["high"] - pc), abs(e["low"] - pc)))
        e["atr"] = fa.sma(tr, 14)
        changed = fa.factors(e)
        for name in base:
            if name == "MONTH_END_FIX":
                continue        # "last day of the month" is calendar knowledge, known in advance
            m0, d0 = base[name]
            m1, d1 = changed[name]
            self.assertTrue(np.array_equal(m0[:cut], m1[:cut]), name)
            both = m0[:cut] & m1[:cut]
            self.assertTrue(np.array_equal(d0[:cut][both], d1[:cut][both]), name)

    def test_every_planned_factor_exists(self):
        names = set(fa.factors(synthetic()))
        for n in ("HOUR_00", "HOUR_23", "MON", "FRI", "MON_AFTER_RED_FRI", "FRI_FADE_WEEK", "MON_GAP_FILL", "ASIA_BREAK",
                  "NY_FADE_16", "OVERLAP_MOM", "ROUND_REJECT", "ROUND_BREAK", "STREAK_4", "STREAK_6", "PRESSURE_3",
                  "RANGE_BREAK", "RANGE_FADE", "RISING_WEDGE_BREAK", "FALLING_WEDGE_BREAK", "PDHL_SWEEP", "RSI_REVERT",
                  "BB_SQUEEZE_BREAK", "MACD_FLIP_TREND", "ADX_PULLBACK", "NR7_BREAK", "VOL_SPIKE", "MONTH_END_FIX"):
            self.assertIn(n, names)

    def test_streak_direction(self):
        d = synthetic(400)
        d["open"][:] = d["close"] + 0.0001          # red bars, then green from bar 50 (ATR ready)
        d["open"][50:] = d["close"][50:] - 0.0001
        m, dirn = fa.factors(d)["STREAK_4"]
        self.assertTrue(m.any())
        self.assertTrue(m[53])                          # the fourth green bar
        self.assertEqual(dirn[53], 1.0)


class StatsTests(unittest.TestCase):
    def test_bh(self):
        q = fa.bh([0.01, 0.04, 0.03, 0.5])
        self.assertAlmostEqual(q[0], 0.04)
        self.assertAlmostEqual(q[3], 0.5)
        self.assertTrue(all(a <= 1 for a in q))

    def test_cluster_mean_counts_a_day_once(self):
        vals = np.array([1.0, 1.0, 1.0, -1.0])
        sym = np.zeros(4)
        days = np.array([1, 1, 1, 2])
        mean, _, ncl, nev = fa.cluster_stats(vals, sym, days)
        self.assertEqual((ncl, nev), (2, 4))
        self.assertAlmostEqual(mean, 0.0)              # day 1 counts once, not three times

    def test_forward_and_rolling(self):
        x = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
        self.assertEqual(list(fa.rolling_max(x, 2)[1:]), [3, 3, 5, 5])
        d = {"close": np.array([1.0, 2.0, 4.0]), "atr": np.array([1.0, 1.0, 1.0]), "cost": np.zeros(3)}
        f, _ = fa.forward(d, 1)
        self.assertEqual(list(f[:2]), [1.0, 2.0])
        self.assertTrue(np.isnan(f[2]))


if __name__ == "__main__":
    unittest.main()
