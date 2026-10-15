"""G113 infrastructure (research/long/g108_data.py): M5 -> M15 / M30 resampling, zero spread, file suffixes."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g108_data as g8  # noqa: E402


def m5(n=12):
    t = int(pd.Timestamp("2025-03-03 10:00").timestamp()) + 300 * np.arange(n)
    c = 100 + np.arange(n, dtype=float)
    return pd.DataFrame({"time": t, "open": c - 0.5, "high": c + 1, "low": c - 2, "close": c,
                         "tickvol": np.arange(1, n + 1, dtype=float), "spread": np.arange(n, dtype=float), "sp": np.arange(n) * 0.01})


class G113InfraTests(unittest.TestCase):
    def test_resample_m15(self):
        r = g8.resample(m5(), 900)
        self.assertEqual(len(r), 4)
        first = r.iloc[0]
        self.assertEqual(int(first["time"]), int(pd.Timestamp("2025-03-03 10:00").timestamp()))
        self.assertEqual((first["open"], first["high"], first["low"], first["close"]), (99.5, 103.0, 98.0, 102.0))
        self.assertEqual(first["tickvol"], 1 + 2 + 3)
        self.assertAlmostEqual(first["sp"], 0.01)                          # mean of 0, 0.01, 0.02

    def test_resample_m30_alignment(self):
        df = m5(18)
        df["time"] = df["time"] + 900                                    # starts at 10:15
        r = g8.resample(df, 1800)
        self.assertEqual(int(r["time"].iloc[0]) % 1800, 0)              # buckets on the half hour
        self.assertEqual(int(r["time"].iloc[0]), int(pd.Timestamp("2025-03-03 10:00").timestamp()))

    def test_finish_bars_switches(self):
        old = (g8.TF, g8.BAR_SEC, g8.NOCOST)
        try:
            g8.TF, g8.BAR_SEC, g8.NOCOST = 5, 300, True
            self.assertTrue((g8.finish_bars(m5())["sp"] == 0).all())
            g8.TF, g8.BAR_SEC, g8.NOCOST = 30, 1800, False
            r = g8.finish_bars(m5())
            self.assertEqual(len(r), 2)
            self.assertTrue((r["sp"] > 0).all())
            g8.TF, g8.BAR_SEC, g8.NOCOST = 5, 300, False
            pd.testing.assert_frame_equal(g8.finish_bars(m5()), m5())   # default: untouched
        finally:
            g8.TF, g8.BAR_SEC, g8.NOCOST = old

    def test_run_label_states_each_switch(self):
        import g109_setups as gs
        m30_cost = gs.run_label(nofilter=False, nocost=False, tf=30)
        self.assertIn("Khung M30", m30_cost)
        self.assertIn("trừ thật", m30_cost)
        self.assertIn("bật", m30_cost)                                   # M30 with spread keeps the cost filter on
        self.assertIn("24 giờ", m30_cost)                                # 48 bars x 30 min
        nc = gs.run_label(nofilter=False, nocost=True, tf=5)
        self.assertIn("Spread: 0", nc)
        self.assertNotIn("trừ thật", nc)
        self.assertIn("4 giờ", nc)
        nf = gs.run_label(nofilter=True, nocost=False, tf=15)
        self.assertIn("TẮT", nf)
        self.assertIn("12 giờ", nf)

    def test_drift_control_other_days_same_month(self):
        import g109_setups as gs
        import g113_summary as su
        rng = np.random.default_rng(1)
        n = 20 * 288
        t = int(pd.Timestamp("2025-03-03").timestamp()) + 300 * np.arange(n)
        c = 100 + np.cumsum(rng.normal(0, 0.1, n))
        df = pd.DataFrame({"time": t, "open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "sp": 0.0})
        P = pd.DataFrame({"i": [300, 3000], "d": [1, -1], "risk": [0.5, 0.5], "day": [t[300] // 86400, t[3000] // 86400]})
        seen = []
        real = gs.simulate
        try:
            def spy(d, entry, stop, target, h, l, c_, sp):
                seen.append((d, round(entry - stop, 9)))
                return real(d, entry, stop, target, h, l, c_, sp)
            gs.simulate = spy
            su.drift_control(P, df, gs, n_draw=3)
        finally:
            gs.simulate = real
        self.assertEqual(len(seen), 6)
        self.assertEqual(sorted(set(seen)), [(-1, -0.5), (1, 0.5)])          # same direction and stop distance
        picks = []
        su.drift_control(P, df, gs, n_draw=5, picks=picks)
        day, mon = t // 86400, pd.to_datetime(t, unit="s").strftime("%Y-%m")
        self.assertEqual(len(picks), 10)
        for i, q in picks:
            self.assertNotEqual(day[q], day[i])                               # never the trade's own day
            self.assertEqual(mon[q], mon[i])                                  # same month
            self.assertTrue(1 <= (t[q] % 86400) // 3600 < 23)

    def test_default_suffixes(self):
        import g109_setups as gs
        if g8.TF == 5 and not g8.NOCOST and not gs.NOFILTER:
            self.assertEqual(g8.TFSUF, "")
            self.assertEqual(gs.SUF, "")


if __name__ == "__main__":
    unittest.main()
