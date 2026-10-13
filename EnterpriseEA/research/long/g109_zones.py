"""G109 step 1: the day zone map, intraday zones, and their labels
(docs/superpowers/plans/2026-10-13-g109-day-zone-map.md).

  G108_SYMBOL=XAUUSD python g109_zones.py     # raw MT5 M5 exports (tick volume); writes data/g109_*_<SYMBOL>.pkl

Map at the server-day open (first M5 bar, price p0 = its open), built from bars closed before it only:
  prior day high / low / middle / close / tick-volume VWAP; prior week high / low (if untaken this week);
  untaken H1 swings (fractal 2/2, last 5 days) and H4 swings (last 10 days); unfilled H1 fair-value gaps (5 days);
  EMA200 H1 / H4, EMA21 / EMA50 D1; round numbers (gold 10 / 50, FX 50 / 100 pips) nearest above and below.
  Candidates within 3 ATR14 D1 of p0. Zone half-width w = max(0.15 ATR14 M30, 2 x the prior day's median spread);
  candidates whose bands overlap (centres < 2w apart) merge: centre = mean, n = confluence.
Intraday zones (appear when formed): Asia range high / low (server h < 10), London opening range 10:00-10:30,
New York opening range 16:30-17:00.
Labels (rest of the server day after the zone is known):
  side      +1 zone above the price when it appears, -1 below, 0 price inside the band
  touched   the band [c - w, c + w] is reached; touch_i = first M5 bar
  reaction  from the touch bar, within 12 M5 bars: +1 bounce (price back away from the near edge by 2w),
            -1 through (2 consecutive closes beyond the far edge), 0 neither; the first event wins
Fake zones (control Z1): each map zone shifted by +/- U(0.5, 1.5) ATR D1, kept at least 2w away from every real
zone, labelled the same way.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8

HERE = Path(__file__).resolve().parent
SYMBOL = g8.SYMBOL
OUT_Z = g8.DATA / f"g109_zones_{SYMBOL}.pkl"
OUT_C = g8.DATA / f"g109_candidates_{SYMBOL}.pkl"
OUT_D = g8.DATA / f"g109_days_{SYMBOL}.pkl"
ZONE_ATR, MIN_W_SPREADS, NEAR_D1 = 0.15, 2.0, 3.0
H1_DAYS, H4_DAYS, FVG_DAYS = 5, 10, 5
REACT_BARS, BOUNCE_W = 12, 2.0
ROUND = {"XAUUSD": (10.0, 50.0), "EURUSD": (0.005, 0.01), "GBPUSD": (0.005, 0.01), "USDJPY": (0.5, 1.0)}
SEED = 109


# --------------------------------------------------------------------------------------------- pure helpers
def bars(t: np.ndarray, o, h, l, c, tv, sec: int) -> pd.DataFrame:
    """OHLC buckets of `sec` seconds from M5 rows, with the first / last M5 index of each bucket."""
    df = pd.DataFrame({"b": t // sec, "i": np.arange(len(t)), "o": o, "h": h, "l": l, "c": c, "tv": tv})
    return df.groupby("b").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), tv=("tv", "sum"),
                               first=("i", "min"), last=("i", "max"))


def merge(cands: list[tuple[float, str]], w: float) -> list[dict]:
    """Merge candidates whose bands overlap (centres closer than 2w), in price order."""
    out: list[dict] = []
    for lev, kind in sorted(cands):
        if out and lev - out[-1]["hi"] < 2 * w:
            z = out[-1]
            z["members"].append(lev); z["kinds"].append(kind); z["hi"] = lev
        else:
            out.append({"members": [lev], "kinds": [kind], "hi": lev})
    return [{"center": float(np.mean(z["members"])), "kinds": "+".join(sorted(set(z["kinds"]))), "n": len(z["members"])}
            for z in out]


def touch_reaction(h: np.ndarray, l: np.ndarray, c: np.ndarray, center: float, w: float, side: int):
    """Forward bars of the zone's window. Returns (touched, first touch offset or -1, reaction)."""
    hit = np.nonzero((h >= center - w) & (l <= center + w))[0]
    if len(hit) == 0:
        return False, -1, 0
    k = int(hit[0])
    if side == 0:
        return True, k, 0
    near, far = center - side * w, center + side * w
    beyond = side * (c - far) > 0
    for j in range(k, min(len(c), k + REACT_BARS)):
        back = (l[j] <= near - BOUNCE_W * w) if side == 1 else (h[j] >= near + BOUNCE_W * w)
        thru = j >= k + 1 and beyond[j] and beyond[j - 1]
        if thru:
            return True, k, -1
        if back:
            return True, k, 1
    return True, k, 0


