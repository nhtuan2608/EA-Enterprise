"""G108 step 3: walk-forward plans (kNN memory and LightGBM) on the structure / liquidity plans, with controls.
Train + validate only (2024-07 .. 2025-12); the 2026 test stays sealed.

  python g108_models.py        # writes docs/superpowers/reports/2026-10-13-g108-step3-models.md

Each month from 2024-12 the models learn from the plans whose exit happened before the month started (labels
known; asserted) and predict the plans of the month: p = P(target before invalidation), EV = p x RR - (1 - p).
  lgbm         LightGBM on all features (g108_features.FEATS)
  knn          per direction, K = 150 nearest past plans on standardised features, win rate shrunk to the base
  C2 time      LightGBM on direction + hour / weekday / session + RR only
  C3 no path   LightGBM without the M5 path / forming M30 features
  C4 shuffled  the lgbm model, path features shuffled between the plans of the month at prediction
  C1 random    the same number of plans drawn at random each month (200 draws)
Rules: EV > 0, and top 10 % (threshold = 90th percentile of the EVs predicted in the earlier months).
Trades: per direction one position at a time (a plan is taken only when the previous one has exited).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g
import g108_features as gf
from g108_patterns import boot_lower, dedupe

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-13-g108-step3-models.md"
FIRST_MONTH, LAST_MONTH = "2024-12-01", "2025-12-01"
K_NN, SHRINK = 150, 20
LGB = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8,
           subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, random_state=108)
SETS = {"lgbm": gf.FEATS, "C2 time": ["d", "hour", "dow", "sess", "rr"],
        "C3 no path": [f for f in gf.FEATS if f not in gf.F_PATH]}


def months():
    return list(pd.date_range(FIRST_MONTH, LAST_MONTH, freq="MS"))


def train_mask(X: pd.DataFrame, start: int) -> np.ndarray:
    """Plans whose label is known before `start` (exit bar closed before it)."""
    return (X["exit_time"] < start).to_numpy()


def ev(p, rr):
    return p * rr - (1 - p)


def fit_predict_lgbm(Xtr, ytr, Xte):
    import lightgbm as lgb
    m = lgb.LGBMClassifier(**LGB)
    m.fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def fit_predict_knn(Xtr, ytr, Xte, base):
    from sklearn.neighbors import NearestNeighbors
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A = np.clip((Xtr - mu) / sd, -5, 5)
    B = np.clip((Xte - mu) / sd, -5, 5)
    nn = NearestNeighbors(n_neighbors=min(K_NN, len(A))).fit(A)
    _, idx = nn.kneighbors(B)
    wins = ytr[idx].sum(1)
    return (wins + SHRINK * base) / (idx.shape[1] + SHRINK)


def walk_forward(X: pd.DataFrame, F: pd.DataFrame, seed=108):
    rng = np.random.default_rng(seed)
    y = (X["outcome"] == 1).to_numpy().astype(int)
    pred = {k: np.full(len(X), np.nan) for k in list(SETS) + ["knn", "C4 shuffled"]}
    audit = []
    for m0 in months():
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = train_mask(X, s)
        te = ((X["time"] >= s) & (X["time"] < e)).to_numpy()
        assert X.loc[tr, "exit_time"].max() < s and X.loc[te, "time"].min() >= s
        assert not (X.loc[te, "period"] == "test").any()
        audit.append((m0.strftime("%Y-%m"), int(tr.sum()), int(te.sum()), pd.to_datetime(X.loc[tr, "exit_time"].max(), unit="s")))
        for name, cols in SETS.items():
            pred[name][te] = fit_predict_lgbm(F.loc[tr, cols], y[tr], F.loc[te, cols])
        Fs = F.loc[te, gf.FEATS].copy()
        perm = rng.permutation(len(Fs))
        Fs[gf.F_PATH] = Fs[gf.F_PATH].to_numpy()[perm]
        pred["C4 shuffled"][te] = fit_predict_lgbm(F.loc[tr, gf.FEATS], y[tr], Fs)
        for d in (1, -1):
            trd, ted = tr & (X["d"] == d).to_numpy(), te & (X["d"] == d).to_numpy()
            if ted.sum() == 0:
                continue
            cols = [c for c in gf.FEATS if c != "d"]
            pred["knn"][ted] = fit_predict_knn(F.loc[trd, cols].to_numpy(float), y[trd], F.loc[ted, cols].to_numpy(float),
                                               y[trd].mean())
        print(audit[-1], flush=True)
    return pred, audit


def auc(p, y):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan")


def select(X: pd.DataFrame, evp: np.ndarray, rule: str) -> np.ndarray:
    if rule == "EV > 0":
        return evp > 0
    sel = np.zeros(len(X), bool)
    mon = X["month"].to_numpy()
    for m in sorted(set(mon)):
        past = evp[(mon < m) & ~np.isnan(evp)]
        if len(past) < 500:
            continue
        sel |= (mon == m) & (evp >= np.quantile(past, 0.90))
    return sel


def trades(X: pd.DataFrame, sel: np.ndarray) -> pd.DataFrame:
    rows = []
    for d in (1, -1):
        free = -1
        S = X[sel & (X["d"] == d).to_numpy()].sort_values("time")
        for r in S.itertuples():
            if r.time < free:
                continue
            rows.append((r.time, d, r.R))
            free = r.exit_time
    return pd.DataFrame(rows, columns=["time", "d", "R"]).sort_values("time")


def line(x: pd.DataFrame, months_n: float) -> str:
    if len(x) == 0:
        return "0 | | | | | |"
    eq = x["R"].cumsum().to_numpy()
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    lb = boot_lower(x["R"].to_numpy(), (x["time"] // 86400).to_numpy())
    return (f"{len(x)} | {len(x) / months_n:.0f} | {100 * (x['R'] > 0).mean():.0f}% | {x['R'].mean():+.3f} | {lb:+.3f} | "
            f"{x['R'].sum():+.1f}R / DD {dd:.1f}R")


def main():
    raw = pd.read_pickle(g.OUT)
    raw = raw[raw["period"] != "test"]                            # sealed
    X = dedupe(raw).reset_index(drop=True)
    m5 = g.load_m5()
    tt = m5["time"].to_numpy(np.int64)
    X["exit_time"] = tt[X["exit_i"].to_numpy()] + 300
    X["month"] = pd.to_datetime(X["time"], unit="s").dt.strftime("%Y-%m")
    F = gf.features(m5, X, gf.long_m30())
    pred, audit = walk_forward(X, F)
    y = (X["outcome"] == 1).to_numpy().astype(int)
    oos = ~np.isnan(pred["lgbm"])
    per = {"OOS 12/2024–03/2025 (cuối train)": oos & (X["period"] == "train").to_numpy(),
           "Validate 04–12/2025": oos & (X["period"] == "validate").to_numpy()}
    rr = X["rr"].to_numpy()
    L = ["# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: "
         "reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày "
         "đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** "
         "Script: research/long/g108_features.py, g108_models.py.", "",
         f"Plan đã gộp (một plan một lần): {len(X)}; có dự báo ngoài mẫu: {int(oos.sum())}. "
         "p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p).", "",
         "## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)", "",
         "| Mô hình | Kỳ | MUA | BÁN |", "|---|---|---|---|"]
    for name in ["lgbm", "knn", "C2 time", "C3 no path", "C4 shuffled"]:
        for pn, m in per.items():
            a = [auc(pred[name][m & (X["d"] == d).to_numpy()], y[m & (X["d"] == d).to_numpy()]) for d in (1, -1)]
            L.append(f"| {name} | {pn} | {a[0]:.3f} | {a[1]:.3f} |")
    L += ["", "AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được \"mục tiêu gần thì dễ chạm\"; "
          "điều cần xem là lợi nhuận (bảng dưới), không phải AUC.", ""]
    vm = per["Validate 04–12/2025"]
    L += ["## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)", "", "| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |", "|---|---|---|---|---|---|"]
    for d in (1, -1):
        m = vm & (X["d"] == d).to_numpy()
        e = ev(pred["lgbm"][m], rr[m])
        q = pd.qcut(e, 10, labels=False, duplicates="drop")
        for k in range(int(q.max()) + 1):
            s = q == k
            L.append(f"| {'MUA' if d == 1 else 'BÁN'} | {k + 1} | {int(s.sum())} | {pred['lgbm'][m][s].mean():.2f} | "
                     f"{100 * y[m][s].mean():.0f}% | {X['R'].to_numpy()[m][s].mean():+.3f} |")
    n_months = {pn: max(1, len(set(X.loc[m, "month"]))) for pn, m in per.items()}
    L += ["", "## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)", "",
          "| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    allsel = np.ones(len(X), bool)
    for pn, m in per.items():
        T0 = trades(X, allsel & m)
        for d, dn in ((1, "MUA"), (-1, "BÁN")):
            L.append(f"| (vào mọi plan) | — | {pn} | {dn} | {line(T0[T0['d'] == d], n_months[pn])} |")
    rand_note = []
    for name in ["lgbm", "knn", "C2 time", "C3 no path", "C4 shuffled"]:
        evp = ev(pred[name], rr)
        for rule in ("EV > 0", "top 10%"):
            sel = select(X, evp, rule)
            for pn, m in per.items():
                Tq = trades(X, sel & m)
                for d, dn in ((1, "MUA"), (-1, "BÁN")):
                    L.append(f"| {name} | {rule} | {pn} | {dn} | {line(Tq[Tq['d'] == d], n_months[pn])} |")
            if name == "lgbm" and rule == "top 10%":
                # C1: the same number of plans per month and direction, drawn at random, 200 times
                rng = np.random.default_rng(7)
                for d, dn in ((1, "MUA"), (-1, "BÁN")):
                    m = vm & (X["d"] == d).to_numpy()
                    chosen = X[sel & m]
                    if len(chosen) == 0:
                        continue
                    pool = X[m]
                    draws = []
                    for _ in range(200):
                        idx = np.concatenate([rng.choice(pool.index[pool["month"] == mo], size=c, replace=False)
                                              for mo, c in chosen.groupby("month").size().items()])
                        draws.append(X.loc[idx, "R"].mean())
                    draws = np.array(draws)
                    rand_note.append(f"- {dn}: lgbm top 10% trên validate R/plan {chosen['R'].mean():+.3f}; chọn ngẫu nhiên cùng "
                                     f"số plan mỗi tháng: trung bình {draws.mean():+.3f}, 95% ≤ {np.quantile(draws, .95):+.3f}; "
                                     f"tỉ lệ lần ngẫu nhiên ≥ mô hình: **{(draws >= chosen['R'].mean()).mean():.3f}**")
    L += ["", "## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)", ""] + rand_note
    L += ["", "## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)", "", "| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |", "|---|---|---|---|---|"]
    evl = ev(pred["lgbm"], rr)
    for mo, ntr, nte, _ in audit:
        m = (X["month"] == mo).to_numpy() & oos
        e = evl[m]
        top = e >= np.quantile(e, 0.9)
        L.append(f"| {mo} | {ntr} | {nte} | {auc(pred['lgbm'][m], y[m]):.3f} | {X['R'].to_numpy()[m][top].mean():+.3f} |")
    L += ["", "## Kiểm tra cuốn chiếu", "", "| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {dd} |" for a, b, c, dd in audit]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
