"""G125 V1b: small M5 follower trades inside open S07 legs (plan docs/superpowers/plans/2026-10-15-g125-v1b-s07-followers.md).

  python g125_s07_followers.py   -> 8 variants on train / validate with N0 and random-direction controls,
                                    then the sealed 2026 test once for the selected variant, alone and with S07

Context: at least one S07 leg open in direction d (G89/G107 port). Entries on tick-built M5 bars:
  PB   previous close on the other side of EMA21(M5), this close back on the d side
  SCH  the first M5 bar of every hour (signal at the :55 close)
Stop = entry - d x s x ATR14(M5) (s 1.0 / 1.5); TP 2R / 3R; closed when no S07 leg is open in d any more, or after
48 bars. One trade at a time. Costs: bar spread; stress +$0.20 per trade.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g125_s07_mini as v1
from g97_forming_bar import ema

HERE = v1.HERE
PER = v1.PER["M5"]
ENTRIES, TPS, STOPS = ("PB", "SCH"), (2.0, 3.0), (1.0, 1.5)
CAP, REPS, STRESS = 48, 200, 0.20
CAPITAL = 10_000.0


class Followers(v1.TF):
    def __init__(self):
        super().__init__("M5", {})
        self.e21 = ema(self.c, 21)
        self.minute = self.ts.minute.to_numpy()
        self.ctx = {d: self.s07[d] > 0 for d in (1, -1)}

    def signals(self, kind, with_ctx=True, rng=None):
        out = []
        c, e = self.c, self.e21
        for i in range(250, len(c) - 2):
            if kind == "PB":
                if c[i - 1] < e[i - 1] and c[i] > e[i]:
                    d = 1
                elif c[i - 1] > e[i - 1] and c[i] < e[i]:
                    d = -1
                else:
                    continue
            else:
                if self.minute[i] != 55:
                    continue
                if with_ctx:
                    d = 1 if self.ctx[1][i] else (-1 if self.ctx[-1][i] else 0)
                    if d == 0:
                        continue
                else:
                    d = rng.choice((-1, 1))
            if with_ctx and not self.ctx[d][i]:
                continue
            out.append((i, d))
        return out

    def run(self, i, d, s, tp_r, ctx_d=None):
        o, h, l, c, sp, a = self.o, self.h, self.l, self.c, self.sp, self.atr
        e = i + 1
        if not np.isfinite(a[i]) or a[i] <= 0:
            return None
        entry = o[e] + (sp[e] if d == 1 else 0.0)
        R = s * a[i]
        stop, tp = entry - d * R, entry + d * tp_r * R
        end = min(len(c) - 1, e + CAP)
        for j in range(e, end + 1):
            if j > e and ((d == 1 and o[j] <= stop) or (d == -1 and o[j] + sp[j] >= stop)):
                return d * (o[j] + (sp[j] if d == -1 else 0.0) - entry) / R, R, j
            if (d == 1 and l[j] <= stop) or (d == -1 and h[j] + sp[j] >= stop):
                return -1.0, R, j
            if (d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp):
                return tp_r, R, j
            if ctx_d is not None and not self.ctx[ctx_d][j]:
                break
            if j == end:
                break
        px = c[j] + (sp[j] if d == -1 else 0.0)
        return d * (px - entry) / R, R, j

    def book(self, sigs, s, tp_r, with_ctx=True, flip=None):
        rows, free = [], -1
        for n, (i, d) in enumerate(sigs):
            if i <= free:
                continue
            dd = d if flip is None else flip[n]
            res = self.run(i, dd, s, tp_r, ctx_d=d if with_ctx else None)
            if res is None:
                continue
            r, R, j = res
            free = j
            rows.append(dict(n=n, i=i, d=dd, r=r, stress=r - STRESS / R, t_in=self.t[i + 1], t_out=self.t[j] + 300))
        return pd.DataFrame(rows)


def per_of(F, b):
    out = np.array([None] * len(b), object)
    for p in ("train", "validate", "test"):
        out[F.mask(p)[b.i.to_numpy()]] = p
    return out


def lower90(x, runs=4000, seed=1251):
    rng = np.random.default_rng(seed)
    return float(np.quantile(rng.choice(x, (runs, len(x))).mean(1), 0.10))


def usd_curve(events):
    """events: DataFrame(t_out, usd) -> total, max drawdown (USD, closed trades), worst calendar month."""
    e = events.sort_values("t_out")
    eq = CAPITAL + np.cumsum(e["usd"].to_numpy())
    dd = float((np.maximum.accumulate(np.r_[CAPITAL, eq])[1:] - eq).max())
    month = e.groupby(pd.to_datetime(e["t_out"], unit="s").dt.to_period("M"))["usd"].sum()
    return eq[-1] - CAPITAL, dd, month.min()


def main():
    F = Followers()
    rng = np.random.default_rng(1250)
    print(f"M5 bars {len(F.t)}; S07 buy context {F.ctx[1].mean():.0%} of bars, sell {F.ctx[-1].mean():.0%}", flush=True)
    rows, books = [], {}
    for kind, tp_r, s in itertools.product(ENTRIES, TPS, STOPS):
        sigs = F.signals(kind)
        b = F.book(sigs, s, tp_r)
        b["per"] = per_of(F, b)
        books[(kind, tp_r, s)] = (sigs, b)
        n0_sigs = F.signals(kind, with_ctx=False, rng=np.random.default_rng(7))
        n0 = F.book(n0_sigs, s, tp_r, with_ctx=False)
        n0["per"] = per_of(F, n0)
        row = dict(entry=kind, tp=tp_r, stop=s)
        for p in ("train", "validate"):
            x, y = b[b.per == p], n0[n0.per == p]
            a, z = PER[p]
            weeks = (pd.Timestamp(z) - pd.Timestamp(a)).days / 7
            row[f"{p[:3]}_n"], row[f"{p[:3]}_wk"], row[f"{p[:3]}_R"] = len(x), len(x) / weeks, x.r.mean()
            row[f"{p[:3]}_buy"], row[f"{p[:3]}_sell"] = x.r[x.d == 1].mean(), x.r[x.d == -1].mean()
            row[f"{p[:3]}_stress"], row[f"{p[:3]}_N0"] = x.stress.mean(), y.r.mean()
        tv = b[b.per.isin(("train", "validate"))]
        row["tv_low90"] = lower90(tv.r.to_numpy())
        # random direction at the same entry bars (validate)
        vs = [(i, d) for (i, d) in sigs if F.mask("validate")[i]]
        rd = []
        for _ in range(REPS):
            flip = rng.choice((-1, 1), len(vs))
            x = F.book(vs, s, tp_r, flip=flip)
            rd.append(x.r.mean())
        rd = np.array(rd)
        row["val_RD"], row["val_p"] = float(np.median(rd)), float(np.mean(rd >= row["val_R"]))
        c1 = row["tra_R"] > 0 and row["val_R"] > 0 and row["tv_low90"] > 0
        c2 = row["tra_R"] > row["tra_N0"] and row["val_R"] > row["val_N0"]
        c3 = row["val_p"] < 0.10
        c4 = min(row["tra_buy"], row["tra_sell"], row["val_buy"], row["val_sell"]) >= -0.05 and row["tra_stress"] > 0 and row["val_stress"] > 0
        row.update(c1=c1, c2=c2, c3=c3, c4=c4, passed=c1 and c2 and c3 and c4)
        rows.append(row)
        print(kind, tp_r, s, f"tra {row['tra_n']}/{row['tra_R']:+.3f} val {row['val_n']}/{row['val_R']:+.3f} RD {row['val_RD']:+.3f} p {row['val_p']:.2f}", flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "out" / "g125_v1b.csv", index=False)
    pd.set_option("display.width", 300)
    print(T.round(3).to_string(index=False))
    ok = T[T.passed]
    if ok.empty:
        print("\nNo variant passes -> 2026 stays sealed.")
        return
    best = ok.assign(m=np.minimum(ok.tra_R, ok.val_R)).sort_values("m").iloc[-1]
    kind, tp_r, s = best.entry, best.tp, best.stop
    sigs, b = books[(kind, tp_r, s)]
    x = b[b.per == "test"]
    print(f"\nSelected {kind} TP{tp_r:g}R stop {s:g} ATR. Opening 2026 once.")
    ts_ = [(i, d) for (i, d) in sigs if F.mask("test")[i]]
    rd = np.array([F.book(ts_, s, tp_r, flip=rng.choice((-1, 1), len(ts_))).r.mean() for _ in range(REPS)])
    n0 = F.book(F.signals(kind, with_ctx=False, rng=np.random.default_rng(7)), s, tp_r, with_ctx=False)
    n0 = n0[per_of(F, n0) == "test"]
    weeks = (x.t_out.max() - x.t_in.min()) / (7 * 86400)
    print(f"  test: {len(x)} trades ({len(x) / weeks:.1f}/week)  R {x.r.mean():+.3f}  low90 {lower90(x.r.to_numpy()):+.3f}  "
          f"win {np.mean(x.r > 0):.0%}  stress {x.stress.mean():+.3f}  buy {len(x[x.d == 1])}/{x.r[x.d == 1].mean():+.3f}  "
          f"sell {len(x[x.d == -1])}/{x.r[x.d == -1].mean():+.3f}  RD {np.median(rd):+.3f} p {np.mean(rd >= x.r.mean()):.3f}  "
          f"N0 {len(n0)}/{n0.r.mean():+.3f}")
    print("  test by month R:", " ".join(f"{k}:{v:+.1f}" for k, v in x.groupby(pd.to_datetime(x.t_in, unit='s').dt.strftime('%m')).r.sum().items()))
    # with S07 on 10k: S07 1.5% x weight, followers 0.25% per trade
    L = F.legs
    L = L.assign(t_out_s=(L.t_out - pd.Timestamp(0)).dt.total_seconds(), usd=L.r * L.money)
    for p in ("train+validate", "test"):
        pp = ("train", "validate") if p != "test" else ("test",)
        y = b[b.per.isin(pp)]
        y = y.assign(t_in=v1.srv_to_utc(y.t_in), t_out=v1.srv_to_utc(y.t_out))     # S07 legs are in UTC
        a, z = y.t_in.min(), y.t_out.max()
        s07 = L[(L.t_out_s >= a) & (L.t_out_s <= z)][["t_out_s", "usd"]].rename(columns={"t_out_s": "t_out"})
        fol = pd.DataFrame({"t_out": y.t_out, "usd": y.r * CAPITAL * 0.0025})
        for name, ev in (("S07 alone", s07), ("followers alone @0.25%", fol), ("S07 + followers", pd.concat([s07, fol]))):
            tot, dd, wm = usd_curve(ev)
            print(f"  {p:15s} {name:24s} {tot:+10,.0f} USD  DD {dd:8,.0f} USD ({100 * dd / CAPITAL:.1f}% of 10k)  worst month {wm:+,.0f}")
    b.to_csv(HERE / "out" / "g125_v1b_trades.csv", index=False)


if __name__ == "__main__":
    main()
