"""G141: the frozen V-candle M30 candidate A (G118) on silver XAGUSD, M30 built from the M15 bars (02/2024-10/2026).
Plan: docs/superpowers/plans/2026-10-22-g141-v-candle-silver.md. Gold over the same window, same M15->M30 build, for comparison.

Usage: g141_v_silver.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g116_v_hedge as g116  # noqa: E402
import g118_v_combos as g118  # noqa: E402
from g117_v_filters import Sim2  # noqa: E402
from g134_extensions import prep_v  # noqa: E402
from g140_holdout import ctx_a, stat, touched  # noqa: E402

SPLIT = pd.Timestamp("2025-06-01")
RUNS = 200
random.seed(141)


def m30_from_m15(path, has_tickvol):
    d = pd.read_csv(path)
    d["b"] = d["time"] // 1800 * 1800
    agg = dict(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), spread=("spread", "mean"))
    m = d.groupby("b").agg(**agg).reset_index().rename(columns={"b": "time"})
    return m


def run(m, point, start):
    m = prep_v(m)
    sp_raw = m["spread"].to_numpy() * point
    med = float(np.median(sp_raw[sp_raw > 0]))
    first = int(m.index[m["ts"] >= pd.Timestamp(start)][0])
    gr = [(v, j) for v, j in g116.find_groups(m) if v >= max(first, 300)]
    F = g118.features(m, gr)
    keep = (F["fan_against"] & F["adx_lt25"] & F["slope_against"]).to_numpy()
    V = [dict(v=v, j=j, s=int(F["vdir"].iat[q]), ts=m["ts"].iat[j]) for q, (v, j) in enumerate(gr) if keep[q]]
    for mult, tag in ((1.0, "u"), (1.5, "u15")):
        m["sp"] = np.maximum(sp_raw, med) * mult
        S = Sim2(m)
        for x in V:
            x[tag] = S.hedge_r(x["v"], x["j"], "A2")[0]
    m["sp"] = np.maximum(sp_raw, med)
    S = Sim2(m)
    V = [x for x in V if x["u"] == x["u"]]
    for x in V:
        x["half"] = "trước 06/2025" if x["ts"] < SPLIT else "từ 06/2025"
    pool = {}
    for k in range(max(first, 300), len(m) - 8):
        if not touched(m, k):
            continue
        hf = "trước 06/2025" if m["ts"].iat[k] < SPLIT else "từ 06/2025"
        for s in (1, -1):
            if ctx_a(m, k, s):
                pool.setdefault((hf, s), []).append(k)
    actual = float(np.mean([x["u"] for x in V])) if V else float("nan")
    hits = 0
    for _ in range(RUNS):
        u = []
        for x in V:
            cands = pool.get((x["half"], x["s"]), [])
            for _ in range(20):
                if not cands:
                    break
                k = random.choice(cands)
                r = S.hedge_r(k, k, "A2")[0]
                if r == r:
                    u.append(r); break
        hits += float(np.mean(u)) >= actual
    p = (hits + 1) / (RUNS + 1)
    out = {"bars": [str(m["ts"].iat[first]), str(m["ts"].iat[-1])], "spread trung vị": round(med, 4),
           "tất cả": stat(x["u"] for x in V), "phí×1,5": stat(x["u15"] for x in V),
           "trước 06/2025": stat(x["u"] for x in V if x["half"] == "trước 06/2025"),
           "từ 06/2025": stat(x["u"] for x in V if x["half"] == "từ 06/2025"),
           "mua / bán": [stat(x["u"] for x in V if x["s"] == 1), stat(x["u"] for x in V if x["s"] == -1)],
           "theo năm": {str(y): stat(x["u"] for x in V if x["ts"].year == y) for y in (2024, 2025, 2026)},
           "p ngẫu nhiên": p}
    ok = (out["tất cả"]["n"] >= 40 and out["trước 06/2025"].get("mean", -1) > 0 and out["từ 06/2025"].get("mean", -1) > 0
          and out["phí×1,5"].get("mean", -1) > 0 and p <= 0.05)
    out["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    xag = m30_from_m15(root / "bars_XAGUSD_M15.csv", False)
    start = pd.to_datetime(xag["time"].iloc[0], unit="s") + pd.Timedelta(days=14)
    res = {"XAGUSD (quyết định)": run(xag, 0.001, start)}
    print(json.dumps(res, ensure_ascii=False), flush=True)
    xau = m30_from_m15(root / "m15v" / "XAUUSD.csv", True)
    xau = xau[xau["time"] >= int(xag["time"].iloc[0]) - 400 * 86400].reset_index(drop=True)
    res["XAUUSD cùng khoảng (so sánh)"] = run(xau, 0.01, start)
    del res["XAUUSD cùng khoảng (so sánh)"]["kết luận"]
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
