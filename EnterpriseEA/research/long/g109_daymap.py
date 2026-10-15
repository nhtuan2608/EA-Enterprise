"""G109 step 2: how good is the day zone map? Train + validate only (2026 test sealed).

  python g109_daymap.py XAUUSD EURUSD GBPUSD USDJPY     # writes docs/superpowers/reports/2026-10-13-g109-daymap.md

A  touch: real map zones vs fake zones at the same distance from the open (buckets of ATR D1)
B  reaction once touched: bounce / through / neither, real vs fake (fake re-weighted to the real distance mix),
   by kind and confluence; day-clustered bootstrap for the real - fake bounce difference
C  which side first (nearest zone above vs below): B1 nearest, B2 train touch-rate table, B3 D1 regime, and a
   walk-forward logistic model (monthly, trained on days before the month) - accuracy and log loss
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-13-g109-daymap.md"
BUCKETS = [0, 0.25, 0.5, 1.0, 2.0, 3.0]
KINDS = ["PDH", "PDL", "PDM", "PDC", "VWAP", "PWH", "PWL", "H1SH", "H1SL", "H4SH", "H4SL", "FVG", "EMA200_H1",
         "EMA200_H4", "EMA21_D1", "EMA50_D1", "R"]


def load(sym: str):
    import g108_data as g8
    Z = pd.read_pickle(g8.DATA / f"g109_zones_{sym}.pkl")
    D = pd.read_pickle(g8.DATA / f"g109_days_{sym}.pkl")
    Z = Z[Z["period"] != "test"].copy()                         # sealed
    D = D[D["period"] != "test"].copy()
    Z["adist"] = Z["dist"].abs()
    Z["bucket"] = pd.cut(Z["adist"], BUCKETS, labels=False, include_lowest=True)
    return Z, D


def boot_diff(a_ok: pd.DataFrame, b_ok: pd.DataFrame, col: str, n=1000, seed=109):
    """Day-clustered bootstrap of mean(a[col]) - mean(b[col]); returns (diff, low 5 %, high 95 %)."""
    rng = np.random.default_rng(seed)
    days = np.union1d(a_ok["day"].unique(), b_ok["day"].unique())
    ga = a_ok.groupby("day")[col].agg(["sum", "count"]).reindex(days, fill_value=0)
    gb = b_ok.groupby("day")[col].agg(["sum", "count"]).reindex(days, fill_value=0)
    out = []
    for _ in range(n):
        k = rng.integers(0, len(days), len(days))
        sa, ca = ga["sum"].to_numpy()[k].sum(), ga["count"].to_numpy()[k].sum()
        sb, cb = gb["sum"].to_numpy()[k].sum(), gb["count"].to_numpy()[k].sum()
        if ca and cb:
            out.append(sa / ca - sb / cb)
    d = a_ok[col].mean() - b_ok[col].mean()
    return d, float(np.quantile(out, 0.05)), float(np.quantile(out, 0.95))


def reweight(fake: pd.DataFrame, real: pd.DataFrame, col: str) -> float:
    """Mean of `col` over the fake zones, re-weighted to the real zones' distance-bucket mix."""
    w = real["bucket"].value_counts(normalize=True)
    m = fake.groupby("bucket")[col].mean()
    common = w.index.intersection(m.index)
    return float((m[common] * w[common]).sum() / w[common].sum()) if len(common) else float("nan")


