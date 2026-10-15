"""G98: wider entry contexts + context-managed holding (no fixed take-profit), XAUUSD M15/H1, both directions.

User (11/10, charts 12-20/03/2026): do not cut trades with early TP/SL; manage by the pattern's reactions and
context, hold for the range expansion; do not stay inside the existing S07 conditions.

  python g98_context.py            -> train + validate tables (test 07/2025-06/2026 stays sealed)

Entry trigger (sell; buy mirrored), at an M15 close, no wait for the H1 close (G97 "early" form):
  M15 close beyond all four EMAs 21/55/100/200 (order not required), DI gap >= 10 in the direction,
  ADX rising, close in the trade-direction half of the forming M30 bar.
Context filters (one at a time):
  X0 none | X1 last closed H1 beyond the H1 EMA200 | X2 last closed H1 beyond the H1 EMA55
  X3 compression before: min M15 ADX of the last 16 bars <= 25 | X4 D1 regime agrees (close and 10-day slope
  of the D1 EMA50, G96) | X5 H1 lower high (sell) / higher low (buy): the last two confirmed H1 swings step
Structural invalidation (also the 1R unit): the 16-bar M15 extreme against the trade + 0.1 ATR M15.
Management (no target; max 10 days):
  S07   M15 close beyond EMA55, EMA100 once 3R (the current S07 exit, for reference)
  H1E   before +1R: M15 close beyond the M15 EMA100; after: H1 close beyond the H1 EMA55
  SWG   stop trails to each confirmed H1 swing (lower high for a sell) once that is past the entry
  FIB   H1 close retracing > 61.8% of the current impulse (last confirmed H1 swing -> extreme), active after 1R
  CHD   H1 close 3 ATR(H1) from the best close
  ADX   after 1R: H1 ADX >= 45 turning down, or the H1 DI lines cross against the trade, or H1 EMA55
Adds (A1 variant): base >= +1R, after a pause (M15 ADX <= 25 since the last leg) a new trigger in the same
direction adds a leg (own invalidation; exits with the base), at most 2 adds. Trade R = sum of legs (each 1R risk).
Costs: bar spread at entry and exit. One base per direction at a time.
"""
from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

from g97_forming_bar import build, dmi, ema

PERIODS = {"train": ("2021-07-20", "2024-01-01"), "validate": ("2024-01-01", "2025-07-01"),
           "test": ("2025-07-01", "2026-07-01"), "exam": ("2026-07-01", "2027-01-01")}
OPEN = ("train", "validate")
CONTEXTS = ("X0", "X1", "X2", "X3", "X4", "X5")
MANAGE = ("S07", "H1E", "SWG", "FIB", "CHD", "ADX")
MAX_BARS = 10 * 96


def prepare():
    m = build().reset_index(drop=True)
    # H1 bars (server hours) from M15, indicators on completed H1 bars
    H = m.groupby("hour").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    H = H.reset_index()
    for n in (21, 55, 200):
        H[f"e{n}"] = ema(H["c"].to_numpy(), n)
    H["pdi"], H["mdi"], H["adx"], H["atr"] = dmi(H["h"].to_numpy(), H["l"].to_numpy(), H["c"].to_numpy())
    hh, ll = H["h"].to_numpy(), H["l"].to_numpy()
    n = len(H)
    sw_hi = np.full(n, np.nan)   # last confirmed swing high known after H1 bar k closes
    sw_lo = np.full(n, np.nan)
    prev_hi = np.full(n, np.nan)
    prev_lo = np.full(n, np.nan)
    last_h = last_l = np.nan
    pl_h = pl_l = np.nan
    for k in range(4, n):
        j = k - 2
        if hh[j] >= hh[j - 2:j + 3].max():
            pl_h, last_h = last_h, hh[j]
        if ll[j] <= ll[j - 2:j + 3].min():
            pl_l, last_l = last_l, ll[j]
        sw_hi[k], sw_lo[k], prev_hi[k], prev_lo[k] = last_h, last_l, pl_h, pl_l
    H["sw_hi"], H["sw_lo"], H["prev_hi"], H["prev_lo"] = sw_hi, sw_lo, prev_hi, prev_lo
    hidx = pd.Series(np.arange(n), index=H["hour"])
    m["hi_cur"] = m["hour"].map(hidx).to_numpy()
    m["h1_done"] = (m["ts"].dt.minute == 45).to_numpy()          # this M15 close completes the H1 bar
    # D1 regime (G96 R1 EMA50) from M15 server days
    m["day"] = m["ts"].dt.normalize()
    D = m.groupby("day").agg(c=("close", "last"))
    e50 = ema(D["c"].to_numpy(), 50)
    side = np.sign(D["c"].to_numpy() - e50)
    slope = np.sign(e50 - np.roll(e50, 10))
    reg = np.where(side == slope, side, 0.0)
    m["d1_reg"] = m["day"].map(pd.Series(np.roll(reg, 1), index=D.index)).to_numpy()   # prior day
    return m, H


