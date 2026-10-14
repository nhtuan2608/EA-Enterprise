"""VHedgeTester reference: the G119 signals the EA should take, from the running terminal's M5 bars (read-only).

  python Tests/vhedge_reference.py                         -> signals of the last 14 days (XAUUSD-VIP)
  python Tests/vhedge_reference.py --days 30 --symbol XAUUSD.r
  python Tests/vhedge_reference.py --csv "<MQL5>/Files/VHedge_XAUUSD-VIP_116119.csv"   -> compare with the EA log

Signal = research g116.find_groups (V body cross of the EMA200, close back inside the V range within 6 bars) +
g119 filter (EMA21..200 spread <= 0.91 ATR14 and V volume >= 1.26x or return volume >= 1.17x of the 20-bar mean).
Times are server times of the return bar (the EA logs it as signal_time).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g116_v_hedge as g  # noqa: E402
from g97_forming_bar import dmi, ema  # noqa: E402

TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def bars(symbol: str, n: int) -> pd.DataFrame:
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, n)
    finally:
        mt5.shutdown()
    if r is None or len(r) == 0:
        raise SystemExit(f"no M5 bars for {symbol}")
    m = pd.DataFrame(r).rename(columns={"tick_volume": "tickvol"})
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    c = m["close"].to_numpy()
    for k in (21, 55, 100, 200):
        m[f"e{k}"] = ema(c, k)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * 0.01
    return m


def signals(m: pd.DataFrame, since: pd.Timestamp, spread_lim=0.91, vv_lim=1.26, rv_lim=1.17) -> pd.DataFrame:
    vol = m["tickvol"].to_numpy().astype(float)
    vavg = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    E = m[["e21", "e55", "e100", "e200"]].to_numpy()
    a = m["atr"].to_numpy()
    rows = []
    for v, j in g.find_groups(m):
        if m["ts"].iat[j] < since:
            continue
        spread = (E[v].max() - E[v].min()) / a[v]
        vv, rv = vol[v] / vavg[v], vol[j] / vavg[j]
        ok = spread <= spread_lim and (vv >= vv_lim or rv >= rv_lim)
        rows.append(dict(v_time=m["ts"].iat[v], signal_time=m["ts"].iat[j], spread=round(spread, 2), v_vol=round(vv, 2),
                         r_vol=round(rv, 2), taken=ok, atr=round(a[j], 3)))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD-VIP")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--csv", default="")
    args = ap.parse_args()
    m = bars(args.symbol, 6000)
    since = m["ts"].iat[-1] - pd.Timedelta(days=args.days)
    s = signals(m, since)
    pd.set_option("display.width", 200)
    print(f"{args.symbol}: V returns since {since:%Y-%m-%d %H:%M} (server): {len(s)}, taken by the filter: {int(s.taken.sum())}")
    print(s.to_string(index=False))
    if args.csv:
        log = pd.read_csv(args.csv, sep=";")
        log["signal_time"] = pd.to_datetime(log["signal_time"].str.replace(".", "-", regex=False))
        ref = set(s.loc[s.taken, "signal_time"])
        ea = set(log["signal_time"])
        window = log["signal_time"] >= since
        ea = set(log.loc[window, "signal_time"])
        print(f"\nEA log: {len(ea)} groups in the window | reference: {len(ref)}")
        print("in reference, missing in EA:", sorted(ref - ea))
        print("in EA, not in reference   :", sorted(ea - ref))


if __name__ == "__main__":
    main()
