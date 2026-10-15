"""G125 V1: S07 in miniature - gold M5/M15 compression breakout nested in the S07 trend
(plan docs/superpowers/plans/2026-10-15-g125-v1-s07-mini.md).

  python g125_s07_mini.py     -> 8 variants + G0 controls on train / validate, random control,
                                 then the sealed 2026 test once for the selected variant (user agreed V1)

Box = high..low of the previous 12 bars; contracted when its width <= 0.8 x the median of the 120 bars before.
Breakout = close beyond the box in the gate direction -> entry at the next open (ask for buys), stop at the other
side (1..4 ATR14), TP 2R / 3R, closed after 48 bars. Gates: GS an S07 leg open in that direction (G89/G107 port),
GR last closed M30 bar with the EMA21/55/100/200 ribbon ordered, G0 none. Costs: bar spread; stress +$0.20 per trade.
"""
from __future__ import annotations

import glob
import itertools
import random

import numpy as np
import pandas as pd

from g97_forming_bar import dmi, ema

HERE = __import__("pathlib").Path(__file__).resolve().parent
PER = {"M5": {"train": ("2024-03-01", "2025-07-01"), "validate": ("2025-07-01", "2026-01-01"), "test": ("2026-01-01", "2027-01-01")},
       "M15": {"train": ("2021-08-01", "2025-07-01"), "validate": ("2025-07-01", "2026-01-01"), "test": ("2026-01-01", "2027-01-01")}}
TFSEC = {"M5": 300, "M15": 900}
TFS, GATES, TPS = ("M5", "M15"), ("G0", "GS", "GR"), (2.0, 3.0)
K, CAP, REPS, STRESS = 12, 48, 200, 0.20


def load_tf(tf):
    if tf == "M5":
        m = pd.concat([pd.read_pickle(f) for f in sorted(glob.glob(str(HERE / "data" / "ticks" / "m5flow_*.pkl")))])
        m = m.drop_duplicates("time").sort_values("time").rename(columns={"hi": "high", "lo": "low"})
    else:
        m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
        m["sp"] = m["spread"] * 0.01
    return m[["time", "open", "high", "low", "close", "sp"]].reset_index(drop=True)


def srv_to_utc(t):
    """Server time -> UTC, as the S07 port does (g67: UTC+2, UTC+3 during US DST). S07 legs carry UTC times."""
    import g67_dmi_ema as g67
    t = np.asarray(t, dtype=np.int64)
    return np.array([x - (10800 if g67.us_dst(int(x) - 7200) else 7200) for x in t], dtype=np.int64)


def s07_open_counts(close_t):
    """Open S07 legs per direction at each bar close (close_t in server time; legs are compared in UTC)."""
    import g107_portfolio as p
    L = pd.DataFrame(p.s07_legs())
    close_t = srv_to_utc(close_t)
    out = {}
    for d in (1, -1):
        x = L[L.d == d]
        a = np.sort((x.t_in - pd.Timestamp(0)).dt.total_seconds().to_numpy())
        b = np.sort((x.t_out - pd.Timestamp(0)).dt.total_seconds().to_numpy())
        out[d] = np.searchsorted(a, close_t, side="right") - np.searchsorted(b, close_t, side="right")
    return out, L


def m30_ribbon(close_t):
    h = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
    c = h["close"].to_numpy()
    e = [ema(c, n) for n in (21, 55, 100, 200)]
    up = (e[0] > e[1]) & (e[1] > e[2]) & (e[2] > e[3])
    dn = (e[0] < e[1]) & (e[1] < e[2]) & (e[2] < e[3])
    ct = h["time"].to_numpy() + 1800
    k = np.searchsorted(ct, close_t, side="right") - 1
    ok = k >= 250
    kk = np.clip(k, 0, None)
    return {1: ok & up[kk], -1: ok & dn[kk]}