def triggers(m, H, d):
    c = m["close"]
    E = [m[f"e{n}"] for n in (21, 55, 100, 200)]
    lo, hi = np.minimum.reduce(E), np.maximum.reduce(E)
    beyond = (c < lo) if d == -1 else (c > hi)
    gap = ((m["mdi"] - m["pdi"]) if d == -1 else (m["pdi"] - m["mdi"])) >= 10
    rising = m["adx"] > m["adx"].shift(1)
    mid = (m["m30_hi"] + m["m30_lo"]) / 2
    half = (c <= mid) if d == -1 else (c >= mid)
    base = (beyond & gap & rising & half).to_numpy()
    prev = m["hi_cur"].to_numpy() - 1                          # last closed H1 bar
    ok = prev >= 0
    pc = np.where(ok, H["c"].to_numpy()[prev.clip(0)], np.nan)
    ctx = {"X0": np.ones(len(m), bool),
           "X1": np.sign(pc - H["e200"].to_numpy()[prev.clip(0)]) == d,
           "X2": np.sign(pc - H["e55"].to_numpy()[prev.clip(0)]) == d,
           "X3": (pd.Series(m["adx"]).rolling(16).min().shift(1) <= 25).to_numpy(),
           "X4": m["d1_reg"].to_numpy() == d}
    if d == -1:
        ctx["X5"] = H["sw_hi"].to_numpy()[prev.clip(0)] < H["prev_hi"].to_numpy()[prev.clip(0)]
    else:
        ctx["X5"] = H["sw_lo"].to_numpy()[prev.clip(0)] > H["prev_lo"].to_numpy()[prev.clip(0)]
    return base, {k: v & ok for k, v in ctx.items()}


class Sim:
    def __init__(self, m, H):
        self.m, self.H = m, H
        self.o, self.h, self.l, self.c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy() * 0.01
        self.atr = m["atr"].to_numpy()
        self.e55, self.e100 = m["e55"].to_numpy(), m["e100"].to_numpy()
        self.adx15 = m["adx"].to_numpy()
        self.hcur, self.done = m["hi_cur"].to_numpy(), m["h1_done"].to_numpy()
        self.Hc, self.He55 = H["c"].to_numpy(), H["e55"].to_numpy()
        self.Hatr, self.Hadx = H["atr"].to_numpy(), H["adx"].to_numpy()
        self.Hpdi, self.Hmdi = H["pdi"].to_numpy(), H["mdi"].to_numpy()
        self.Hsw_hi, self.Hsw_lo = H["sw_hi"].to_numpy(), H["sw_lo"].to_numpy()
        self.hh16 = pd.Series(self.h).rolling(16).max().to_numpy()
        self.ll16 = pd.Series(self.l).rolling(16).min().to_numpy()

    def leg_open(self, i, d):
        e = i + 1
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        stop = (self.ll16[i] - 0.1 * self.atr[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr[i])
        risk = d * (entry - stop)
        return (e, entry, stop, risk) if risk > 0 else None

    def run(self, i, d, manage, trig=None, adds=False):
        """Base at the trigger bar i; returns (R of all legs, bars held, n legs, exit bar)."""
        first = self.leg_open(i, d)
        if first is None:
            return None
        e0, entry0, stop0, risk0 = first
        legs = [[entry0, stop0, risk0, None]]              # entry, stop, risk, closed px
        best_close = self.c[e0]
        extreme = self.c[e0]
        stop_trail = stop0
        last_leg_bar, paused = e0, False
        j = e0
        exit_px = None
        while j < len(self.c) - 1 and j - e0 < MAX_BARS:
            hi, lo = self.h[j], self.l[j]
            # broker invalidation per leg (base: trailing stop)
            for k, L in enumerate(legs):
                if L[3] is not None:
                    continue
                st = stop_trail if k == 0 else L[1]
                if (d == 1 and lo <= st) or (d == -1 and hi + self.sp[j] >= st):
                    L[3] = st
            if legs[0][3] is not None:
                exit_px = legs[0][3]
                break
            cl = self.c[j]
            best_close = max(best_close, cl) if d == 1 else min(best_close, cl)
            extreme = max(extreme, hi) if d == 1 else min(extreme, lo)
            r_now = d * (cl - entry0) / risk0
            r_best = d * (best_close - entry0) / risk0
            stop_exit = False
            hk = self.hcur[j]
            if manage == "S07":
                ema = self.e100[j] if r_best >= 3 else self.e55[j]
                stop_exit = d * (cl - ema) < 0
            elif manage in ("H1E", "FIB", "ADX", "SWG", "CHD"):
                if r_best < 1 and manage != "CHD" and manage != "SWG":
                    stop_exit = d * (cl - self.e100[j]) < 0
                elif self.done[j]:
                    hc = self.Hc[hk]
                    if manage == "H1E":
                        stop_exit = d * (hc - self.He55[hk]) < 0
                    elif manage == "FIB":
                        origin = self.Hsw_hi[hk] if d == -1 else self.Hsw_lo[hk]
                        if np.isfinite(origin) and d * (extreme - origin) > 0:
                            stop_exit = d * (extreme - hc) > 0.618 * d * (extreme - origin)
                    elif manage == "ADX":
                        exhausted = self.Hadx[hk] < self.Hadx[hk - 1] and self.Hadx[hk - 1] >= 45
                        cross = (self.Hpdi[hk] - self.Hmdi[hk]) * d < 0
                        stop_exit = exhausted or cross or d * (hc - self.He55[hk]) < 0
                    elif manage == "CHD":
                        stop_exit = d * (best_close - hc) >= 3 * self.Hatr[hk]
                    elif manage == "SWG":
                        sw = self.Hsw_hi[hk] if d == -1 else self.Hsw_lo[hk]
                        if np.isfinite(sw) and d * (entry0 - sw) < 0 and d * (sw - stop_trail) > 0:
                            stop_trail = sw + (0.1 * self.Hatr[hk] if d == -1 else -0.1 * self.Hatr[hk])
            if stop_exit:
                exit_px = cl + (self.sp[j] if d == -1 else 0.0)
                break
            # adds after a pause
            if adds and trig is not None:
                if self.adx15[j] <= 25:
                    paused = True
                n_open = sum(1 for L in legs if L[3] is None)
                if paused and r_now >= 1 and len(legs) < 3 and trig[j] and j - last_leg_bar >= 4 and n_open == len(legs):
                    leg = self.leg_open(j, d)
                    if leg:
                        legs.append([leg[1], leg[2], leg[3], None])
                        last_leg_bar, paused = j, False
            j += 1
        if exit_px is None:
            exit_px = self.c[j] + (self.sp[j] if d == -1 else 0.0)
        total = pnl = 0.0
        for L in legs:
            px = L[3] if L[3] is not None else exit_px
            total += d * (px - L[0]) / L[2]
            pnl += d * (px - L[0])
        self.last_pnl_atr = pnl / self.atr[i]
        return total, j - e0, len(legs), j


def book(sim, m, d, mask, manage, trig, adds):
    rows = []
    free = 0
    for i in np.flatnonzero(mask):
        if i < free or i + 2 >= len(m):
            continue
        res = sim.run(i, d, manage, trig, adds)
        if res is None:
            continue
        r, bars, legs, jx = res
        rows.append((m["ts"].iat[i], d, r, bars, legs, sim.last_pnl_atr))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "d", "r", "bars", "legs", "pnl_atr"])


