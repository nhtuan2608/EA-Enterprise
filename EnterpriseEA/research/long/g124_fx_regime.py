"""G124 R1: FX compression breakout gated by the D1 trend regime (plan docs/superpowers/plans/2026-10-15-g124-fx-regime-breakout.md).

  python g124_fx_regime.py        -> train / validate for 8 variants + G0/G1 controls, random-entry control,
                                     then the sealed test 2023..10/2026 once for the selected variant (user agreed G124)

Basket: EURUSD GBPUSD AUDUSD NZDUSD USDCAD USDJPY (terminal history, H4 + D1 from 2010; data/fx124).
Box = high..low of the previous K H4 bars; contracted when its width <= 0.8 x the median box width of the 120 bars
before. Breakout = H4 close beyond the box -> entry at the next open, stop at the other side (1..4 ATR14 H4).
Gates (closed D1 bars): G0 none | G1 120-day return sign | G2 G1 + ER60 >= train median | G3 G1 + ER60 >= train q67.
Exits: E1 TP 3R | E2 break-even at +1R then 3 ATR(H4) chandelier on closes; both capped at 180 H4 bars.
Costs: bar spread at entry/exit (bar minimum; +1 pip stress column) (ask for buys in, sells out), USD 6/lot commission; swap at today's broker rates
reported separately (3x on the rollover weekday).
"""
from __future__ import annotations

import itertools
import json
import random
import sys

import numpy as np
import pandas as pd

from g97_forming_bar import dmi

HERE = __import__("pathlib").Path(__file__).resolve().parent
DATA = HERE / "data" / "fx124"
PAIRS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDJPY")
COMM = {"EURUSD": 0.00006, "GBPUSD": 0.00006, "AUDUSD": 0.00006, "NZDUSD": 0.00006, "USDCAD": 0.000083, "USDJPY": 0.009}
PER = {"train": (2010, 2018), "validate": (2019, 2022), "test": (2023, 2026)}
KS, EXITS, GATES = (12, 24), ("E1", "E2"), ("G0", "G1", "G2", "G3")
VARIANT_GATES = ("G2", "G3")
CAP, REPS = 180, 200
# bar spreads in the MT5 history are the bar minimum; stress = one extra pip per round trip
STRESS_PIP = {s: (0.01 if s.endswith("JPY") else 0.0001) for s in PAIRS}


def period(year):
    for p, (a, b) in PER.items():
        if a <= year <= b:
            return p
    return None


