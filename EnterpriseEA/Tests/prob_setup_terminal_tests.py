"""ProbSetupEA reference on the live terminal feed: the oracle (Tests/prob_setup_oracle.py) run on the terminal's own
closed M15 / H1 / H4 / D1 bars (MetaTrader5 package, read-only: copy_rates only) gives the same C1 / C2 signals,
entries, stops, X1 results and factors as the research table built from the raw M5 exports, over their overlap in
2025 (the 2026 test stays sealed: rows from 2026 are never compared or printed). Skipped without a running terminal."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prob_setup_oracle as po  # noqa: E402

PKL = HERE.parent / "research" / "long" / "data" / "g112_chase_XAUUSD_m15.pkl"
SEALED = int(pd.Timestamp("2026-01-01").timestamp())


def terminal_frames():
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        return None
    try:
        sym = "XAUUSD-VIP"
        if not mt5.symbol_select(sym, True):
            return None
        pt = mt5.symbol_info(sym).point
        get = lambda tf, n: mt5.copy_rates_from_pos(sym, tf, 1, n)
        r, h1, h4, d1 = get(mt5.TIMEFRAME_M15, 30000), get(mt5.TIMEFRAME_H1, 9000), get(mt5.TIMEFRAME_H4, 4000), get(mt5.TIMEFRAME_D1, 1000)
    finally:
        mt5.shutdown()
    if r is None or h1 is None or h4 is None or d1 is None:
        return None
    bars = {"time": [int(x) for x in r["time"]], "open": r["open"].tolist(), "high": r["high"].tolist(), "low": r["low"].tolist(),
            "close": r["close"].tolist(), "tickvol": r["tick_volume"].astype(float).tolist(), "sp": (r["spread"] * pt).tolist()}
    fr = lambda x: {"time": [int(v) for v in x["time"]], "high": x["high"].tolist(), "low": x["low"].tolist(), "close": x["close"].tolist()}
    return bars, fr(h1), fr(h4), fr(d1)


class ProbSetupTerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fr = terminal_frames() if PKL.exists() else None
        if fr is None:
            raise unittest.SkipTest("no running MT5 terminal / research table")
        T = pd.DataFrame(po.signals(*fr, 900))
        C = pd.read_pickle(PKL)
        C = C[C["typ"].isin(["C1", "C2"])]
        t0 = max(int(T["time"].min()) + 60 * 86400, int(C["time"].min()))      # 60 days of warm-up on the terminal
        t1 = min(int(C["time"].max()), SEALED - 1)
        if t1 - t0 < 30 * 86400:
            raise unittest.SkipTest("terminal history does not overlap the research period")
        cls.a = C[(C["time"] >= t0) & (C["time"] <= t1)]
        cls.b = T[(T["time"] >= t0) & (T["time"] <= t1)]

    def test_same_signals_on_the_terminal_feed(self):
        ka = set(zip(self.a["time"], self.a["typ"], self.a["d"]))
        kb = set(zip(self.b["time"], self.b["typ"], self.b["d"]))
        self.assertGreater(len(ka), 100)
        self.assertEqual(ka, kb)

    def test_same_trades_and_factors(self):
        M = self.a.merge(self.b, on=["time", "typ", "d"], suffixes=("_r", "_t"))
        self.assertTrue(np.allclose(M["entry_r"], M["entry_t"], atol=1e-6))
        self.assertTrue(np.allclose(M["stop_r"], M["stop_t"], atol=1e-6))
        self.assertTrue(np.allclose(M["X1_none"], M["R"], atol=1e-6))
        self.assertTrue((M["sess"] == M["f_sess"]).all())
        self.assertTrue((M["d1_with"] == M["f_d1"]).all())
        self.assertTrue((M["diverg"].fillna(-1).astype(int) == M["f_div"]).all())
        self.assertTrue((np.round(M["h4_side"]).astype(int) == M["f_h4"]).all())


if __name__ == "__main__":
    unittest.main()
