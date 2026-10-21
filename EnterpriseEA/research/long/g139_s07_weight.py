"""G139 part B: the adviser's confirmation layers as a risk weight on the S07 M30 book (G89 port, both sides).

Baseline = the EA today: 1.5% x EA weight (base without the ordered ribbon 0.67, adds 0.67) x 0.5 for a leg against the D1
state (G134). Score of a base leg = trend + structure + volume + momentum groups of the A5 table (max 70) on the last closed
M30 bar before the entry, in the leg's direction. Threshold = median score of the train-period bases (fixed once).
Variant: bases under the threshold and their adds at x 0.5. Plan: docs/superpowers/plans/2026-10-22-g139-hybrid-setups.md.

Usage: g139_s07_weight.py <data dir> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g89_full_book as fb  # noqa: E402
import g139_hybrid as hy  # noqa: E402
from g134_extensions import YEAR, sim  # noqa: E402

PER = [("train", g.ts(2021, 7, 1), g.ts(2024, 1, 1)), ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
       ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1))]
PERMS = 2000
np.random.seed(139)


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def main():
    root = Path(sys.argv[1])
    g.HERE = root.parent
    clusters = []
    for d in (1, -1):
        bases = []
        for main_, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            bases += fb.base_book(fb.e73.context(main_, sub), d, t0, t1, early=True, re=True)
        clusters += [(d, cl) for cl in fb.attach_adds(bases, fb.add_pool(d))]
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = hy.prepare(g.load("XAUUSD"))
    t = D["t"]
    rows = []
    for d, cl in clusters:
        b = cl[0]
        i = int(np.searchsorted(t, int(b["srv_in"]) - 1800, side="right")) - 1     # last M30 bar closed at the entry
        sc = hy.score(D, i, d, with_pattern=False, with_risk=False) if i > 300 else None
        legs = []
        for j, L in enumerate(cl):
            k = int(np.searchsorted(t, int(L["srv_in"]), side="right")) - 1
            w = (1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD
            w *= 1.0 if D["d1"][k] == d else 0.5
            legs.append(dict(t_in=int(L["ein"]), t_out=int(L["eout"]), r=float(L["rh"]), w=w))
        rows.append(dict(d=d, ein=int(b["ein"]), r=float(b["rh"]), score=sc, legs=legs, p=period(int(b["ein"]))))
    rows = [x for x in rows if x["score"] is not None]
    thr = float(np.median([x["score"] for x in rows if x["p"] == "train"]))
    for x in rows:
        x["high"] = x["score"] >= thr

    def book(mult):
        return [dict(t_in=L["t_in"], t_out=L["t_out"], r=L["r"], risk=0.015 * L["w"] * (1.0 if x["high"] else mult))
                for x in rows for L in x["legs"]]

    def dd_p90(bk):
        a, out = g.ts(2021, 7, 1), []
        while a + YEAR <= g.ts(2026, 7, 1) + 1:
            out.append(sim(bk, a, int(a + YEAR))[1]); a += 30 * 86400
        return float(np.percentile(out, 90))

    res = {"ngưỡng (trung vị train)": thr, "chân gốc": len(rows)}
    res["R chân gốc"] = {}
    for p, _, _ in PER:
        hi = [x["r"] for x in rows if x["p"] == p and x["high"]]
        lo = [x["r"] for x in rows if x["p"] == p and not x["high"]]
        res["R chân gốc"][p] = {"cao": [len(hi), round(float(np.mean(hi)), 3) if hi else None],
                                "thấp": [len(lo), round(float(np.mean(lo)), 3) if lo else None]}
        for side, dd in (("mua", 1), ("bán", -1)):
            hi_ = [x["r"] for x in rows if x["p"] == p and x["high"] and x["d"] == dd]
            lo_ = [x["r"] for x in rows if x["p"] == p and not x["high"] and x["d"] == dd]
            res["R chân gốc"][p][side] = [len(hi_), round(float(np.mean(hi_)), 3) if hi_ else None,
                                          len(lo_), round(float(np.mean(lo_)), 3) if lo_ else None]
    pool = [x for x in rows if x["p"] in ("train", "validate")]
    lab = np.array([x["high"] for x in pool]); r = np.array([x["r"] for x in pool])
    act = r[lab].mean() - r[~lab].mean()
    hits = sum((r[s].mean() - r[~s].mean()) >= act for s in (np.random.permutation(lab) for _ in range(PERMS)))
    res["chênh train+validate"] = round(float(act), 3)
    res["p hoán vị"] = (hits + 1) / (PERMS + 1)
    res["danh mục"] = {}
    for name, mult in (("mốc (EA hiện tại)", 1.0), ("điểm thấp × 0,5", 0.5)):
        bk = book(mult)
        row = {p: [round(v, 4) if isinstance(v, float) else v for v in sim(bk, a, z)] for p, a, z in PER}
        row["dd_p90_1y"] = round(dd_p90(bk), 4)
        res["danh mục"][name] = row
    base, var = res["danh mục"]["mốc (EA hiện tại)"], res["danh mục"]["điểm thấp × 0,5"]
    ok = (all(res["R chân gốc"][p]["cao"][1] is not None and res["R chân gốc"][p]["thấp"][1] is not None
              and res["R chân gốc"][p]["cao"][1] > res["R chân gốc"][p]["thấp"][1] for p, _, _ in PER)
          and res["p hoán vị"] <= 0.01 and all(var[p][2] >= base[p][2] for p, _, _ in PER)
          and var["dd_p90_1y"] <= base["dd_p90_1y"])
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