def fvg(h: np.ndarray, l: np.ndarray, j: int):
    """H1 fair-value gap closed at bar j: (+1, low, high) bullish, (-1, low, high) bearish, or None."""
    if j < 2:
        return None
    if l[j] > h[j - 2]:
        return 1, h[j - 2], l[j]
    if h[j] < l[j - 2]:
        return -1, h[j], l[j - 2]
    return None


def week_of(day: np.ndarray) -> np.ndarray:
    return (day + 3) // 7                                     # Monday-based weeks (1970-01-01 was a Thursday)


# --------------------------------------------------------------------------------------------- build
def build(df: pd.DataFrame, hist: pd.DataFrame | None = None, symbol: str = SYMBOL, days_only: list[int] | None = None):
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float) if "tickvol" in df else np.full(len(t), np.nan)
    n = len(t)
    hmax, lmin = g8.RangeExt(h, np.maximum), g8.RangeExt(l, np.minimum)
    day = t // 86400
    hour = (t % 86400) // 3600
    minute = (t % 3600) // 60
    D1 = bars(t, o, h, l, c, tv, 86400)
    days = D1.index.to_numpy(np.int64)
    atr_d1 = g8.wilder_atr(D1["h"].to_numpy(), D1["l"].to_numpy(), D1["c"].to_numpy())
    M30 = bars(t, o, h, l, c, tv, 1800)
    atr30 = g8.wilder_atr(M30["h"].to_numpy(), M30["l"].to_numpy(), M30["c"].to_numpy())
    m30_end = (M30.index.to_numpy(np.int64) + 1) * 1800
    H1 = bars(t, o, h, l, c, tv, 3600)
    H4 = bars(t, o, h, l, c, tv, 14400)
    h1h, h1l, h1last = H1["h"].to_numpy(), H1["l"].to_numpy(), H1["last"].to_numpy()
    h4h, h4l, h4last = H4["h"].to_numpy(), H4["l"].to_numpy(), H4["last"].to_numpy()
    sh1, sl1 = g8.fractals(h1h, h1l)
    sh4, sl4 = g8.fractals(h4h, h4l)
    import g108_features as gf
    emas = {}
    for name, sec, per in (("ema200_h1", 3600, 200), ("ema200_h4", 14400, 200), ("ema21_d1", 86400, 21), ("ema50_d1", 86400, 50)):
        b, cl = gf.htf_closes(df, hist, sec)
        emas[name] = (b, g8.ema(cl, per), sec)
    d1b, d1c = gf.htf_closes(df, hist, 86400)
    d1e50 = g8.ema(d1c, 50)
    week = week_of(day)
    steps = ROUND.get(symbol, ROUND["XAUUSD"])
    rng = np.random.default_rng(SEED)
    Z, C, DAYS = [], [], []
    for k in range(1, len(days)):
        if days_only is not None and int(days[k]) not in days_only:
            continue
        a, b = int(D1["first"].iloc[k]), int(D1["last"].iloc[k])
        pa, pb = int(D1["first"].iloc[k - 1]), int(D1["last"].iloc[k - 1])
        t0, p0 = t[a], o[a]
        k30 = np.searchsorted(m30_end, t0, side="right") - 1
        if k30 < 30 or k < 15:
            continue
        ad = atr_d1[k - 1]
        w = max(ZONE_ATR * atr30[k30], MIN_W_SPREADS * float(np.median(sp[pa:pb + 1])))
        cands: list[tuple[float, str]] = []
        # prior day
        PH, PL = h[pa:pb + 1].max(), l[pa:pb + 1].min()
        cands += [(PH, "PDH"), (PL, "PDL"), ((PH + PL) / 2, "PDM"), (c[pb], "PDC")]
        tvd = tv[pa:pb + 1]
        if np.isfinite(tvd).all() and tvd.sum() > 0:
            tp = (h[pa:pb + 1] + l[pa:pb + 1] + c[pa:pb + 1]) / 3
            cands.append((float((tp * tvd).sum() / tvd.sum()), "VWAP"))
        # prior week, if untaken during this week before t0
        wk = week[a]
        pw = np.nonzero(week[:a] == wk - 1)[0]
        if len(pw):
            WH, WL, wl = h[pw].max(), l[pw].min(), int(pw[-1])
            if wl + 1 > a - 1 or hmax.q(wl + 1, a - 1) <= WH:
                cands.append((WH, "PWH"))
            if wl + 1 > a - 1 or lmin.q(wl + 1, a - 1) >= WL:
                cands.append((WL, "PWL"))
        # untaken H1 / H4 swings confirmed before t0
        for (sh, sl, hh, ll, last, look, tag) in ((sh1, sl1, h1h, h1l, h1last, H1_DAYS, "H1"), (sh4, sl4, h4h, h4l, h4last, H4_DAYS, "H4")):
            for idx, ext, sign in ((sh, hh, 1), (sl, ll, -1)):
                for j in idx:
                    if j + 2 >= len(last) or last[j + 2] >= a or t[last[j]] < t0 - look * 86400:
                        continue
                    lev = ext[j]
                    e = last[j]
                    if e + 1 <= a - 1:
                        if sign == 1 and hmax.q(e + 1, a - 1) > lev:
                            continue
                        if sign == -1 and lmin.q(e + 1, a - 1) < lev:
                            continue
                    cands.append((float(lev), f"{tag}{'SH' if sign == 1 else 'SL'}"))
        # unfilled H1 fair-value gaps
        j0 = np.searchsorted(t[h1last], t0 - FVG_DAYS * 86400)
        for j in range(max(2, j0), len(h1last)):
            if h1last[j] >= a:
                break
            f = fvg(h1h, h1l, j)
            if f is None:
                continue
            sgn, lo_, hi_ = f
            e = h1last[j]
            if e + 1 <= a - 1:
                if sgn == 1 and lmin.q(e + 1, a - 1) < hi_:
                    continue                                    # price traded into a bullish gap
                if sgn == -1 and hmax.q(e + 1, a - 1) > lo_:
                    continue
            cands.append(((lo_ + hi_) / 2, "FVG"))
        # EMAs at the last closed bucket before t0
        for name, (bb, ee, sec) in emas.items():
            kk = np.searchsorted((bb + 1) * sec, t0, side="right") - 1
            if kk >= 0:
                cands.append((float(ee[kk]), name.upper()))
        # round numbers
        for st in steps:
            cands += [(np.floor(p0 / st) * st, f"R{st:g}"), (np.ceil(p0 / st) * st, f"R{st:g}")]
        cands = list(dict.fromkeys((float(lv), kd) for lv, kd in cands if abs(lv - p0) <= NEAR_D1 * ad))
        C += [dict(day=int(days[k]), kind=kd, level=lv) for lv, kd in cands]
        zones = merge(cands, w)
        rows = []
        for z in zones:
            side = 1 if z["center"] - w > p0 else (-1 if z["center"] + w < p0 else 0)
            rows.append(dict(z, side=side, map=True, fake=False, from_i=a))
        # fake zones (control)
        reals = [r["center"] for r in rows]
        for r in list(rows):
            for _ in range(5):
                fc = r["center"] + rng.choice((-1, 1)) * rng.uniform(0.5, 1.5) * ad
                if all(abs(fc - x) >= 2 * w for x in reals):
                    side = 1 if fc - w > p0 else (-1 if fc + w < p0 else 0)
                    rows.append(dict(center=float(fc), kinds="FAKE", n=1, side=side, map=True, fake=True, from_i=a))
                    break
        # intraday zones: Asia range, London / New York opening ranges
        for tag, m in (("ASIA", (hour[a:b + 1] < 10)),
                       ("LOR", (hour[a:b + 1] == 10) & (minute[a:b + 1] < 30)),
                       ("NYOR", (hour[a:b + 1] == 16) & (minute[a:b + 1] >= 30))):
            idx = np.nonzero(m)[0] + a
            if len(idx) == 0 or idx[-1] + 1 > b:
                continue
            e = int(idx[-1])
            ref = c[e]
            for lev, kd in ((h[idx].max(), f"{tag}_H"), (l[idx].min(), f"{tag}_L")):
                side = 1 if lev - w > ref else (-1 if lev + w < ref else 0)
                rows.append(dict(center=float(lev), kinds=kd, n=1, side=side, map=False, fake=False, from_i=e + 1))
        for r in rows:
            s0 = r["from_i"]
            touched, off, react = touch_reaction(h[s0:b + 1], l[s0:b + 1], c[s0:b + 1], r["center"], w, r["side"])
            r.update(day=int(days[k]), t0=int(t0), p0=p0, w=w, atr_d1=ad, dist=(r["center"] - p0) / ad,
                     touched=touched, touch_i=(s0 + off if touched else -1), reaction=react)
            Z.append(r)
        # day record: nearest map zone above / below (real zones)
        up = [r for r in rows if r["map"] and not r["fake"] and r["side"] == 1]
        dn = [r for r in rows if r["map"] and not r["fake"] and r["side"] == -1]
        kd1 = np.searchsorted((d1b + 1) * 86400, t0, side="right") - 1
        reg = 0
        if kd1 >= 10:
            sd, sl_ = np.sign(d1c[kd1] - d1e50[kd1]), np.sign(d1e50[kd1] - d1e50[kd1 - 10])
            reg = int(sd) if sd == sl_ else 0
        rec = dict(day=int(days[k]), t0=int(t0), p0=p0, atr_d1=ad, w=w, regime=reg, dow=int((days[k] + 3) % 7),
                   prev_range=(PH - PL) / ad, prev_close_pos=(c[pb] - PL) / max(PH - PL, 1e-12))
        for name, lst, key in (("up", up, min), ("dn", dn, max)):
            if lst:
                z = key(lst, key=lambda r: r["center"])
                rec.update({f"{name}_dist": abs(z["center"] - p0) / ad, f"{name}_n": z["n"], f"{name}_kinds": z["kinds"],
                            f"{name}_touch": z["touch_i"] if z["touched"] else -1})
            else:
                rec.update({f"{name}_dist": np.nan, f"{name}_n": 0, f"{name}_kinds": "", f"{name}_touch": -1})
        ut, dt_ = rec["up_touch"], rec["dn_touch"]
        rec["first"] = 0 if (ut < 0 and dt_ < 0) else (1 if (dt_ < 0 or (ut >= 0 and ut < dt_)) else (-1 if (ut < 0 or dt_ < ut) else 0))
        DAYS.append(rec)
    return pd.DataFrame(Z), pd.DataFrame(C), pd.DataFrame(DAYS)


def main():
    import g108_features as gf
    df = g8.load_m5_raw()
    print(SYMBOL, "M5", len(df), pd.to_datetime(df["time"].iloc[0], unit="s"), "->", pd.to_datetime(df["time"].iloc[-1], unit="s"))
    Z, C, D = build(df, gf.long_m30())
    for X in (Z, D):
        X["period"] = g8.period(X["t0"])
    Z.to_pickle(OUT_Z); C.to_pickle(OUT_C); D.to_pickle(OUT_D)
    print("days", len(D), "zones", len(Z), "map real", int((Z["map"] & ~Z["fake"]).sum()), "fake", int(Z["fake"].sum()),
          "intraday", int((~Z["map"]).sum()), "->", OUT_Z.name)


if __name__ == "__main__":
    main()
