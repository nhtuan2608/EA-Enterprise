"""G102: instead of taking profit, add a leg at each profit milestone; or one far swing target. (G100 entries)

User (11/10): "instead of TP, add positions at those TP points; or find one bigger point to take profit for a swing".

  python g102_pyramid_tp.py

Base trade = G101 (user's rule V2, initial invalidation at the 16-bar M15 extreme, exit rule X from +1R).
Exit rules X: H1E55, H4E55, D1E21 (armed as in G101).
Adds:   P0 none | P3 a new leg at every +3R of the base (3R, 6R, 9R; max 3 adds) | P5 every +5R (max 3)
        each add risks 1 unit with its own stop at the 16-bar M15 extreme at that bar; adds close with the base
        (or at their own stop). Result = sum of all legs in units of one leg's risk.
Targets (base and adds close together): T0 none | T10 10R of the base | T20 20R | TD the 120-day D1 low (sell) /
        high (buy) beyond the entry, else none | TA 10 x ATR(D1) from the entry.
Periods: train 07/2021-2023, validate 2024-06/2025 (entries); test sealed; the user's 12/03/2026 example shown apart.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g98_context as g98
import g100_user_rule as u
from g101_loose_hold import Loose

EXITS = ("H1E55", "H4E55", "D1E21")
ADDS = {"P0": None, "P3": 3.0, "P5": 5.0}
TARGETS = ("T0", "T10", "T20", "TD", "TA")


class Pyr(Loose):
    def __init__(self, m):
        super().__init__(m)
        day = m["ts"].dt.normalize()
        D = m.groupby(day).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
        pc = D["c"].shift(1)
        datr = (np.maximum(D["h"], pc) - np.minimum(D["l"], pc)).rolling(20).mean().shift(1)
        self.d_atr = day.map(datr).to_numpy()
        self.d_lo120 = day.map(D["l"].rolling(120).min().shift(1)).to_numpy()
        self.d_hi120 = day.map(D["h"].rolling(120).max().shift(1)).to_numpy()

    def run2(self, i, d, rule, add_step, target):
        e = i + 1
        if e >= len(self.c):
            return None
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        stop = (self.ll16[i] - 0.1 * self.atr[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr[i])
        risk = d * (entry - stop)
        if not risk > 0:
            return None
        tgt = None
        if target == "T10":
            tgt = entry + d * 10 * risk
        elif target == "T20":
            tgt = entry + d * 20 * risk
        elif target == "TA" and np.isfinite(self.d_atr[i]):
            tgt = entry + d * 10 * self.d_atr[i]
        elif target == "TD":
            lv = self.d_lo120[i] if d == -1 else self.d_hi120[i]
            if np.isfinite(lv) and d * (lv - entry) > 0:
                tgt = lv
        tf, kind = rule[:2], rule[2:]
        A, B = self.T[tf], self.T["H1"]
        legs = [[entry, stop, risk, None]]
        best, best_close, armed = entry, None, False
        next_add = add_step
        j = e
        exit_px = None
        while j < len(self.c):
            hi, lo = self.h[j], self.l[j]
            for k, L in enumerate(legs[1:], 1):
                if L[3] is None and ((d == 1 and lo <= L[1]) or (d == -1 and hi + self.sp[j] >= L[1])):
                    L[3] = L[1]
            if (d == 1 and lo <= stop) or (d == -1 and hi + self.sp[j] >= stop):
                exit_px = stop
                break
            if tgt is not None and ((d == 1 and hi >= tgt) or (d == -1 and lo + self.sp[j] <= tgt)):
                exit_px = tgt
                break
            best = max(best, hi) if d == 1 else min(best, lo)
            r_best = d * (best - entry) / risk
            cl = self.c[j]
            if A["done"][j]:
                hc0 = A["close"][j]
                best_close = hc0 if best_close is None else (max(best_close, hc0) if d == 1 else min(best_close, hc0))
            hit = False
            if r_best < 1:
                hit = d * (cl - self.e100[j]) < 0
            elif kind.startswith("E"):
                ema = A[f"e{kind[1:]}"][j]
                if A["done"][j] and d * (A["close"][j] - ema) > 0:
                    armed = True
                if rule == "H1E55" or armed:
                    hit = bool(A["done"][j]) and d * (A["close"][j] - ema) < 0
                else:
                    hit = bool(B["done"][j]) and d * (B["close"][j] - B["e55"][j]) < 0
            if hit:
                exit_px = cl + (self.sp[j] if d == -1 else 0.0)
                break
            # add a leg at each milestone of the base (current close beyond entry + step R)
            if add_step and len(legs) < 4 and d * (cl - entry) / risk >= next_add:
                ae = j + 1
                if ae < len(self.c):
                    a_entry = self.o[ae] + (self.sp[ae] if d == 1 else 0.0)
                    a_stop = (self.ll16[j] - 0.1 * self.atr[j]) if d == 1 else (self.hh16[j] + 0.1 * self.atr[j])
                    a_risk = d * (a_entry - a_stop)
                    if a_risk > 0:
                        legs.append([a_entry, a_stop, a_risk, None])
                next_add += add_step
            j += 1
        if exit_px is None:
            j = len(self.c) - 1
            exit_px = self.c[j]
        total = 0.0
        for L in legs:
            px = L[3] if L[3] is not None else exit_px
            total += d * (px - L[0]) / L[2]
        return total, j, len(legs)


def book(P, m, d, mask, rule, add, tgt):
    rows, free = [], 0
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = P.run2(i, d, rule, ADDS[add], tgt)
        if res is None:
            continue
        r, jx, n = res
        rows.append((m["ts"].iat[i], r, n, (jx - i) / 96))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "r", "legs", "days"])


def stats(t, p):
    a, b = g98.PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)]
    if x.empty:
        return {}
    eq = x["r"].cumsum().to_numpy()
    return dict(n=len(x), R=x["r"].mean(), totR=x["r"].sum(), big10=int((x["r"] >= 10).sum()),
                ddR=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()))


def main():
    m, H = g98.prepare()
    P = Pyr(m)
    ts = m["ts"]
    lim = (ts < pd.Timestamp(g98.PERIODS["test"][0])).to_numpy()
    mk_s, _ = u.masks(m, -1)
    i = np.flatnonzero(mk_s["V2"] & ((ts >= "2026-03-12 14:00") & (ts < "2026-03-13")).to_numpy())[0]
    print("12/03/2026 sell (illustration, sealed test period):")
    for rule, add, tgt in itertools.product(EXITS, ADDS, TARGETS):
        r, jx, n = P.run2(i, -1, rule, ADDS[add], tgt)
        print(f"  {rule} {add} {tgt}: {r:+.1f}R, legs {n}, exit {ts.iat[jx]:%d/%m} px {m['close'].iat[jx]:.0f}")
    rows = []
    for d in (-1, 1):
        mk, _ = u.masks(m, d)
        for rule, add, tgt in itertools.product(EXITS, ADDS, TARGETS):
            t = book(P, m, d, mk["V2"] & lim, rule, add, tgt)
            row = dict(dir="SELL" if d == -1 else "BUY", exit=rule, adds=add, target=tgt)
            for p in g98.OPEN:
                for k, v in stats(t, p).items():
                    row[f"{p[:3]}_{k}"] = v
            rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv("out/g102_pyramid_tp.csv", index=False)
    pd.set_option("display.width", 220)
    print()
    print(tab.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
