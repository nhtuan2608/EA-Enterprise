"""G95 phase 1 (part 2): trend-conditioned pullbacks and US news reactions on XAUUSD (MT5 data only).

Same windows as g95_xau_read.py (discovery M5 05/2024-06/2025; quiet M15 07/2021-2023; test unseen).

Q7 trend     D1 side = prior D1 close vs EMA50 D1 (prior day). After a k-bar move of >= 3 ATR with / against
             that side, the next k bars measured in the D1 direction (ATR of the entry timeframe)
Q8 news      USD HIGH release times (calendar export, server time). Reaction = first 15 min (M5: 3 bars,
             M15: 1 bar) from the bar open at T, in ATR. Continuation = the next 30/60/120 min in the
             reaction direction; by reaction size
"""
from __future__ import annotations

import csv
import glob

import numpy as np
import pandas as pd

from g95_xau_read import DATA, DISC_FROM, DISC_TO, QUIET_FROM, QUIET_TO, atr, load

CAL = r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\EnterpriseEA\research\calendar\calendar_*.csv"


def d1_side() -> pd.Series:
    d1 = pd.read_csv(DATA / "bars_XAUUSD_D1.csv")
    d1["day"] = pd.to_datetime(d1["time"], unit="s").dt.date
    ema = d1["close"].ewm(span=50, adjust=False).mean()
    side = np.sign(d1["close"] - ema).shift(1)          # known at the open of the day
    return pd.Series(side.to_numpy(), index=d1["day"])


def q7(df: pd.DataFrame, name: str, ks=(6, 12, 24)):
    side = df["day"].map(d1_side()).to_numpy()
    a = atr(df).to_numpy()
    c = df["close"].to_numpy()
    rows = []
    for k in ks:
        past = (c - np.roll(c, k)) / a
        fut = (np.roll(c, -k) - c) / a
        ok = np.isfinite(past) & np.isfinite(fut) & np.isfinite(side) & (side != 0)
        ok[:k] = False
        ok[-k:] = False
        base = (side[ok] * fut[ok]).mean()
        for th in (2.0, 3.0, 4.0):
            for kind, m in (("with D1", ok & (np.sign(past) == side) & (np.abs(past) >= th)),
                            ("against D1 (dip)", ok & (np.sign(past) == -side) & (np.abs(past) >= th))):
                if m.sum() < 30:
                    continue
                f = side[m] * fut[m]
                # thin by k so overlapping windows do not inflate n
                idx = np.flatnonzero(m)
                keep = idx[np.insert(np.diff(idx) >= k, 0, True)]
                rows.append((k, th, kind, len(keep), round(float((side[keep] * fut[keep]).mean()), 3),
                             round(float((side[keep] * fut[keep] > 0).mean()), 3), round(float(base), 3)))
    print(f"\nQ7 {name}: next k bars in the D1 direction (ATR) after a k-bar move")
    print(pd.DataFrame(rows, columns=["k", "move>=", "move", "n", "next_in_D1_dir", "share_pos", "all_bars_base"])
          .to_string(index=False))


def releases() -> np.ndarray:
    t = set()
    for f in glob.glob(CAL):
        for r in csv.DictReader(open(f, encoding="utf-8", errors="replace")):
            if r["currency"] == "USD" and r["importance"] == "HIGH":
                t.add(int(r["time_server"]))
    return np.array(sorted(t), dtype=np.int64)


def q8(df: pd.DataFrame, name: str, bar_min: int):
    rel = releases()
    times = df["time"].to_numpy()
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    a = atr(df).to_numpy()
    first = 15 // bar_min
    rows = []
    for t in rel:
        i = int(np.searchsorted(times, t))
        if i >= len(times) or times[i] != t or i < 20:
            continue
        j = i + first - 1                      # last bar of the first 15 minutes
        if j + 120 // bar_min >= len(c):
            continue
        ref = a[i - 1]
        if not ref > 0:
            continue
        react = (c[j] - o[i]) / ref
        d = np.sign(react)
        row = dict(react=abs(react))
        for h in (30, 60, 120):
            row[f"next{h}"] = d * (c[j + h // bar_min] - c[j]) / ref
        rows.append(row)
    t = pd.DataFrame(rows)
    if t.empty:
        print(f"\nQ8 {name}: no releases")
        return
    t["size"] = pd.cut(t["react"], [0, 2, 4, 8, 1e9], labels=["<2", "2-4", "4-8", ">=8"])
    g = t.groupby("size", observed=True)
    out = g[["next30", "next60", "next120"]].mean()
    out["n"] = g.size()
    out["share_cont_60"] = g["next60"].apply(lambda s: (s > 0).mean())
    print(f"\nQ8 {name}: {len(t)} USD HIGH releases; continuation after the first 15 min (ATR of the bar TF)")
    print(out.round(3).to_string())


def main():
    m5 = load(DATA / "m5v" / "XAUUSD.csv")
    disc = m5[(m5["ts"] >= DISC_FROM) & (m5["ts"] < DISC_TO)].reset_index(drop=True)
    m15 = load(DATA / "m15v" / "XAUUSD.csv")
    quiet = m15[(m15["ts"] >= QUIET_FROM) & (m15["ts"] < QUIET_TO)].reset_index(drop=True)
    loud15 = m15[(m15["ts"] >= DISC_FROM) & (m15["ts"] < DISC_TO)].reset_index(drop=True)
    q7(disc, "M5 discovery", ks=(12, 24, 48))
    q7(loud15, "M15 discovery")
    q7(quiet, "M15 quiet")
    q8(disc, "M5 discovery", 5)
    q8(loud15, "M15 discovery", 15)
    q8(quiet, "M15 quiet", 15)


if __name__ == "__main__":
    main()
