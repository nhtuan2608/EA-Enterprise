"""G113 summary: every setup family of G109-G112 on M5 / M15 / M30, with the real spread and with spread = 0, as a
plain rule (every trade, no overlap within the family), against a fair drift control: the same trade (direction,
stop distance, 2R target, market entry at a bar open) on random bars of OTHER days of the same month (20 draws).

  python g113_summary.py [XAUUSD EURUSD GBPUSD USDJPY]   -> docs/superpowers/reports/2026-10-14-g113-summary-tables.md
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-14-g113-summary-tables.md"
VARIANTS = (("M5", 5, 0), ("M5 spread 0", 5, 1), ("M15", 15, 0), ("M15 spread 0", 15, 1), ("M30", 30, 0), ("M30 spread 0", 30, 1))
N_DRAW = 20


def drift_control(P: pd.DataFrame, df: pd.DataFrame, gs, n_draw: int = N_DRAW, seed: int = 113, picks: list | None = None) -> np.ndarray:
    """Mean R of the same trades moved to random bars on other days of the same month (market entry at the open)."""
    rng = np.random.default_rng(seed)
    t = df["time"].to_numpy(np.int64)
    o, h, l, c, sp = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "sp"))
    n = len(t)
    hour = (t % 86400) // 3600
    day = t // 86400
    mon = pd.to_datetime(t, unit="s").strftime("%Y-%m").to_numpy()
    ok = (hour >= 1) & (hour < 23) & (np.arange(n) + gs.MAX_BARS < n)
    by_month = {m: np.nonzero(ok & (mon == m))[0] for m in np.unique(mon)}
    out = np.zeros(n_draw)
    rows = list(P[["i", "d", "risk", "day"]].itertuples(index=False))
    for k in range(n_draw):
        R = []
        for i, d, risk, dd in rows:
            cand = by_month[mon[int(i)]]
            cand = cand[day[cand] != dd]
            if len(cand) == 0 or not np.isfinite(risk) or risk <= 0:
                continue
            q = int(cand[rng.integers(len(cand))])
            if picks is not None:
                picks.append((int(i), q))
            en = o[q] + (sp[q] if d == 1 else 0.0)
            f = slice(q, q + gs.MAX_BARS)
            R.append(gs.simulate(int(d), en, en - d * risk, en + d * 2 * risk, h[f], l[f], c[f], sp[f])["a"])
        out[k] = np.mean(R) if R else np.nan
    return out


def family_rows(sym: str, tf: int, nocost: int):
    os.environ["G108_SYMBOL"] = sym
    os.environ["G113_TF"] = str(tf)
    os.environ["G109_NOCOST"] = str(nocost)
    os.environ.pop("G109_NOFILTER", None)
    import g108_data as g8
    import g108_patterns as gpat
    import g109_zones as gz
    import g109_setups as gs
    import g114_prob as gp
    for m in (g8, gz, gs, gp):
        importlib.reload(m)
    df = g8.load_m5_raw()
    P = gp.pool(sym, df)
    out = []
    for fam, g in P.groupby("fam"):
        sel = g.iloc[gp.one_at_a_time(g["i"].to_numpy(), g["bars"].to_numpy(), np.zeros(len(g)))]
        rec = {"fam": fam}
        for per in ("train", "validate"):
            x = sel[sel["period"] == per]
            rec[per] = gp.stats(x)
            if len(x) >= 30 and not nocost:
                dc = drift_control(x, df, gs)
                rec[per]["rand"] = float(np.nanmean(dc))
                rec[per]["p"] = float(np.mean(dc >= rec[per]["R"]))
        out.append(rec)
    return out, gp.FAM_NAME


def cell(s: dict) -> str:
    if s.get("n", 0) == 0:
        return "0"
    txt = f"{s['n']} · {s['R']:+.3f} ({s['lo']:+.3f})"
    if "rand" in s:
        txt += f" · ngẫu nhiên {s['rand']:+.3f}, p {s['p']:.2f}"
    return txt


def main(symbols):
    L = ["# G113 tổng hợp: bảng số theo khung và chi phí", "",
         "Mỗi ô: lệnh · R/lệnh (cận dưới 90% bootstrap theo ngày). Luật = mọi lệnh của loại setup, không chồng lệnh trong cùng "
         "loại. Với bản có spread: \"ngẫu nhiên\" = cùng lệnh (chiều, khoảng stop, mục tiêu 2R, vào lệnh thị trường) đặt ở nến "
         f"ngẫu nhiên của ngày khác trong cùng tháng ({N_DRAW} lần), p = tỉ lệ lần ngẫu nhiên ≥ thật. Test 2026 niêm phong.", ""]
    for sym in symbols:
        L += [f"## {sym}", "", "| Loại | Bản | Train | Validate |", "|---|---|---|---|"]
        res = {}
        for name, tf, nc in VARIANTS:
            rows, names = family_rows(sym, tf, nc)
            for r in rows:
                res.setdefault(r["fam"], []).append((name, r))
            print(sym, name, "done", flush=True)
        for fam in sorted(res):
            for name, r in res[fam]:
                L.append(f"| {names[fam]} | {name} | {cell(r['train'])} | {cell(r['validate'])} |")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
