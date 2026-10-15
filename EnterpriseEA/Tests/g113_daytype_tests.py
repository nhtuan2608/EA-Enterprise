"""G113 part 3 (research/long/g113_daytype.py): day features before 10:00 only, labels, routing from predictions only."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g113_daytype as gd  # noqa: E402


def synthetic(days=90, seed=5):
    rng = np.random.default_rng(seed)
    n = days * 288
    t = int(pd.Timestamp("2025-01-06").timestamp()) + 300 * np.arange(n)
    c = 3000 + np.cumsum(rng.normal(0, 1.0, n))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) + rng.uniform(0, 0.8, n),
                         "low": np.minimum(o, c) - rng.uniform(0, 0.8, n), "close": c,
                         "tickvol": rng.integers(50, 500, n).astype(float), "spread": 5, "sp": 0.05})


class G113DayTypeTests(unittest.TestCase):
    def test_features_use_only_bars_before_ten(self):
        df = synthetic()
        D = gd.day_table(df)
        self.assertGreater(len(D), 10)
        target = D.iloc[-5]
        cut = int(target["i10"])                                          # first bar at 10:00 of that day
        Dp = gd.day_table(df.iloc[:cut + 1].reset_index(drop=True))
        rowp = Dp[Dp["day"] == target["day"]]
        self.assertEqual(len(rowp), 1)
        for f in gd.FEATS:
            self.assertTrue(np.isclose(float(target[f]), float(rowp[f].iloc[0]), equal_nan=True), f)

    def test_labels(self):
        D = gd.day_table(synthetic())
        self.assertTrue(((D["type"] == 1) == (D["body"] >= 0.6)).all())
        self.assertTrue(((D["type"] == -1) == (D["body"] <= 0.3)).all())
        self.assertTrue((D["trend"] == (D["type"] == 1).astype(int)).all())

    def test_route_from_predictions_only(self):
        jan = [int(pd.Timestamp("2025-01-02").timestamp()) + 43200 * k for k in range(50)]   # 50 decisions in January
        feb = [int(pd.Timestamp("2025-02-03").timestamp()) + 86400 * k for k in range(20)]
        D = pd.DataFrame({"t10": jan + feb})
        p = np.r_[np.linspace(0, 1, 50), np.array([0.95] * 10 + [0.05] * 10)]
        r = gd.route(D, p)
        self.assertTrue((r[:50] == 0).all())                              # no earlier month: no routing
        self.assertTrue((r[50:60] == 1).all() and (r[60:] == -1).all())   # cut-offs from January only
        D2 = D.assign(type=1, body=0.9, trend=1)                          # labels present but unused
        self.assertTrue((gd.route(D2, p) == r).all())


if __name__ == "__main__":
    unittest.main()