class TF:
    def __init__(self, tf, legs_cache):
        self.tf = tf
        m = load_tf(tf)
        self.t = m["time"].to_numpy()
        self.o, self.h, self.l, self.c, self.sp = (m[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
        _, _, _, self.atr = dmi(self.h, self.l, self.c)
        self.ts = pd.to_datetime(self.t, unit="s")
        self.hour = self.ts.hour.to_numpy()
        close_t = self.t + TFSEC[tf]
        self.s07, self.legs = s07_open_counts(close_t)
        self.rib = m30_ribbon(close_t)
        hh = pd.Series(self.h).rolling(K).max().shift(1).to_numpy()
        ll = pd.Series(self.l).rolling(K).min().shift(1).to_numpy()
        w = hh - ll
        med = pd.Series(w).shift(1).rolling(120).median().to_numpy()
        self.hh, self.ll, self.con = hh, ll, w <= 0.8 * med

    def gate(self, g, i, d):
        if g == "G0":
            return True
        if g == "GS":
            return self.s07[d][i] > 0
        return bool(self.rib[d][i])

    def mask(self, p):
        a, b = PER[self.tf][p]
        return np.asarray((self.ts >= a) & (self.ts < b))

    def sim(self, i, d, stop, tp_r):
        o, h, l, c, sp, a = self.o, self.h, self.l, self.c, self.sp, self.atr
        e = i + 1
        if e >= len(c) - 1:
            return None
        entry = o[e] + (sp[e] if d == 1 else 0.0)
        R = d * (entry - stop)
        if not (np.isfinite(a[i]) and 1.0 * a[i] <= R <= 4.0 * a[i]):
            return None
        tp = entry + d * tp_r * R
        end = min(len(c) - 1, e + CAP)
        for j in range(e, end + 1):
            if j > e and ((d == 1 and o[j] <= stop) or (d == -1 and o[j] + sp[j] >= stop)):
                px = o[j] + (sp[j] if d == -1 else 0.0)
                return d * (px - entry) / R, R, j
            if (d == 1 and l[j] <= stop) or (d == -1 and h[j] + sp[j] >= stop):
                return -1.0, R, j
            if (d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp):
                return tp_r, R, j
        px = c[end] + (sp[end] if d == -1 else 0.0)
        return d * (px - entry) / R, R, end

    def book(self, g, tp_r):
        rows, free = [], -1
        for i in np.flatnonzero(self.con & np.isfinite(self.hh)):
            if i <= free or i < 200:
                continue
            d = 1 if self.c[i] > self.hh[i] else (-1 if self.c[i] < self.ll[i] else 0)
            if d == 0 or not self.gate(g, i, d):
                continue
            stop = self.ll[i] if d == 1 else self.hh[i]
            res = self.sim(i, d, stop, tp_r)
            if res is None:
                continue
            r, R, j = res
            free = j
            rows.append(dict(i=i, d=d, r=r, stress=r - STRESS / R, k=R / self.atr[i], hour=self.hour[i],
                             t_in=self.t[i + 1], t_out=self.t[j] + TFSEC[self.tf], risk=R))
        return pd.DataFrame(rows)

    def control(self, real, g, tp_r, mk, rng):
        pools = {}
        cand = np.flatnonzero(mk & np.isfinite(self.atr))
        cand = cand[(cand > 200) & (cand < len(self.c) - 2)]
        for d in (1, -1):
            ok = np.array([self.gate(g, i, d) for i in cand], bool) if g != "G0" else np.ones(len(cand), bool)
            for hr in range(24):
                pools[(hr, d)] = cand[ok & (self.hour[cand] == hr)]
        means = []
        for _ in range(REPS):
            rs = []
            for t in real.itertuples():
                pool = pools[(t.hour, t.d)]
                if len(pool) == 0:
                    continue
                i = int(pool[rng.randrange(len(pool))])
                e = i + 1
                entry = self.o[e] + (self.sp[e] if t.d == 1 else 0.0)
                res = self.sim(i, t.d, entry - t.d * t.k * self.atr[i], tp_r)
                if res is not None:
                    rs.append(res[0])
            means.append(np.mean(rs) if rs else np.nan)
        return np.array(means)


def lower90(x, runs=4000, seed=125):
    rng = np.random.default_rng(seed)
    return float(np.quantile(rng.choice(x, (runs, len(x))).mean(1), 0.10))


def curve(x, risk):
    x = x.sort_values("t_out")
    eq = np.cumsum(x["r"].to_numpy()) * risk
    dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    years = max((x["t_out"].max() - x["t_in"].min()) / (365.25 * 86400), 1e-9)
    return eq[-1] / years, dd


def main():
    rng = random.Random(125)
    cache = {}
    D = {tf: TF(tf, cache) for tf in TFS}
    rows, books = [], {}
    for tf, tp_r, g in itertools.product(TFS, TPS, GATES):
        T = D[tf]
        b = T.book(g, tp_r)
        b["per"] = None
        for p in ("train", "validate", "test"):
            b.loc[T.mask(p)[b.i.to_numpy()], "per"] = p
        books[(tf, tp_r, g)] = b
        row = dict(tf=tf, tp=tp_r, gate=g, role="control" if g == "G0" else "variant")
        for p in ("train", "validate"):
            x = b[b.per == p]
            weeks = (np.datetime64(PER[tf][p][1]) - np.datetime64(PER[tf][p][0])).astype("timedelta64[D]").astype(int) / 7
            row[f"{p[:3]}_n"], row[f"{p[:3]}_wk"], row[f"{p[:3]}_R"] = len(x), len(x) / weeks, x.r.mean()
            row[f"{p[:3]}_buy"], row[f"{p[:3]}_sell"] = x.r[x.d == 1].mean(), x.r[x.d == -1].mean()
            row[f"{p[:3]}_stress"] = x.stress.mean()
        tv = b[b.per.isin(("train", "validate"))]
        row["tv_low90"] = lower90(tv.r.to_numpy()) if len(tv) > 10 else np.nan
        if g != "G0":
            x = b[b.per == "validate"]
            ctl = T.control(x, g, tp_r, T.mask("validate"), rng)
            row["val_ctl"], row["val_p"] = float(np.nanmedian(ctl)), float(np.nanmean(ctl >= x.r.mean()))
        rows.append(row)
        print(tf, tp_r, g, f"tra {row['tra_n']}/{row['tra_R']:+.3f} val {row['val_n']}/{row['val_R']:+.3f}", flush=True)
    R = pd.DataFrame(rows)
    passed = []
    for i, r in R[R.role == "variant"].iterrows():
        g0 = R[(R.tf == r.tf) & (R.tp == r.tp) & (R.gate == "G0")].iloc[0]
        c1 = r.tra_R > 0 and r.val_R > 0 and r.tv_low90 > 0
        c2 = r.tra_R > g0.tra_R and r.val_R > g0.val_R
        c3 = r.val_p < 0.10
        c4 = (min(r.tra_buy, r.tra_sell, r.val_buy, r.val_sell) >= -0.05) and r.tra_stress > 0 and r.val_stress > 0
        R.loc[i, ["c1", "c2", "c3", "c4"]] = [c1, c2, c3, c4]
        if c1 and c2 and c3 and c4:
            passed.append((min(r.tra_R, r.val_R), r.tf, r.tp, r.gate))
    R.to_csv(HERE / "out" / "g125_v1.csv", index=False)
    pd.set_option("display.width", 300)
    print(R.round(3).to_string(index=False))
    if not passed:
        print("\nNo variant passes -> 2026 stays sealed.")
        return
    _, tf, tp_r, g = max(passed)
    T, b = D[tf], books[(tf, tp_r, g)]
    x = b[b.per == "test"]
    print(f"\nSelected {tf} TP{tp_r:g}R {g}. Opening 2026 once.")
    ctl = T.control(x, g, tp_r, T.mask("test"), rng)
    g0 = books[(tf, tp_r, "G0")]
    g0 = g0[g0.per == "test"]
    print(f"  test: {len(x)} trades ({len(x) / 41:.1f}/week)  R {x.r.mean():+.3f}  low90 {lower90(x.r.to_numpy()):+.3f}  "
          f"win {np.mean(x.r > 0):.0%}  stress {x.stress.mean():+.3f}  buy {x.r[x.d == 1].mean():+.3f} "
          f"sell {x.r[x.d == -1].mean():+.3f}  random {np.nanmedian(ctl):+.3f} p {np.nanmean(ctl >= x.r.mean()):.3f}  "
          f"G0 {len(g0)}/{g0.r.mean():+.3f}")
    for p in ("train", "validate", "test"):
        y = b[b.per == p]
        yr, dd = curve(y, 0.5)
        print(f"  {p} @0.5%: {yr:+.1f}%/yr  DD {dd:.1f}%")
    print("  test by month R:", " ".join(f"{k}:{v:+.1f}" for k, v in
                                        x.groupby(pd.to_datetime(x.t_in, unit='s').dt.strftime('%m')).r.sum().items()))
    b.to_csv(HERE / "out" / "g125_v1_trades.csv", index=False)


if __name__ == "__main__":
    main()
