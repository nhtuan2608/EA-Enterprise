"""G112 step 2: how far chases run (distribution), which conditions repeat, and adds / exits vs random adds.
Train + validate only (2026 sealed).

  [G109_NOFILTER=1] python g112_stats.py XAUUSD EURUSD GBPUSD USDJPY   # writes docs/superpowers/reports/2026-10-13-g112-step2[_nf].md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g109_setups import SUF, run_label
from g108_patterns import boot_lower

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g112-step2{SUF}.md"
EXITS = ("X1", "X2", "X3", "X4", "X5")
ADDS = ("none", "rule", "random")
XN = {"X1": "TP 2R", "X2": "trailing swing M5", "X3": "trailing 1,5 ATR", "X4": "TP vùng/FVG phía trước", "X5": "TP MFE trung vị (train)"}
AN = {"none": "không bồi", "rule": "bồi theo quy tắc", "random": "bồi ngẫu nhiên"}


def no_overlap(X: pd.DataFrame, bars_col: str) -> pd.DataFrame:
    keep, free = [], -1
    for r in X.sort_values("e").itertuples():
        if r.e >= free:
            keep.append(r.Index); free = r.e + getattr(r, bars_col)
    return X.loc[keep]


def seq(x: pd.DataFrame, col: str) -> str:
    if len(x) < 10:
        return f"{len(x)} | | | |"
    v = x.sort_values("e")[col].to_numpy()
    eq = np.cumsum(v); dd = float(np.max(np.maximum.accumulate(eq) - eq))
    return f"{len(v)} | {v.mean():+.3f} | {boot_lower(v, x.sort_values('e')['day'].to_numpy()):+.3f} | {v.sum():+.1f} / DD {dd:.1f}"


def section(sym: str) -> list[str]:
    C = pd.read_pickle(g8.DATA / f"g112_chase_{sym}{SUF}.pkl")
    assert not (C["period"] == "test").any()
    L = [f"## {sym}", "", f"Tín hiệu (train + validate): {len(C)} — {C.groupby('typ').size().to_dict()}.", "",
         "### 1. Phân phối: một cú đuổi đi được bao xa (48 nến, không bồi)", "",
         "| Tín hiệu | Chiều | Kỳ | Lệnh | MFE trung vị (R) | MFE 75% (R) | +1R trước −1R | +2R | +3R | TP 2R: R/lệnh | Ngẫu nhiên: R/lệnh |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for typ in sorted(C["typ"].unique()):
        for d, dn in ((1, "MUA"), (-1, "BÁN")):
            for per in ("train", "validate"):
                x = C[(C["typ"] == typ) & (C["d"] == d) & (C["period"] == per)]
                if len(x) < 20:
                    continue
                L.append(f"| {typ} | {dn} | {per} | {len(x)} | {x['mfe'].median():.2f} | {x['mfe'].quantile(.75):.2f} | "
                         f"{100 * x['hit1'].mean():.0f}% | {100 * x['hit2'].mean():.0f}% | {100 * x['hit3'].mean():.0f}% | "
                         f"{x['X1_none'].mean():+.3f} | {x['rand_X1'].mean():+.3f} |")
    # repetition: conditions better than the pooled base on both periods
    C = C.copy()
    C["g_sess"] = C["sess"].map({0: "phiên Á", 1: "phiên Âu", 2: "phiên Mỹ"})
    C["g_adx"] = np.where(C["adx_h1"] >= 25, "ADX H1 ≥ 25", np.where(C["adx_h1"] < 20, "ADX H1 < 20", "ADX 20–25"))
    C["g_adxup"] = np.where(C["adx_up"] == 1, "ADX H1 đang tăng", "ADX H1 đang giảm")
    C["g_d1"] = np.where(C["d1_with"] > 0, "cùng chế độ D1", np.where(C["d1_with"] < 0, "ngược chế độ D1", "D1 trung tính"))
    C["g_h4"] = np.where(C["h4_side"] > 0, "cùng phía EMA200 H4", "ngược phía EMA200 H4")
    q = C.loc[C["period"] == "train", "rv1"].quantile([1 / 3, 2 / 3]).to_numpy()
    C["g_vol"] = np.where(C["rv1"] <= q[0], "volume nến tín hiệu thấp", np.where(C["rv1"] >= q[1], "volume nến tín hiệu cao", "volume giữa"))
    C["g_div"] = np.where(C["diverg"] == 1, "có phân kỳ giá–delta", "không phân kỳ")
    C["g_room"] = np.where(C["room"] < 1, "cản/FVG phía trước < 1R", np.where(C["room"] < 2, "cản phía trước 1–2R", "cản phía trước ≥ 2R"))
    L += ["", "### 2. Sự lặp lại: điều kiện nào hơn mức chung ở CẢ train lẫn validate (TP 2R không bồi, theo lệnh)", "",
          "| Nhóm | Train: lệnh · R/lệnh · +2R% | Validate: lệnh · R/lệnh · +2R% | Hơn mức chung cả hai kỳ? |", "|---|---|---|---|"]
    base = {per: C.loc[C["period"] == per, "X1_none"].mean() for per in ("train", "validate")}
    L.append(f"| (mức chung) | {int((C['period'] == 'train').sum())} · {base['train']:+.3f} | {int((C['period'] == 'validate').sum())} · {base['validate']:+.3f} | |")
    for col in ("g_sess", "g_adx", "g_adxup", "g_d1", "g_h4", "g_vol", "g_div", "g_room"):
        for v in sorted(C[col].dropna().unique()):
            a, b = C[(C[col] == v) & (C["period"] == "train")], C[(C[col] == v) & (C["period"] == "validate")]
            if len(a) < 30 or len(b) < 30:
                continue
            ok = a["X1_none"].mean() > base["train"] and b["X1_none"].mean() > base["validate"]
            pos = a["X1_none"].mean() > 0 and b["X1_none"].mean() > 0
            L.append(f"| {v} | {len(a)} · {a['X1_none'].mean():+.3f} · {100 * a['hit2'].mean():.0f}% | {len(b)} · {b['X1_none'].mean():+.3f} · "
                     f"{100 * b['hit2'].mean():.0f}% | {'**có' + (', dương cả hai' if pos else '') + '**' if ok else 'không'} |")
    L += ["", "### 3. Bồi lệnh và cách chốt (R theo rủi ro ban đầu, lệnh không chồng theo từng loại tín hiệu, gộp hai chiều)", "",
          "| Cách chốt | Bồi | Train: lệnh · R/lệnh · cận dưới · tổng / DD | Validate: lệnh · R/lệnh · cận dưới · tổng / DD |", "|---|---|---|---|"]
    best, best_v = None, -9
    for X in EXITS:
        for A in ADDS:
            col = f"{X}_{A}"
            parts = {}
            for per in ("train", "validate"):
                x = C[C["period"] == per]
                parts[per] = pd.concat([no_overlap(x[x["typ"] == ty], f"{col}_bars") for ty in x["typ"].unique()])
            L.append(f"| {XN[X]} | {AN[A]} | {seq(parts['train'], col)} | {seq(parts['validate'], col)} |")
            m = parts["train"][col].mean()
            if m > best_v:
                best_v, best = m, (X, A)
    L += ["", f"Tốt nhất trên train: **{XN[best[0]]}, {AN[best[1]]}** (R/lệnh train {best_v:+.3f}); xem dòng tương ứng ở validate.", ""]
    return L


def main(symbols):
    L = ["# G112 bước 1–2: mua đuổi / bán đuổi — phân phối, sự lặp lại, bồi lệnh và cách chốt", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g112-chase-and-adds.md. Dữ liệu raw MT5 (EURUSD/GBPUSD đã đổi sang giờ "
         f"server). Chỉ train 07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); **test 2026 niêm phong**. " + run_label() +
         f" Script: research/long/g112_chase.py, g112_stats.py, g112_audit.py.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
