"""G125 V2: gold session-range OCO breakouts (plan docs/superpowers/plans/2026-10-16-g125-v2-session-oco.md).

  python g125_session_oco.py   -> 6 variants + F0 controls on train / validate, random-window control,
                                  then the sealed 2026 test once for the selected variant, alone and with S07 + VHedge G119

M15 bars, server time. Range sessions: A 01:00-09:00 (orders 09:00-17:00), L 10:00-11:00 (11:00-17:00),
N 16:30-17:30 (17:30-23:00). Buy stop at the range high + 0.1 ATR14(M15), sell stop at the low - 0.1 ATR; OCO (a bar
that reaches both levels counts as -1R); stop at the range middle; TP 2R / 3R; open trades closed at 23:00.
F1 = range width / ATR14(D1, previous day) <= the train median of that session. Costs: bar spread; stress +$0.20.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from g97_forming_bar import dmi

HERE = __import__("pathlib").Path(__file__).resolve().parent
PER = {"train": ("2021-08-01", "2025-01-01"), "validate": ("2025-01-01", "2026-01-01"), "test": ("2026-01-01", "2027-01-01")}
SESS = {"A": (60, 540, 1020), "L": (600, 660, 1020), "N": (990, 1050, 1380)}     # minutes: range start, range end, orders end
CUT = 1380                                                                       # 23:00 server
TPS, REPS, STRESS = (2.0, 3.0), 200, 0.20


class Data:
    def __init__(self):
        m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
        m["sp"] = m["spread"] * 0.01
        self.t = m["time"].to_numpy()
        self.o, self.h, self.l, self.c, self.sp = (m[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
        _, _, _, self.atr = dmi(self.h, self.l, self.c)
        self.day = self.t // 86400
        self.tod = (self.t % 86400) // 60
        D = m.assign(day=self.day).groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
        _, _, _, atr_d = dmi(D["high"].to_numpy(), D["low"].to_numpy(), D["close"].to_numpy())
        self.atr_d1_prev = dict(zip(D.index.to_numpy(), np.r_[np.nan, atr_d[:-1]]))
        self.days = {d: np.flatnonzero(self.day == d) for d in D.index.to_numpy()}

    def period(self, day):
        ts = pd.Timestamp(int(day) * 86400, unit="s")
        for p, (a, b) in PER.items():
            if pd.Timestamp(a) <= ts < pd.Timestamp(b):
                return p
        return None

    def oco(self, idx, r0, r1, o1, cut, tp_r):
        """idx: bar indices of one day. Range [r0, r1) minutes, orders [r1, o1), exit by cut. -> dict or None."""
        tod = self.tod[idx]
        rng = idx[(tod >= r0) & (tod < r1)]
        if len(rng) < 0.8 * (r1 - r0) / 15:
            return None
        hi, lo = self.h[rng].max(), self.l[rng].min()
        a = self.atr[rng[-1]]
        if not np.isfinite(a):
            return None
        width = hi - lo
        B, S, mid = hi + 0.1 * a, lo - 0.1 * a, 0.5 * (hi + lo)
        act = idx[(tod >= r1) & (tod < o1)]
        hold = idx[(tod >= r1) & (tod < cut)]
        if len(act) == 0:
            return None
        trig = None
        for j in act:
            bu = self.h[j] + self.sp[j] >= B
            bd = self.l[j] <= S
            if bu and bd:
                return dict(d=0, r=-1.0, stress=-1.0, width=width, R=np.nan, j=j)
            if bu or bd:
                trig = (j, 1 if bu else -1)
                break
        if trig is None:
            return dict(d=None, width=width)                                       # no fill
        j, d = trig
        sp = self.sp
        if d == 1:
            entry = max(B, self.o[j] + sp[j])
        else:
            entry = min(S, self.o[j])
        stop = mid
        R = d * (entry - stop)
        if R <= 0:
            return None
        tp = entry + d * tp_r * R
        if (d == 1 and self.l[j] <= stop) or (d == -1 and self.h[j] + sp[j] >= stop):   # same bar back to the middle
            return dict(d=d, r=-1.0, stress=-1.0 - STRESS / R, width=width, R=R, j=j)
        rest = hold[hold > j]
        for k in rest:
            if (d == 1 and self.o[k] <= stop) or (d == -1 and self.o[k] + sp[k] >= stop):
                r = d * (self.o[k] + (sp[k] if d == -1 else 0) - entry) / R
                return dict(d=d, r=r, stress=r - STRESS / R, width=width, R=R, j=k)
            if (d == 1 and self.l[k] <= stop) or (d == -1 and self.h[k] + sp[k] >= stop):
                return dict(d=d, r=-1.0, stress=-1.0 - STRESS / R, width=width, R=R, j=k)
            if (d == 1 and self.h[k] >= tp) or (d == -1 and self.l[k] + sp[k] <= tp):
                return dict(d=d, r=tp_r, stress=tp_r - STRESS / R, width=width, R=R, j=k)
        k = rest[-1] if len(rest) else j
        r = d * (self.c[k] + (sp[k] if d == -1 else 0) - entry) / R
        return dict(d=d, r=r, stress=r - STRESS / R, width=width, R=R, j=k)


def book(D, s, tp_r, thr=None):
    r0, r1, o1 = SESS[s]
    rows = []
    for day, idx in D.days.items():
        p = D.period(day)
        if p is None:
            continue
        res = D.oco(idx, r0, r1, o1, CUT, tp_r)
        if res is None or res["d"] is None:
            continue
        a1 = D.atr_d1_prev.get(day, np.nan)
        rel = res["width"] / a1 if np.isfinite(a1) and a1 > 0 else np.nan
        if thr is not None and not (rel <= thr):
            continue
        rows.append(dict(day=day, per=p, d=res["d"], r=res["r"], stress=res["stress"], rel=rel,
                         t_out=int(D.t[res["j"]]) + 900))
    return pd.DataFrame(rows)


def widths(D, s):
    r0, r1, _ = SESS[s]
    out = []
    for day, idx in D.days.items():
        if D.period(day) != "train":
            continue
        tod = D.tod[idx]
        rng = idx[(tod >= r0) & (tod < r1)]
        a1 = D.atr_d1_prev.get(day, np.nan)
        if len(rng) >= 0.8 * (r1 - r0) / 15 and np.isfinite(a1) and a1 > 0:
            out.append((D.h[rng].max() - D.l[rng].min()) / a1)
    return np.array(out)


def control(D, s, tp_r, thr, days, rng):
    r0, r1, o1 = SESS[s]
    L_rng, L_act, L_hold = r1 - r0, o1 - r1, CUT - r1
    starts = np.arange(0, CUT - L_rng - 60, 15)
    means = []
    for _ in range(REPS):
        rs = []
        for day in days:
            idx = D.days[day]
            a1 = D.atr_d1_prev.get(day, np.nan)
            for _try in range(20):
                st = int(rng.choice(starts))
                q1 = st + L_rng
                res = D.oco(idx, st, q1, min(q1 + L_act, CUT), min(q1 + L_hold, CUT), tp_r)
                if res is None:
                    continue
                if not (np.isfinite(a1) and res["width"] / a1 <= thr):
                    continue
                if res["d"] is not None:
                    rs.append(res["r"])
                break
        means.append(np.mean(rs) if rs else np.nan)
    return np.array(means)


def lower90(x, runs=4000, seed=1252):
    g = np.random.default_rng(seed)
    return float(np.quantile(g.choice(x, (runs, len(x))).mean(1), 0.10))


def main():
    D = Data()
    rng = np.random.default_rng(1253)
    thr = {s: float(np.median(widths(D, s))) for s in SESS}
    print("F1 thresholds (range / ATR D1, train median):", {k: round(v, 3) for k, v in thr.items()}, flush=True)
    rows, books = [], {}
    for s, tp_r in itertools.product(SESS, TPS):
        b1, b0 = book(D, s, tp_r, thr[s]), book(D, s, tp_r)
        books[(s, tp_r)] = b1
        row = dict(session=s, tp=tp_r)
        for p in ("train", "validate"):
            x, y = b1[b1.per == p], b0[b0.per == p]
            weeks = (pd.Timestamp(PER[p][1]) - pd.Timestamp(PER[p][0])).days / 7
            row[f"{p[:3]}_n"], row[f"{p[:3]}_wk"], row[f"{p[:3]}_R"] = len(x), len(x) / weeks, x.r.mean()
            row[f"{p[:3]}_buy"], row[f"{p[:3]}_sell"] = x.r[x.d == 1].mean(), x.r[x.d == -1].mean()
            row[f"{p[:3]}_both"] = (x.d == 0).mean()
            row[f"{p[:3]}_stress"], row[f"{p[:3]}_F0"] = x.stress.mean(), y.r.mean()
        tv = b1[b1.per.isin(("train", "validate"))]
        row["tv_low90"] = lower90(tv.r.to_numpy())
        vd = b1[b1.per == "validate"].day.to_numpy()
        ctl = control(D, s, tp_r, thr[s], vd, rng)
        row["val_ctl"], row["val_p"] = float(np.nanmedian(ctl)), float(np.nanmean(ctl >= row["val_R"]))
        c1 = row["tra_R"] > 0 and row["val_R"] > 0 and row["tv_low90"] > 0
        c2 = row["tra_R"] > row["tra_F0"] and row["val_R"] > row["val_F0"]
        c3 = row["val_p"] < 0.10
        c4 = min(row["tra_buy"], row["tra_sell"], row["val_buy"], row["val_sell"]) >= -0.05 and row["tra_stress"] > 0 and row["val_stress"] > 0
        row.update(c1=c1, c2=c2, c3=c3, c4=c4, passed=c1 and c2 and c3 and c4)
        rows.append(row)
        print(s, tp_r, f"tra {row['tra_n']}/{row['tra_R']:+.3f} (F0 {row['tra_F0']:+.3f}) val {row['val_n']}/{row['val_R']:+.3f} "
              f"(F0 {row['val_F0']:+.3f}) ctl {row['val_ctl']:+.3f} p {row['val_p']:.2f}", flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "out" / "g125_v2.csv", index=False)
    pd.set_option("display.width", 300)
    print(T.round(3).to_string(index=False))
    for (s, tp_r), b in books.items():
        x = b[b.per.isin(("train", "validate"))]
        print(s, tp_r, "by year R:", " ".join(f"{y}:{v:+.1f}" for y, v in
                                                x.groupby(pd.to_datetime(x.day * 86400, unit="s").dt.year).r.sum().items()))
    ok = T[T.passed]
    if ok.empty:
        print("\nNo variant passes -> 2026 stays sealed.")
        return
    best = ok.assign(m=np.minimum(ok.tra_R, ok.val_R)).sort_values("m").iloc[-1]
    s, tp_r = best.session, best.tp
    b = books[(s, tp_r)]
    x = b[b.per == "test"]
    print(f"\nSelected session {s} TP{tp_r:g}R F1. Opening 2026 once.")
    ctl = control(D, s, tp_r, thr[s], x.day.to_numpy(), rng)
    b0 = book(D, s, tp_r)
    b0 = b0[b0.per == "test"]
    print(f"  test: {len(x)} trades  R {x.r.mean():+.3f}  low90 {lower90(x.r.to_numpy()):+.3f}  win {np.mean(x.r > 0):.0%}  "
          f"stress {x.stress.mean():+.3f}  buy {x.r[x.d == 1].mean():+.3f} sell {x.r[x.d == -1].mean():+.3f}  "
          f"random {np.nanmedian(ctl):+.3f} p {np.nanmean(ctl >= x.r.mean()):.3f}  F0 {len(b0)}/{b0.r.mean():+.3f}")
    print("  test by month R:", " ".join(f"{k}:{v:+.1f}" for k, v in x.groupby(pd.to_datetime(x.day * 86400, unit='s').dt.strftime('%m')).r.sum().items()))
    b.to_csv(HERE / "out" / "g125_v2_trades.csv", index=False)


if __name__ == "__main__":
    main()
