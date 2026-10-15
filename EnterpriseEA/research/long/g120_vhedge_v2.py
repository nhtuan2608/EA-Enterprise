"""G120: VHedge version 2 - exits (partial / swing trail / time exit), M30 confirmation, profiles; vs S07.

User (15/10/2026): build items 1 + 2 + 5 for VHedgeTester and compare performance again.

  python g120_vhedge_v2.py

Groups: G116 M5 V returns 05/2024..10/2026. Hedge as G116/G119 (stops at the open +- (stop + 0.1) ATR, add at the
break with the survivor's stop, TP 5R, BE at +1R). Units: U = gap between the two stops (= 2 leg risks).
Exits:
  E0  baseline (TP 5R, BE +1R)
  E1  partial: close 50% of every open leg at +2R, the rest to 5R
  E2  swing trail: from +2R, stops follow the last confirmed M5 swing (2 bars each side) beyond the entry
  E3  time exit: close everything after 24 bars (2 h) from the resolution if +1R was never reached
  E13, E23, E123 combinations
Profiles (filters at the V bar):
  G119   EMA21..200 spread low & (V volume high | return volume high)      (2024 terciles, as G119)
  BIGV   V range high & EMA spread low
  M30C   last closed M30 bar: EMA21/55/100 fanned against the V break, ADX14 M30 < 25, M30 EMA200 slope against
  G119+M30C, BIGV+M30C
Random control: random candles near the EMA200 through the same profile, E0.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g116_v_hedge as g
import g118_v_combos as g118
import g119_v_m5_native as q
from g97_forming_bar import dmi, ema

EXITS = ("E0", "E1", "E2", "E3", "E13", "E23", "E123")
STOPS = (1.0, 1.5)
TS_TIME = 24


def m30_context(m5: pd.DataFrame, F: pd.DataFrame) -> np.ndarray:
    h = pd.read_csv(g118.HERE / "data" / "m30v" / "XAUUSD.csv")
    h["ts"] = pd.to_datetime(h["time"], unit="s")
    h = h[h["ts"] >= "2023-06-01"].reset_index(drop=True)
    c = h["close"].to_numpy()
    e21, e55, e100, e200 = (ema(c, n) for n in (21, 55, 100, 200))
    _, _, adx, atr = dmi(h["high"].to_numpy(), h["low"].to_numpy(), c)
    close_t = (h["ts"] + pd.Timedelta(minutes=30)).to_numpy()
    out = np.zeros(len(F), bool)
    for i, r in enumerate(F.itertuples()):
        vt = m5["ts"].iat[r.v] + pd.Timedelta(minutes=5)          # the M5 V bar closed
        k = int(np.searchsorted(close_t, np.datetime64(vt), side="right")) - 1
        if k < 60:
            continue
        vd = 1 if m5["close"].iat[r.v] > m5["e200"].iat[r.v] else -1
        fan = 1 if e21[k] > e55[k] > e100[k] else (-1 if e21[k] < e55[k] < e100[k] else 0)
        slope = (e200[k] - e200[k - 48]) / atr[k]
        out[i] = (fan == -vd) and adx[k] < 25 and np.sign(slope) == -vd
    return out


class SimV2(q.Sim3):
    def __init__(self, m):
        super().__init__(m)
        hh, ll = self.h, self.l
        n = len(hh)
        self.sw_hi = np.full(n, np.nan)
        self.sw_lo = np.full(n, np.nan)
        a, b = np.nan, np.nan
        for k in range(4, n):
            j = k - 2
            if hh[j] >= hh[j - 2:j + 3].max():
                a = hh[j]
            if ll[j] <= ll[j - 2:j + 3].min():
                b = ll[j]
            self.sw_hi[k], self.sw_lo[k] = a, b

    def manage(self, t, d, legs, surv_entry, surv_sl, mode, k):
        """mode = exit id E0..E123 (k = target R). legs: [entry, sl]; returns pnl in price units (size 1 per leg)."""
        ex = mode
        o, h, l, c, sp = self.o, self.H0, self.L0, self.c, self.sp
        R = d * (surv_entry - surv_sl)
        if R <= 0:
            return None
        tp = surv_entry + d * k * R
        size = [1.0] * len(legs)
        pnl = 0.0
        open_ = [True] * len(legs)
        best = surv_entry
        be = partial = False
        end = min(len(c) - 1, t + g.CAP)
        j = t + 1
        while j <= end:
            for i, L in enumerate(legs):
                if open_[i] and ((d == 1 and l[j] <= L[1]) or (d == -1 and h[j] + sp[j] >= L[1])):
                    pnl += size[i] * d * (L[1] - L[0]); open_[i] = False
            if not any(open_):
                return pnl
            if (d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp):
                for i, L in enumerate(legs):
                    if open_[i]:
                        pnl += size[i] * d * (tp - L[0])
                return pnl
            best = max(best, h[j]) if d == 1 else min(best, l[j])
            rb = d * (best - surv_entry) / R
            if "1" in ex and not partial and rb >= 2:
                lvl = surv_entry + d * 2 * R
                for i, L in enumerate(legs):
                    if open_[i]:
                        pnl += 0.5 * size[i] * d * (lvl - L[0]); size[i] *= 0.5
                partial = True
            if not be and rb >= 1:
                be = True
                for L in legs:
                    if d * (L[0] - L[1]) > 0:
                        L[1] = L[0]
            if "2" in ex and rb >= 2:
                sw = self.sw_lo[j] if d == 1 else self.sw_hi[j]
                if np.isfinite(sw) and d * (sw - surv_entry) > 0:
                    for L in legs:
                        if d * (sw - L[1]) > 0:
                            L[1] = sw
            if "3" in ex and j - t >= TS_TIME and rb < 1:
                px = c[j] + (sp[j] if d == -1 else 0.0)
                for i, L in enumerate(legs):
                    if open_[i]:
                        pnl += size[i] * d * (px - L[0])
                return pnl
            j += 1
        jj = min(j, end)
        px = c[jj] + (sp[jj] if d == -1 else 0.0)
        for i, L in enumerate(legs):
            if open_[i]:
                pnl += size[i] * d * (px - L[0])
        return pnl

    def r2(self, v, j, mult, ex):
        mid = self.o[j + 1]
        self.h[v], self.l[v] = mid + mult * self.atr[j], mid - mult * self.atr[j]
        res = self.hedge(v, j, 0.1, 3, "K", "SAME", ex, 5.0)
        self._reset(v)
        return np.nan if res is None else res[0]


def profiles(BF: pd.DataFrame, m30c: np.ndarray) -> dict:
    g119 = (BF["ema_spread_low"] & (BF["v_vol_high"] | BF["r_vol_high"])).to_numpy()
    bigv = (BF["v_size_high"] & BF["ema_spread_low"]).to_numpy()
    return {"G119": g119, "BIGV": bigv, "M30C": m30c, "G119+M30C": g119 & m30c, "BIGV+M30C": bigv & m30c}


def half(t):
    return t.dt.year.astype(str) + np.where(t.dt.month <= 6, "H1", "H2")


def main():
    m = g118.load("M5")
    gr, pg = g.find_groups(m), g.find_groups(m, pseudo=True)
    F, P = q.raw_features(m, gr), q.raw_features(m, pg)
    ref = F[F.t < "2025-01-01"]
    BF, BP = q.binarize(F, ref), q.binarize(P, ref)
    PF = profiles(BF, m30_context(m, F))
    PP = profiles(BP, m30_context(m, P))
    S = SimV2(m)
    years = (F.t.max() - F.t.min()).days / 365.25
    rows = []
    for mult in STOPS:
        cache = {}
        for ex in EXITS:
            cache[ex] = np.array([S.r2(v, j, mult, ex) for v, j in gr])
        rnd = np.array([S.r2(v, j, mult, "E0") for v, j in pg])
        for prof, mk in PF.items():
            for ex in EXITS:
                R = cache[ex]
                sel = mk & ~np.isnan(R)
                x = R[sel]
                if len(x) < 30:
                    continue
                tt = F.t[sel]
                halves = pd.Series(x).groupby(half(tt).to_numpy()).sum()
                eq = np.cumsum(x)
                pm = PP[prof] & ~np.isnan(rnd)
                rows.append(dict(profile=prof, stop=mult, exit=ex, n=len(x), per_yr=len(x) / years, R=x.mean(),
                                 U_yr=x.sum() / years, win=(x > 0).mean(), p2=(x >= 2).mean(),
                                 ddU=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
                                 halves_pos=int((halves > 0).sum()), n_halves=len(halves),
                                 rnd_R=rnd[pm].mean() if pm.sum() >= 30 else np.nan,
                                 by_half=" ".join(f"{a}:{b:+.0f}" for a, b in halves.items())))
    T = pd.DataFrame(rows)
    T.to_csv("out/g120_vhedge_v2.csv", index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 90)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
