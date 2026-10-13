"""G110 step 1: break events with tick-volume vs price features ("fake push"), hold / fail labels and the follow
(S2) and fade (F) trades (docs/superpowers/plans/2026-10-13-g110-break-quality-volume.md).

  G108_SYMBOL=XAUUSD python g110_breaks.py       # raw MT5 M5 with tick volume -> data/g110_events_<SYMBOL>.pkl

Levels known before the break: Z = real G109 zones (day map + intraday), G = the latest confirmed M5 swing highs /
lows of the day (fractal 2/2), F = G109 fake zones (control). Half-width w as G109 (from the day table).
Break: the first 2 consecutive M5 closes beyond the far edge; decision at the second close (bar j). Labels:
  hold     no close back inside within the next 6 bars
  follow   limit at the far edge for 12 bars, stop on the other side of the level +/- spread, target 2R
  fade     a close back inside within 6 bars -> enter against the break at the next open, stop beyond the break
           extreme +/- spread, target 2R
Both trades: exits a / b / c (g109_setups.simulate), at most 4 h, stop >= 8 spreads, ATR M5 >= 3 spreads, no entry
23:00-01:00. Random control: same day, direction, stop distance and RR at random bars (5 draws).
Volume features use bars <= j; relative volume = tick volume / median of the same minute-of-day on the 20 previous
days (earlier bars only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g109_setups as gs
import g109_zones as gz

OUT_E = g8.DATA / f"g110_events_{gz.SYMBOL}{gs.SUF}.pkl"
HOLD_BARS, LIMIT_BARS, RR, N_RANDOM = 6, 12, 2.0, 5


# --------------------------------------------------------------------------------------------- pure helpers
def rel_volume(t: np.ndarray, tv: np.ndarray, days: int = 20) -> np.ndarray:
    """Tick volume / median of the same minute-of-day over the previous `days` occurrences (earlier bars only)."""
    s = pd.Series(tv, index=np.arange(len(tv)))
    med = s.groupby(t % 86400).transform(lambda x: x.shift(1).rolling(days, min_periods=10).median())
    return (s / med).to_numpy()


def clv(o, h, l, c):
    """Close location in the bar range: +1 at the high, -1 at the low (0 for a flat bar)."""
    rng = h - l
    return np.where(rng > 0, ((c - l) - (h - c)) / np.where(rng > 0, rng, 1.0), 0.0)


def break_event(side: int, far: float, c: np.ndarray):
    """Offset of the second of the first 2 consecutive closes beyond `far`, or None."""
    b = (c > far) if side == 1 else (c < far)
    for j in range(1, len(c)):
        if b[j] and b[j - 1]:
            return j
    return None


def hold_and_reclaim(side: int, far: float, c_after: np.ndarray):
    """(hold, offset of the first close back inside within HOLD_BARS or None)."""
    for k in range(min(HOLD_BARS, len(c_after))):
        if side * (c_after[k] - far) <= 0:
            return False, k
    return True, None


# --------------------------------------------------------------------------------------------- price action
def _slope(y: np.ndarray) -> float:
    return float(np.polyfit(np.arange(len(y)), y, 1)[0])


def flag_feats(c: np.ndarray, h: np.ndarray, l: np.ndarray, j: int, s: int, a30: float):
    """(pole, consolidation range, consolidation slope, flag): impulse j-36..j-12, consolidation j-13..j-2."""
    pole = s * (c[j - 12] - c[j - 36]) / a30
    seg = slice(j - 13, j - 1)
    rng = (h[seg].max() - l[seg].min()) / a30
    cons = s * _slope(c[seg]) / a30
    return pole, rng, cons, int(pole >= 1.5 and rng <= 1.0 and cons <= 0)


def wedge_feats(h: np.ndarray, l: np.ndarray, j: int, s: int, a30: float):
    """(slope of highs, slope of lows, convergence, wedge type, wedge_with) over bars j-25..j-2.
    Type +1 rising (both up, converging), -1 falling (both down, converging); wedge_with = +1 for the classic break
    (rising wedge broken down, falling wedge broken up), -1 for the other side, 0 without a wedge."""
    seg = slice(j - 25, j - 1)
    sh, sl = _slope(h[seg]) / a30, _slope(l[seg]) / a30
    conv = sl - sh
    conv_ok = conv > 0.25 * max(abs(sh), abs(sl))                # real convergence, not a parallel channel
    wt = 1 if (sh > 0 and sl > 0 and conv_ok) else (-1 if (sh < 0 and sl < 0 and conv_ok) else 0)
    return s * sh, s * sl, conv, wt, -s * wt


def nr7(h: np.ndarray, l: np.ndarray, j: int) -> int:
    r = h[j - 8:j - 1] - l[j - 8:j - 1]                       # bars j-8 .. j-2; the last one is the bar before the break
    return int(r[-1] <= r.min())


def m5_fvgs(h: np.ndarray, l: np.ndarray):
    """M5 fair-value gaps closed at bar k: arrays (k, low, high, direction)."""
    k = np.arange(2, len(h))
    bull = l[k] > h[k - 2]
    bear = h[k] < l[k - 2]
    kb, kr = k[bull], k[bear]
    K = np.r_[kb, kr]; LO = np.r_[h[kb - 2], h[kr]]; HI = np.r_[l[kb], l[kr - 2]]; DIR = np.r_[np.ones(len(kb)), -np.ones(len(kr))]
    o = np.argsort(K, kind="stable")
    return K[o], LO[o], HI[o], DIR[o]


def void_ahead(j: int, s: int, cj: float, fv, hmax, lmin, a30: float, lookback: int = 288):
    """Nearest unfilled M5 gap ahead of the break (formed in the last `lookback` bars): (distance, size) in ATR M30."""
    K, LO, HI, _ = fv
    a, b = np.searchsorted(K, j - lookback), np.searchsorted(K, j, side="right")
    best = None
    for q in range(a, b):
        k, lo, hi = int(K[q]), LO[q], HI[q]
        if s == 1 and lo > cj and (k + 1 > j or hmax.q(k + 1, j) < lo):
            dist = (lo - cj) / a30
        elif s == -1 and hi < cj and (k + 1 > j or lmin.q(k + 1, j) > hi):
            dist = (cj - hi) / a30
        else:
            continue
        if best is None or dist < best[0]:
            best = (dist, (hi - lo) / a30)
    return best if best is not None else (9.0, 0.0)


# --------------------------------------------------------------------------------------------- build
def build(df: pd.DataFrame, Z: pd.DataFrame, D: pd.DataFrame, hist: pd.DataFrame | None = None, seed: int = 110) -> pd.DataFrame:
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float)
    n = len(t)
    hour = (t % 86400) // 3600
    atr5 = g8.wilder_atr(h, l, c)
    rv = rel_volume(t, tv)
    cl = clv(o, h, l, c)
    M30 = gz.bars(t, o, h, l, c, np.zeros(n), 1800)
    atr30 = g8.wilder_atr(M30["h"].to_numpy(), M30["l"].to_numpy(), M30["c"].to_numpy())
    m30_end = (M30.index.to_numpy(np.int64) + 1) * 1800
    H1 = gz.bars(t, o, h, l, c, np.zeros(n), 3600)
    P1, M1, A1 = gf.dmi(H1["h"].to_numpy(), H1["l"].to_numpy(), H1["c"].to_numpy())
    h1_end = (H1.index.to_numpy(np.int64) + 1) * 3600
    b4, c4 = gf.htf_closes(df, hist, 14400)
    e4 = g8.ema(c4, 200)
    sh, sl = g8.fractals(h, l)
    sh_last, sh_prev = g8.last_two_confirmed(sh, h, n)
    sl_last, sl_prev = g8.last_two_confirmed(sl, l, n)
    hmax, lmin = g8.RangeExt(h, np.maximum), g8.RangeExt(l, np.minimum)
    fv = m5_fvgs(h, l)
    h1h, h1l, h1last = H1["h"].to_numpy(), H1["l"].to_numpy(), H1["last"].to_numpy()
    s1h, s1l = g8.fractals(h1h, h1l)
    sw1_hi = np.full(n, np.nan); sw1_lo = np.full(n, np.nan)        # latest confirmed H1 swing as of each M5 bar
    for idx, arr, ext in ((s1h, sw1_hi, h1h), (s1l, sw1_lo, h1l)):
        for q in idx:
            if q + 2 < len(h1last):
                arr[h1last[q + 2]:] = ext[q]
    real_z = {}
    for z in Z.itertuples():
        if not z.fake:
            real_z.setdefault(int(z.day), []).append((z.center, z.w, int(z.from_i)))
    day = t // 86400
    first_of = pd.Series(np.arange(n)).groupby(day).min().to_dict()
    last_of = pd.Series(np.arange(n)).groupby(day).max().to_dict()
    Dd = D.set_index("day")
    rng = np.random.default_rng(seed)
    rows = []

    def trade(d, entry, stop, e):
        risk = d * (entry - stop)
        if risk <= 0 or risk < gs.MIN_STOP_SPREADS * sp[e] or atr5[e - 1] < gs.MIN_ATR5_SPREADS * sp[e] or hour[e] >= 23 or hour[e] < 1:
            return None
        f = slice(e, min(n, e + gs.MAX_BARS))
        r = gs.simulate(d, entry, stop, entry + d * RR * risk, h[f], l[f], c[f], sp[f])
        return r, risk

    def rand_r(d, risk, a, b):
        out = []
        for _ in range(N_RANDOM):
            q = int(rng.integers(a, b + 1))
            if hour[q] >= 23 or hour[q] < 1:
                continue
            en = o[q] + (sp[q] if d == 1 else 0.0)
            f = slice(q, min(n, q + gs.MAX_BARS))
            out.append(gs.simulate(d, en, en - d * risk, en + d * RR * risk, h[f], l[f], c[f], sp[f])["a"])
        return float(np.mean(out)) if out else np.nan

    # levels per day: (type, centre, w, side, from_i, kinds, n)
    levels = {}
    for z in Z.itertuples():
        if z.side == 0:
            continue
        levels.setdefault(int(z.day), []).append(("F" if z.fake else "Z", z.center, z.w, int(z.side), int(z.from_i), z.kinds, int(z.n)))
    for idx, ext, side in ((sh, h, 1), (sl, l, -1)):
        for j in idx:
            dd = int(day[j])
            if dd not in Dd.index or j + 3 > last_of[dd] or day[j + 2] != dd:
                continue
            levels.setdefault(dd, []).append(("G", float(ext[j]), float(Dd.loc[dd, "w"]), side, int(j + 3), "M5SWING", 1))
    for dd, lv in levels.items():
        if dd not in Dd.index:
            continue
        a_day, e_day = first_of[dd], last_of[dd]
        regime = int(Dd.loc[dd, "regime"])
        for typ, cen, w, side, s0, kinds, nconf in lv:
            if s0 >= e_day:
                continue
            far = cen + side * w
            off = break_event(side, far, c[s0:e_day + 1])
            if off is None:
                continue
            j = s0 + off                                           # decision bar (second close beyond)
            if j < 40 or j >= e_day or hour[j] >= 23 or hour[j] < 1:
                continue
            k30 = np.searchsorted(m30_end, t[j] + 300, side="right") - 1
            a30 = atr30[max(k30, 0)]
            k1 = np.searchsorted(h1_end, t[j] + 300, side="right") - 1
            k4 = np.searchsorted((b4 + 1) * 14400, t[j] + 300, side="right") - 1
            s = side                                               # break direction
            br = slice(j - 1, j + 1)
            ap = slice(j - 7, j - 1)
            tvb = float(np.nanmean(rv[br]))
            body = s * (c[j] - o[j - 1]) / max(atr5[j], 1e-12)
            d6 = slice(j - 5, j + 1); d12 = slice(j - 11, j + 1)
            den6, den12 = np.nansum(rv[d6]), np.nansum(rv[d12])
            delta6 = s * np.nansum(cl[d6] * rv[d6]) / den6 if den6 > 0 else np.nan
            delta12 = s * np.nansum(cl[d12] * rv[d12]) / den12 if den12 > 0 else np.nan
            price12 = s * (c[j] - c[j - 12]) / a30
            y6 = rv[ap]
            slope = float(np.polyfit(np.arange(6), y6, 1)[0]) if np.isfinite(y6).all() else np.nan
            wick = np.mean([((h[q] - max(o[q], c[q])) if s == 1 else (min(o[q], c[q]) - l[q])) / max(h[q] - l[q], 1e-12) for q in (j - 1, j)])
            rec = dict(day=dd, time=int(t[j]), j=j, s0=s0, type=typ, kinds=kinds, n=nconf, s=s, center=cen, w=w, far=far,
                       tv_break=tvb, tv_appr=float(np.nanmean(rv[ap])), tv_slope=slope, body=body,
                       effort=body / tvb if tvb and np.isfinite(tvb) and tvb > 0 else np.nan,
                       delta6=delta6, delta12=delta12, price12=price12,
                       diverg=float(np.sign(price12) != np.sign(delta12)) if np.isfinite(delta12) else np.nan,
                       wick=wick, beyond=s * (c[j] - far) / w,
                       compress=(h[j - 13:j - 1].max() - l[j - 13:j - 1].min()) / a30,
                       adx_h1=float(A1[max(k1, 0)]), di_h1=s * float(P1[max(k1, 0)] - M1[max(k1, 0)]),
                       d1_with=s * regime, h4_side=s * float(np.sign(c[j] - e4[max(k4, 0)])) if k4 >= 0 else 0.0,
                       hour=int(hour[j]), sess=g8.session_of(int(hour[j])),
                       open_dist=s * (c[j] - o[a_day]) / float(Dd.loc[dd, "atr_d1"]))
            # price action (bars <= j)
            pole, cons_rng, cons_slope, flag = flag_feats(c, h, l, j, s, a30)
            wsh, wsl, wconv, wtype, wwith = wedge_feats(h, l, j, s, a30)
            vd, vs = void_ahead(j, s, c[j], fv, hmax, lmin, a30)
            ahead = [((cz - wz) - c[j]) if s == 1 else (c[j] - (cz + wz)) for cz, wz, fz in real_z.get(dd, []) if fz <= j]
            ahead = [x for x in ahead if x > 0]
            sw = sw1_hi[j] if s == 1 else sw1_lo[j]
            up = sh_last[j] > sh_prev[j] and sl_last[j] > sl_prev[j]
            dn = sh_last[j] < sh_prev[j] and sl_last[j] < sl_prev[j]
            rng_pre = (h[j - 13:j - 1] - l[j - 13:j - 1]).mean()
            rec.update(nr7=nr7(h, l, j), expand=float((h[j - 1:j + 1] - l[j - 1:j + 1]).mean() / max(rng_pre, 1e-12)),
                       void_ahead=vd, void_size=vs, zone_ahead=(min(ahead) / a30 if ahead else 9.0),
                       bos_h1=int(np.isfinite(sw) and s * (c[j] - sw) > 0), bos_dist=(s * (c[j] - sw) / a30 if np.isfinite(sw) else np.nan),
                       struct_m5=s * (1 if up else (-1 if dn else 0)), pole=pole, cons_rng=cons_rng, cons_slope=cons_slope,
                       flag_pat=flag, wedge_hi=wsh, wedge_lo=wsl, wedge_conv=wconv, wedge_type=wtype, wedge_with=wwith,
                       pa_close=s * float(cl[j - 1:j + 1].mean()))
            hold, back = hold_and_reclaim(s, far, c[j + 1:e_day + 1])
            rec["hold"] = int(hold)
            # follow (S2): limit at the far edge
            fill = None
            for k in range(j + 1, min(e_day, j + LIMIT_BARS) + 1):
                if (s == 1 and l[k] + sp[k] <= far) or (s == -1 and h[k] >= far):
                    fill = k
                    break
            if fill is not None:
                stop = (cen - w - sp[j]) if s == 1 else (cen + w + sp[j])
                res = trade(s, far, stop, fill)
                if res is not None:
                    r, risk = res
                    rec.update(fo_i=fill, fo_Ra=r["a"], fo_Rb=r["b"], fo_Rc=r["c"], fo_bars=r["bars"], fo_risk=risk,
                               fo_rand=rand_r(s, risk, a_day, e_day))
            # fade (F): a close back inside within 6 bars
            if back is not None:
                kb = j + 1 + back
                e = kb + 1
                if e <= e_day:
                    ext = h[j - 1:kb + 1].max() if s == 1 else l[j - 1:kb + 1].min()
                    d = -s
                    entry = o[e] + (sp[e] if d == 1 else 0.0)
                    stop = ext - sp[kb] if d == 1 else ext + sp[kb]
                    res = trade(d, entry, stop, e)
                    if res is not None:
                        r, risk = res
                        rec.update(fa_i=e, fa_Ra=r["a"], fa_Rb=r["b"], fa_Rc=r["c"], fa_bars=r["bars"], fa_risk=risk,
                                   fa_rand=rand_r(d, risk, a_day, e_day))
            rows.append(rec)
    return pd.DataFrame(rows).sort_values(["time", "type"]).reset_index(drop=True)


def main():
    df = g8.load_m5_raw()
    Z, D = pd.read_pickle(gz.OUT_Z), pd.read_pickle(gz.OUT_D)
    E = build(df, Z, D, gf.long_m30())
    E["period"] = g8.period(E["time"])
    E = E[E["period"] != "test"].reset_index(drop=True)            # sealed: test-period events are not kept
    E.to_pickle(OUT_E)
    print(gz.SYMBOL, "events", len(E), E.groupby(["type"]).size().to_dict(), "hold", round(float(E["hold"].mean()), 3),
          "follow trades", int(E["fo_Ra"].notna().sum()), "fade trades", int(E["fa_Ra"].notna().sum()), "->", OUT_E.name)


if __name__ == "__main__":
    main()
