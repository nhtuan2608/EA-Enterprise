"""ProbSetupEA reference (Tests/prob_setup_oracle.py) against the research tables: the C1 / C2 chase signals of gold
on M15 (research/long/data/g112_chase_XAUUSD_m15.pkl) - same signals, entry, stop, X1 result and G114 factors."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prob_setup_oracle as po  # noqa: E402

PKL = ROOT / "research" / "long" / "data" / "g112_chase_XAUUSD_m15.pkl"


def frames():
    import g108_data as g8
    import g108_features as gf
    assert g8.TF == 5 and g8.SYMBOL == "XAUUSD" and not g8.NOCOST
    m5 = g8.load_m5_raw()
    b = g8.resample(m5, 900)
    hist = gf.long_m30()
    h1 = g8.resample(b.assign(tickvol=0.0), 3600)
    b4, c4 = gf.htf_closes(b, hist, 14400)
    bd, cd = gf.htf_closes(b, hist, 86400)
    bars = {k: b[k].to_numpy().tolist() for k in ("time", "open", "high", "low", "close", "tickvol", "sp")}
    bars["time"] = [int(x) for x in bars["time"]]
    return (b, bars, {"time": [int(x) for x in h1["time"]], "high": h1["high"].tolist(), "low": h1["low"].tolist(), "close": h1["close"].tolist()},
            {"time": [int(x) * 14400 for x in b4], "close": c4.tolist()}, {"time": [int(x) * 86400 for x in bd], "close": cd.tolist()})


@unittest.skipUnless(PKL.exists() and os.environ.get("G113_TF", "5") == "5", "research table / raw data not available")
class ProbSetupOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b, bars, h1, h4, d1 = frames()
        C = pd.read_pickle(PKL)
        C = C[C["typ"].isin(["C1", "C2"])]
        t0, t1 = int(pd.Timestamp("2025-05-01").timestamp()), int(pd.Timestamp("2025-08-01").timestamp())
        cls.C = C[(C["time"] >= t0) & (C["time"] < t1)].copy()
        sig = po.signals(bars, h1, h4, d1, 900)
        S = pd.DataFrame(sig)
        cls.S = S[(S["time"] >= t0) & (S["time"] < t1)].copy()

    def test_same_signals(self):
        a = set(zip(self.C["j"], self.C["typ"], self.C["d"]))
        b = set(zip(self.S["j"], self.S["typ"], self.S["d"]))
        self.assertGreater(len(a), 100)
        self.assertEqual(a, b)

    def test_entry_stop_and_result(self):
        M = self.C.merge(self.S, on=["j", "typ", "d"], suffixes=("_r", "_o"))
        self.assertEqual(len(M), len(self.C))
        for c in ("entry", "stop", "risk"):
            self.assertTrue(np.allclose(M[f"{c}_r"], M[f"{c}_o"], atol=1e-9), c)
        self.assertTrue(np.allclose(M["X1_none"], M["R"], atol=1e-9))
        self.assertTrue((M["X1_none_bars"] == M["bars"]).all())

    def test_factors(self):
        import g114_prob as gp
        M = self.C.merge(self.S, on=["j", "typ", "d"])
        self.assertTrue((M["sess"] == M["f_sess"]).all())
        self.assertTrue((M["d1_with"] == M["f_d1"]).all())
        self.assertTrue((np.round(M["h4_side"]).astype(int) == M["f_h4"]).all())          # stored relative to the trade
        self.assertTrue((gp.band(M["adx_h1"], [20, 30]) == M["f_adx"]).all())
        self.assertTrue((gp.band(M["rv6"], [0.9, 1.3]) == M["f_vol"]).all())
        self.assertTrue((M["diverg"].fillna(-1).astype(int) == M["f_div"]).all())
        self.assertTrue((gp.band(M["day_pos"], [0.33, 0.67]) == M["f_pos"]).all())


if __name__ == "__main__":
    unittest.main()
