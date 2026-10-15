"""G105: open the sealed test 07/2025-06/2026 once (plan docs/superpowers/plans/2026-10-11-g105-test-open.md).

  python g105_test_open.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g98_context as g98
import g100_user_rule as u
from g104_liquidity_tp import Liq

TEST = ("2025-07-01", "2026-07-01")
EXAM = ("2026-07-01", "2027-01-01")


def run_cfg(Q, d, i, cfg):
    kind, arg = cfg
    if kind == "TP":                       # BOX hold + target (G104)
        tgt, mode = arg
        res = Q.run_tp(i, d, tgt, mode)
        if res is None:
            return None
        r, jx, why, _, _ = res
        return r, jx, why
    meth, adds = arg                       # G103 hold
    res = Q.run(i, d, meth, adds)
    if res is None:
        return None
    tot, _, jx, _, why, _ = res
    return tot, jx, why


def book(Q, m, d, mask, cfg):
    rows, free = [], 0
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = run_cfg(Q, d, i, cfg)
        if res is None:
            continue
        r, jx, why = res
        rows.append((m["ts"].iat[i], r, why, (jx - i) / 96))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "r", "why", "days"])


def window(t, a, b):
    return t[(t["t"] >= a) & (t["t"] < b)]


def summary(x):
    if x.empty:
        return "n 0"
    eq = x["r"].cumsum().to_numpy()
    dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    return (f"n {len(x)}  R/trade {x['r'].mean():+.3f}  total {x['r'].sum():+.1f}R  win {(x['r'] > 0).mean():.0%}  "
            f">=10R {(x['r'] >= 10).sum()}  maxDD {dd:.1f}R  best {x['r'].max():+.1f}R")


def main():
    m, H = g98.prepare()
    Q = Liq(m, H)
    ts = m["ts"]
    rng = np.random.default_rng(105)
    plan = {
        -1: (("TP", ("ORG", "FULL")), 30,
             {"BOX no TP": ("TP", ("NONE", "FULL")), "BOX + ORG half": ("TP", ("ORG", "HALF")),
              "BOX + D1S half": ("TP", ("D1S", "HALF"))}),
        1: (("HOLD", ("BOX", True)), 60,
            {"BOX no adds": ("HOLD", ("BOX", False)), "SW2 + adds": ("HOLD", ("SW2", True)),
             "BOX + ORG half": ("TP", ("ORG", "HALF"))}),
    }
    for d in (-1, 1):
        name = "SELL" if d == -1 else "BUY"
        cfg, min_n, neigh = plan[d]
        mk, ctx = u.masks(m, d)
        in_test = ((ts >= TEST[0]) & (ts < TEST[1])).to_numpy()
        in_exam = (ts >= EXAM[0]).to_numpy()
        t_all = book(Q, m, d, mk["V2"] & (in_test | in_exam), cfg)
        tt = window(t_all, *TEST)
        print(f"\n===== {name} {cfg} =====")
        print("TEST 07/2025-06/2026:", summary(tt))
        print("EXAM 07/2026-10/2026:", summary(window(t_all, *EXAM)))
        if not tt.empty:
            mon = tt.groupby(tt["t"].dt.to_period("M"))["r"].agg(["size", "sum"]).round(1)
            print("by month (n, R):", {str(k): (int(v["size"]), v["sum"]) for k, v in mon.iterrows()})
            print("exit reasons:", tt["why"].value_counts().to_dict())
        # control
        pool = np.flatnonzero(ctx & in_test)
        dens = (mk["V2"] & in_test).sum() / max(len(pool), 1)
        sims = []
        for _ in range(100):
            pick = np.zeros(len(m), bool)
            pick[pool[rng.random(len(pool)) < dens]] = True
            x = window(book(Q, m, d, pick, cfg), *TEST)
            sims.append(x["r"].mean() if len(x) else np.nan)
        sims = np.array(sims)
        real = tt["r"].mean() if len(tt) else np.nan
        p = float(np.nanmean(sims >= real))
        print(f"random-entry control: median R/trade {np.nanmedian(sims):+.3f}, p {p:.3f}")
        pos = 0
        for nm, c in neigh.items():
            x = window(book(Q, m, d, mk["V2"] & in_test, c), *TEST)
            pos += int(len(x) > 0 and x["r"].mean() > 0)
            print(f"  neighbour {nm}: {summary(x)}")
        c1 = len(tt) >= min_n and real > 0
        c2 = p < 0.10
        c3 = pos >= 2
        print(f"criteria: R>0 with n>={min_n}: {c1} | control p<0.10: {c2} | neighbours {pos}/3 >= 2: {c3} -> "
              f"{'PASS' if (c1 and c2 and c3) else 'FAIL'}")
        for lab, a, b in (("03/03/2026", "2026-03-03", "2026-03-04"), ("12/03/2026", "2026-03-12", "2026-03-13")):
            x = t_all[(t_all["t"] >= a) & (t_all["t"] < b)]
            if len(x):
                print(f"  user example {lab}: " + "; ".join(f"{r.t:%H:%M} {r.r:+.1f}R ({r.why}, {r.days:.0f}d)"
                                                          for r in x.itertuples()))


if __name__ == "__main__":
    main()
