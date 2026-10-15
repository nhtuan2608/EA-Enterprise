"""G124 R1b: the one-time test 2023..10/2026 of the R1 cell K24 / E1 (TP 3R) / G1 (120-day direction)
(plan docs/superpowers/plans/2026-10-15-g124-r1b-test.md). Run once.

  python g124_r1b_test.py
"""
from __future__ import annotations

import json
import random

import numpy as np

import g124_fx_regime as g

SPLIT = 1760054400                      # 2025-10-10 00:00 UTC


def main():
    meta = json.load(open(g.DATA / "meta.json"))
    P = {s: g.Pair(s, meta[s]) for s in g.PAIRS}
    thr = {"G2": 0.11, "G3": 0.159}                       # unused by G0 / G1
    b = g.book(P, 24, "E1", "G1", thr)
    b0 = g.book(P, 24, "E1", "G0", thr)
    x, x0 = b[b.per == "test"], b0[b0.per == "test"]
    ctl = g.control(P, x, "E1", "G1", thr, random.Random(1241))
    print(f"test K24 E1 G1: {len(x)} trades  R {x.r.mean():+.3f}  low90 {g.lower90(x.r.to_numpy()):+.3f}  "
          f"win {np.mean(x.r > 0):.0%}  +1 pip {x.stress.mean():+.3f}  with swap {x.rs.mean():+.3f}")
    print(f"  buy {len(x[x.d == 1])}/{x.r[x.d == 1].mean():+.3f}  sell {len(x[x.d == -1])}/{x.r[x.d == -1].mean():+.3f}")
    print(f"  random same direction: median {np.nanmedian(ctl):+.3f}  p {np.nanmean(ctl >= x.r.mean()):.3f}")
    print(f"  G0 (no direction filter): {len(x0)} trades  R {x0.r.mean():+.3f}")
    for name, m in (("2023..2025-10-09", x.t_out < SPLIT), ("2025-10-10..", x.t_out >= SPLIT)):
        y = x[m]
        print(f"  {name}: {len(y)} trades  R {y.r.mean():+.3f}")
    for risk in (0.5, 1.0):
        yr, dd = g.curve(x, risk)
        print(f"  @{risk}%/trade: {yr:+.1f}%/yr  DD {dd:.1f}%")
    w, l = x.r[x.r > 0], x.r[x.r <= 0]
    print(f"  PF {w.sum() / -l.sum():.2f}  avg win {w.mean():+.2f}  avg loss {l.mean():+.2f}  "
          f"losing streak {g.max_neg_run(x.sort_values('t_out').r.to_numpy())}")
    print("  by year:", " ".join(f"{yy}:{len(v)}/{v.r.sum():+.1f}R" for yy, v in x.groupby("year")))
    print("  by pair:", " ".join(f"{s}:{len(v)}/{v.r.mean():+.2f}" for s, v in x.groupby("sym")))
    x.to_csv(g.HERE / "out" / "g124_r1b_test_trades.csv", index=False)


if __name__ == "__main__":
    main()
