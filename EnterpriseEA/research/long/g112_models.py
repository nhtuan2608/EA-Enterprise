"""G112 step 3: walk-forward P(chase reaches +2R before -1R): context (C), + volume (CV), + price action / room
ahead (CP), + both (CVP); trade the top 20 % (cut-off from earlier months), no overlap per signal type; random control.

  [G109_NOFILTER=1] python g112_models.py XAUUSD EURUSD GBPUSD USDJPY   # writes docs/superpowers/reports/2026-10-13-g112-models[_nf].md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g109_setups import SUF
from g108_patterns import boot_lower
from g110_models import LGB, auc
from g112_stats import no_overlap

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g112-models{SUF}.md"
CTX = ["d", "typ_c", "risk_atr", "hour", "sess", "adx_h1", "adx_up", "d1_with", "h4_side"]
VOLF = ["rv1", "rv6", "delta12", "diverg", "move6", "body"]
PAF = ["void_ahead", "zone_ahead", "room", "compress", "day_pos"]
SETS = {"C": CTX, "CV": CTX + VOLF, "CP": CTX + PAF, "CVP": CTX + VOLF + PAF}
TRADE_COLS = (("X1_none", "TP 2R"), ("X3_none", "trailing 1,5 ATR"), ("X1_rule", "TP 2R + bồi"))


def walk(C: pd.DataFrame, cols) -> np.ndarray:
    import lightgbm as lgb
    p = np.full(len(C), np.nan)
    for m0 in pd.date_range("2024-12-01", "2025-12-01", freq="MS"):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = (C["time"] < s - 86400).to_numpy(); te = ((C["time"] >= s) & (C["time"] < e)).to_numpy()
        if te.sum() == 0 or tr.sum() < 500:
            continue
        assert C.loc[tr, "time"].max() < s - 86400 <= C.loc[te, "time"].min()
        p[te] = lgb.LGBMClassifier(**LGB).fit(C.loc[tr, cols], C.loc[tr, "hit2"]).predict_proba(C.loc[te, cols])[:, 1]
    return p


def chosen(C: pd.DataFrame, sel: np.ndarray, col: str) -> pd.DataFrame:
    X = C[sel]
    return pd.concat([no_overlap(X[X["typ"] == ty], f"{col}_bars") for ty in X["typ"].unique()]) if len(X) else X


def line(x: pd.DataFrame, col: str) -> str:
    if len(x) < 10:
        return f"{len(x)} | |"
    return f"{len(x)} | {x[col].mean():+.3f} ({boot_lower(x[col].to_numpy(), x['day'].to_numpy()):+.3f})"


def section(sym: str) -> list[str]:
    C = pd.read_pickle(g8.DATA / f"g112_chase_{sym}{SUF}.pkl").sort_values("time").reset_index(drop=True)
    assert not (C["period"] == "test").any()
    C["typ_c"] = C["typ"].map({"C1": 1, "C2": 2, "C3": 3})
    C["month"] = pd.to_datetime(C["time"], unit="s").dt.strftime("%Y-%m")
    mon = C["month"].to_numpy()
    y = C["hit2"].to_numpy()
    L = [f"## {sym}", "", "| Mô hình | AUC cuối train / validate | " + " | ".join(f"{nm}: cuối train lệnh · R (cận dưới) | validate" for _, nm in TRADE_COLS) +
         " | Ngẫu nhiên ≥ mô hình (validate, TP 2R) |", "|---|---|" + "---|---|" * len(TRADE_COLS) + "---|"]
    rng = np.random.default_rng(12)
    for name, cols in SETS.items():
        p = walk(C, cols)
        hi = np.full(len(C), np.nan)
        for m in sorted(set(mon)):
            past = p[(mon < m) & ~np.isnan(p)]
            if len(past) >= 500:
                hi[mon == m] = np.quantile(past, 0.8)
        sel = p >= hi
        a = [auc(y[(C["period"] == per).to_numpy()], p[(C["period"] == per).to_numpy()]) for per in ("train", "validate")]
        cells = []
        for col, _ in TRADE_COLS:
            X = chosen(C, sel, col)
            cells += [line(X[X["period"] == "train"], col), line(X[X["period"] == "validate"], col)]
        X1v = chosen(C, sel & (C["period"] == "validate").to_numpy(), "X1_none")
        prand = float("nan")
        if len(X1v) >= 10:
            cnt = C[sel & (C["period"] == "validate").to_numpy()].groupby("month").size()
            pool = C[(C["period"] == "validate").to_numpy() & ~np.isnan(p)]
            draws = []
            for _ in range(200):
                idx = np.concatenate([rng.choice(pool.index[pool["month"] == mo], size=min(k, int((pool["month"] == mo).sum())), replace=False)
                                      for mo, k in cnt.items()])
                s2 = np.zeros(len(C), bool); s2[idx] = True
                draws.append(chosen(C, s2, "X1_none")["X1_none"].mean())
            prand = float(np.mean(np.array(draws) >= X1v["X1_none"].mean()))
        L.append(f"| {name} | {a[0]:.3f} / {a[1]:.3f} | " + " | ".join(cells) + f" | {prand:.3f} |")
    allc = []
    for col, _ in TRADE_COLS:
        X = chosen(C, np.ones(len(C), bool), col)
        allc += [line(X[X["period"] == "train"], col), line(X[X["period"] == "validate"], col)]
    L.append("| mốc: mọi tín hiệu | | " + " | ".join(allc) + " | |")
    L.append("")
    return L


def main(symbols):
    L = ["# G112 bước 3: học cuốn chiếu chọn cú đuổi tốt (đạt +2R trước −1R)", "",
         "Ngày 14/10/2026. Plan: docs/superpowers/plans/2026-10-13-g112-chase-and-adds.md (mục 4). Chỉ train và validate; **test 2026 niêm phong**. "
         f"Bộ lọc chi phí: {'TẮT (spread vẫn trừ)' if SUF else 'bật'}. Mỗi tháng mô hình học từ tín hiệu trước tháng ít nhất 1 ngày (có assert); "
         "vào nhóm 20% xác suất cao nhất (ngưỡng từ các tháng trước); lệnh không chồng theo loại tín hiệu. R/lệnh kèm cận dưới 90% trong ngoặc.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
