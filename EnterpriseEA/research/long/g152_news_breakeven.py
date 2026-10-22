"""G152: the News Guard break-even before USD HIGH events on the S07 M30 book (G89 port).
Plan: docs/superpowers/plans/2026-10-23-g152-news-breakeven.md.

Usage: g152_news_breakeven.py <data dir> <out.json>
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g147_risk_map as rm  # noqa: E402
from g134_extensions import YEAR, sim  # noqa: E402
from g148_layered_risk_map import CAL  # noqa: E402

IGNORE = ("initial jobless claims", "eia crude oil", "lagarde speech", "cb consumer confidence", "durable goods", "home sales",
          "s&p global services pmi", "note auction", "money stock")
TOP = ("nonfarm payrolls", "cpi", "core pce", "fed interest rate decision", "fomc press conference")
PER = [("chọn 05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1))]
LEAD = 900


def events():
    allv, top = set(), set()
    for f in sorted(CAL.glob("calendar_*.csv")):
        with f.open(encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["currency"] != "USD" or r["importance"] != "HIGH":
                    continue
                n = r["name"].lower()
                t = int(r["time_server"])
                if not any(k in n for k in IGNORE):
                    allv.add(t)
                if any(k in n for k in TOP):
                    top.add(t)
    return np.array(sorted(allv)), np.array(sorted(top))


def legs(root):
    import g89_full_book as fb
    out = []
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            bases += fb.base_book(fb.e73.context(main, sub), d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                w = (1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD
                k = int(np.searchsorted(D["t"], int(L["srv_in"]), side="right")) - 1
                w *= 1.0 if D["d1"][k] == d else 0.5
                out.append(dict(d=d, srv_in=int(L["srv_in"]), srv_out=int(L["srv_out"]), ein=int(L["ein"]), eout=int(L["eout"]),
                                entry=float(L["entry"]), dist=float(L["risk"]), r=float(L["r"]), rh=float(L["rh"]), w=w,
                                kind=L.get("kind", "ADD") if j == 0 else "ADD"))
    g.set_tf("M30")
    g.DATA = root / "m30v"
    return out, rm.prepare(g.load("XAUUSD"))


def apply_be(L, D, ev, min_r):
    """R of the leg under the rule; (new_rh, moved, changed)."""
    t, h, l, c, sp = D["t"], D["h"], D["l"], D["c"], D["sp"]
    k0 = int(np.searchsorted(ev, L["srv_in"] + LEAD, side="right"))
    for tau in ev[k0:]:
        arm = int(tau) - LEAD
        if arm >= L["srv_out"]:
            break
        kc = int(np.searchsorted(t, arm - 1800, side="right")) - 1          # last M30 bar closed by arm
        if kc < 0 or t[kc] < L["srv_in"] - 1800:
            continue
        if L["d"] * (c[kc] - L["entry"]) / L["dist"] < min_r:
            continue
        be = L["entry"] + L["d"] * sp[kc]                                   # as the EA: entry + spread (buy) / - spread (sell)
        ks = int(np.searchsorted(t, arm, side="left"))
        kx = int(np.searchsorted(t, L["srv_out"], side="right")) - 1
        for k in range(ks, kx + 1):
            hit = (l[k] <= be) if L["d"] == 1 else (h[k] + sp[k] >= be)
            if hit:
                r_new = L["d"] * (be - L["entry"]) / L["dist"] - D["comm"] / L["dist"]
                return r_new - (L["r"] - L["rh"]), True, True                 # same extra harsh costs as the original leg
        return L["rh"], True, False                                        # moved, never touched before the original exit
    return L["rh"], False, False


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    allv, top = events()
    book, D = legs(root)
    book = [L for L in book if PER[0][1] <= L["srv_in"] < PER[-1][2]]
    variants = {"V0 không hòa vốn": None, "V1 như EA (mọi tin, ≥ 0,3R)": (allv, 0.3), "V2 chỉ tin lớn (≥ 0,3R)": (top, 0.3),
                "V3 mọi tin, ≥ 2R": (allv, 2.0)}
    R, info = {}, {}
    for name, spec in variants.items():
        rs, moved, changed, saved, cut = [], 0, 0, 0, 0
        for L in book:
            if spec is None:
                rs.append(L["rh"]); continue
            r_new, mv, ch = apply_be(L, D, spec[0], spec[1])
            rs.append(r_new); moved += mv; changed += ch
            if ch:
                saved += L["rh"] < r_new - 1e-9
                cut += L["rh"] > r_new + 1e-9
        R[name] = np.array(rs)
        info[name] = {"lệnh bị dời SL": moved, "lệnh đóng ở hòa vốn": changed, "được cứu (gốc kém hơn)": saved,
                      "bị cắt lãi (gốc tốt hơn)": cut}
    per = np.array([next((pn for pn, a, z in PER if a <= L["srv_in"] < z), None) for L in book], dtype=object)
    yrs = np.array([int(np.datetime64(L["srv_in"], "s").astype("datetime64[Y]").astype(int) + 1970) for L in book])
    res = {"lệnh": len(book), "thông tin": info, "biến thể": {}}

    def dd_p90(bk):
        a, out = g.ts(2018, 5, 1), []
        while a + YEAR <= g.ts(2026, 7, 1) + 1:
            out.append(sim(bk, a, int(a + YEAR))[1]); a += 30 * 86400
        return float(np.percentile(out, 90))

    for name, rs in R.items():
        bk = [dict(t_in=L["ein"], t_out=L["eout"], r=float(r), risk=0.015 * L["w"]) for L, r in zip(book, rs)]
        row = {pn: {"tổng R": round(float(rs[per == pn].sum()), 1), "R/lệnh": round(float(rs[per == pn].mean()), 3),
                    "MAR": round(sim(bk, a, z)[2], 2), "%/năm, DD": [round(100 * sim(bk, a, z)[0], 1), round(100 * sim(bk, a, z)[1], 1)]}
               for pn, a, z in PER}
        row["DD p90 1 năm"] = round(100 * dd_p90(bk), 1)
        row["theo năm"] = {str(y): round(float(rs[yrs == y].sum()), 1) for y in range(2018, 2027)}
        res["biến thể"][name] = row
    v0, v1 = R["V0 không hòa vốn"], R["V1 như EA (mọi tin, ≥ 0,3R)"]
    diff = v0 - v1
    rng = np.random.default_rng(152)
    boots = np.array([diff[rng.integers(0, len(diff), len(diff))].sum() for _ in range(2000)])
    res["V0 − V1 tổng R"] = round(float(diff.sum()), 1)
    res["p bootstrap (V0 − V1 ≤ 0)"] = float((boots <= 0).mean())
    a0, a1 = res["biến thể"]["V0 không hòa vốn"], res["biến thể"]["V1 như EA (mọi tin, ≥ 0,3R)"]
    ok = (all(a0[pn]["tổng R"] > a1[pn]["tổng R"] for pn, _, _ in PER) and all(a0[pn]["MAR"] >= a1[pn]["MAR"] for pn, _, _ in PER)
          and a0["DD p90 1 năm"] <= a1["DD p90 1 năm"] + 3 and res["p bootstrap (V0 − V1 ≤ 0)"] <= 0.05)
    res["kết luận (bỏ hòa vốn trước tin cho S07)"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
