"""G111 step 1: Fibonacci levels (prior day, Asia range, day-so-far) with fake ratios, retracement depth, and zone
tests with the reversal trade T (docs/superpowers/plans/2026-10-13-g111-retrace-fib-tests.md).

  G108_SYMBOL=XAUUSD python g111_levels.py      # raw MT5 M5 -> data/g111_levels_<SYMBOL>.pkl, data/g111_tests_<SYMBOL>.pkl

Fibonacci of a leg low -> high (up) or high -> low (down), retracement ratio r measured back from the end of the leg:
  P  prior server day, leg direction = close vs open; known at the day open
  A  Asia range (server h < 10), direction = last Asia close vs the day open; known from the first bar at 10:00
  D  the day so far at 15:00 server, direction = close vs the day open; known from the first bar at 15:00
Ratios FIB = 23.6 / 38.2 / 50 / 61.8 / 78.6 %, fake ratios = 30 / 45 / 55 / 70 % (control). Band half-width w as G109.
Test: the first bar after the level is known whose range reaches the band from the side the price was on, without a
close beyond the far edge (a close beyond = a break, no test). Trade T against the approach: a resting limit at the
near edge (filled on that bar), stop = far edge + 0.5 w +/- spread, target 2R (also the next real zone, RR >= 1);
on the fill bar only the stop is checked; then g109 exits a / b / c, at most 4 h; cost filter as G109.
Features use bars <= k - 1 (the limit rests before the touch).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g109_setups as gs
import g109_zones as gz
import g110_breaks as gb

OUT_L = g8.DATA / f"g111_levels_{gz.SYMBOL}{gs.SUF}.pkl"
OUT_T = g8.DATA / f"g111_tests_{gz.SYMBOL}{gs.SUF}.pkl"
FIB = (0.236, 0.382, 0.5, 0.618, 0.786)
FAKE = (0.30, 0.45, 0.55, 0.70)
STOP_W, RR, N_RANDOM = 0.5, 2.0, 5


def fib_levels(lo: float, hi: float, up: bool, ratios) -> list[tuple[float, float]]:
    """(ratio, price) of the retracements of a leg lo -> hi (up) or hi -> lo (down)."""
    rng = hi - lo
    return [(r, hi - r * rng) if up else (r, lo + r * rng) for r in ratios]


def find_test(side: int, center: float, w: float, h: np.ndarray, l: np.ndarray, c: np.ndarray, sp=None):
    """Offset of the first bar whose price fills the resting limit at the near edge (a sell limit when the bid high
    reaches it, side +1; a buy limit when the ASK low = bid low + spread reaches it, side -1) without a close beyond
    the far edge; None when that first fill bar is a break or the edge is never reached."""
    near, far = center - side * w, center + side * w
    sp = np.zeros(len(h)) if sp is None else sp
    reach = np.nonzero((h >= near) if side == 1 else (l + sp <= near))[0]
    if len(reach) == 0:
        return None
    k = int(reach[0])
    return None if side * (c[k] - far) > 0 else k


def trade_t(d: int, entry: float, stop: float, target: float, h, l, c, sp) -> dict | None:
    """Reversal trade filled on bar 0 at the limit: bar 0 can only stop it; then the g109 exits from bar 1."""
    risk = d * (entry - stop)
    if risk <= 0:
        return None
    if (d == 1 and l[0] <= stop) or (d == -1 and h[0] + sp[0] >= stop):
        return {"a": -1.0, "b": -1.0, "c": -1.0, "bars": 1}
    if len(h) < 2:
        return None
    r = gs.simulate(d, entry, stop, target, h[1:], l[1:], c[1:], sp[1:])
    r["bars"] += 1
    return r


def build(df: pd.DataFrame, Z: pd.DataFrame, D: pd.DataFrame, hist: pd.DataFrame | None = None, seed: int = 111):
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float)
    n = len(t)
    hour = (t % 86400) // 3600
    atr5 = g8.wilder_atr(h, l, c)
    rv = gb.rel_volume(t, tv)
    cl = gb.clv(o, h, l, c)
    M30 = gz.bars(t, o, h, l, c, np.zeros(n), 1800)
    atr30 = g8.wilder_atr(M30["h"].to_numpy(), M30["l"].to_numpy(), M30["c"].to_numpy())
    m30_end = (M30.index.to_numpy(np.int64) + 1) * 1800
    H1 = gz.bars(t, o, h, l, c, np.zeros(n), 3600)
    _, _, A1 = gf.dmi(H1["h"].to_numpy(), H1["l"].to_numpy(), H1["c"].to_numpy())
    h1_end = (H1.index.to_numpy(np.int64) + 1) * 3600
    b4, c4 = gf.htf_closes(df, hist, 14400)
    e4 = g8.ema(c4, 200)
    day = t // 86400
    first_of = pd.Series(np.arange(n)).groupby(day).min().to_dict()
    last_of = pd.Series(np.arange(n)).groupby(day).max().to_dict()
    days = sorted(first_of)
    Dd = D.set_index("day")
    rng = np.random.default_rng(seed)
    LV, TS = [], []
    for kd in range(1, len(days)):
        dd, pd_ = days[kd], days[kd - 1]
        if dd not in Dd.index:
            continue
        a, e_day = first_of[dd], last_of[dd]
        pa, pb = first_of[pd_], last_of[pd_]
        w, ad, regime = float(Dd.loc[dd, "w"]), float(Dd.loc[dd, "atr_d1"]), int(Dd.loc[dd, "regime"])
        PH, PL = h[pa:pb + 1].max(), l[pa:pb + 1].min()
        up_p = c[pb] >= o[pa]
        levels = []                                              # (family, ratio, price, from_i, fake)
        for fam_fake, ratios in ((False, FIB), (True, FAKE)):
            for r, px in fib_levels(PL, PH, up_p, ratios):
                levels.append(("P", r, px, a, fam_fake))
        asia = np.nonzero(hour[a:e_day + 1] < 10)[0] + a
        if len(asia) > 6 and asia[-1] + 1 <= e_day:
            AH, AL = h[asia].max(), l[asia].min()
            for fam_fake, ratios in ((False, FIB), (True, FAKE)):
                for r, px in fib_levels(AL, AH, c[asia[-1]] >= o[a], ratios):
                    levels.append(("A", r, px, int(asia[-1]) + 1, fam_fake))
        upto = np.nonzero(hour[a:e_day + 1] < 15)[0] + a
        if len(upto) > 12 and upto[-1] + 1 <= e_day:
            DH, DL = h[upto].max(), l[upto].min()
            for fam_fake, ratios in ((False, FIB), (True, FAKE)):
                for r, px in fib_levels(DL, DH, c[upto[-1]] >= o[a], ratios):
                    levels.append(("D", r, px, int(upto[-1]) + 1, fam_fake))
        # retracement depth of today into the prior day's range
        rng_p = PH - PL
        depth = ((PH - l[a:e_day + 1].min()) / rng_p) if up_p else ((h[a:e_day + 1].max() - PL) / rng_p)
        LV.append(dict(day=dd, t0=int(t[a]), up=int(up_p), prev_range=rng_p / ad, depth=depth))
        # all levels of the day: fib levels + G109 zones (real, fake)
        Zd = Z[Z["day"] == dd]
        allv = [(f"{fam}{'FAKE' if fk else 'FIB'}", r, px, fi, fk) for fam, r, px, fi, fk in levels]
        allv += [("ZONE" if not z.fake else "ZFAKE", np.nan, z.center, int(z.from_i), bool(z.fake)) for z in Zd.itertuples() if z.map or not z.fake]
        real_px = [(px, fi) for fam, r, px, fi, fk in allv if not fk]
        kinds_of = {round(z.center, 6): z.kinds for z in Zd.itertuples()}
        for fam, ratio, px, fi, fk in allv:
            if fi >= e_day or abs(px - o[a]) > gz.NEAR_D1 * ad:
                continue
            ref = c[fi - 1]
            side = 1 if px - w > ref else (-1 if px + w < ref else 0)
            if side == 0:
                continue
            off = find_test(side, px, w, h[fi:e_day + 1], l[fi:e_day + 1], c[fi:e_day + 1], sp[fi:e_day + 1])
            if off is None:
                continue
            k = fi + off
            if k < 40 or hour[k] >= 23 or hour[k] < 1:
                continue
            d = -side
            entry = px - side * w                                 # near edge
            stop = px + side * (w + STOP_W * w) + side * sp[k - 1]
            risk = d * (entry - stop)
            if risk < gs.MIN_STOP_SPREADS * sp[k - 1] or atr5[k - 1] < gs.MIN_ATR5_SPREADS * sp[k - 1]:
                continue
            fwd = slice(k, min(n, k + gs.MAX_BARS + 1))
            res = trade_t(d, entry, stop, entry + d * RR * risk, h[fwd], l[fwd], c[fwd], sp[fwd])
            if res is None:
                continue
            nz = [z for z in Zd.itertuples() if not z.fake and z.from_i <= k - 1]
            tz = gs.next_zone(d, entry, [(z.center, z.w) for z in nz])
            res_z = None
            if tz is not None and d * (tz - entry) / risk >= 1.0:
                res_z = trade_t(d, entry, stop, tz, h[fwd], l[fwd], c[fwd], sp[fwd])
            # features (bars <= k - 1)
            q = k - 1
            k30 = np.searchsorted(m30_end, t[q] + g8.BAR_SEC, side="right") - 1
            a30 = atr30[max(k30, 0)]
            k1 = np.searchsorted(h1_end, t[q] + g8.BAR_SEC, side="right") - 1
            k4 = np.searchsorted((b4 + 1) * 14400, t[q] + g8.BAR_SEC, side="right") - 1
            d12 = slice(q - 11, q + 1)
            den = np.nansum(rv[d12])
            delta12 = side * np.nansum(cl[d12] * rv[d12]) / den if den > 0 else np.nan
            price12 = side * (c[q] - c[q - 12]) / a30                # move toward the level
            y6 = rv[q - 5:q + 1]
            conf = sum(1 for x, f0 in real_px if f0 <= k - 1 and abs(x - px) <= w) - (1 if (not fk and fi <= k - 1) else 0)   # others known before the touch
            rec = dict(day=dd, time=int(t[k]), k=k, fi=int(fi), fam=fam, ratio=ratio, fake=fk, center=px, w=w, side=side, d=d,
                       kinds=kinds_of.get(round(px, 6), ""), conf=conf, entry=entry, stop=stop, risk=risk,
                       rv6=float(np.nanmean(rv[q - 5:q + 1])), rv12=float(np.nanmean(rv[q - 11:q + 1])),
                       rv_slope=float(np.polyfit(np.arange(6), y6, 1)[0]) if np.isfinite(y6).all() else np.nan,
                       speed=price12, delta12=delta12, diverg=float(np.sign(price12) != np.sign(delta12)) if np.isfinite(delta12) else np.nan,
                       adx_h1=float(A1[max(k1, 0)]), d1_with=d * regime,
                       h4_side=d * float(np.sign(c[q] - e4[max(k4, 0)])) if k4 >= 0 else 0.0,
                       hour=int(hour[k]), dist_open=abs(px - o[a]) / ad,
                       Ra=res["a"], Rb=res["b"], Rc=res["c"], bars=res["bars"],
                       Rz=(res_z["a"] if res_z else np.nan))
            rr_ = []
            for _ in range(N_RANDOM):
                qq = int(rng.integers(a, e_day + 1))
                if hour[qq] >= 23 or hour[qq] < 1:
                    continue
                en = o[qq] + (sp[qq] if d == 1 else 0.0)
                f2 = slice(qq, min(n, qq + gs.MAX_BARS))
                rr_.append(gs.simulate(d, en, en - d * risk, en + d * RR * risk, h[f2], l[f2], c[f2], sp[f2])["a"])
            rec["Rrand"] = float(np.mean(rr_)) if rr_ else np.nan
            TS.append(rec)
    return pd.DataFrame(LV), pd.DataFrame(TS)


def main():
    df = g8.load_m5_raw()
    Z, D = pd.read_pickle(gz.OUT_Z), pd.read_pickle(gz.OUT_D)
    LV, TS = build(df, Z, D, gf.long_m30())
    for X in (LV, TS):
        X["period"] = g8.period(X["t0"] if "t0" in X else X["time"])
    LV = LV[LV["period"] != "test"]; TS = TS[TS["period"] != "test"]  # sealed
    LV.to_pickle(OUT_L); TS.to_pickle(OUT_T)
    print(gz.SYMBOL, "days", len(LV), "tests", len(TS), TS.groupby("fam").size().to_dict(), "->", OUT_T.name)


if __name__ == "__main__":
    main()
