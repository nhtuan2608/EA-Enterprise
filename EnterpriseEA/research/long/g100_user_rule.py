"""G100: the user's own rule as described (no USD, no extra filters), held by context (no take-profit).

Entry at an M15 close inside an H1 bar (sell; buy mirrored), from g97_forming_bar.conditions():
  V1 strict  C1 close < EMA21 < EMA55 < EMA100 < EMA200, C2 DI gap >= 10, C3 ADX rising,
             C4 last closed H1 below the H1 EMA200, C5 close in the lower half of the forming M30 bar
  V2 early   close below all four EMAs (order not required) + C2 + C3 + C4 + C5
  V3 wick    V1 + C6 upper wick on the forming H1 bar
Management from g98_context.Sim (no target, max 10 days): S07, H1E, SWG, CHD; with / without adds (A1).
Control: entries at random M15 bars that are below all four EMAs with the last H1 below its EMA200
(same count, same management), 40 runs.
Periods: train 07/2021-2023, validate 2024-06/2025; test 07/2025-06/2026 sealed.

  python g100_user_rule.py
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

import g97_forming_bar as g97
import g98_context as g98


def masks(m, d):
    cs = g97.conditions(m, d)
    c = m["close"]
    E = [m[f"e{n}"] for n in (21, 55, 100, 200)]
    beyond = (c < np.minimum.reduce(E)) if d == -1 else (c > np.maximum.reduce(E))
    v1 = cs.inside & cs.C1 & cs.C2 & cs.C3 & cs.C4 & cs.C5
    v2 = cs.inside & beyond & cs.C2 & cs.C3 & cs.C4 & cs.C5
    v3 = v1 & cs.C6
    ctx = cs.inside & beyond & cs.C4
    return {"V1": v1.to_numpy(), "V2": v2.to_numpy(), "V3": v3.to_numpy()}, ctx.to_numpy()


def stats(t, p):
    a, b = g98.PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)].sort_values("t")
    if x.empty:
        return dict(n=0)
    eq = x["r"].cumsum().to_numpy()
    dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    years = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
    return dict(n=len(x), R=x["r"].mean(), win=(x["r"] > 0).mean(), totR=x["r"].sum(), R_per_year=x["r"].sum() / years,
                ddR=dd, big5=int((x["r"] >= 5).sum()), best=x["r"].max(), hold_h=x["bars"].median() / 4)


def main():
    m, H = g98.prepare()
    sim = g98.Sim(m, H)
    lim = (m["ts"] < pd.Timestamp(g98.PERIODS["test"][0])).to_numpy()
    rng = np.random.default_rng(8)
    rows = []
    for d in (-1, 1):
        mk, ctx = masks(m, d)
        for v, mg, ad in itertools.product(("V1", "V2", "V3"), ("S07", "H1E", "SWG", "CHD"), (False, True)):
            t = g98.book(sim, m, d, mk[v] & lim, mg, mk["V2"] & lim, ad)
            row = dict(dir="SELL" if d == -1 else "BUY", rule=v, manage=mg, adds=int(ad))
            for p in g98.OPEN:
                for k, val in stats(t, p).items():
                    row[f"{p[:3]}_{k}"] = val
            # fair random control on mean R (train and validate)
            if mg in ("H1E", "SWG") and not ad:
                pool = np.flatnonzero(ctx & lim)
                dens = (mk[v] & lim).sum() / max(len(pool), 1)
                sims = {p: [] for p in g98.OPEN}
                for _ in range(40):
                    pick = np.zeros(len(m), bool)
                    pick[pool[rng.random(len(pool)) < dens]] = True
                    ts = g98.book(sim, m, d, pick, mg, mk["V2"] & lim, ad)
                    for p in g98.OPEN:
                        sims[p].append(stats(ts, p).get("R", np.nan))
                for p in g98.OPEN:
                    row[f"{p[:3]}_rand_p"] = float((np.array(sims[p]) >= row[f"{p[:3]}_R"]).mean())
            rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv("out/g100_user_rule.csv", index=False)
    pd.set_option("display.width", 280)
    cols = ["dir", "rule", "manage", "adds", "tra_n", "tra_R", "tra_win", "tra_R_per_year", "tra_ddR", "tra_big5", "tra_best",
            "tra_hold_h", "tra_rand_p", "val_n", "val_R", "val_win", "val_R_per_year", "val_ddR", "val_big5", "val_best",
            "val_rand_p"]
    print(t[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