class Pair:
    def __init__(self, sym, meta):
        self.sym = sym
        h = pd.read_csv(DATA / f"{sym}_H4.csv")
        d = pd.read_csv(DATA / f"{sym}_D1.csv")
        self.pt = meta["point"]
        self.comm = COMM[sym]
        self.sw_long, self.sw_short, self.sw3 = meta["swap_long"], meta["swap_short"], meta["swap3"]
        self.t = h["time"].to_numpy()
        self.o, self.h, self.l, self.c = (h[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp = h["spread"].to_numpy() * self.pt
        _, _, _, self.atr = dmi(self.h, self.l, self.c)
        self.year = pd.to_datetime(self.t, unit="s").year.to_numpy()
        # D1 regime, from closed daily bars only
        dc = d["close"].to_numpy()
        mom = np.sign(dc / pd.Series(dc).shift(120).to_numpy() - 1)
        move = np.abs(pd.Series(dc).diff()).rolling(60).sum().to_numpy()
        er = np.abs(dc - pd.Series(dc).shift(60).to_numpy()) / move
        k = np.searchsorted(d["time"].to_numpy(), (self.t // 86400) * 86400, side="left") - 1
        ok = k >= 0
        self.mom = np.where(ok, mom[np.clip(k, 0, None)], np.nan)
        self.er = np.where(ok, er[np.clip(k, 0, None)], np.nan)
        self.d1_er_train = er[(pd.to_datetime(d["time"], unit="s").dt.year <= PER["train"][1]).to_numpy()]
        self.box = {}
        for K in KS:
            hh = pd.Series(self.h).rolling(K).max().shift(1).to_numpy()
            ll = pd.Series(self.l).rolling(K).min().shift(1).to_numpy()
            w = hh - ll
            med = pd.Series(w).shift(1).rolling(120).median().to_numpy()
            self.box[K] = (hh, ll, w <= 0.8 * med)

    def gate(self, g, i, d, thr):
        if g == "G0":
            return True
        if not np.isfinite(self.mom[i]) or self.mom[i] != d:
            return False
        if g == "G1":
            return True
        return np.isfinite(self.er[i]) and self.er[i] >= thr[g]

    def signals(self, K):
        hh, ll, con = self.box[K]
        out = []
        for i in range(130, len(self.c) - 2):
            if not con[i] or not np.isfinite(self.atr[i]):
                continue
            if self.c[i] > hh[i]:
                out.append((i, 1, ll[i]))
            elif self.c[i] < ll[i]:
                out.append((i, -1, hh[i]))
        return out

    def sim(self, i, d, stop, ex):
        """Entry at bar i+1 open. Returns (r, r_with_swap, exit_bar) or None."""
        o, h, l, c, sp, a = self.o, self.h, self.l, self.c, self.sp, self.atr
        e = i + 1
        entry = o[e] + (sp[e] if d == 1 else 0.0)
        R = d * (entry - stop)
        if not (1.0 * a[i] <= R <= 4.0 * a[i]):
            return None
        tp = entry + d * 3 * R if ex == "E1" else None
        best, be = entry, False
        end = min(len(c) - 1, e + CAP)
        px, j = None, e
        for j in range(e, end + 1):
            if j > e:                                                    # gap through the stop at the open
                if d == 1 and o[j] <= stop:
                    px = o[j]; break
                if d == -1 and o[j] + sp[j] >= stop:
                    px = o[j] + sp[j]; break
            if (d == 1 and l[j] <= stop) or (d == -1 and h[j] + sp[j] >= stop):
                px = stop; break
            if tp is not None and ((d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp)):
                px = tp; break
            if ex == "E2":
                best = max(best, c[j]) if d == 1 else min(best, c[j])
                if not be and d * (best - entry) >= R:
                    be = True
                    stop = entry if d * (entry - stop) > 0 else stop
                if be:
                    trail = best - d * 3 * a[j]
                    if d * (trail - stop) > 0:
                        stop = trail
        if px is None:
            j = end
            px = c[j] + (sp[j] if d == -1 else 0.0)
        r = (d * (px - entry) - self.comm) / R
        nights = self.nights(self.t[e], self.t[j])
        sw = (self.sw_long if d == 1 else self.sw_short) * self.pt * nights
        return r, r + sw / R, j

    def nights(self, t0, t1):
        d0, d1 = t0 // 86400, t1 // 86400
        if d1 <= d0:
            return 0
        days = np.arange(d0, d1)                       # rollovers at the end of these server days
        wd = (days + 3) % 7                            # 1970-01-01 was a Thursday -> Monday = 0
        n = len(days) + 2 * int(np.sum(wd == (self.sw3 - 1)))
        return n


def book(P, K, ex, g, thr):
    rows = []
    for p in P.values():
        free = -1
        for i, d, stop in p.signals(K):
            if i <= free or not p.gate(g, i, d, thr):
                continue
            res = p.sim(i, d, stop, ex)
            if res is None:
                continue
            r, rs, j = res
            free = j
            rows.append(dict(sym=p.sym, i=i, d=d, year=int(p.year[i]), per=period(int(p.year[i])), r=r, rs=rs,
                             k=d * (p.o[i + 1] + (p.sp[i + 1] if d == 1 else 0) - stop) / p.atr[i], t_out=p.t[j],
                             stress=r - STRESS_PIP[p.sym] / (d * (p.o[i + 1] + (p.sp[i + 1] if d == 1 else 0) - stop))))
    return pd.DataFrame(rows)


def control(P, real, ex, g, thr, rng, reps=REPS):
    pools = {}
    for p in P.values():
        for y in np.unique(p.year):
            for d in (1, -1):
                idx = np.flatnonzero((p.year == y) & np.isfinite(p.atr))
                idx = idx[(idx > 130) & (idx < len(p.c) - 2)]
                pools[(p.sym, y, d)] = [i for i in idx if p.gate(g, i, d, thr)]
    means = []
    for _ in range(reps):
        rs = []
        for t in real.itertuples():
            pool = pools.get((t.sym, t.year, t.d)) or []
            if not pool:
                continue
            p = P[t.sym]
            i = pool[rng.randrange(len(pool))]
            stop = p.o[i + 1] + (p.sp[i + 1] if t.d == 1 else 0) - t.d * t.k * p.atr[i]
            res = p.sim(i, t.d, stop, ex)
            if res is not None:
                rs.append(res[0])
        means.append(np.mean(rs) if rs else np.nan)
    return np.array(means)


def lower90(x, runs=4000, seed=124):
    rng = np.random.default_rng(seed)
    return float(np.quantile(rng.choice(x, (runs, len(x))).mean(1), 0.10))


def curve(x, risk):
    x = x.sort_values("t_out")
    eq = np.cumsum(x["r"].to_numpy()) * risk
    dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    years = (x["t_out"].max() - x["t_out"].min()) / (365.25 * 86400)
    return eq[-1] / years, dd


def max_neg_run(byyear):
    best = cur = 0
    for v in byyear:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def main():
    meta = json.load(open(DATA / "meta.json"))
    P = {s: Pair(s, meta[s]) for s in PAIRS}
    er_train = np.concatenate([p.d1_er_train for p in P.values()])
    er_train = er_train[np.isfinite(er_train)]
    thr = {"G2": float(np.median(er_train)), "G3": float(np.quantile(er_train, 2 / 3))}
    print("ER60 thresholds (train):", {k: round(v, 3) for k, v in thr.items()}, flush=True)
    rng = random.Random(124)
    rows, books = [], {}
    for K, ex, g in itertools.product(KS, EXITS, GATES):
        b = book(P, K, ex, g, thr)
        books[(K, ex, g)] = b
        row = dict(K=K, exit=ex, gate=g, role="variant" if g in VARIANT_GATES else "control")
        for p in ("train", "validate"):
            x = b[b.per == p]
            row[f"{p[:3]}_n"], row[f"{p[:3]}_R"] = len(x), x.r.mean()
            row[f"{p[:3]}_buy"], row[f"{p[:3]}_sell"] = x.r[x.d == 1].mean(), x.r[x.d == -1].mean()
            row[f"{p[:3]}_Rswap"] = x.rs.mean()
            row[f"{p[:3]}_Rstress"] = x.stress.mean()
        tv = b[b.per.isin(("train", "validate"))]
        row["tv_low90"] = lower90(tv.r.to_numpy()) if len(tv) > 10 else np.nan
        by_year = tv.groupby("year").r.sum().reindex(range(2010, 2023), fill_value=0.0)
        row["neg_run"] = max_neg_run(by_year.to_numpy())
        share = tv.groupby("sym").r.sum()
        row["top_pair_share"] = float(share.max() / share[share > 0].sum()) if (share > 0).any() else np.nan
        row["by_pair"] = " ".join(f"{s[:3]}{s[3:4]}:{v:+.0f}" for s, v in share.items())
        if g in VARIANT_GATES:
            x = b[b.per == "validate"]
            ctl = control(P, x, ex, g, thr, rng)
            row["val_ctl"], row["val_p"] = float(np.nanmedian(ctl)), float(np.nanmean(ctl >= x.r.mean()))
        rows.append(row)
        print(K, ex, g, f"tra {row['tra_n']}/{row['tra_R']:+.3f} val {row['val_n']}/{row['val_R']:+.3f}", flush=True)
    T = pd.DataFrame(rows)
    # criteria
    def ctl_R(K, ex, g, per):
        return T[(T.K == K) & (T.exit == ex) & (T.gate == g)][f"{per}_R"].iat[0]
    passed = []
    for i, r in T[T.role == "variant"].iterrows():
        c1 = r.tra_R > 0 and r.val_R > 0 and r.tv_low90 > 0
        c2 = all(r[f"{p}_R"] > ctl_R(r.K, r.exit, g, p) for g in ("G0", "G1") for p in ("tra", "val"))
        c3 = r.val_p < 0.10
        c4 = r.neg_run <= 2 and r.top_pair_share <= 0.5
        T.loc[i, "c1"], T.loc[i, "c2"], T.loc[i, "c3"], T.loc[i, "c4"] = c1, c2, c3, c4
        if c1 and c2 and c3 and c4:
            passed.append((min(r.tra_R, r.val_R), r.K, r.exit, r.gate))
    T.to_csv(HERE / "out" / "g124_r1.csv", index=False)
    pd.set_option("display.width", 280)
    pd.set_option("display.max_colwidth", 60)
    print(T.round(3).to_string(index=False))
    for k in sorted(books):
        x = books[k]
        x = x[x.per.isin(("train", "validate"))]
        print(k, "by year:", " ".join(f"{y}:{v:+.1f}" for y, v in x.groupby("year").r.sum().items()))
    if not passed:
        print("\nNo variant passes -> test 2023..2026 stays sealed.")
        return
    _, K, ex, g = max(passed)
    print(f"\nSelected: K{K} {ex} {g}. Opening the test 2023..10/2026 once.")
    for gg in (g, "G0", "G1"):
        b = books[(K, ex, gg)]
        x = b[b.per == "test"]
        line = (f"  {gg}: test {len(x)} trades  R {x.r.mean():+.3f}  with swap {x.rs.mean():+.3f}  +1 pip {x.stress.mean():+.3f}  win {np.mean(x.r > 0):.0%}  "
                f"buy {x.r[x.d == 1].mean():+.3f} sell {x.r[x.d == -1].mean():+.3f}")
        if gg == g:
            ctl = control(P, x, ex, g, thr, rng)
            line += f"  random {np.nanmedian(ctl):+.3f} p {np.nanmean(ctl >= x.r.mean()):.3f}  low90 {lower90(x.r.to_numpy()):+.3f}"
        print(line)
    b = books[(K, ex, g)]
    for p in ("train", "validate", "test"):
        x = b[b.per == p]
        for risk in (0.5, 1.0):
            yr, dd = curve(x, risk)
            print(f"  {p} @{risk}%: {yr:+.1f}%/yr  DD {dd:.1f}%")
    x = b[b.per == "test"]
    print("  test by year:", " ".join(f"{y}:{v:+.1f}" for y, v in x.groupby("year").r.sum().items()))
    print("  test by pair:", " ".join(f"{s}:{len(v)}/{v.r.mean():+.2f}" for s, v in x.groupby("sym")))
    b.to_csv(HERE / "out" / "g124_r1_trades.csv", index=False)


if __name__ == "__main__":
    main()
