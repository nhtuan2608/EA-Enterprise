"""G109 step 3: scalp setups at the day-map zones with real costs (plan section 3 / 3b), vs fake zones (Z1) and
random entries (Z2). Train + validate only; the 2026 test stays sealed.

  G108_SYMBOL=XAUUSD python g109_setups.py        # data/g109_trades_<SYMBOL>.pkl

S1 sweep & reclaim  the first time price goes beyond the zone's far edge (from the side it started on): if the
                    excursion beyond that edge stays <= 0.5 ATR14 M30 and an M5 close comes back inside within 3 bars,
                    enter against the sweep at the next open; stop = sweep extreme +/- spread
S2 break & retest   the first 2 consecutive M5 closes beyond the far edge: a limit at that edge (12 bars); stop =
                    the other side of the zone +/- spread
target              the nearest real zone beyond the entry (its near edge), kept when RR >= 1 (fixed before results);
                    comparison: a fixed 2R target
exits               a: stop / target; b: break-even once +1R was reached on an earlier bar; c: 50 % off at +1R,
                    the rest to the target (original stop); all: at most 48 M5 bars (4 h), then the close
filters             stop >= 8 spreads, ATR14 M5 >= 3 spreads, no entry 23:00-01:00 server
Same bar: stop first. Buys exit at bid, sells at ask (bid + spread).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g109_zones as gz

import os
# G109_NOFILTER=1 (user request 13/10/2026): no cost filter (stop / ATR vs spread); the spread still costs every trade
NOFILTER = os.environ.get("G109_NOFILTER", "0") == "1"
SUF = "_nf" if NOFILTER else ""
OUT_T = g8.DATA / f"g109_trades_{gz.SYMBOL}{SUF}.pkl"
MAX_BARS, SWEEP_ATR, RECLAIM_BARS, BREAK_CLOSES, LIMIT_BARS = 48, 0.5, 3, 2, 12
MIN_STOP_SPREADS, MIN_ATR5_SPREADS, MIN_RR = (0.0, 0.0, 1.0) if NOFILTER else (8.0, 3.0, 1.0)
N_RANDOM = 5


# --------------------------------------------------------------------------------------------- pure helpers
def simulate(d: int, entry: float, stop: float, target: float, h, l, c, sp) -> dict:
    """Forward bars from the entry bar. Returns R for exits a / b / c and the bars held (exit a)."""
    risk = d * (entry - stop)
    one_r = entry + d * risk
    out = {}
    for mode in ("a", "b", "c"):
        st, half, armed, R = stop, False, False, None
        k = 0
        for k in range(min(len(h), MAX_BARS)):
            bid_hi, bid_lo = h[k], l[k]
            ask_hi, ask_lo = h[k] + sp[k], l[k] + sp[k]
            hit_stop = (bid_lo <= st) if d == 1 else (ask_hi >= st)
            hit_tgt = (bid_hi >= target) if d == 1 else (ask_lo <= target)
            hit_1r = (bid_hi >= one_r) if d == 1 else (ask_lo <= one_r)
            if hit_stop:
                loss = d * (st - entry) / risk
                R = (0.5 + 0.5 * loss) if (mode == "c" and half) else loss
                break
            if hit_tgt:
                gain = d * (target - entry) / risk
                R = (0.5 * 1.0 + 0.5 * gain) if mode == "c" and (half or hit_1r) else gain
                break
            if mode == "b" and armed:
                st = entry                                        # break-even from the bar after +1R
            if hit_1r:
                armed = True
                if mode == "c":
                    half = True
            if mode == "b" and armed:
                st = entry
        if R is None:
            k = min(len(c), MAX_BARS) - 1
            px = c[k] if d == 1 else c[k] + sp[k]
            last = d * (px - entry) / risk
            R = (0.5 + 0.5 * last) if (mode == "c" and half) else last
        out[mode] = R
        if mode == "a":
            out["bars"] = k + 1
    return out


def detect_s1(side: int, center: float, w: float, atr30: float, h, l, c):
    """Sweep & reclaim on the zone's forward bars. Returns (reclaim offset, sweep extreme) or None."""
    far = center + side * w
    beyond = np.nonzero((h > far) if side == 1 else (l < far))[0]
    if len(beyond) == 0:
        return None
    s = int(beyond[0])
    ext = None
    for j in range(s, min(len(c), s + RECLAIM_BARS)):
        ext = max(h[s:j + 1]) if side == 1 else min(l[s:j + 1])
        if side * (ext - far) > SWEEP_ATR * atr30:
            return None
        if side * (c[j] - far) < 0:
            return j, float(ext)
    return None


def detect_s2(side: int, center: float, w: float, c):
    """Break: the first 2 consecutive closes beyond the far edge. Returns the offset of the second close or None."""
    far = center + side * w
    b = (c > far) if side == 1 else (c < far)
    for j in range(1, len(c)):
        if b[j] and b[j - 1]:
            return j
    return None


def next_zone(d: int, entry: float, zones: list[tuple[float, float]]):
    """Near edge of the nearest zone beyond the entry in direction d. zones: (centre, half-width)."""
    best = None
    for cen, w in zones:
        edge = cen - d * w
        if d * (edge - entry) > 0 and (best is None or d * (edge - best) < 0):
            best = edge
    return best


