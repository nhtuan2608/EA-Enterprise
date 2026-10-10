"""G95 phase 1: read XAUUSD intraday behaviour before designing a new method (MT5 data only).

Discovery window only: M5 2024-05-14 .. 2025-06-30. 07/2025-06/2026 stays unseen (test), 07/2026+ examples.
M15 07/2021-12/2023 is used as the "quiet gold" comparison; H1/D1 2010+ for the volatility regime.

  python g95_xau_read.py            -> prints the tables used in reports/2026-10-11-g95-xau-read.md

Q1 regime     ATR(14) D1 in % of price per year; M5 range in $ and in % per year
Q2 follow/fade variance ratio VR(k) of M5 log returns, k = 3..48 bars; conditional forward move after
               a k-bar move of >= 1.5 ATR (does the next k bars continue or give back?)
Q3 clock       by New York hour: share of the daily range, |drift|, VR(6), spread / ATR
Q4 boxes       M5 boxes (24 bars, width <= 4 ATR M5): first close outside -> reaches +1 width before
               the opposite edge? by box width, hour and H1 EMA side
Q5 levels      first touch of prior-day high/low, Asia high/low, $25 round numbers: break by >= 0.5 ATR
               and hold vs reject (1 h)
Q6 cost        spread in $ and as a share of ATR M5 and of a 1 ATR stop
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "data"
NY = ZoneInfo("America/New_York")
DISC_FROM, DISC_TO = pd.Timestamp("2024-05-14"), pd.Timestamp("2025-07-01")
QUIET_FROM, QUIET_TO = pd.Timestamp("2021-07-20"), pd.Timestamp("2024-01-01")


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["time"], unit="s")          # server time (NY + 7 h)
    ny = (df["ts"] - pd.Timedelta(hours=7))
    df["ny_hour"] = ny.dt.hour
    df["ny_date"] = ny.dt.date                                 # trading day: NY 17:00 rollover = server 00:00
    df["day"] = df["ts"].dt.date
    return df.reset_index(drop=True)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = np.maximum(df["high"], pc) - np.minimum(df["low"], pc)
    return tr.rolling(n).mean()


def vr(r: np.ndarray, k: int) -> float:
    r = r[~np.isnan(r)]
    if len(r) < 10 * k:
        return np.nan
    v1 = r.var()
    rk = np.convolve(r, np.ones(k), "valid")[::k]
    return rk.var() / (k * v1) if v1 > 0 else np.nan


def q1_regime():
    print("\nQ1 regime: ATR14 D1 % of price, M5/M15 mean range")
    d1 = pd.read_csv(DATA / "bars_XAUUSD_D1.csv")
    d1["ts"] = pd.to_datetime(d1["time"], unit="s")
    d1["atrp"] = atr(d1) / d1["close"] * 100
    d1["rng"] = (d1["high"] - d1["low"]) / d1["close"] * 100
    y = d1.groupby(d1["ts"].dt.year).agg(atr_pct=("atrp", "mean"), day_range_pct=("rng", "mean"),
                                         price=("close", "mean"))
    print(y.round(2).to_string())


def q2_follow_fade(df: pd.DataFrame, name: str):
    lr = np.log(df["close"]).diff().to_numpy()
    print(f"\nQ2 {name}: variance ratio (1 = random walk, >1 follow-through, <1 mean reversion)")
    print("  " + "  ".join(f"VR({k})={vr(lr, k):.3f}" for k in (3, 6, 12, 24, 48)))
    a = atr(df).to_numpy()
    c = df["close"].to_numpy()
    rows = []
    for k in (3, 6, 12, 24):
        past = (c - np.roll(c, k)) / a
        fut = (np.roll(c, -k) - c) / a
        ok = np.isfinite(past) & np.isfinite(fut)
        ok[:k] = False
        ok[-k:] = False
        for th in (1.5, 3.0):
            m = ok & (np.abs(past) >= th)
            if m.sum() < 30:
                continue
            same = np.sign(past[m]) * fut[m]
            rows.append((k, th, int(m.sum()), same.mean(), (same > 0).mean()))
    print(pd.DataFrame(rows, columns=["k", "move_atr", "n", "next_k_same_dir_atr", "share_continue"]).round(3)
          .to_string(index=False))


def q3_clock(df: pd.DataFrame, name: str):
    a = atr(df)
    df = df.assign(rng=df["high"] - df["low"], ret=df["close"].diff(), sp=df["spread"] * 0.01, atr=a)
    day_rng = df.groupby("ny_date")["rng"].transform("sum")
    df["share"] = df["rng"] / day_rng
    g = df.groupby("ny_hour")
    lr = np.log(df["close"]).diff()
    vr6 = {h: vr(lr[df["ny_hour"] == h].to_numpy(), 3) for h in range(24)}
    out = pd.DataFrame({
        "range_share_%": g["share"].sum() / df["ny_date"].nunique() * 100,
        "mean_bar_range_$": g["rng"].mean(),
        "drift_$/bar": g["ret"].mean(),
        "spread_$": g["sp"].median(),
        "spread/atr": (g["sp"].median() / g["atr"].median()),
        "VR3_in_hour": pd.Series(vr6),
    })
    out.index.name = "NY hour (VN = NY+11 summer / +12 winter)"
    print(f"\nQ3 {name}: by New York hour")
    print(out.round(3).to_string())


def q4_boxes(df: pd.DataFrame, name: str, n: int = 24, max_w: float = 4.0, horizon: int = 72):
    a = atr(df).to_numpy()
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    hh = pd.Series(h).rolling(n).max().shift(1).to_numpy()
    ll = pd.Series(l).rolling(n).min().shift(1).to_numpy()
    # H1-equivalent trend side: close vs EMA of 12*50 M5 bars (EMA50 H1)
    ema = pd.Series(c).ewm(span=600, adjust=False).mean().to_numpy()
    rows = []
    last = -10**9
    for i in range(700, len(c) - horizon):
        w = hh[i] - ll[i]
        if not np.isfinite(w) or a[i - 1] <= 0 or w > max_w * a[i - 1]:
            continue
        up, dn = c[i] > hh[i], c[i] < ll[i]
        if not (up or dn) or i - last < n:
            continue
        last = i
        d = 1 if up else -1
        target = c[i] + d * w
        stop = ll[i] if up else hh[i]
        res = 0
        for j in range(i + 1, i + horizon + 1):
            if (d == 1 and l[j] <= stop) or (d == -1 and h[j] >= stop):
                res = -1
                break
            if (d == 1 and h[j] >= target) or (d == -1 and l[j] <= target):
                res = 1
                break
        rows.append(dict(ny_hour=int(df["ny_hour"].iat[i]), w_atr=w / a[i - 1], d=d,
                         with_trend=int(np.sign(c[i] - ema[i]) == d), res=res))
    b = pd.DataFrame(rows)
    if b.empty:
        return
    print(f"\nQ4 {name}: {len(b)} box breaks (24 bars) -> +1 width (1) before the opposite edge (-1), 0 = neither in 6h")
    b["wq"] = pd.qcut(b["w_atr"], 4, labels=["narrow", "q2", "q3", "wide"])
    b["sess"] = pd.cut(b["ny_hour"], [-1, 2, 7, 11, 16, 23], labels=["NY close/Asia(17-21h ny wrap)", "Asia 03-07",
                                                                       "London 08-11", "NY 12-16", "late 17-23"])
    for col in ("wq", "with_trend", "sess", "d"):
        t = b.groupby(col, observed=True)["res"].agg(n="size", win=lambda s: (s == 1).mean(),
                                                     loss=lambda s: (s == -1).mean())
        t["edge_R_at_1:1"] = t["win"] - t["loss"]
        print(t.round(3).to_string())


def q5_levels(df: pd.DataFrame, name: str):
    a = atr(df).to_numpy()
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    day = df["ny_date"].to_numpy()
    hour = df["ny_hour"].to_numpy()
    # prior NY-day high/low and the Asia range (NY 19:00-02:59 = server 02-09) of the current day
    daily = df.groupby("ny_date").agg(dh=("high", "max"), dl=("low", "min"))
    prev = daily.shift(1)
    pdh = pd.Series(day).map(prev["dh"]).to_numpy()
    pdl = pd.Series(day).map(prev["dl"]).to_numpy()
    rows = []
    touched = set()
    for i in range(700, len(c) - 12):
        if not np.isfinite(pdh[i]) or a[i] <= 0:
            continue
        lv = []
        if h[i] >= pdh[i] > l[i] or (h[i] >= pdh[i] and c[i - 1] < pdh[i]):
            lv.append(("PDH", pdh[i], 1))
        if l[i] <= pdl[i] < h[i] or (l[i] <= pdl[i] and c[i - 1] > pdl[i]):
            lv.append(("PDL", pdl[i], -1))
        r25 = np.floor(h[i] / 25) * 25
        if l[i] < r25 <= h[i]:
            lv.append(("R25", r25, 1 if c[i - 1] < r25 else -1))
        for kind, p, d in lv:
            key = (kind, day[i], round(p, 2))
            if key in touched:
                continue
            touched.add(key)
            fut = c[i + 12]
            moved = d * (fut - p) / a[i]
            rows.append(dict(kind=kind, ny_hour=hour[i], beyond_1h_atr=moved,
                             broke=int(moved >= 0.5 * np.sqrt(12)), rejected=int(moved <= -0.5 * np.sqrt(12))))
    t = pd.DataFrame(rows)
    print(f"\nQ5 {name}: first touch of a level, close 1h later beyond (+) or back (-), in ATR M5")
    print(t.groupby("kind").agg(n=("broke", "size"), mean_atr=("beyond_1h_atr", "mean"),
                                broke=("broke", "mean"), rejected=("rejected", "mean")).round(3).to_string())


def main():
    q1_regime()
    m5 = load(DATA / "m5v" / "XAUUSD.csv")
    disc = m5[(m5["ts"] >= DISC_FROM) & (m5["ts"] < DISC_TO)].reset_index(drop=True)
    m15 = load(DATA / "m15v" / "XAUUSD.csv")
    quiet = m15[(m15["ts"] >= QUIET_FROM) & (m15["ts"] < QUIET_TO)].reset_index(drop=True)
    loud15 = m15[(m15["ts"] >= DISC_FROM) & (m15["ts"] < DISC_TO)].reset_index(drop=True)
    print(f"\nM5 discovery bars: {len(disc)}  M15 quiet: {len(quiet)}  M15 discovery: {len(loud15)}")
    q2_follow_fade(disc, "M5 discovery 05/2024-06/2025")
    q2_follow_fade(loud15, "M15 discovery 05/2024-06/2025")
    q2_follow_fade(quiet, "M15 quiet 07/2021-2023")
    q3_clock(disc, "M5 discovery")
    q4_boxes(disc, "M5 discovery")
    q4_boxes(quiet, "M15 quiet", horizon=24)
    q5_levels(disc, "M5 discovery")


if __name__ == "__main__":
    main()
