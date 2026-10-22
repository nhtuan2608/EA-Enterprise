"""Audit 1 (22/10/2026): re-run the G89 S07 M30 book (full variant) on the PC data and check
(a) it reproduces the G89 report per year, (b) which legs fall before the first intraday bar (2018-03-19: D1 bars only),
(c) how much of the result rests on the largest legs (per year, with the top 3 legs removed; share of the top 1% / top 10).

Usage: audit_g89.py <data dir> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402

INTRADAY = g.ts(2018, 3, 19)


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    import g89_full_book as fb
    rows, legs = fb.run(dict(sides=(1, -1), early=True, re=True, adds=True))
    for x in legs:
        x["rw"] = x["rh"] * x["w"]                          # R x weight, as the report's "R tổng (theo trọng số)"
        x["year"] = int(np.datetime64(int(x["ein"]), "s").astype("datetime64[Y]").astype(int) + 1970)
    res = {"chân": len(legs), "chân trước 19/03/2018 (nến D1)": sum(x["ein"] < INTRADAY for x in legs)}
    res["theo năm"] = {}
    for y in sorted({x["year"] for x in legs}):
        L = [x for x in legs if x["year"] == y]
        rw = sorted(x["rw"] for x in L)
        res["theo năm"][y] = {"lệnh": len(L), "R theo trọng số": round(sum(rw), 1), "bỏ 3 lệnh lớn nhất": round(sum(rw[:-3]), 1),
                              "mua": round(sum(x["rw"] for x in L if x["d"] == 1), 1), "bán": round(sum(x["rw"] for x in L if x["d"] == -1), 1),
                              "trước 19/03/2018": sum(x["ein"] < INTRADAY for x in L)}
    post = [x for x in legs if x["ein"] >= INTRADAY]
    rw = np.array(sorted((x["rw"] for x in post), reverse=True))
    k1 = max(1, len(rw) // 100)
    res["từ 19/03/2018"] = {"lệnh": len(post), "R theo trọng số": round(float(rw.sum()), 1),
                            "phần của 1% lệnh lớn nhất": round(float(rw[:k1].sum() / rw.sum()), 3),
                            "phần của 10 lệnh lớn nhất": round(float(rw[:10].sum() / rw.sum()), 3),
                            "R bỏ 10 lệnh lớn nhất": round(float(rw[10:].sum()), 1),
                            "năm dương khi bỏ 3 lệnh lớn nhất mỗi năm": sum(v["bỏ 3 lệnh lớn nhất"] > 0 for y, v in res["theo năm"].items() if y >= 2018)}
    kinds = {}
    for x in post:
        kinds.setdefault(x["kind"].split("-")[0], []).append(x["rh"])
    res["theo loại (từ 2018-03-19), R/lệnh"] = {k: [len(v), round(float(np.mean(v)), 3)] for k, v in sorted(kinds.items())}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