def period_stats(t):
    out = {}
    for p in OPEN:
        a, b = PERIODS[p]
        x = t[(t["t"] >= a) & (t["t"] < b)]
        out[p] = (len(x), x["r"].mean() if len(x) else np.nan, x["r"].sum(), (x["r"] > 0).mean() if len(x) else np.nan,
                  x["bars"].median() / 4 if len(x) else np.nan, x["r"].max() if len(x) else np.nan)
    return out


def main():
    m, H = prepare()
    sim = Sim(m, H)
    lim = m["ts"] < pd.Timestamp(PERIODS["test"][0])          # sealed test: no trade may start there
    rows, books = [], {}
    for d in (-1, 1):
        base, ctx = triggers(m, H, d)
        for cx, mg, ad in itertools.product(CONTEXTS, MANAGE, (False, True)):
            mask = base & ctx[cx] & lim.to_numpy()
            t = book(sim, m, d, mask, mg, base & lim.to_numpy(), ad)
            books[(d, cx, mg, ad)] = t
            s = period_stats(t)
            row = dict(dir="SELL" if d == -1 else "BUY", ctx=cx, manage=mg, adds=int(ad))
            for p, (n, mr, tot, win, hold_h, mx) in s.items():
                row.update({f"{p}_n": n, f"{p}_R": mr, f"{p}_tot": tot, f"{p}_win": win, f"{p}_hold_h": hold_h,
                            f"{p}_max": mx})
            rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv("out/g98_cells.csv", index=False)
    pd.set_option("display.width", 260)
    cols = ["dir", "ctx", "manage", "adds", "train_n", "train_R", "train_win", "train_hold_h", "train_max",
            "validate_n", "validate_R", "validate_win", "validate_hold_h", "validate_max"]
    for dname in ("SELL", "BUY"):
        sub = tab[tab["dir"] == dname].sort_values("train_R", ascending=False)
        print(f"\n{dname}: top 15 cells by train R/trade")
        print(sub[cols].head(15).round(3).to_string(index=False))
        print(f"{dname}: cells positive train {int((sub.train_R > 0).sum())}/{len(sub)}, validate "
              f"{int((sub.validate_R > 0).sum())}, both {int(((sub.train_R > 0) & (sub.validate_R > 0)).sum())}")
    print("\nmean R by management (all contexts, both directions, train | validate):")
    print(tab.groupby(["manage", "adds"])[["train_R", "validate_R"]].mean().round(3).to_string())
    print("\nmean R by context:")
    print(tab.groupby(["dir", "ctx"])[["train_R", "validate_R"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
