"""G109 step 1 (research/long/g109_zones.py): zone merge, touch / reaction labels, fair-value gaps, weeks,
the map built only from bars closed before the day, fake zones apart from real ones."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g109_zones as gz  # noqa: E402


def synthetic(days=25, seed=4):
    rng = np.random.default_rng(seed)
    n = days * 288
    t = int(pd.Timestamp("2025-03-03").timestamp()) + 300 * np.arange(n)
    c = 3000 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.9, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.9, n)
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "tickvol": rng.integers(50, 500, n).astype(float),
                         "spread": 25, "sp": 0.25})


class G109ZonesTests(unittest.TestCase):
    def test_merge_overlapping_bands(self):
        z = gz.merge([(100.0, "PDH"), (100.5, "R10"), (103.0, "FVG"), (101.5, "H1SH")], w=0.4)
        self.assertEqual([x["n"] for x in z], [2, 1, 1])                   # 100 / 100.5 merge (< 2w = 0.8 apart); 101.5 is 1.0 away
        self.assertEqual(z[0]["kinds"], "PDH+R10")
        self.assertAlmostEqual(z[0]["center"], 100.25)
        z2 = gz.merge([(100.0, "A"), (100.7, "B"), (101.4, "C")], w=0.4)
        self.assertEqual(len(z2), 1)                                       # chained overlaps form one zone
        self.assertEqual(z2[0]["n"], 3)

    def test_touch_and_reaction(self):
        # zone above at 105 +/- 0.5, price approaches from below
        h = np.array([103, 104.6, 104.8, 103.5, 102.0]); l = h - 1.0; c = h - 0.5
        self.assertEqual(gz.touch_reaction(h, l, c, 105.0, 0.5, 1), (True, 1, 1))   # back below 104.5 - 1.0 -> bounce
        h2 = np.array([103, 104.8, 106.0, 106.5, 106.2]); l2 = h2 - 0.4; c2 = h2 - 0.1
        self.assertEqual(gz.touch_reaction(h2, l2, c2, 105.0, 0.5, 1), (True, 1, -1))  # 2 closes > 105.5 -> through
        h3 = np.array([103, 103.5, 104.0]); l3 = h3 - 1; c3 = h3 - 0.5
        self.assertEqual(gz.touch_reaction(h3, l3, c3, 105.0, 0.5, 1), (False, -1, 0))
        # zone below, approach from above, bounce up
        l4 = np.array([97, 95.4, 95.6, 96.6]); h4 = l4 + 1.0; c4 = l4 + 0.5
        self.assertEqual(gz.touch_reaction(h4, l4, c4, 95.0, 0.5, -1), (True, 1, 1))

    def test_fvg(self):
        h = np.array([10.0, 11.0, 13.0]); l = np.array([9.0, 10.0, 12.0])
        self.assertEqual(gz.fvg(h, l, 2), (1, 10.0, 12.0))                  # low of bar 3 above high of bar 1
        h2 = np.array([13.0, 12.0, 10.0]); l2 = np.array([12.0, 10.5, 9.0])
        self.assertEqual(gz.fvg(h2, l2, 2), (-1, 10.0, 12.0))
        self.assertIsNone(gz.fvg(np.array([10.0, 11, 12]), np.array([9.0, 9.5, 9.8]), 2))

    def test_week_is_monday_based(self):
        mon = int(pd.Timestamp("2026-10-12").timestamp()) // 86400
        self.assertEqual(gz.week_of(np.array([mon]))[0], gz.week_of(np.array([mon + 6]))[0])
        self.assertEqual(gz.week_of(np.array([mon]))[0], gz.week_of(np.array([mon - 1]))[0] + 1)

    def test_map_uses_only_bars_before_the_day(self):
        df = synthetic()
        days = (df["time"] // 86400).unique()
        target = int(days[-2])
        a = int(np.nonzero(df["time"].to_numpy() // 86400 == target)[0][0])
        Zf, Cf, _ = gz.build(df, None, "XAUUSD", days_only=[target])
        Zt, Ct, _ = gz.build(df.iloc[:a + 1].reset_index(drop=True), None, "XAUUSD", days_only=[target])
        cols = ["center", "kinds", "n", "side", "w", "dist"]
        fr = Zf[Zf["map"] & ~Zf["fake"]][cols].reset_index(drop=True)
        tr = Zt[Zt["map"] & ~Zt["fake"]][cols].reset_index(drop=True)
        self.assertGreater(len(fr), 3)
        pd.testing.assert_frame_equal(fr, tr)
        pd.testing.assert_frame_equal(Cf.reset_index(drop=True), Ct.reset_index(drop=True))

    def test_zone_rules(self):
        df = synthetic()
        Z, C, D = gz.build(df, None, "XAUUSD")
        self.assertGreater(len(D), 5)
        real = Z[Z["map"] & ~Z["fake"]]
        fake = Z[Z["fake"]]
        for d, grp in Z.groupby("day"):
            r = grp[grp["map"] & ~grp["fake"]]["center"].to_numpy()
            for fc, w in grp[grp["fake"]][["center", "w"]].to_numpy():
                self.assertTrue((np.abs(r - fc) >= 2 * w - 1e-9).all())
        self.assertTrue((np.abs(real["center"] - real["p0"]) <= gz.NEAR_D1 * real["atr_d1"] + real["w"]).all())
        side_ok = np.where(real["side"] == 1, real["center"] - real["w"] > real["p0"],
                           np.where(real["side"] == -1, real["center"] + real["w"] < real["p0"], True))
        self.assertTrue(side_ok.all())
        self.assertTrue((Z.loc[~Z["touched"], "touch_i"] == -1).all())
        self.assertTrue(set(D["first"].unique()) <= {-1, 0, 1})
        self.assertIn("PDH", set(C["kind"]))
        self.assertGreater(len(fake), 0)


if __name__ == "__main__":
    unittest.main()
