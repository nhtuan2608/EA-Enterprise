"""G111 step 3: walk-forward P(reversal trade T wins) at tested levels: context (C), + volume dry-up / divergence (CV),
+ Fibonacci / confluence (CF), + both (CVF); trade the top 10 %; random control. Train + validate only.

  python g111_models.py XAUUSD EURUSD GBPUSD USDJPY     # writes docs/superpowers/reports/2026-10-13-g111-models[_nf].md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g109_setups import SUF, run_label
from g108_patterns import boot_lower
from g110_models import LGB, auc

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g111-models{SUF}.md"
CTX = ["d", "side", "adx_h1", "d1_with", "h4_side", "hour", "dist_open"]
VOLF = ["rv6", "rv12", "rv_slope", "speed", "delta12", "diverg"]
FIBF = ["is_fib", "is_fake", "is_zone", "ratio_f", "fam_p", "fam_a", "fam_d", "conf"]
SETS = {"C": CTX, "CV": CTX + VOLF, "CF": CTX + FIBF, "CVF": CTX + VOLF + FIBF}


def prep(T: pd.DataFrame) -> pd.DataFrame:
    T = T.sort_values("time").reset_index(drop=True)
    T["y"] = (T["Ra"] > 0).astype(int)
    T["is_fib"] = T["fam"].str.endswith("FIB").astype(int)
    T["is_fake"] = T["fake"].astype(int)
    T["is_zone"] = T["fam"].isin(["ZONE", "ZFAKE"]).astype(int)
    T["ratio_f"] = T["ratio"].fillna(-1.0)
    for f in ("p", "a", "d"):
        T[f"fam_{f}"] = T["fam"].str.startswith(f.upper()).astype(int) * (1 - T["is_zone"])
    T["month"] = pd.to_datetime(T["time"], unit="s").dt.strftime("%Y-%m")
    return T


def walk(T: pd.DataFrame, cols) -> np.ndarray:
    import lightgbm as lgb
    p = np.full(len(T), np.nan)
    for m0 in pd.date_range("2024-12-01", "2025-12-01", freq="MS"):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = (T["time"] < s - 86400).to_numpy(); te = ((T["time"] >= s) & (T["time"] < e)).to_numpy()
        if te.sum() == 0 or tr.sum() < 300:
            continue
        assert T.loc[tr, "time"].max() < s - 86400 <= T.loc[te, "time"].min()
        p[te] = lgb.LGBMClassifier(**LGB).fit(T.loc[tr, cols], T.loc[tr, "y"]).predict_proba(T.loc[te, cols])[:, 1]
    return p


def pick(T: pd.DataFrame, sel: np.ndarray) -> pd.DataFrame:
    X = T[sel].sort_values("k")
    keep, free = [], -1
    for r in X.itertuples():
        if r.k >= free:
            keep.append(r.Index); free = r.k + r.bars
    return X.loc[keep]


def line(x: pd.DataFrame) -> str:
    if len(x) < 5:
        return f"{len(x)} | | | |"
    return f"{len(x)} | {100 * (x['Ra'] > 0).mean():.0f}% | {x['Ra'].mean():+.3f} | {boot_lower(x['Ra'].to_numpy(), x['day'].to_numpy()):+.3f}"


def section(sym: str) -> list[str]:
    T = prep(pd.read_pickle(g8.DATA / f"g111_tests_{sym}{SUF}.pkl"))
    assert not (T["period"] == "test").any()
    y = T["y"].to_numpy()
    L = [f"## {sym}", "", f"Sự kiện test: {len(T)}.", "", "| Mô hình | AUC cuối train | AUC validate | Lệnh top 10% cuối train: lệnh · thắng · R · cận dưới | Validate | Ngẫu nhiên ≥ mô hình (validate) |",
         "|---|---|---|---|---|---|"]
    rng = np.random.default_rng(11)
    mon = T["month"].to_numpy()
    for name, cols in SETS.items():
        p = walk(T, cols)
        hi = np.full(len(T), np.nan)
        for m in sorted(set(mon)):
            past = p[(mon < m) & ~np.isnan(p)]
            if len(past) >= 300:
                hi[mon == m] = np.quantile(past, 0.9)
        sel = p >= hi
        X = pick(T, sel)
        a = [auc(y[(T["period"] == per).to_numpy()], p[(T["period"] == per).to_numpy()]) for per in ("train", "validate")]
        xv = X[X["period"] == "validate"]
        prand = float("nan")
        if len(xv) >= 5:
            draws = []
            pool = T[(T["period"] == "validate").to_numpy() & ~np.isnan(p)]
            for _ in range(200):
                idx = np.concatenate([rng.choice(pool.index[pool["month"] == mo], size=min(cnt, int((pool["month"] == mo).sum())), replace=False)
                                      for mo, cnt in T[sel & (T["period"] == "validate").to_numpy()].groupby("month").size().items()])
                s2 = np.zeros(len(T), bool); s2[idx] = True
                draws.append(pick(T, s2)["Ra"].mean())
            prand = float(np.mean(np.array(draws) >= xv["Ra"].mean()))
        L.append(f"| {name} | {a[0]:.3f} | {a[1]:.3f} | {line(X[X['period'] == 'train'])} | {line(xv)} | {prand:.3f} |")
    all_tr = pick(T, (T["period"] == "train").to_numpy()); all_va = pick(T, (T["period"] == "validate").to_numpy())
    L.append(f"| mốc: mọi test | | | {line(all_tr)} | {line(all_va)} | |")
    buy = T["d"].to_numpy() == 1
    L.append(f"| mốc: chỉ MUA (test đáy) | | | {line(pick(T, buy & (T['period'] == 'train').to_numpy()))} | {line(pick(T, buy & (T['period'] == 'validate').to_numpy()))} | |")
    L.append("")
    return L


def main(symbols):
    L = ["# G111 bước 3: học cuốn chiếu cho lệnh đảo chiều khi test mức", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g111-retrace-fib-tests.md. Chỉ train và validate; **test 2026 niêm phong**. " +
         run_label() + " "
         "Mỗi tháng mô hình học từ các test trước tháng ít nhất 1 ngày (có assert); vào lệnh ở nhóm 10% cao nhất (ngưỡng từ các "
         "tháng trước), lệnh không chồng; đối chứng chọn ngẫu nhiên cùng số sự kiện mỗi tháng (200 lần).", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
