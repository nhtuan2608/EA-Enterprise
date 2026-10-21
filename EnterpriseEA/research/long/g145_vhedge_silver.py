"""G145: the live VHedge G119 rules unchanged on silver M5. Plan: docs/superpowers/plans/2026-10-22-g145-vhedge-silver.md.

Usage: g145_vhedge_silver.py <results dir with xag_m5.csv and xau_m5.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g116_v_hedge as g116  # noqa: E402
import g119_v_m5_native as q  # noqa: E402
from g97_forming_bar import dmi, ema  # noqa: E402
from g120_combo import SimExit  # noqa: E402

RUNS = 200


def prep(path, point):
    m = pd.read_csv(path)
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    c = m["close"].to_numpy()
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * point
    return m


def g119(F):
    """The bot's fixed thresholds (Bots/VHedgeBot.mqh)."""
    return ((F["ema_spread"] <= 0.91) & ((F["v_vol"] >= 1.26) | (F["r_vol"] >= 1.17))).to_numpy()


def stat(xs):
    xs = [x for x in xs if x == x]
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


def run(path, point, decide):
    m = prep(path, point)
    mid = m["ts"].iloc[0] + (m["ts"].iloc[-1] - m["ts"].iloc[0]) / 2
    gr, pg = g116.find_groups(m), g116.find_groups(m, pseudo=True)
    F, P = q.raw_features(m, gr), q.raw_features(m, pg)
    real = [gr[k] for k in np.flatnonzero(g119(F))]
    pseudo = [pg[k] for k in np.flatnonzero(g119(P))]
    sp0 = m["sp"].to_numpy().copy()
    out_u = {}
    for mult, tag in ((1.0, "u"), (1.5, "u15")):
        m["sp"] = sp0 * mult
        S = SimExit(m)
        out_u[tag] = [S.group(v, j, 1.5) for v, j in real]
    m["sp"] = sp0
    S = SimExit(m)
    rows = []
    for (v, j), a, b in zip(real, out_u["u"], out_u["u15"]):
        if a is None:
            continue
        rows.append(dict(ts=m["ts"].iat[j], u=a[0], u15=b[0] if b else np.nan, d=1 if m["close"].iat[v] > m["e200"].iat[v] else -1))
    for x in rows:
        x["half"] = "nửa đầu" if x["ts"] < mid else "nửa sau"
    res = {"bars": [str(m["ts"].iloc[0]), str(m["ts"].iloc[-1])], "mốc giữa": str(mid),
           "tất cả": stat(x["u"] for x in rows), "phí×1,5": stat(x["u15"] for x in rows),
           "nửa đầu": stat(x["u"] for x in rows if x["half"] == "nửa đầu"),
           "nửa sau": stat(x["u"] for x in rows if x["half"] == "nửa sau"),
           "phá lên / phá xuống": [stat(x["u"] for x in rows if x["d"] == 1), stat(x["u"] for x in rows if x["d"] == -1)],
           "theo quý": {}}
    for k, grp in pd.DataFrame(rows).groupby(pd.DataFrame(rows)["ts"].dt.to_period("Q")):
        res["theo quý"][str(k)] = stat(grp["u"])
    u_sorted = sorted(x["u"] for x in rows)
    res["bỏ 2 nhóm lớn nhất"] = stat(u_sorted[:-2]) if len(u_sorted) > 2 else None
    if not decide:
        return res
    # control: pseudo groups (near EMA200, no body cross) through the same profile and management, same half
    byh = {"nửa đầu": [], "nửa sau": []}
    for v, j in pseudo:
        byh["nửa đầu" if m["ts"].iat[j] < mid else "nửa sau"].append((v, j))
    actual = float(np.mean([x["u"] for x in rows]))
    rng = random.Random(145)
    cache = {}
    hits = 0
    for _ in range(RUNS):
        u = []
        for x in rows:
            for _ in range(20):
                vj = rng.choice(byh[x["half"]])
                if vj not in cache:
                    r = S.group(vj[0], vj[1], 1.5)
                    cache[vj] = r[0] if r else np.nan
                if cache[vj] == cache[vj]:
                    u.append(cache[vj]); break
        hits += float(np.mean(u)) >= actual
    res["p đối chứng"] = (hits + 1) / (RUNS + 1)
    res["số nhóm đối chứng"] = len(pseudo)
    ok = (res["tất cả"]["n"] >= 60 and res["nửa đầu"].get("mean", -1) > 0 and res["nửa sau"].get("mean", -1) > 0
          and res["phí×1,5"].get("mean", -1) > 0 and res["p đối chứng"] <= 0.05)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return res


def main():
    d = Path(sys.argv[1]).resolve()
    res = {"XAGUSD (quyết định)": run(d / "xag_m5.csv", 0.001, True)}
    print(json.dumps(res, ensure_ascii=False), flush=True)
    res["XAUUSD cùng khoảng (so sánh)"] = run(d / "xau_m5.csv", 0.01, False)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
