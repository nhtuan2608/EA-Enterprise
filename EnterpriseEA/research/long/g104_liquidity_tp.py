"""G104: take profit at prior liquidity (old lows / equal lows / origin of the last rally) on top of the G103 BOX hold.

User (11/10): a sell swing still needs a target zone: the liquidity left earlier, or the old lows price heads to.

  python g104_liquidity_tp.py

Entries: G100 V2 (M15), G103 protection and BOX hold (close-based H1 level, hard stop 1.5 ATR(H1) beyond).
Targets (sell; buy mirrored with highs), fixed at the entry from swings confirmed before it, the nearest one at
least 3R beyond the entry:
  H4S  confirmed H4 swing low (2 bars each side)
  D1S  confirmed D1 swing low
  EQL  equal lows: two confirmed H4 swing lows of the last 60 days within 0.25 ATR(D1) of each other
  ORG  origin of the last rally: the lowest low of the 30 days before the 20-day high
No target found -> the trade is held as plain BOX.
Modes: FULL close all at the target | HALF close 50% at the target, the rest holds on BOX.
Periods: train 07/2021-2023, validate 2024-06/2025 (entries); test sealed; 12/03/2026 shown apart.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g98_context as g98
import g100_user_rule as u
from g103_structure_hold import Hold

TARGETS = ("NONE", "H4S", "D1S", "EQL", "ORG")
MODES = ("FULL", "HALF")


def swings(m, rule):
    """Confirmed swing highs/lows of a timeframe built from M15: arrays (confirm_time, level)."""
    s = m.set_index("ts")
    b = s.resample(rule).agg({"high": "max", "low": "min"}).dropna()
    hi, lo, t = b["high"].to_numpy(), b["low"].to_numpy(), b.index
    step = pd.Timedelta(rule)
    H, L = [], []
    for k in range(2, len(b) - 2):
        conf = t[k + 2] + step                        # known once bar k+2 has closed
        if hi[k] >= hi[k - 2:k + 3].max():
            H.append((conf, hi[k]))
        if lo[k] <= lo[k - 2:k + 3].min():
            L.append((conf, lo[k]))
    to = lambda x: (np.array([a for a, _ in x], dtype="datetime64[ns]"), np.array([v for _, v in x]))
    return to(H), to(L)


class Liq(Hold):
    def __init__(self, m, H):
        super().__init__(m, H)
        self.ts = m["ts"].to_numpy()
        self.h4 = swings(m, "4h")
        self.d1 = swings(m, "1D")
        day = m["ts"].dt.normalize()
        D = m.groupby(day).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
        pc = D["c"].shift(1)
        self.datr = day.map((np.maximum(D["h"], pc) - np.minimum(D["l"], pc)).rolling(20).mean().shift(1)).to_numpy()
        self.D = D

    def target(self, i, d, entry, risk, kind):
        t = self.ts[i]
        lim = entry + d * 3 * risk                  # at least 3R away
        beyond = (lambda v: v <= lim) if d == -1 else (lambda v: v >= lim)
        if kind in ("H4S", "D1S"):
            (th, vh), (tl, vl) = self.h4 if kind == "H4S" else self.d1
            tt, vv = (tl, vl) if d == -1 else (th, vh)
            ok = (tt <= t) & np.array([beyond(v) for v in vv]) if len(vv) else np.array([], bool)
            if not ok.any():
                return None
            c = vv[ok]
            return c.max() if d == -1 else c.min()  # the nearest one beyond 3R
        if kind == "EQL":
            (th, vh), (tl, vl) = self.h4
            tt, vv = (tl, vl) if d == -1 else (th, vh)
            sel = (tt <= t) & (tt >= t - np.timedelta64(60, "D"))
            v = np.sort(vv[sel])
            tol = 0.25 * self.datr[i] if np.isfinite(self.datr[i]) else np.nan
            levels = [0.5 * (a + b) for a, b in zip(v[:-1], v[1:]) if b - a <= tol]
            levels = [x for x in levels if beyond(x)]
            if not levels:
                return None
            return max(levels) if d == -1 else min(levels)
        if kind == "ORG":
            day = pd.Timestamp(t).normalize()
            D = self.D[self.D.index < day]
            if len(D) < 50:
                return None
            last20 = D.iloc[-20:]
            if d == -1:
                top_day = last20["h"].idxmax()
                prior = D[D.index < top_day].iloc[-30:]
                v = prior["l"].min() if len(prior) else np.nan
            else:
                bot_day = last20["l"].idxmin()
                prior = D[D.index < bot_day].iloc[-30:]
                v = prior["h"].max() if len(prior) else np.nan
            return v if np.isfinite(v) and beyond(v) else None
        return None

    def run_tp(self, i, d, kind, mode):
        e = i + 1
        if e >= len(self.c):
            return None
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        hard0 = (self.ll16[i] - 0.1 * self.atr15[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr15[i])
        risk = d * (entry - hard0)
        if not risk > 0:
            return None
        tgt = None if kind == "NONE" else self.target(i, d, entry, risk, kind)
        level, hard, best, last_box = None, hard0, entry, None
        part = None                      # R of the half closed at the target
        j = e
        exit_px, why = None, "end"
        while j < len(self.c):
            hi, lo = self.h[j], self.l[j]
            if (d == 1 and lo <= hard) or (d == -1 and hi + self.sp[j] >= hard):
                exit_px, why = hard, "hard"
                break
            if tgt is not None and part is None and ((d == 1 and hi >= tgt) or (d == -1 and lo + self.sp[j] <= tgt)):
                if mode == "FULL":
                    exit_px, why = tgt, "target"
                    break
                part = d * (tgt - entry) / risk
            best = max(best, hi) if d == 1 else min(best, lo)
            r_best = d * (best - entry) / risk
            if self.done[j]:
                k = self.hc[j]
                hc, at = self.Hc[k], self.Hatr[k]
                if k >= 1 and self.box_ok[k - 1]:
                    bx = (self.box_hi[k - 1], self.box_lo[k - 1])
                    if d * (hc - (bx[1] if d == -1 else bx[0])) > 0:
                        last_box = bx
                if last_box is not None and r_best >= 1:
                    new = last_box[0] if d == -1 else last_box[1]
                    if level is None or d * (new - level) > 0:
                        level = new
                        cand = level + (1.5 * at if d == -1 else -1.5 * at)
                        if d * (cand - hard) > 0:
                            hard = cand
                if level is not None and d * (hc - (level + (0.25 * at if d == -1 else -0.25 * at))) < 0:
                    exit_px, why = self.c[j] + (self.sp[j] if d == -1 else 0), "level"
                    break
            j += 1
        if exit_px is None:
            j = len(self.c) - 1
            exit_px = self.c[j]
        rest = d * (exit_px - entry) / risk
        r = rest if part is None else 0.5 * part + 0.5 * rest
        return r, j, why, tgt is not None, (d * (tgt - entry) / risk if tgt is not None else np.nan)


def book(Q, m, d, mask, kind, mode):
    rows, free = [], 0
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = Q.run_tp(i, d, kind, mode)
        if res is None:
            continue
        r, jx, why, has, dist = res
        rows.append((m["ts"].iat[i], r, why, has, dist))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "r", "why", "has_tgt", "tgt_R"])


def stats(t, p):
    a, b = g98.PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)]
    if x.empty:
        return {}
    eq = x["r"].cumsum().to_numpy()
    return dict(n=len(x), R=x["r"].mean(), totR=x["r"].sum(), win=(x["r"] > 0).mean(),
                ddR=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()), has_tgt=x["has_tgt"].mean(),
                tgt_R=x["tgt_R"].median(), hit=(x["why"] == "target").mean())


def main():
    m, H = g98.prepare()
    Q = Liq(m, H)
    ts = m["ts"]
    lim = (ts < pd.Timestamp(g98.PERIODS["test"][0])).to_numpy()
    mk_s, _ = u.masks(m, -1)
    i = np.flatnonzero(mk_s["V2"] & ((ts >= "2026-03-12 14:00") & (ts < "2026-03-13")).to_numpy())[0]
    print("12/03/2026 sell (illustration, sealed test period), entry", round(m["open"].iat[i + 1], 1))
    for kind, mode in itertools.product(TARGETS, MODES):
        if kind == "NONE" and mode == "HALF":
            continue
        r, jx, why, has, dist = Q.run_tp(i, -1, kind, mode)
        e = m["open"].iat[i + 1]
        print(f"  {kind:4s} {mode}: target {'-' if not has else round(e - dist * (Q.hh16[i] + 0.1 * Q.atr15[i] - e), 0)}"
              f" ({dist:.1f}R)  result {r:+.1f}R, exit {ts.iat[jx]:%d/%m} by {why}")
    rows = []
    for d in (-1, 1):
        mk, _ = u.masks(m, d)
        for kind, mode in itertools.product(TARGETS, MODES):
            if kind == "NONE" and mode == "HALF":
                continue
            t = book(Q, m, d, mk["V2"] & lim, kind, mode)
            row = dict(dir="SELL" if d == -1 else "BUY", target=kind, mode=mode)
            for p in g98.OPEN:
                for k, v in stats(t, p).items():
                    row[f"{p[:3]}_{k}"] = v
            rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv("out/g104_liquidity_tp.csv", index=False)
    pd.set_option("display.width", 250)
    print()
    print(tab.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
