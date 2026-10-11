"""MKT04 follow-up (descriptive, after the test was seen): the gold limit plan (L) and market plan (M) with the S07
family gates and weights - H4 EMA200 side for both sides, the S07S location rule for sells (top of the last 8 M30 bars
within 0.5 ATR of the last closed H4 EMA200), weight 1.0 when EMA21/55/100 are ordered with the close beyond EMA21,
else 0.67. Same walk-forward predictions and thresholds as MKT04.

  python mkt04_gold_s07_gates.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import mkt03_context as m3
import mkt04_context_h4 as m4

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-mkt04-gold-s07-gates.md"
THETA_Q = {"L": 0.90, "M": 0.80}          # the quantiles MKT04 chose on validate


def gates():
    df = m4.load("XAUUSD")
    c, h, l = (df[k].to_numpy() for k in ("close", "high", "low"))
    cs = pd.Series(c)
    e21, e55, e100 = (cs.ewm(span=n, adjust=False).mean().to_numpy() for n in (21, 55, 100))
    top8 = pd.Series(h).rolling(9).max().to_numpy()
    return pd.DataFrame({"time": df["time"], "e21": e21, "e55": e55, "e100": e100, "top8": top8, "c": c})


def simulate(F, plan, theta, t0, t1, mode):
    """mode: 'none' | 'gate' (S07 gates) ; returns trades with weight."""
    out = []
    busy = -1
    G = F[(F["time"] >= t0) & (F["time"] < t1)]
    for row in G.itertuples(index=False):
        if row.i <= busy:
            continue
        cands = []
        for d, sfx in ((1, "p"), (-1, "n")):
            p = getattr(row, f"P_{plan}_{sfx}")
            if not (p == p and p > theta and p > 0):
                continue
            if mode == "gate":
                if row.h4_side != d:
                    continue
                if d == -1:
                    he = row.c - row.h4_dist * row.atr
                    if not (row.top8 >= he - 0.5 * row.atr):
                        continue
            cands.append((p, d, sfx))
        if not cands:
            continue
        p, d, sfx = max(cands)
        r = getattr(row, f"R_{plan}_{sfx}")
        if r != r:
            continue
        ordered = (row.e21 > row.e55 > row.e100 and row.c > row.e21) if d == 1 else \
                  (row.e21 < row.e55 < row.e100 and row.c < row.e21)
        w = 1.0 if (mode == "none" or ordered) else 0.67
        out.append({"t": row.time, "r": float(r), "d": d, "w": w, "ord": ordered})
        busy = int(getattr(row, f"X_{plan}_{sfx}"))
    return out


def stats(tr, yrs):
    if not tr:
        return "0 | | | | | |"
    rs = [x["r"] for x in tr]
    wr = [x["r"] * x["w"] for x in tr]
    eq = pk = dd = 0.0
    for x in sorted(tr, key=lambda z: z["t"]):
        eq += 0.5 * x["r"] * x["w"]
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    l90 = m3.lower(rs, 0.10) if len(rs) > 1 else float("nan")
    return (f"{len(rs)} | {m3.mean(rs):+.3f} | {l90:+.3f} | {sum(wr) / len(wr):+.3f} | "
            f"{0.5 * sum(wr) / yrs:+.1f}% | {dd:.1f}%")


def main():
    g = m4.GROUPS["Vàng"]
    F = m4.build_group("Vàng", g)
    m3.walk_forward(F, g)
    # add the atr used by the features (d_e21 = (c - e21) / atr) and the gate columns
    G = gates()
    F = F.merge(G, on="time", how="left")
    F["atr"] = (F["c"] - F["e21"]) / F["d_e21"]
    v0 = m3.ts(*g["oos"])
    periods = {"Validate 01/2020–09/2025": (v0, m3.TEST0), "Test 10/2025–10/2026": (m3.TEST0, m3.TEST1)}
    L = ["# MKT04 bổ sung: vàng với bộ lọc và trọng số họ S07 — mô tả (sau khi đã xem test)", "",
         "Cùng dự báo cuốn chiếu và ngưỡng của MKT04 (L: phân vị 90%, M: phân vị 80% trên validate). Bộ lọc S07: lệnh "
         "cùng phía EMA200 H4 (nến H4 đã đóng); lệnh bán thêm điều kiện vị trí S07S (đỉnh 8 nến M30 gần nhất ≥ EMA200 H4 "
         "− 0,5 ATR). Trọng số: 1,0 khi EMA21/55/100 xếp đúng thứ tự và giá vượt EMA21 theo chiều lệnh, ngược lại 0,67 "
         "(như gốc S07). S07ES / S07RS / S07AS (vào sớm / vào lại / bồi) gắn với tín hiệu S07 nên không áp được. "
         "%/năm và DD ở 0,5% × trọng số, cộng dồn.", "",
         "**Đây là phân tích mô tả sau khi đã nhìn kỳ test, không phải kiểm định mới.**", ""]
    for plan in ("L", "M"):
        vp = pd.concat([F.loc[(F["time"] >= v0) & (F["time"] < m3.TEST0), f"P_{plan}_{s}"] for s in ("p", "n")]).dropna()
        th = float(vp.quantile(THETA_Q[plan]))
        L += [f"## Kế hoạch {plan} ({'limit' if plan == 'L' else 'market'}), θ {th:+.3f}", "",
              "| Kỳ | Bản | Chiều | Lệnh | R/lệnh | Cận dưới 90% | R × trọng số / lệnh | %/năm @0,5% × trọng số | DD |",
              "|---|---|---|---|---|---|---|---|---|"]
        for pname, (t0, t1) in periods.items():
            yrs = (t1 - t0) / (365.25 * 86400)
            for mode, mname in (("none", "MKT04 gốc"), ("gate", "+ lọc/trọng số S07")):
                tr = simulate(F, plan, th, t0, t1, mode)
                for side, sname in ((None, "cả hai"), (1, "mua"), (-1, "bán")):
                    sub = [x for x in tr if side is None or x["d"] == side]
                    L.append(f"| {pname} | {mname} | {sname} | {stats(sub, yrs)} |")
        L.append("")
        print(plan, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
