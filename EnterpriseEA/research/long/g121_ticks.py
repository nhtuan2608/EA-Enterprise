"""G121 data: XAUUSD real ticks from the running terminal (read-only) -> M5 order-flow bars + daily tick profiles.

  python g121_ticks.py                 -> all days from 2024-02-20 to the last closed day (skips months already built)

Per M5 bar (server time, bid-change ticks only, tick rule on the bid):
  n      bid changes        up / down  upticks / downticks      delta = up - down
  top / bot  ticks printed in the top / bottom 20% of the bar's bid range
  open / hi / lo / close  bid OHLC      sp  median ask - bid in price
Per server day: tick counts per $0.50 bid bin (profile), stored as (day, lo_bin_price, counts[]).
Out: data/ticks/m5flow_YYYY-MM.pkl and data/ticks/profile_YYYY-MM.npz
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "ticks"
SYMBOL = "XAUUSD-VIP"
TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
BIN = 0.5


def day_ticks(mt5, d: datetime):
    tk = mt5.copy_ticks_range(SYMBOL, d, d + timedelta(days=1), mt5.COPY_TICKS_ALL)
    if tk is None or len(tk) == 0:
        return None
    tk = tk[(tk["flags"] & 2) != 0]                      # bid changed
    return tk if len(tk) else None


def bars_from_ticks(tk) -> pd.DataFrame:
    t = tk["time"].astype(np.int64)
    bid = tk["bid"].astype(float)
    step = np.diff(bid, prepend=bid[0])
    bar = (t // 300) * 300
    df = pd.DataFrame({"bar": bar, "bid": bid, "sp": tk["ask"].astype(float) - bid, "up": step > 0, "down": step < 0})
    g = df.groupby("bar")
    hi, lo = g["bid"].transform("max"), g["bid"].transform("min")
    rng = (hi - lo).replace(0, np.nan)
    df["top"] = (df["bid"] >= hi - 0.2 * rng)
    df["bot"] = (df["bid"] <= lo + 0.2 * rng)
    out = g.agg(n=("bid", "size"), up=("up", "sum"), down=("down", "sum"), top=("top", "sum"), bot=("bot", "sum"),
                hi=("bid", "max"), lo=("bid", "min"), open=("bid", "first"), close=("bid", "last"), sp=("sp", "median"))
    out["delta"] = out["up"] - out["down"]
    return out.reset_index().rename(columns={"bar": "time"})


def profile(tk):
    b = np.floor(tk["bid"] / BIN).astype(np.int64)
    lo = int(b.min())
    counts = np.bincount(b - lo)
    return lo * BIN, counts.astype(np.int32)


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(mt5.last_error())
    OUT.mkdir(parents=True, exist_ok=True)
    start = datetime(2024, 2, 20, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    try:
        while month < end:
            nxt = (month + timedelta(days=32)).replace(day=1)
            tag = f"{month:%Y-%m}"
            fbar, fprof = OUT / f"m5flow_{tag}.pkl", OUT / f"profile_{tag}.npz"
            last_month = nxt >= end
            if fbar.exists() and fprof.exists() and not last_month:
                month = nxt
                continue
            bars, days, los, cnts = [], [], [], []
            d = max(month, start)
            while d < min(nxt, end):
                tk = day_ticks(mt5, d)
                if tk is not None:
                    bars.append(bars_from_ticks(tk))
                    lo, c = profile(tk)
                    days.append(int(d.timestamp())); los.append(lo); cnts.append(c)
                d += timedelta(days=1)
            if bars:
                pd.concat(bars, ignore_index=True).to_pickle(fbar)
                np.savez_compressed(fprof, days=np.array(days), lo=np.array(los),
                                    counts=np.array(cnts, dtype=object), allow_pickle=True)
                print(tag, "bars", sum(len(b) for b in bars), "days", len(days), flush=True)
            month = nxt
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
