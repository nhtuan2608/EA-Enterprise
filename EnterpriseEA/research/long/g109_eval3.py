"""G109 step 3 evaluation: setups at real zones vs fake zones (Z1) and random entries (Z2), by direction, exit and
the step-2 hypotheses. Train + validate only (2026 sealed).

  python g109_eval3.py XAUUSD EURUSD GBPUSD USDJPY     # writes docs/superpowers/reports/2026-10-13-g109-setups.md

Trades of a group are taken without overlap (one open trade per symbol, setup, target and zone source at a time).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g108_patterns import boot_lower

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-13-g109-setups.md"
LOWS = ("PDL", "H1SL", "H4SL", "PWL", "ASIA_L", "LOR_L", "NYOR_L")
HIGHS = ("PDH", "H1SH", "H4SH", "PWH", "ASIA_H", "LOR_H", "NYOR_H")


def no_overlap(X: pd.DataFrame) -> pd.DataFrame:
    keep, free = [], -1
    for r in X.sort_values("i").itertuples():
        if r.i < free:
            continue
        keep.append(r.Index)
        free = r.i + r.bars
    return X.loc[keep]


def stat(x: pd.DataFrame, col="Ra") -> str:
    if len(x) < 5:
        return f"{len(x)} | | | |"
    lb = boot_lower(x[col].to_numpy(), x["day"].to_numpy())
    return f"{len(x)} | {100 * (x[col] > 0).mean():.0f}% | {x[col].mean():+.3f} | {lb:+.3f}"


def group_of(kinds: str) -> str:
    ks = kinds.split("+")
    if "PDC" in ks:
        return "có PDC"
    lo, hi = any(k in LOWS for k in ks), any(k in HIGHS for k in ks)
    return "đáy (PDL/swing low/biên dưới)" if lo and not hi else ("đỉnh (PDH/swing high/biên trên)" if hi and not lo else "khác")


def section(sym: str) -> list[str]:
    T = pd.read_pickle(g8.DATA / f"g109_trades_{sym}.pkl")
    assert not (T["period"] == "test").any()
    L = [f"## {sym}", ""]
    L += ["### Lệnh không chồng: vùng thật so với vùng giả (Z1) và vào ngẫu nhiên (Z2), cách thoát a", "",
          "| Setup | Mục tiêu | Kỳ | Chiều | Thật: lệnh · thắng · R/lệnh · cận dưới 90% | Z1 vùng giả: lệnh · thắng · R · cận dưới | Z2 ngẫu nhiên: R/lệnh |",
          "|---|---|---|---|---|---|---|"]
    for setup in ("S1", "S2"):
        for tg in ("zone", "2R"):
            for per in ("train", "validate"):
                for d, dn in ((1, "MUA"), (-1, "BÁN")):
                    base = T[(T["setup"] == setup) & (T["target"] == tg) & (T["period"] == per) & (T["d"] == d)]
                    real = no_overlap(base[~base["fake"]])
                    fake = no_overlap(base[base["fake"]])
                    L.append(f"| {setup} | {tg} | {per} | {dn} | {stat(real)} | {stat(fake)} | "
                             f"{real['Rrand'].mean():+.3f} |" if len(real) else f"| {setup} | {tg} | {per} | {dn} | 0 | {stat(fake)} | |")
    L += ["", "### Cách thoát (vùng thật, lệnh không chồng, hai chiều gộp)", "",
          "| Setup | Mục tiêu | Kỳ | a: stop/mục tiêu | b: hòa vốn sau +1R | c: chốt 50% ở +1R |", "|---|---|---|---|---|---|"]
    for setup in ("S1", "S2"):
        for tg in ("zone", "2R"):
            for per in ("train", "validate"):
                x = T[(T["setup"] == setup) & (T["target"] == tg) & (T["period"] == per) & ~T["fake"]]
                x = pd.concat([no_overlap(x[x["d"] == d]) for d in (1, -1)])
                if len(x) == 0:
                    continue
                L.append(f"| {setup} | {tg} | {per} | " + " | ".join(f"{x[c].mean():+.3f}" for c in ("Ra", "Rb", "Rc")) + f" ({len(x)} lệnh) |")
    R = T[~T["fake"] & (T["target"] == "zone")].copy()
    R["grp"] = R["kinds"].map(group_of)
    R["trend"] = np.where(R["adx_h1"] >= 25, "xu hướng (ADX H1 ≥ 25)", np.where(R["adx_h1"] < 20, "đi ngang (< 20)", "giữa"))
    R["with_d1"] = np.where(R["regime"] * R["d"] > 0, "cùng chế độ D1", np.where(R["regime"] * R["d"] < 0, "ngược chế độ D1", "D1 trung tính"))
    R["conf"] = np.where(R["n"] >= 3, "hợp lưu ≥ 3", np.where(R["n"] == 2, "hợp lưu 2", "1 mức"))
    R["src"] = np.where(R["map"], "vùng bản đồ", "vùng trong ngày")
    L += ["", "### Giả thuyết từ bước 2 (vùng thật, mục tiêu là vùng kế tiếp, cách thoát a, theo lệnh)", "",
          "| Setup | Nhóm | Giá trị | Train: lệnh · thắng · R · cận dưới | Validate: lệnh · thắng · R · cận dưới |", "|---|---|---|---|---|"]
    for setup in ("S1", "S2"):
        for col, name in (("grp", "loại vùng"), ("trend", "chế độ H1"), ("with_d1", "so với D1"), ("conf", "hợp lưu"), ("src", "nguồn vùng")):
            for v in sorted(R[col].unique()):
                x = R[(R["setup"] == setup) & (R[col] == v)]
                L.append(f"| {setup} | {name} | {v} | {stat(x[x['period'] == 'train'])} | {stat(x[x['period'] == 'validate'])} |")
    L.append("")
    return L


def main(symbols):
    L = ["# G109 bước 3: scalp tại vùng (S1 quét rồi rút râu, S2 phá rồi retest bằng limit)", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g109-day-zone-map.md (mục 3, 3b). Dữ liệu raw MT5 "
         "(EURUSD/GBPUSD đã đổi sang giờ server). Chỉ train 07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); "
         "**test 2026 niêm phong**. Script: research/long/g109_setups.py, g109_eval3.py.", "",
         "Chi phí thật (spread), stop ≥ 8 spread, ATR M5 ≥ 3 spread, không vào 23:00–01:00, giữ tối đa 4 giờ. Mục tiêu "
         "\"zone\" = mép gần của vùng thật kế tiếp, chỉ nhận RR ≥ 1 (chốt trước khi xem kết quả); \"2R\" = mục tiêu cố định. "
         "Z1 = cùng luật tại vùng giả (dời ± 0,5–1,5 ATR D1); Z2 = vào ngẫu nhiên cùng ngày, cùng chiều, cùng khoảng stop và RR.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