def side_first(D: pd.DataFrame, Z: pd.DataFrame):
    """Rows: days where the nearest upper or lower zone was touched first. Returns the table of predictions."""
    X = D[(D["first"] != 0) & D["up_dist"].notna() & D["dn_dist"].notna()].copy()
    X["y"] = (X["first"] == 1).astype(int)
    X["month"] = pd.to_datetime(X["t0"], unit="s").dt.strftime("%Y-%m")
    X["b1"] = (X["up_dist"] < X["dn_dist"]).astype(int)
    X["b3"] = np.where(X["regime"] == 1, 1, np.where(X["regime"] == -1, 0, X["b1"]))
    # B2: touch rate by distance bucket on train (real map zones), side with the higher rate
    tr = Z[(Z["period"] == "train") & Z["map"] & ~Z["fake"] & (Z["side"] != 0)]
    rate = tr.groupby("bucket")["touched"].mean()
    def p(d):
        b = int(pd.cut([d], BUCKETS, labels=False, include_lowest=True)[0]) if d == d and d <= 3 else len(BUCKETS) - 2
        return float(rate.get(b, rate.mean()))
    X["b2"] = (X["up_dist"].map(p) > X["dn_dist"].map(p)).astype(int)
    feats = ["ldr", "up_dist", "dn_dist", "up_n", "dn_n", "regime", "prev_close_pos", "prev_range", "dow"]
    X["ldr"] = np.log(X["dn_dist"] / X["up_dist"])
    from sklearn.linear_model import LogisticRegression
    X["p_model"] = np.nan
    for mo in sorted(X["month"].unique()):
        s = pd.Timestamp(mo + "-01").timestamp()
        trm = X["t0"] < s - 86400
        te = X["month"] == mo
        if trm.sum() < 80:
            continue
        A = X.loc[trm, feats].fillna(0).to_numpy(); mu, sd = A.mean(0), A.std(0) + 1e-9
        m = LogisticRegression(C=0.5, max_iter=500).fit((A - mu) / sd, X.loc[trm, "y"])
        X.loc[te, "p_model"] = m.predict_proba((X.loc[te, feats].fillna(0).to_numpy() - mu) / sd)[:, 1]
    return X


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def section(sym: str) -> list[str]:
    Z, D = load(sym)
    L = [f"## {sym}", "", f"Ngày (train + validate): {len(D)}; vùng bản đồ thật {int((Z['map'] & ~Z['fake']).sum())}, "
         f"vùng giả {int(Z['fake'].sum())}, vùng trong ngày {int((~Z['map']).sum())}.", ""]
    real = Z[Z["map"] & ~Z["fake"] & (Z["side"] != 0)]
    fake = Z[Z["fake"] & (Z["side"] != 0)]
    # A touch by distance
    L += ["### A. Tỉ lệ chạm trong ngày theo khoảng cách (ATR D1), vùng thật so với vùng giả", "",
          "| Khoảng cách | Kỳ | Thật: số vùng · chạm | Giả: số vùng · chạm |", "|---|---|---|---|"]
    for b in range(len(BUCKETS) - 1):
        for per in ("train", "validate"):
            r = real[(real["bucket"] == b) & (real["period"] == per)]
            f = fake[(fake["bucket"] == b) & (fake["period"] == per)]
            L.append(f"| {BUCKETS[b]}–{BUCKETS[b + 1]} | {per} | {len(r)} · {100 * r['touched'].mean():.0f}% | "
                     f"{len(f)} · {100 * f['touched'].mean():.0f}% |")
    # B reaction
    rt, ft = real[real["touched"]].copy(), fake[fake["touched"]].copy()
    for X in (rt, ft):
        X["bounce"] = (X["reaction"] == 1).astype(float)
        X["through"] = (X["reaction"] == -1).astype(float)
    L += ["", "### B. Phản ứng khi chạm (trong 12 nến M5): bật lại / xuyên qua", "",
          "| Nhóm | Kỳ | Thật: lần chạm · bật · xuyên | Giả (cân theo khoảng cách): bật · xuyên | Chênh bật (thật − giả) [5%; 95%] |",
          "|---|---|---|---|---|"]
    groups = [("tất cả", lambda x: np.ones(len(x), bool))]
    groups += [(f"hợp lưu n={k}", (lambda k: lambda x: (x["n"] == k) if k < 3 else (x["n"] >= 3))(k)) for k in (1, 2, 3)]
    groups += [(f"có {kd}", (lambda kd: lambda x: x["kinds"].str.contains(kd, regex=False))(kd)) for kd in KINDS]
    for name, fn in groups:
        for per in ("train", "validate"):
            r = rt[(rt["period"] == per)]
            r = r[fn(r)]
            f = ft[ft["period"] == per]
            if len(r) < 30:
                continue
            fb, fth = reweight(f, r, "bounce"), reweight(f, r, "through")
            d, lo, hi = boot_diff(r, f[f["bucket"].isin(r["bucket"].unique())], "bounce")
            L.append(f"| {name} | {per} | {len(r)} · {100 * r['bounce'].mean():.0f}% · {100 * r['through'].mean():.0f}% | "
                     f"{100 * fb:.0f}% · {100 * fth:.0f}% | {100 * (r['bounce'].mean() - fb):+.1f} [{100 * lo:+.1f}; {100 * hi:+.1f}] |")
    intra = Z[~Z["map"] & Z["touched"] & (Z["side"] != 0)].copy()
    if len(intra):
        intra["k"] = intra["kinds"].str.replace("_H", "").str.replace("_L", "")
        L += ["", "Vùng trong ngày (không có vùng giả để so; chỉ mô tả):", "", "| Vùng | Kỳ | Lần chạm · bật · xuyên |", "|---|---|---|"]
        for (k, per), x in intra.groupby(["k", "period"]):
            L.append(f"| {k} | {per} | {len(x)} · {100 * (x['reaction'] == 1).mean():.0f}% · {100 * (x['reaction'] == -1).mean():.0f}% |")
    # C side first
    X = side_first(D, Z)
    L += ["", "### C. Nhận định đầu ngày: vùng trên hay vùng dưới được chạm trước", "",
          f"Ngày có ít nhất một trong hai vùng gần nhất được chạm: {len(X)}.", "",
          "| Cách đoán | Kỳ | Ngày | Đúng | Log loss |", "|---|---|---|---|---|"]
    for per in ("train", "validate"):
        s = X[X["period"] == per]
        for name, col in (("B1 vùng gần hơn", "b1"), ("B2 tần suất chạm (train)", "b2"), ("B3 xu hướng D1", "b3")):
            L.append(f"| {name} | {per} | {len(s)} | {100 * (s[col] == s['y']).mean():.1f}% | |")
        m = s[s["p_model"].notna()]
        if len(m):
            L.append(f"| Mô hình (cuốn chiếu) | {per} | {len(m)} | {100 * ((m['p_model'] > 0.5).astype(int) == m['y']).mean():.1f}% | "
                     f"{logloss(m['y'].to_numpy(), m['p_model'].to_numpy()):.3f} (B1 cùng ngày: {100 * (m['b1'] == m['y']).mean():.1f}%) |")
    L.append("")
    return L


def main(symbols):
    L = ["# G109 bước 2: bản đồ vùng đầu ngày có đúng không", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g109-day-zone-map.md. Dữ liệu raw MT5 (EURUSD/GBPUSD đổi "
         "từ UTC sang giờ server). Chỉ train 07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); **test 2026 niêm phong**. "
         "Script: research/long/g109_zones.py, g109_daymap.py, g109_audit.py.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
