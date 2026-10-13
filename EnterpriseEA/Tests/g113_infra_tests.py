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

    def test_default_suffixes(self):
        import g109_setups as gs
        if g8.TF == 5 and not g8.NOCOST and not gs.NOFILTER:
            self.assertEqual(g8.TFSUF, "")
            self.assertEqual(gs.SUF, "")


if __name__ == "__main__":
    unittest.main()