# --------------------------------------------------------------------------------------------- build
def build(df: pd.DataFrame, Z: pd.DataFrame, D: pd.DataFrame, seed=109) -> pd.DataFrame:
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    n = len(t)
    hour = (t % 86400) // 3600
    atr5 = g8.wilder_atr(h, l, c)
    M30 = gz.bars(t, o, h, l, c, np.zeros(n), 1800)
    atr30 = g8.wilder_atr(M30["h"].to_numpy(), M30["l"].to_numpy(), M30["c"].to_numpy())
    m30_end = (M30.index.to_numpy(np.int64) + 1) * 1800
    H1 = gz.bars(t, o, h, l, c, np.zeros(n), 3600)
    _, _, adx1 = gf.dmi(H1["h"].to_numpy(), H1["l"].to_numpy(), H1["c"].to_numpy())
    h1_end = (H1.index.to_numpy(np.int64) + 1) * 3600
    day_last = {int(dd): int(i) for dd, i in pd.Series(np.arange(n), index=t // 86400).groupby(level=0).max().items()}
    reg = dict(zip(D["day"], D["regime"]))
    rng = np.random.default_rng(seed)
    rows = []
    for day, Zd in Z.groupby("day"):
        e_day = day_last[int(day)]
        real = Zd[~Zd["fake"]]
        for z in Zd.itertuples():
            if z.side == 0:
                continue
            s0 = int(z.from_i)
            k30 = np.searchsorted(m30_end, t[s0], side="right") - 1
            a30 = atr30[max(k30, 0)]
            for setup in ("S1", "S2"):
                if setup == "S1":
                    r = detect_s1(int(z.side), z.center, z.w, a30, h[s0:e_day + 1], l[s0:e_day + 1], c[s0:e_day + 1])
                    if r is None:
                        continue
                    j = s0 + r[0]
                    d = -int(z.side)                              # against the sweep
                    e = j + 1
                    if e > e_day:
                        continue
                    entry = o[e] + (sp[e] if d == 1 else 0.0)
                    stop = r[1] - sp[j] if d == 1 else r[1] + sp[j]
                    known = j
                else:
                    j2 = detect_s2(int(z.side), z.center, z.w, c[s0:e_day + 1])
                    if j2 is None:
                        continue
                    j = s0 + j2
                    d = int(z.side)                               # with the break
                    lim = z.center + z.side * z.w
                    fill = None
                    for k in range(j + 1, min(e_day, j + LIMIT_BARS) + 1):
                        if (d == 1 and l[k] + sp[k] <= lim) or (d == -1 and h[k] >= lim):
                            fill = k
                            break
                    if fill is None:
                        continue
                    e = fill
                    entry = lim
                    stop = (z.center - z.w - sp[j]) if d == 1 else (z.center + z.w + sp[j])
                    known = j
                if hour[e] >= 23 or hour[e] < 1:
                    continue
                risk = d * (entry - stop)
                if risk <= 0 or risk < MIN_STOP_SPREADS * sp[e] or atr5[known] < MIN_ATR5_SPREADS * sp[e]:
                    continue
                zl = [(r_.center, r_.w) for r_ in real.itertuples() if r_.from_i <= known]
                tz = next_zone(d, entry, zl)
                k1 = np.searchsorted(h1_end, t[known] + 300, side="right") - 1
                base = dict(day=int(day), t0=int(z.t0), time=int(t[e]), i=int(e), setup=setup, d=d, fake=bool(z.fake),
                            center=z.center, w=z.w, from_i=s0, known=int(known), a30=a30,
                            map=bool(z.map), kinds=z.kinds, n=int(z.n), zside=int(z.side), entry=entry, stop=stop,
                            risk=risk, risk_atr30=risk / a30, regime=reg.get(int(day), 0), adx_h1=float(adx1[max(k1, 0)]),
                            hour=int(hour[e]))
                fwd = slice(e, min(n, e + MAX_BARS))
                for tgt_name, target in (("zone", tz), ("2R", entry + d * 2 * risk)):
                    if target is None:
                        continue
                    rr = d * (target - entry) / risk
                    if tgt_name == "zone" and rr < MIN_RR:
                        continue
                    res = simulate(d, entry, stop, target, h[fwd], l[fwd], c[fwd], sp[fwd])
                    # Z2: random entries the same day, same direction, stop distance and RR
                    rnd = []
                    if not z.fake:
                        lo_i = int(Zd["from_i"].min())
                        for _ in range(N_RANDOM):
                            q = int(rng.integers(lo_i, e_day + 1))
                            if hour[q] >= 23 or hour[q] < 1:
                                continue
                            en = o[q] + (sp[q] if d == 1 else 0.0)
                            fq = slice(q, min(n, q + MAX_BARS))
                            rnd.append(simulate(d, en, en - d * risk, en + d * rr * risk, h[fq], l[fq], c[fq], sp[fq])["a"])
                    rows.append(dict(base, target=tgt_name, rr=rr, Ra=res["a"], Rb=res["b"], Rc=res["c"], bars=res["bars"],
                                     Rrand=float(np.mean(rnd)) if rnd else np.nan))
    return pd.DataFrame(rows)


def main():
    df = g8.load_m5_raw()
    Z, D = pd.read_pickle(gz.OUT_Z), pd.read_pickle(gz.OUT_D)
    Z = Z[Z["period"] != "test"]                                 # sealed
    D = D[D["period"] != "test"]
    T = build(df, Z, D)
    T["period"] = g8.period(T["time"])
    assert not (T["period"] == "test").any()
    T.to_pickle(OUT_T)
    print(gz.SYMBOL, "trades", len(T), T.groupby(["setup", "fake", "target"]).size().to_dict(), "->", OUT_T.name)


if __name__ == "__main__":
    main()
