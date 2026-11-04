"""G162b: S07 scale-in - split the base entry into parts (signal + pullback limit / confirmed M30 rejection) under the same maximum loss
at the original stop; every part exits with the base leg. Plan: docs/superpowers/plans/2026-11-04-g162-smart-adds.md (branch B).
B0 must reproduce the S07 book's harsh R exactly.

Usage: g162b_s07_scale_in.py <data dir> <out dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g89_full_book as fb  # noqa: E402
import g136_p1p4 as p4  # noqa: E402

START, SPLIT, END = g.ts(2018, 5, 1), g.ts(2023, 1, 1), g.ts(2026, 11, 1)
BOOT, SEED, NULL_RUNS = 2000, 162, 200
ALPHA = 0.05 / 3
WEEK = 7 * 86400


def book():
    legs = []
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            ctx = fb.e73.context(main, sub)
            comm = ctx["P"]["comm"]
            for b in fb.base_book(ctx, d, t0, t1, early=True, re=True):
                b["_comm"] = comm
                bases.append(b)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                comm = L.get("_comm", cl[0]["_comm"])
                w = (1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD
                legs.append(dict(d=d, base=j == 0, srv_in=int(L["srv_in"]), srv_out=int(L["srv_out"]), entry=float(L["entry"]),
                                 dist=float(L["risk"]), r=float(L["r"]), rh=float(L["rh"]), comm=comm, w=w))
    return legs


def confirm(o, h, l, c, j, d):
    rg = h[j] - l[j]
    wick = (min(o[j], c[j]) - l[j]) if d == 1 else (h[j] - max(o[j], c[j]))
    return rg > 0 and wick >= 0.5 * rg and d * (c[j] - o[j]) > 0


def parts(L, M, variant, rng=None):
    """List of (risk share, entry price) for a base leg; unfilled parts are dropped."""
    d, e, dist = L["d"], L["entry"], L["dist"]
    if variant == "B0":
        return [(1.0, e)]
    t, o, h, l, c = M["t"], M["o"], M["h"], M["l"], M["c"]
    exit_px = e + d * (L["r"] * dist + L["comm"])
    a = int(np.searchsorted(t, L["srv_in"], side="right"))         # first M30 bar starting after the entry bar
    z = int(np.searchsorted(t, L["srv_out"], side="right")) - 1     # the bar holding the exit
    out = [(0.5, e)]
    ext = (lambda j: l[j]) if d == 1 else (lambda j: h[j])
    if variant == "B1":
        lv = e - d * 0.5 * dist
        last = z if d * (exit_px - lv) <= 0 else z - 1               # the exit bar counts only if the exit is beyond the limit
        for j in range(a, last + 1):
            if d * (ext(j) - lv) <= 0:
                out.append((0.5, o[j] if d * (o[j] - lv) < 0 else lv))
                break
        return out
    def in_zone(j, lo, hi):
        x = d * (e - ext(j)) / dist                                  # pullback depth in stop units
        return lo <= x <= hi
    if variant == "B2":
        for j in range(a, z):
            if in_zone(j, 0.3, 0.7) and confirm(o, h, l, c, j, d):
                out.append((0.5, c[j]))
                break
        return out
    if variant == "B3":
        k = a
        for j in range(a, z):
            if in_zone(j, 0.2, 0.5) and confirm(o, h, l, c, j, d):
                out.append((0.25, c[j]))
                k = j + 1
                break
        else:
            return out
        for j in range(k, z):
            if in_zone(j, 0.5, 0.8) and confirm(o, h, l, c, j, d):
                out.append((0.25, c[j]))
                break
        return out
    if variant == "BNULL":
        js = [j for j in range(a, z) if in_zone(j, 0.3, 0.7)]
        if js:
            out.append((0.5, c[js[int(rng.integers(0, len(js)))]]))
        return out
    raise ValueError(variant)


def leg_r(L, prts):
    """Result in R of the original leg (1 R = loss at the original stop), with the book's harsh costs per unit of price."""
    d, e, dist = L["d"], L["entry"], L["dist"]
    sl = e - d * dist
    exit_px = e + d * (L["r"] * dist + L["comm"])
    cost = (L["r"] - L["rh"]) * dist + L["comm"]                    # harsh extra + commission, price units per unit of lots
    tot = 0.0
    for share, ep in prts:
        dp = d * (ep - sl)
        if dp <= 0:
            continue
        tot += share * (d * (exit_px - ep) - cost) / dp
    return tot


