"""G138 on the PC, step 1d: G134 part 1 (S07 legs against the D1 SMA state x 1 / x 0.5 / x 0 on the G89 book, MAR per
period) repeated with three D1 definitions:
  a  as G134: server days of data/m30v, SMA 50/200 (the EA's broker D1 bars: 5 a week, checked in g138_pc_checks.py)
  b  server days with Sunday bars merged into Monday (only 2010-2012 have Sunday bars on the PC data)
  c  server days, SMA 42/167 (the calendar span of 50/200 six-day bins)
Same book, weights, compounding and periods as g134_extensions.part1; nothing else changed.

Usage: g138_g134_part1.py <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g134_extensions as g134  # noqa: E402


def d1_state(variant):
    m = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
    day = m["time"] // 86400
    n1, n2 = 50, 200
    if variant == "b":
        day = day + ((day + 3) % 7 == 6)          # (day + 3) % 7: Monday 0 ... Sunday 6 -> Sunday joins Monday
    if variant == "c":
        n1, n2 = 42, 167
    D = m.assign(day=day).groupby("day")["close"].last()
    s1, s2 = D.rolling(n1).mean(), D.rolling(n2).mean()
    return dict(zip(D.index.to_numpy(), np.sign((s1 - s2).fillna(0).to_numpy())))


PER = [("Train 03/2018–2021", g134.ts("2018-03-05"), g134.ts("2022-01-01")),
       ("Validate 2022–2025", g134.ts("2022-01-01"), g134.ts("2026-01-01")),
       ("2026", g134.ts("2026-01-01"), g134.ts("2026-10-10"))]


def run(legs, variant):
    st = d1_state(variant)
    days = np.array(sorted(st))
    for x in legs:
        k = np.searchsorted(days, x["s_in"] // 86400, side="left") - 1          # last completed server day (as G134)
        x["aligned"] = bool(k >= 0 and st[days[k]] == x["d"])
    out = {}
    for name, wmul in (("x1", 1.0), ("x0.5", 0.5), ("x0", 0.0)):
        L_ = [dict(t_in=x["s_in"], t_out=x["s_in"] + (x["u_out"] - x["u_in"]), r=x["r"],
                   risk=0.015 * x["w"] * (1.0 if x["aligned"] else wmul)) for x in legs]
        out[name] = {p: dict(zip(("cagr", "dd", "mar", "n"), g134.sim(L_, a, b))) for p, a, b in PER}
    out["share_aligned_from_2018_03"] = round(float(np.mean([x["aligned"] for x in legs if x["s_in"] >= g134.ts("2018-03-05")])), 4)
    out["keep_x0.5"] = all(out["x0.5"][p]["mar"] >= out["x1"][p]["mar"] for p, _, _ in PER)
    # R of the legs with / against D1 per period (context for the MAR table)
    out["r_by_state"] = {}
    for p, a, b in PER:
        seg = [x for x in legs if a <= x["s_in"] < b]
        w = [x["r"] for x in seg if x["aligned"]]
        ag = [x["r"] for x in seg if not x["aligned"]]
        out["r_by_state"][p] = {"cùng": [len(w), round(float(np.mean(w)), 3) if w else None],
                                "ngược": [len(ag), round(float(np.mean(ag)), 3) if ag else None]}
    return out


def main():
    legs = g134.s07_legs()
    base = [dict(x) for x in legs]
    res = {"legs": len(legs)}
    flips = {}
    for v in ("a", "b", "c"):
        rows = [dict(x) for x in base]
        res[v] = run(rows, v)
        flips[v] = [x["aligned"] for x in rows]
        print(v, json.dumps({k: res[v][k] for k in ("share_aligned_from_2018_03", "keep_x0.5")}),
              {n: {p: round(c["mar"], 2) for p, c in res[v][n].items()} for n in ("x1", "x0.5", "x0")}, flush=True)
    res["flip_vs_a"] = {v: round(float(np.mean(np.array(flips[v]) != np.array(flips["a"]))), 4) for v in ("b", "c")}
    Path(sys.argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
