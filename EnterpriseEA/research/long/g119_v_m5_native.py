"""G119: the G116 V setup on M5 with M5-native conditions only (candle shape, structure, volume, compression).

User (14/10/2026): G118 combos lean on higher timeframes and give too little R per year; try other conditions.

  python g119_v_m5_native.py

Groups: G116 (M5 V body cross of the EMA200, close back inside the V range within 6 bars), 05/2024..10/2026.
Outcome configs (hedge, add at the break, BE at +1R): stop +-1 / +-1.5 / +-2 ATR(M5) x exit X3 / X2 3R / X2 5R.
Conditions (M5 only, at the V bar or the return bar; thresholds = terciles of the 2024 groups):
  V candle: body share, rejection wick on the break side, close position, size vs ATR, tick volume vs 20 bars
  return: bars to return, depth outside the V range before returning, return-candle body share and volume
  context: 12-bar range / ATR before V (compression), EMA21..200 spread / ATR (EMAs bundled), V breaks the 24-bar
  swing high/low, bars since the previous EMA200 body cross, ATR(M5) vs its 100-bar mean, distance of the V close
  to a $5 round number, minute of the hour (round half-hour).
Consistency: 5 half-years (2024H1 from 05/14 .. 2026H2 to 10/09). Pass: >= 80 groups, >= 4 of 5 half-years with total
R > 0, total R >= 10 per year, beats random candles near EMA200 through the same combo. Chance level: same search on
outcomes shuffled within each half-year (20 runs).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g116_v_hedge as g
import g118_v_combos as g118
from g117_v_filters import Sim2

CFGS = [(s, x, k) for s in (1.0, 1.5, 2.0) for x, k in (("X3", 2.0), ("X2", 3.0), ("X2", 5.0))]


class Sim3(Sim2):
    def r(self, v, j, mult, X, k):
        mid = self.o[j + 1]
        self.h[v], self.l[v] = mid + mult * self.atr[j], mid - mult * self.atr[j]
        res = self.hedge(v, j, 0.1, 3, "K", "SAME", X, k)
        self._reset(v)
        return np.nan if res is None else res[0]


def raw_features(m, groups):
    o, c, h, l, e200 = (m[k].to_numpy() for k in ("open", "close", "high", "low", "e200"))
    e21, e55, e100, a = (m[k].to_numpy() for k in ("e21", "e55", "e100", "atr"))
    vol = m["tickvol"].to_numpy().astype(float)
    vavg = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    aavg = pd.Series(a).rolling(100).mean().to_numpy()
    body = ((o < e200) & (c > e200)) | ((o > e200) & (c < e200))
    last_cross = np.full(len(c), -10**9)
    lc = -10**9
    for i in range(len(c)):
        last_cross[i] = lc
        if body[i]:
            lc = i
    rows = []
    for v, j in groups:
        rng_v = max(h[v] - l[v], 1e-9)
        d = 1 if c[v] > e200[v] else -1
        wick_break = (h[v] - max(o[v], c[v])) if d == 1 else (min(o[v], c[v]) - l[v])   # wick beyond the break side
        out_depth = 0.0
        for q in range(v + 1, j):
            out_depth = max(out_depth, h[q] - h[v], l[v] - l[q])
        rng_j = max(h[j] - l[j], 1e-9)
        sw_hi, sw_lo = h[v - 24:v].max(), l[v - 24:v].min()
        emas = np.array([e21[v], e55[v], e100[v], e200[v]])
        rows.append(dict(
            v=v, j=j, t=m["ts"].iat[j],
            v_body=abs(c[v] - o[v]) / rng_v, v_wick=wick_break / rng_v,
            v_close_pos=((c[v] - l[v]) / rng_v) if d == 1 else ((h[v] - c[v]) / rng_v),
            v_size=rng_v / a[v], v_vol=vol[v] / vavg[v] if vavg[v] > 0 else np.nan,
            ret_bars=j - v, ret_depth=out_depth / a[v],
            r_body=abs(c[j] - o[j]) / rng_j, r_vol=vol[j] / vavg[j] if vavg[j] > 0 else np.nan,
            box12=(h[v - 12:v].max() - l[v - 12:v].min()) / a[v], ema_spread=(emas.max() - emas.min()) / a[v],
            breaks_swing=float((d == 1 and h[v] > sw_hi) or (d == -1 and l[v] < sw_lo)),
            since_cross=v - last_cross[v], atr_ratio=a[v] / aavg[v] if aavg[v] > 0 else np.nan,
            round5=min(c[v] % 5.0, 5.0 - c[v] % 5.0) / a[v], minute=int(m["ts"].iat[v].minute)))
    return pd.DataFrame(rows)


NUM = ["v_body", "v_wick", "v_close_pos", "v_size", "v_vol", "ret_depth", "r_body", "r_vol", "box12", "ema_spread",
       "since_cross", "atr_ratio", "round5"]


def binarize(R, ref):
    """Low / high tercile flags from the reference (2024) groups, plus a few fixed flags."""
    B = pd.DataFrame(index=R.index)
    for f in NUM:
        lo, hi = np.nanpercentile(ref[f], [33.3, 66.7])
        B[f"{f}_low"] = R[f] <= lo
        B[f"{f}_high"] = R[f] >= hi
    B["ret_fast"] = R.ret_bars <= 2
    B["ret_slow"] = R.ret_bars >= 4
    B["breaks_swing"] = R.breaks_swing == 1
    B["round_hour"] = R.minute.isin([55, 0, 25, 30])
    return B


def half(t):
    return t.dt.year.astype(str) + np.where(t.dt.month <= 6, "H1", "H2")


def main():
    m = g118.load("M5")
    gr, pg = g.find_groups(m), g.find_groups(m, pseudo=True)
    F, P = raw_features(m, gr), raw_features(m, pg)
    ref = F[F.t < "2025-01-01"]
    BF, BP = binarize(F, ref), binarize(P, ref)
    conds = list(BF.columns)
    hf, hp = half(F.t).to_numpy(), half(P.t).to_numpy()
    years = (F.t.max() - F.t.min()).days / 365.25
    S = Sim3(m)
    print(f"M5 groups {len(gr)}, random candles {len(pg)}, conditions {len(conds)}", flush=True)
    rows, chance = [], {}
    rng = np.random.default_rng(119)
    combo_list = [c for k in (1, 2, 3) for c in itertools.combinations(conds, k)
                  if len({x.rsplit('_', 1)[0] for x in c}) == len(c)]          # no low+high of the same feature
    for mult, X, k in CFGS:
        R = np.array([S.r(v, j, mult, X, k) for v, j in gr])
        PR = np.array([S.r(v, j, mult, X, k) for v, j in pg])
        cfg = f"stop {mult} ATR, {X}{'' if X == 'X3' else ' ' + str(k) + 'R'}"
        def scan(Rv, record):
            cnt = 0
            for c in combo_list:
                mk = np.logical_and.reduce([BF[x].to_numpy() for x in c]) & ~np.isnan(Rv)
                n = mk.sum()
                if n < 80:
                    continue
                tot = Rv[mk].sum()
                halves = pd.Series(Rv[mk]).groupby(hf[mk]).sum()
                hpos = int((halves > 0).sum())
                ok = hpos >= 4 and tot / years >= 10
                if not record:
                    cnt += ok
                    continue
                pm = np.logical_and.reduce([BP[x].to_numpy() for x in c]) & ~np.isnan(PR)
                rnd = PR[pm].mean() if pm.sum() >= 40 else np.nan
                rows.append(dict(cfg=cfg, combo=" & ".join(c), n=n, R=Rv[mk].mean(), U_per_year=tot / years,
                                 win=(Rv[mk] > 0).mean(), p2=(Rv[mk] >= 2).mean(), halves_pos=hpos, rnd_R=rnd, ok=ok,
                                 by_half=" ".join(f"{a}:{b:+.0f}" for a, b in halves.items())))
            return cnt
        scan(R, True)
        nulls = []
        for _ in range(20):
            Rs = R.copy()
            for hh in np.unique(hf):
                idx = np.flatnonzero(hf == hh)
                Rs[idx] = rng.permutation(Rs[idx])
            nulls.append(scan(Rs, False))
        chance[cfg] = (np.median(nulls), np.percentile(nulls, 90))
        base = np.nanmean(R)
        print(f"{cfg}: all groups R {base:+.3f}, U/yr {np.nansum(R) / years:+.0f}", flush=True)
    T = pd.DataFrame(rows)
    T["beats_rnd"] = T.R > T.rnd_R
    T.to_csv("out/g119_m5_native.csv", index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 70)
    print("\npassing combos (>=4/5 half-years positive, >=10 U/yr) vs chance (median / 90th pct):")
    for cfg in T.cfg.unique():
        real = int(T[(T.cfg == cfg) & T.ok].shape[0])
        real_b = int(T[(T.cfg == cfg) & T.ok & T.beats_rnd].shape[0])
        print(f"  {cfg}: {real} (beat random {real_b}) | chance {chance[cfg][0]:.0f} / {chance[cfg][1]:.0f}")
    top = T[T.ok & T.beats_rnd].sort_values("U_per_year", ascending=False)
    print("\ntop passers by U per year:")
    print(top[["cfg", "combo", "n", "R", "U_per_year", "win", "p2", "halves_pos", "rnd_R", "by_half"]].round(3).head(30).to_string(index=False))


if __name__ == "__main__":
    main()
