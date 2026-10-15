"""G110 step 3: walk-forward P(break holds) with context only (C), + volume (V), + price action (P), + both (VP);
follow the top 10 %, fade the bottom 10 %; controls. Train + validate only (2026 sealed).

  python g110_models.py XAUUSD EURUSD GBPUSD USDJPY     # writes docs/superpowers/reports/2026-10-13-g110-models.md

Each month from 2024-12 the classifier learns from the events at least one day before the month (labels resolve in
6 M5 bars, trades within 4 h) and scores the events of the month. Thresholds: 90th / 10th percentile of the scores of
the earlier months. Trades on real levels (Z + G) without overlap (one open trade per symbol and rule); the same
model applied to the fake zones (F) and the same number of random trades per month (200 draws) are the controls.
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
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g110-models{SUF}.md"
CTX = ["s", "isZ", "n", "beyond", "adx_h1", "di_h1", "d1_with", "h4_side", "hour", "sess", "open_dist"]
VOLF = ["tv_break", "tv_appr", "tv_slope", "effort", "delta6", "delta12", "diverg", "wick", "body"]
PAF = ["nr7", "expand", "compress", "void_ahead", "void_size", "zone_ahead", "bos_h1", "bos_dist", "struct_m5", "pole",
       "cons_rng", "cons_slope", "flag_pat", "wedge_hi", "wedge_lo", "wedge_conv", "wedge_type", "wedge_with", "pa_close"]
SETS = {"C": CTX, "V": CTX + VOLF, "P": CTX + PAF, "VP": CTX + VOLF + PAF}
LGB = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, random_state=110)


def walk(E: pd.DataFrame, cols: list[str]) -> np.ndarray:
    import lightgbm as lgb
    p = np.full(len(E), np.nan)
    for m0 in pd.date_range("2024-12-01", "2025-12-01", freq="MS"):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = (E["time"] < s - 86400).to_numpy()
        te = ((E["time"] >= s) & (E["time"] < e)).to_numpy()
        if te.sum() == 0 or tr.sum() < 500:
            continue
        assert E.loc[tr, "time"].max() < s - 86400 <= E.loc[te, "time"].min()
        m = lgb.LGBMClassifier(**LGB).fit(E.loc[tr, cols], E.loc[tr, "hold"])
        p[te] = m.predict_proba(E.loc[te, cols])[:, 1]
    return p


def thresholds(E: pd.DataFrame, p: np.ndarray):
    """Per event: (high, low) cut-offs = 90th / 10th percentile of the scores of the earlier months."""
    hi = np.full(len(E), np.nan); lo = np.full(len(E), np.nan)
    mon = E["month"].to_numpy()
    for m in sorted(set(mon)):
        past = p[(mon < m) & ~np.isnan(p)]
        if len(past) < 1000:
            continue
        hi[mon == m], lo[mon == m] = np.quantile(past, 0.9), np.quantile(past, 0.1)
    return hi, lo


def trades(E: pd.DataFrame, follow: np.ndarray, fade: np.ndarray, col="Ra") -> pd.DataFrame:
    """Follow / fade trades of the selected events, one open trade at a time (by entry bar)."""
    parts = []
    for pre, sel, kind in (("fo", follow, "theo"), ("fa", fade, "ngược")):
        R = E[f"{pre}_{col}"].to_numpy()
        m = sel & np.isfinite(R)
        parts.append(pd.DataFrame({"i": E[f"{pre}_i"].to_numpy()[m], "bars": E[f"{pre}_bars"].to_numpy()[m], "R": R[m],
                                   "day": E["day"].to_numpy()[m], "kind": kind, "period": E["period"].to_numpy()[m]}))
    T = pd.concat(parts, ignore_index=True).sort_values("i", kind="stable")
    i, b = T["i"].to_numpy(), T["bars"].to_numpy()
    keep = np.zeros(len(T), bool)
    free = -1
    for q in range(len(T)):
        if i[q] >= free:
            keep[q] = True
            free = i[q] + b[q]
    return T[keep]


def line(x: pd.DataFrame) -> str:
    if len(x) < 5:
        return f"{len(x)} | | | |"
    return f"{len(x)} | {100 * (x['R'] > 0).mean():.0f}% | {x['R'].mean():+.3f} | {boot_lower(x['R'].to_numpy(), x['day'].to_numpy()):+.3f}"


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    m = ~np.isnan(p)
    return float(roc_auc_score(y[m], p[m])) if m.sum() > 50 and len(set(y[m])) > 1 else float("nan")


def section(sym: str) -> list[str]:
    E = pd.read_pickle(g8.DATA / f"g110_events_{sym}{SUF}.pkl")
    assert not (E["period"] == "test").any()
    E = E.sort_values("time").reset_index(drop=True)
    E["isZ"] = (E["type"] == "Z").astype(int)
    E["month"] = pd.to_datetime(E["time"], unit="s").dt.strftime("%Y-%m")
    real = E["type"].isin(["Z", "G"]).to_numpy()
    fake = (E["type"] == "F").to_numpy()
    y = E["hold"].to_numpy()
    L = [f"## {sym}", "", "### Dự báo cú phá có giữ không (AUC ngoài mẫu, mức thật Z + G)", "", "| Mô hình | Cuối train 12/2024–03/2025 | Validate 04–12/2025 |", "|---|---|---|"]
    P = {}
    for name, cols in SETS.items():
        P[name] = walk(E, cols)
        a = [auc(y[real & (E["period"] == per).to_numpy()], P[name][real & (E["period"] == per).to_numpy()]) for per in ("train", "validate")]
        L.append(f"| {name} | {a[0]:.3f} | {a[1]:.3f} |")
    L += ["", "### Lệnh (theo = 10% xác suất giữ cao nhất, ngược = 10% thấp nhất; không chồng; cách thoát a)", "",
          "| Mô hình | Mức | Kỳ | Theo: lệnh · thắng · R · cận dưới | Ngược: lệnh · thắng · R · cận dưới | Gộp: lệnh · thắng · R · cận dưới |",
          "|---|---|---|---|---|---|"]
    rng = np.random.default_rng(7)
    rand_lines = []
    for name in SETS:
        hi, lo = thresholds(E, P[name])
        for lv, mask in (("thật", real), ("giả (F)", fake)):
            fol = mask & (P[name] >= hi); fad = mask & (P[name] <= lo)
            T = trades(E, fol, fad)
            for per in ("train", "validate"):
                x = T[T["period"] == per]
                L.append(f"| {name} | {lv} | {per} | {line(x[x['kind'] == 'theo'])} | {line(x[x['kind'] == 'ngược'])} | {line(x)} |")
            if lv == "thật":
                for per in ("validate",):
                    x = T[T["period"] == per]
                    if len(x) < 5:
                        continue
                    pool = E[real & (E["period"] == per).to_numpy()]
                    nf = int((fol & (E["period"] == per).to_numpy()).sum()); na = int((fad & (E["period"] == per).to_numpy()).sum())
                    draws = []
                    for _ in range(200):
                        fo_r = np.zeros(len(E), bool); fa_r = np.zeros(len(E), bool)
                        idx = pool.index.to_numpy()
                        fo_r[rng.choice(idx, size=min(nf, len(idx)), replace=False)] = True
                        fa_r[rng.choice(idx, size=min(na, len(idx)), replace=False)] = True
                        draws.append(trades(E, fo_r, fa_r)["R"].mean())
                    draws = np.array(draws)
                    rand_lines.append(f"- {name}, validate: gộp R/lệnh {x['R'].mean():+.3f}; chọn ngẫu nhiên cùng số sự kiện: trung bình "
                                      f"{np.nanmean(draws):+.3f}, 95% ≤ {np.nanquantile(draws, .95):+.3f}; tỉ lệ ngẫu nhiên ≥ mô hình **{np.mean(draws >= x['R'].mean()):.3f}**")
    # references
    adx = (E["adx_h1"] >= 25).to_numpy()
    refs = {"tất cả theo": (real, np.zeros(len(E), bool)), "tất cả ngược": (np.zeros(len(E), bool), real),
            "G109: theo khi ADX H1 ≥ 25": (real & adx, np.zeros(len(E), bool))}
    for nm, (fo, fa) in refs.items():
        T = trades(E, fo, fa)
        for per in ("train", "validate"):
            x = T[T["period"] == per]
            L.append(f"| mốc: {nm} | thật | {per} | {line(x[x['kind'] == 'theo'])} | {line(x[x['kind'] == 'ngược'])} | {line(x)} |")
    L += ["", "### Đối chứng chọn ngẫu nhiên (validate)", ""] + rand_lines + [""]
    return L


def main(symbols):
    L = ["# G110 bước 3: học cuốn chiếu — phá thật hay giả, với bối cảnh (C), + volume (V), + price action (P), + cả hai (VP)", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g110-break-quality-volume.md (mục 3 và 5). Chỉ train và validate; "
         "**test 2026 niêm phong**. " + run_label() + " Mỗi tháng, mô hình học từ các sự kiện trước tháng ít nhất 1 ngày (có assert). "
         "Script: research/long/g110_models.py.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
