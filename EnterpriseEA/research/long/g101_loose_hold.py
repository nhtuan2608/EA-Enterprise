"""G101: looser exits for a swing hold (H4/D1), no time cap. Entries = the user's rule (G100 V1/V2).

User (11/10, H4 chart 11/2025-10/2026): what if the exit is loosened to hold a swing for weeks/months?

  python g101_loose_hold.py

Before +1R every rule exits on an M15 close beyond the M15 EMA100 (as G100 H1E); from +1R it exits only on:
  H1E55   H1 close beyond the H1 EMA55 (G100 reference)
  H4E55   H4 close beyond the H4 EMA55
  H4E200  H4 close beyond the H4 EMA200
  D1E21   D1 close beyond the D1 EMA21
  D1E55   D1 close beyond the D1 EMA55
  D1E100  D1 close beyond the D1 EMA100
  D1C5    D1 close 5 ATR(D1) away from the best D1 close since entry
A slow-EMA rule arms after the first H4/D1 close on the trade side of that EMA; until then the trade is held on
the H1 EMA55. The initial invalidation (16-bar M15 extreme +/- 0.1 ATR) stays at the broker for the whole trade. No time cap.
One trade at a time per direction. Spread at entry and exit.
Periods: train 07/2021-2023, validate 2024-06/2025 (entries only; a trade may run into later data), test sealed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g98_context as g98
import g100_user_rule as u

RULES = ("H1E55", "H4E55", "H4E200", "D1E21", "D1E55", "D1E100", "D1C5")


def htf(m):
    ts = m["ts"]
    out = {}
    for name, key in (("H1", ts.dt.floor("h")), ("H4", ts.dt.floor("4h")), ("D1", ts.dt.normalize())):
        done = (key != key.shift(-1)).to_numpy()
        closes = m["close"][done].to_numpy()
        hi = m.groupby(key)["high"].max().to_numpy()
        lo = m.groupby(key)["low"].min().to_numpy()
        pc = np.concatenate([[closes[0]], closes[:-1]])
        atr = pd.Series(np.maximum(hi, pc) - np.minimum(lo, pc)).rolling(20).mean().to_numpy()
        arr = {"done": done, "close": np.full(len(m), np.nan), "atr": np.full(len(m), np.nan)}
        arr["close"][done] = closes
        arr["atr"][done] = atr
        for n in (21, 55, 100, 200):
            e = np.full(len(m), np.nan)
            e[done] = pd.Series(closes).ewm(span=n, adjust=False).mean().to_numpy()
            arr[f"e{n}"] = e
        out[name] = arr
    return out


class Loose:
    def __init__(self, m):
        self.m = m
        self.o, self.h, self.l, self.c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy() * 0.01
        self.atr = m["atr"].to_numpy()
        self.e100 = m["e100"].to_numpy()
        self.hh16 = pd.Series(self.h).rolling(16).max().to_numpy()
        self.ll16 = pd.Series(self.l).rolling(16).min().to_numpy()
        self.T = htf(m)

    def run(self, i, d, rule):
        e = i + 1
        if e >= len(self.c):
            return None
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        stop = (self.ll16[i] - 0.1 * self.atr[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr[i])
        risk = d * (entry - stop)
        if not risk > 0:
            return None
        tf, kind = rule[:2], rule[2:]
        A = self.T[tf]
        best = entry
        best_close = None
        armed = False
        j = e
        while j < len(self.c):
            if (d == 1 and self.l[j] <= stop) or (d == -1 and self.h[j] + self.sp[j] >= stop):
                return d * (stop - entry) / risk, j, "stop"
            best = max(best, self.h[j]) if d == 1 else min(best, self.l[j])
            if A["done"][j]:
                hc0 = A["close"][j]
                best_close = hc0 if best_close is None else (max(best_close, hc0) if d == 1 else min(best_close, hc0))
            r_best = d * (best - entry) / risk
            cl = self.c[j]
            if r_best < 1:
                if d * (cl - self.e100[j]) < 0:
                    return (d * (cl - entry) - (self.sp[j] if d == -1 else 0)) / risk, j, "pre1R"
            elif A["done"][j] or (rule != "H1E55" and self.T["H1"]["done"][j] and not armed and kind.startswith("E")):
                hc = A["close"][j] if A["done"][j] else np.nan
                if kind.startswith("E"):
                    ema = A[f"e{kind[1:]}"][j]
                    if A["done"][j] and d * (hc - ema) > 0:
                        armed = True                  # the HTF bar closed on the trade side of its EMA
                    if armed:
                        hit = bool(A["done"][j]) and d * (hc - ema) < 0
                    else:                             # not armed yet: hold on the H1 EMA55
                        B = self.T["H1"]
                        hit = bool(B["done"][j]) and d * (B["close"][j] - B["e55"][j]) < 0
                else:
                    hit = d * (best_close - hc) >= 5 * A["atr"][j]
                if hit:
                    return (d * (cl - entry) - (self.sp[j] if d == -1 else 0)) / risk, j, rule
            j += 1
        return d * (self.c[-1] - entry) / risk, len(self.c) - 1, "open"


def book(L, m, d, mask, rule):
    rows, free = [], 0
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = L.run(i, d, rule)
        if res is None:
            continue
        r, jx, why = res
        rows.append((m["ts"].iat[i], r, (jx - i) / 96, why))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "r", "days", "why"])


def stats(t, p):
    a, b = g98.PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)]
    if x.empty:
        return {}
    eq = x["r"].cumsum().to_numpy()
    return dict(n=len(x), R=x["r"].mean(), totR=x["r"].sum(), win=(x["r"] > 0).mean(), big10=int((x["r"] >= 10).sum()),
                best=x["r"].max(), days=x["days"].median(), ddR=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()))


def main():
    m, H = g98.prepare()
    L = Loose(m)
    ts = m["ts"]
    lim = (ts < pd.Timestamp(g98.PERIODS["test"][0])).to_numpy()
    # 1) the user's examples (illustration only; they lie in the sealed test period)
    mk_s, _ = u.masks(m, -1)
    for lab, a, b, off in (("03/03/2026", "2026-03-03 06:00", "2026-03-04", 5), ("12/03/2026", "2026-03-12 14:00", "2026-03-13", 4)):
        i = np.flatnonzero(mk_s["V2"] & ((ts >= a) & (ts < b)).to_numpy())[0]
        print(f"\n{lab} sell at {ts.iat[i] + pd.Timedelta(hours=off, minutes=15):%d/%m %H:%M} VN, entry {m['open'].iat[i + 1]:.0f}")
        for rule in RULES:
            r, jx, why = L.run(i, -1, rule)
            print(f"  {rule:6s} exit {ts.iat[jx]:%d/%m/%Y} px {m['close'].iat[jx]:.0f} -> {r:+.1f}R ({why}, {(jx - i) / 96:.0f} days)")
    # 2) every entry in train / validate, both directions
    rows = []
    for d in (-1, 1):
        mk, _ = u.masks(m, d)
        for v in ("V1", "V2"):
            for rule in RULES:
                t = book(L, m, d, mk[v] & lim, rule)
                row = dict(dir="SELL" if d == -1 else "BUY", rule=v, exit=rule)
                for p in g98.OPEN:
                    for k, val in stats(t, p).items():
                        row[f"{p[:3]}_{k}"] = val
                rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv("out/g101_loose_hold.csv", index=False)
    pd.set_option("display.width", 260)
    cols = ["dir", "rule", "exit", "tra_n", "tra_R", "tra_totR", "tra_win", "tra_big10", "tra_best", "tra_days", "tra_ddR",
            "val_n", "val_R", "val_totR", "val_win", "val_big10", "val_best", "val_days", "val_ddR"]
    print()
    print(tab[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