def metrics(rows):
    """rows: (srv_out, weighted R); MAR = total / max drawdown in R."""
    if not rows:
        return {"tổng R": 0.0, "DD R": 0.0, "MAR": None, "PF": None, "n": 0}
    rows = sorted(rows)
    x = np.array([r for _, r in rows])
    eq = np.cumsum(x)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    return {"tổng R": round(float(x.sum()), 2), "DD R": round(dd, 2), "MAR": round(float(x.sum()) / dd, 2) if dd > 0 else None,
            "PF": round(float(pos / neg), 3) if neg > 0 else None, "n": len(x)}


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    legs = [x for x in book() if START <= x["srv_in"] < END]
    d1 = p4.d1_from("M30")
    for x in legs:
        x["wt"] = x["w"] * (1.0 if d1(x["srv_in"]) == x["d"] else 0.5)
    g.set_tf("M30")
    g.DATA = root / "m30v"
    M = g.load("XAUUSD")
    # code check: B0 == book harsh R
    chk = max(abs(leg_r(x, parts(x, M, "B0")) - x["rh"]) for x in legs if x["base"])
    print("check B0 vs book rh: max |diff| =", round(chk, 9), flush=True)
    res = {"kiểm code (B0 = R harsh của sổ)": bool(chk < 1e-9), "số lệnh gốc": sum(x["base"] for x in legs),
           "số lệnh ADD": sum(not x["base"] for x in legs)}
    adds = [(x["srv_out"], x["wt"] * x["rh"], x["srv_in"], x["d"]) for x in legs if not x["base"]]
    bases = [x for x in legs if x["base"]]

    def run(variant, rng=None):
        per = []
        miss = []
        for x in bases:
            pr = parts(x, M, variant, rng)
            per.append(x["wt"] * leg_r(x, pr))
            if variant != "B0":
                miss.append(len(pr) == 1)
        return np.array(per), miss

    def book_metrics(per, a, z, side=None):
        rows = [(x["srv_out"], r) for x, r in zip(bases, per) if a <= x["srv_in"] < z and (side is None or x["d"] == side)]
        rows += [(so, r) for so, r, si, d in adds if a <= si < z and (side is None or d == side)]
        return metrics(rows)

    b0, _ = run("B0")
    res["B0"] = {"kỳ chọn": book_metrics(b0, START, SPLIT), "kỳ kiểm": book_metrics(b0, SPLIT, END), "cả kỳ": book_metrics(b0, START, END)}
    print("B0", res["B0"], flush=True)
    rng = np.random.default_rng(SEED)
    null = [run("BNULL", rng)[0] for _ in range(NULL_RUNS)]
    null_tot = [float(p.sum()) for p in null]
    res["B-null"] = {"tổng R lệnh gốc p50 / p95": [round(float(np.percentile(null_tot, 50)), 2), round(float(np.percentile(null_tot, 95)), 2)]}
    wk = np.array([x["srv_in"] // WEEK for x in bases])
    uw = np.unique(wk)
    for v in ("B1", "B2", "B3"):
        per, miss = run(v)
        diff = per - b0
        W = np.array([diff[wk == u].sum() for u in uw])
        bs = [W[rng.integers(0, len(W), len(W))].sum() for _ in range(BOOT)]
        ci = [round(float(np.percentile(bs, 100 * ALPHA / 2)), 2), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 2)]
        sel, kk, full = book_metrics(per, START, SPLIT), book_metrics(per, SPLIT, END), book_metrics(per, START, END)
        miss = np.array(miss)
        side = {s: round(float(diff[np.array([x["d"] == s for x in bases])].sum()), 2) for s in (1, -1)}
        crit = {
            "1 CI chênh tổng R > 0": ci[0] > 0,
            "2 tổng R và MAR hơn B0 ở cả hai kỳ": all(m["tổng R"] > b["tổng R"] and (m["MAR"] or -9) > (b["MAR"] or -9)
                                                       for m, b in ((sel, res["B0"]["kỳ chọn"]), (kk, res["B0"]["kỳ kiểm"]))),
            "3 DD R không tệ hơn 10 %": full["DD R"] <= 1.10 * res["B0"]["cả kỳ"]["DD R"],
            "5 cả hai chiều không âm": side[1] >= 0 and side[-1] >= 0,
        }
        if v in ("B2", "B3"):
            crit["4 hơn p95 B-null"] = float(per.sum()) > float(np.percentile(null_tot, 95))
        res[v] = {"kỳ chọn": sel, "kỳ kiểm": kk, "cả kỳ": full, "chênh tổng R so với B0": round(float(diff.sum()), 2), f"CI {1 - ALPHA:.2%}": ci,
                  "chênh theo chiều (mua / bán)": [side[1], side[-1]],
                  "tỷ lệ phần sau không khớp": round(float(miss.mean()), 3),
                  "R TB B0 của lệnh không khớp": round(float(b0[miss].mean()), 3) if miss.any() else None,
                  "R TB B0 của lệnh có khớp": round(float(b0[~miss].mean()), 3) if (~miss).any() else None,
                  "tổng R lệnh gốc": round(float(per.sum()), 2), "tiêu chí": crit, "đạt": all(crit.values())}
        print(v, "| chênh", res[v]["chênh tổng R so với B0"], ci, "| chọn", sel, "| kiểm", kk, "| chiều", side, "| miss", res[v]["tỷ lệ phần sau không khớp"],
              res[v]["R TB B0 của lệnh không khớp"], res[v]["R TB B0 của lệnh có khớp"], "| ĐẠT" if res[v]["đạt"] else "", flush=True)
    res["B0"]["tổng R lệnh gốc"] = round(float(b0.sum()), 2)
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("null", res["B-null"], "B0 base R", res["B0"]["tổng R lệnh gốc"], "done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
