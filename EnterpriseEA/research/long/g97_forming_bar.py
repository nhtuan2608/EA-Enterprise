"""G97 look: predict the forming H1 bar from a locked M15 state (user idea 11/10, chart 12/03/2026). MT5 data only.

At the close of an M15 bar inside an H1 bar (:15, :30, :45 server time), for a sell (buy mirrored):
  C1 M15 ribbon   close < EMA21 < EMA55 < EMA100 < EMA200
  C2 M15 DMI      DI- - DI+ >= GAP (the DI lines far apart)
  C3 M15 ADX      rising (ADX now > ADX one bar ago)
  C4 H1 context   the last closed H1 bar closed below the H1 EMA200
  C5 M30 pressure close in the lower half of the forming M30 bar's range
  C6 H1 wick      the forming H1 bar has an upper wick >= 25% of its range so far (optional)
Prediction: the forming H1 bar closes below the entry (continuation to the round hour).
Trade (scalp): enter at the next M15 open, stop above the forming H1 high + 0.1 ATR M15, exit at the H1 close.
Costs: the bar spread at entry (shorts pay it at the exit).

  python g97_forming_bar.py example     -> the rule bar by bar on 12/03/2026 (VN time)
  python g97_forming_bar.py train       -> train period only (07/2021-2023); validate/test stay sealed
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from g95_xau_read import DATA

GAP = 10.0
TRAIN = ("2021-07-20", "2024-01-01")


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def dmi(h, l, c, n=14):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    up = h - np.concatenate([[h[0]], h[:-1]])
    dn = np.concatenate([[l[0]], l[:-1]]) - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    rma = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    a = rma(tr)
    pdi, mdi = 100 * rma(pdm) / a, 100 * rma(mdm) / a
    adx = rma(100 * abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9))
    return pdi, mdi, adx, a


def build() -> pd.DataFrame:
    m = pd.read_csv(DATA / "m15v" / "XAUUSD.csv")
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    h, l, c, o = (m[k].to_numpy() for k in ("high", "low", "close", "open"))
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(h, l, c)
    # H1 from M15 (server hour buckets), EMA200 on closed H1 bars
    m["hour"] = m["ts"].dt.floor("h")
    H = m.groupby("hour").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    H["e200"] = ema(H["c"].to_numpy(), 200)
    H["side"] = np.sign(H["c"] - H["e200"])
    prev_side = H["side"].shift(1)                      # last closed H1 bar before this hour
    m["h1_prev_side"] = m["hour"].map(prev_side)
    m["h1_close"] = m["hour"].map(H["c"])
    # forming H1 and M30 bars up to and including this M15 bar
    g = m.groupby("hour")
    m["h1_open"] = g["open"].transform("first")
    m["h1_hi"] = g["high"].cummax()
    m["h1_lo"] = g["low"].cummin()
    m["half"] = m["ts"].dt.floor("30min")
    g30 = m.groupby("half")
    m["m30_hi"] = g30["high"].cummax()
    m["m30_lo"] = g30["low"].cummin()
    m["minute"] = m["ts"].dt.minute
    return m


def conditions(m: pd.DataFrame, d: int) -> pd.DataFrame:
    c = m["close"]
    if d == -1:
        ribbon = (c < m["e21"]) & (m["e21"] < m["e55"]) & (m["e55"] < m["e100"]) & (m["e100"] < m["e200"])
        gap = (m["mdi"] - m["pdi"]) >= GAP
        mid = c <= (m["m30_hi"] + m["m30_lo"]) / 2
        body_top = np.maximum(m["h1_open"], c)
        wick = (m["h1_hi"] - body_top) >= 0.25 * (m["h1_hi"] - m["h1_lo"]).clip(lower=1e-9)
    else:
        ribbon = (c > m["e21"]) & (m["e21"] > m["e55"]) & (m["e55"] > m["e100"]) & (m["e100"] > m["e200"])
        gap = (m["pdi"] - m["mdi"]) >= GAP
        mid = c >= (m["m30_hi"] + m["m30_lo"]) / 2
        body_bot = np.minimum(m["h1_open"], c)
        wick = (body_bot - m["h1_lo"]) >= 0.25 * (m["h1_hi"] - m["h1_lo"]).clip(lower=1e-9)
    rising = m["adx"] > m["adx"].shift(1)
    h1 = m["h1_prev_side"] == d
    inside = m["minute"] != 45          # the M15 bar opening at :45 closes on the hour: nothing left to predict
    return pd.DataFrame({"C1": ribbon, "C2": gap, "C3": rising, "C4": h1, "C5": mid, "C6": wick, "inside": inside})


def trades(m: pd.DataFrame, mask: pd.Series, d: int) -> pd.DataFrame:
    idx = np.flatnonzero(mask.to_numpy())
    o, sp = m["open"].to_numpy(), m["spread"].to_numpy() * 0.01
    hi, lo, atr = m["high"].to_numpy(), m["low"].to_numpy(), m["atr"].to_numpy()
    hour = m["hour"].to_numpy()
    rows = []
    last_hour = None
    for i in idx:
        if hour[i] == last_hour or i + 1 >= len(m) or hour[i + 1] != hour[i]:
            continue                      # one trade per H1 bar; the next M15 bar must still be inside it
        last_hour = hour[i]
        e = i + 1
        entry = o[e] + (sp[e] if d == 1 else 0.0)
        stop = (m["h1_lo"].iat[i] - 0.1 * atr[i]) if d == 1 else (m["h1_hi"].iat[i] + 0.1 * atr[i])
        risk = d * (entry - stop)
        if not risk > 0:
            continue
        j, px = e, None
        while j < len(m) and hour[j] == hour[i]:
            if (d == 1 and lo[j] <= stop) or (d == -1 and hi[j] + sp[j] >= stop):
                px = stop
                break
            j += 1
        if px is None:
            j -= 1
            px = m["close"].iat[j] + (sp[j] if d == -1 else 0.0)
        rows.append(dict(t=m["ts"].iat[i], d=d, r=d * (px - entry) / risk,
                         cont=int(d * (m["h1_close"].iat[i] - m["close"].iat[i]) > 0), risk_atr=risk / atr[i]))
    return pd.DataFrame(rows)


def example(m):
    w = m[(m["ts"] >= "2026-03-12 14:00") & (m["ts"] < "2026-03-12 19:00")]
    cs = conditions(m, -1).loc[w.index]
    print("12/03/2026, sell rule at each M15 close (VN = server + 4; bar shown by its close time)")
    for k in w.index:
        r = m.loc[k]
        close_vn = r["ts"] + pd.Timedelta(minutes=15) + pd.Timedelta(hours=4)
        flags = " ".join(f"{c}={int(cs.at[k, c])}" for c in ("C1", "C2", "C3", "C4", "C5", "C6"))
        ok = all(cs.loc[k, ["C1", "C2", "C3", "C4", "C5", "inside"]])
        print(f"{close_vn:%H:%M} VN  c={r['close']:.1f}  DI-={r['mdi']:.1f} DI+={r['pdi']:.1f} ADX={r['adx']:.1f}  {flags}"
              f"  -> {'SELL' if ok else '-'}  (H1 closes {r['h1_close']:.1f})")


def train(m):
    p = m[(m["ts"] >= TRAIN[0]) & (m["ts"] < TRAIN[1])]
    out = []
    for d in (-1, 1):
        cs = conditions(m, d).loc[p.index]
        base = cs["inside"]
        variants = {
            "all inside bars (control)": base,
            "C1 ribbon": base & cs.C1,
            "C1+C2+C3": base & cs.C1 & cs.C2 & cs.C3,
            "C1..C4": base & cs.C1 & cs.C2 & cs.C3 & cs.C4,
            "C1..C5 (user rule)": base & cs.C1 & cs.C2 & cs.C3 & cs.C4 & cs.C5,
            "C1..C6 (+H1 wick)": base & cs.C1 & cs.C2 & cs.C3 & cs.C4 & cs.C5 & cs.C6,
        }
        for name, mk in variants.items():
            t = trades(p, mk, d)
            if t.empty:
                continue
            out.append(dict(dir="SELL" if d == -1 else "BUY", rule=name, n=len(t), h1_continues=t["cont"].mean(),
                            mean_r=t["r"].mean(), win=(t["r"] > 0).mean(), risk_atr=t["risk_atr"].median()))
    pd.set_option("display.width", 200)
    print("train 07/2021-2023, M15 XAUUSD; one trade per H1 bar; exit at the H1 close")
    print(pd.DataFrame(out).round(3).to_string(index=False))


if __name__ == "__main__":
    M = build()
    {"example": example, "train": train}[sys.argv[1] if len(sys.argv) > 1 else "example"](M)
