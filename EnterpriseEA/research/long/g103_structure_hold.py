"""G103: hold by price structure instead of EMAs; sweep-resistant positive stops; confirmed wick adds.

User (11/10): do not exit on EMA55 H1/H4; find a better way to hold sells (and buys); adds only after a
confirmation + a rejection wick; once holding, move the stop into profit but avoid being swept.

  python g103_structure_hold.py

Entries: the user's rule (G100 V2, M15). Initial protection: the 16-bar M15 extreme + 0.1 ATR (hard, intrabar).
Hold methods (sell; buy mirrored). From the activation point the stop is CLOSE-based: an H1 close beyond
level + 0.25 ATR(H1) exits at that close; a hard stop sits at level + 1.5 ATR(H1) at the broker (sweeps).
  REF   G100 H1E reference: H1 close beyond the H1 EMA55 after +1R (EMA based, for comparison)
  SW1   level = last confirmed H1 swing high below the entry (trails each new lower high); active from +1R
  SW2   level = the second-last confirmed lower high (more room)
  BE2   at +2R the level becomes entry - 0.5R (locks +0.5R), then SW1
  BOX   level = the high of the last H1 pause box (8 bars, width <= 2.5 ATR(H1)) that price closed below,
        active from +1R
Adds (+A): the base level is already beyond the entry (risk-free base); an H1 bar with an upper wick >= 50% of
its range closing in its lower half (rejection), its high not above the level; the next H1 bar closes below that
bar's low -> add at the next open, stop = wick high + 0.25 ATR(H1) (hard), exits with the base; max 2 adds,
at least 4 H1 bars apart.
Sweep share: exits by stop/level after which price ran >= 2R further in the trade direction within 24 H1 bars.
Periods: train 07/2021-2023, validate 2024-06/2025 (entries); test sealed. The 12/03/2026 sell is shown apart.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g98_context as g98
import g100_user_rule as u

METHODS = ("REF", "SW1", "SW2", "BE2", "BOX")


class Hold:
    def __init__(self, m, H):
        self.m = m
        self.o, self.h, self.l, self.c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy() * 0.01
        self.atr15 = m["atr"].to_numpy()
        self.hh16 = pd.Series(self.h).rolling(16).max().to_numpy()
        self.ll16 = pd.Series(self.l).rolling(16).min().to_numpy()
        self.hc = m["hi_cur"].to_numpy()
        self.done = m["h1_done"].to_numpy()
        self.Ho, self.Hh, self.Hl, self.Hc = (H[k].to_numpy() for k in ("o", "h", "l", "c"))
        self.Hatr, self.He55 = H["atr"].to_numpy(), H["e55"].to_numpy()
        n = len(H)
        # confirmed swings (2 bars each side), known at the close of bar k: lists of the last two
        self.sw_hi1 = np.full(n, np.nan); self.sw_hi2 = np.full(n, np.nan)
        self.sw_lo1 = np.full(n, np.nan); self.sw_lo2 = np.full(n, np.nan)
        a1 = a2 = b1 = b2 = np.nan
        for k in range(4, n):
            j = k - 2
            if self.Hh[j] >= self.Hh[j - 2:j + 3].max():
                a2, a1 = a1, self.Hh[j]
            if self.Hl[j] <= self.Hl[j - 2:j + 3].min():
                b2, b1 = b1, self.Hl[j]
            self.sw_hi1[k], self.sw_hi2[k], self.sw_lo1[k], self.sw_lo2[k] = a1, a2, b1, b2
        # pause boxes: last 8 H1 bars with width <= 2.5 ATR
        bh = pd.Series(self.Hh).rolling(8).max().to_numpy()
        bl = pd.Series(self.Hl).rolling(8).min().to_numpy()
        self.box_ok = (bh - bl) <= 2.5 * self.Hatr
        self.box_hi, self.box_lo = bh, bl

    def run(self, i, d, method, adds):
        e = i + 1
        if e >= len(self.c):
            return None
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        hard0 = (self.ll16[i] - 0.1 * self.atr15[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr15[i])
        risk = d * (entry - hard0)
        if not risk > 0:
            return None
        level = None                  # close-based trailing level (None = not active)
        hard = hard0
        best = entry
        legs = [[entry, None, risk]]  # entry, exit px, risk (for R units)
        add_stops = []
        last_add_h = -10
        pend = None                   # (h1 index of the wick bar, its extreme)
        last_box = None
        j = e
        why = "end"
        exit_px = None
        while j < len(self.c):
            hi, lo = self.h[j], self.l[j]
            # hard stops (intrabar)
            for k, st in enumerate(add_stops):
                L = legs[k + 1]
                if L[1] is None and ((d == 1 and lo <= st) or (d == -1 and hi + self.sp[j] >= st)):
                    L[1] = st
            if (d == 1 and lo <= hard) or (d == -1 and hi + self.sp[j] >= hard):
                exit_px, why = hard, "hard"
                break
            best = max(best, hi) if d == 1 else min(best, lo)
            r_best = d * (best - entry) / risk
            if self.done[j]:
                k = self.hc[j]
                hc, at = self.Hc[k], self.Hatr[k]
                if method == "REF":
                    if r_best >= 1 and d * (hc - self.He55[k]) < 0:
                        exit_px, why = self.c[j] + (self.sp[j] if d == -1 else 0), "ema"
                        break
                else:
                    new = None
                    if method in ("SW1", "SW2", "BE2") and (r_best >= 1 or method == "BE2" and r_best >= 2):
                        sw = (self.sw_hi1[k] if method != "SW2" else self.sw_hi2[k]) if d == -1 else \
                             (self.sw_lo1[k] if method != "SW2" else self.sw_lo2[k])
                        if np.isfinite(sw) and d * (sw - entry) > 0 and (r_best >= 1 and method != "BE2" or r_best >= 2):
                            new = sw
                        if method == "BE2" and r_best >= 2:
                            lock = entry + d * 0.5 * risk
                            new = lock if new is None else (min(new, lock) if d == -1 else max(new, lock))
                    if method == "BOX":
                        if self.box_ok[k - 1] if k >= 1 else False:
                            bx = (self.box_hi[k - 1], self.box_lo[k - 1])
                            if d * (hc - (bx[1] if d == -1 else bx[0])) > 0:      # closed out of the box in the trade direction
                                last_box = bx
                        if last_box is not None and r_best >= 1:
                            new = last_box[0] if d == -1 else last_box[1]
                    if new is not None:
                        if level is None or d * (new - level) > 0:               # only tighten
                            level = new
                            cand = level + (1.5 * at if d == -1 else -1.5 * at)
                            if d * (cand - hard) > 0:                            # the hard stop only tightens
                                hard = cand
                    if level is not None and d * (hc - (level + (0.25 * at if d == -1 else -0.25 * at))) < 0:
                        exit_px, why = self.c[j] + (self.sp[j] if d == -1 else 0), "level"
                        break
                # confirmed wick adds
                if adds and level is not None and d * (level - entry) > 0 and len(legs) < 3 and k - last_add_h >= 4:
                    if pend is not None and pend[0] == k - 1:
                        if d * (hc - pend[1]) > 0:
                            ae = j + 1
                            if ae < len(self.c):
                                a_entry = self.o[ae] + (self.sp[ae] if d == 1 else 0)
                                a_stop = pend[2]
                                a_risk = d * (a_entry - a_stop)
                                if a_risk > 0:
                                    legs.append([a_entry, None, a_risk])
                                    add_stops.append(a_stop)
                                    last_add_h = k
                        pend = None
                    rng = self.Hh[k] - self.Hl[k]
                    if rng > 0:
                        if d == -1:
                            wick = self.Hh[k] - max(self.Ho[k], hc)
                            ok = wick >= 0.5 * rng and hc <= self.Hl[k] + 0.5 * rng and self.Hh[k] <= level
                            if ok:
                                pend = (k, self.Hl[k], self.Hh[k] + 0.25 * at)
                        else:
                            wick = min(self.Ho[k], hc) - self.Hl[k]
                            ok = wick >= 0.5 * rng and hc >= self.Hh[k] - 0.5 * rng and self.Hl[k] >= level
                            if ok:
                                pend = (k, self.Hh[k], self.Hl[k] - 0.25 * at)
            j += 1
        if exit_px is None:
            j = len(self.c) - 1
            exit_px = self.c[j]
        total = 0.0
        for L in legs:
            px = L[1] if L[1] is not None else exit_px
            total += d * (px - L[0]) / L[2]
        base_r = d * (exit_px - entry) / risk
        # swept: after a stop/level exit, price ran >= 2R further in the trade direction within 24 H1 bars
        swept = False
        if why in ("hard", "level"):
            end = min(len(self.c), j + 96)
            fut = self.l[j:end].min() if d == -1 else self.h[j:end].max()
            swept = d * (fut - exit_px) >= 2 * risk
        return total, base_r, j, len(legs), why, swept


def book(Hd, m, d, mask, method, adds):
    rows, free = [], 0
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = Hd.run(i, d, method, adds)
        if res is None:
            continue
        tot, br, jx, n, why, sw = res
        rows.append((m["ts"].iat[i], tot, br, n, why, sw, (jx - i) / 96))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "r", "base_r", "legs", "why", "swept", "days"])


def stats(t, p):
    a, b = g98.PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)]
    if x.empty:
        return {}
    eq = x["r"].cumsum().to_numpy()
    stopped = x[x["why"].isin(["hard", "level"])]
    return dict(n=len(x), R=x["r"].mean(), totR=x["r"].sum(), win=(x["r"] > 0).mean(), big10=int((x["r"] >= 10).sum()),
                ddR=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
                swept=stopped["swept"].mean() if len(stopped) else np.nan, adds=(x["legs"] - 1).sum(), days=x["days"].median())


def main():
    m, H = g98.prepare()
    Hd = Hold(m, H)
    ts = m["ts"]
    lim = (ts < pd.Timestamp(g98.PERIODS["test"][0])).to_numpy()
    mk_s, _ = u.masks(m, -1)
    i = np.flatnonzero(mk_s["V2"] & ((ts >= "2026-03-12 14:00") & (ts < "2026-03-13")).to_numpy())[0]
    print("12/03/2026 sell (illustration, sealed test period):")
    for meth, ad in itertools.product(METHODS, (False, True)):
        tot, br, jx, n, why, sw = Hd.run(i, -1, meth, ad)
        print(f"  {meth}{'+A' if ad else '  '}: {tot:+.1f}R (base {br:+.1f}R, legs {n}), exit {ts.iat[jx]:%d/%m %H:%M} px "
              f"{m['close'].iat[jx]:.0f} by {why}")
    rows = []
    for d in (-1, 1):
        mk, _ = u.masks(m, d)
        for meth, ad in itertools.product(METHODS, (False, True)):
            t = book(Hd, m, d, mk["V2"] & lim, meth, ad)
            row = dict(dir="SELL" if d == -1 else "BUY", method=meth + ("+A" if ad else ""))
            for p in g98.OPEN:
                for k, v in stats(t, p).items():
                    row[f"{p[:3]}_{k}"] = v
            rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv("out/g103_structure_hold.csv", index=False)
    pd.set_option("display.width", 250)
    print()
    print(tab.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
