"""G150: the stable don't-rules of G147-G149 as x0.5 risk filters on the S07 M30 book and the T2 XAU book; VHedge report only.
Plan: docs/superpowers/plans/2026-10-22-g150-dont-rules-on-bots.md.

Usage: g150_dont_rules.py <data dir> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g147_risk_map as rm  # noqa: E402
import g148_layered_risk_map as lm  # noqa: E402
from g134_extensions import YEAR, sim  # noqa: E402

RULES = ("D1 ATR thấp", "D2 sát EMA200 D1", "D3 giờ 01/15–17", "D4 đuổi phá biên Á", "D5 bắt về VWAP")
PER = [("chọn 05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1))]
SEL_YEARS = (2018, 2019, 2020, 2021)
PERMS, PVAL = 2000, 0.005


class Feat:
    def __init__(self, root):
        g.set_tf("M30")
        g.DATA = root / "m30v"
        self.D = rm.prepare(g.load("XAUUSD"))
        self.B, self.C = lm.bar_context(self.D), lm.daily_context(self.D)

    def rules(self, srv_entry, d):
        D, B, C = self.D, self.B, self.C
        k = int(np.searchsorted(D["t"], srv_entry - 1800, side="right")) - 1     # last M30 bar closed at the entry
        if k < 300:
            return None
        A = D["atr"][k]
        hr = int((srv_entry % 86400) // 3600)
        out = {"D1 ATR thấp": bool(D["atrr"][k] < 0.8),
               "D2 sát EMA200 D1": bool(abs(D["c"][k] - C["dE200"][k]) <= C["dA"][k]),
               "D3 giờ 01/15–17": hr in (1, 15, 16, 17)}
        if d:
            ah, al = B["asia_h"][k], B["asia_l"][k]
            out["D4 đuổi phá biên Á"] = bool(9 <= hr <= 14 and np.isfinite(ah) and ((d == 1 and D["c"][k] > ah) or (d == -1 and D["c"][k] < al)))
            out["D5 bắt về VWAP"] = bool(d * (D["c"][k] - B["vwap"][k]) <= -1.5 * A)
        return out


def year(u):
    return int(np.datetime64(int(u), "s").astype("datetime64[Y]").astype(int) + 1970)


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def s07_book(F):
    import g136_p1p4 as p1
    legs = p1.m30_book()
    D = F.D
    out = []
    for x in legs:
        k = int(np.searchsorted(D["t"], x["srv"], side="right")) - 1
        w = x["w"] * (1.0 if D["d1"][k] == x["d"] else 0.5)
        f = F.rules(x["srv"], x["d"])
        if f is not None:
            out.append(dict(ein=x["ein"], eout=x["eout"], r=x["r"], risk=0.015 * w, d=x["d"], f=f))
    return out


def t2_book(F):
    import discovery as dsc
    B = dsc.load("XAUUSD", "H4")
    out = []
    for t in dsc.trades("T2", {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}, "XAUUSD"):
        srv = int(B["t"][t["i"]]) + 14400                                   # entry at the H4 signal bar's close
        f = F.rules(srv, t["dir"])
        if f is not None:
            out.append(dict(ein=int(B["utc"][t["i"]]) + 14400, eout=int(B["utc"][t["exit_i"]]) + 14400, r=float(t["r"]),
                            risk=0.005, d=t["dir"], f=f))
    return out


def vhedge_book(F):
    import g120_combo as c120
    df = c120.vhedge()["G119"]
    out = []
    for _, row in df.iterrows():
        f = F.rules(int(row["t_in"]), 0)
        if f is not None:
            out.append(dict(ein=int(row["t_in"]), eout=int(row["t_out"]), r=float(row["U"]), risk=0.015, d=0, f=f))
    return out


def analyse(book, rules, decide=True):
    res = {"lệnh": len(book)}
    for rname in rules:
        has = np.array([x["f"][rname] for x in book])
        r = np.array([x["r"] for x in book])
        yrs = np.array([year(x["ein"]) for x in book])
        per = np.array([period(x["ein"]) for x in book], dtype=object)
        row = {"tỷ lệ dính": round(float(has.mean()), 3)}
        row["Δ theo năm"] = {str(y): (round(float(r[(yrs == y) & has].mean() - r[(yrs == y) & ~has].mean()), 3)
                                      if ((yrs == y) & has).any() and ((yrs == y) & ~has).any() else None) for y in range(2018, 2027)}
        for pn, _, _ in PER:
            m = per == pn
            row[f"Δ {pn}"] = round(float(r[m & has].mean() - r[m & ~has].mean()), 3) if (m & has).any() and (m & ~has).any() else None
            row[f"dính / không {pn}"] = [int((m & has).sum()), round(float(r[m & has].mean()), 3) if (m & has).any() else None,
                                         int((m & ~has).sum()), round(float(r[m & ~has].mean()), 3) if (m & ~has).any() else None]
        if decide:
            ys = [row["Δ theo năm"][str(y)] for y in SEL_YEARS]
            cand = (sum(v is not None and v < 0 for v in ys) >= 3 and (row["Δ chọn 05/2018–2021"] or 0) <= -0.10
                    and 0.05 <= row["tỷ lệ dính"] <= 0.40)
            row["ứng viên"] = cand
            if cand:
                base = [dict(t_in=x["ein"], t_out=x["eout"], r=x["r"], risk=x["risk"]) for x in book]
                var = [dict(t_in=x["ein"], t_out=x["eout"], r=x["r"], risk=x["risk"] * (0.5 if x["f"][rname] else 1.0)) for x in book]
                row["MAR mốc / biến thể"] = {pn: [round(sim(base, a, z)[2], 2), round(sim(var, a, z)[2], 2)] for pn, a, z in PER}
                m = per != None  # noqa: E711
                act = r[m & has].mean() - r[m & ~has].mean()
                rng = np.random.default_rng(150)
                lab = has[m]; rr = r[m]
                hits = sum((rr[s].mean() - rr[~s].mean()) <= act for s in (rng.permutation(lab) for _ in range(PERMS)))
                row["p hoán vị"] = (hits + 1) / (PERMS + 1)
                ok = ((row["Δ 2022–2023"] or 1) < 0 and (row["Δ 2024–06/2026"] or 1) < 0
                      and all(v[1] >= v[0] for v in row["MAR mốc / biến thể"].values()) and row["p hoán vị"] <= PVAL)
                row["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
            else:
                row["kết luận"] = "không thành ứng viên"
        res[rname] = row
    return res


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    F = Feat(root)
    res = {}
    res["S07 M30"] = analyse(s07_book(F), RULES)
    print("S07", json.dumps({k: v.get("kết luận") for k, v in res["S07 M30"].items() if isinstance(v, dict)}, ensure_ascii=False), flush=True)
    res["T2 XAU"] = analyse(t2_book(F), RULES)
    print("T2", json.dumps({k: v.get("kết luận") for k, v in res["T2 XAU"].items() if isinstance(v, dict)}, ensure_ascii=False), flush=True)
    try:
        res["VHedge G119 (báo cáo)"] = analyse(vhedge_book(F), RULES[:3], decide=False)
    except Exception as exc:                                           # report-only part must not stop the run
        res["VHedge G119 (báo cáo)"] = {"lỗi": f"{type(exc).__name__}: {exc}"}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
