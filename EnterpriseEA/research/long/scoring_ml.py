"""G33b: the trade-quality score again with stronger models (scikit-learn, LightGBM). MT5 data only.

  python scoring_ml.py

Same rows and features as scoring.py (G33). Models: L2 logistic regression (scikit-learn) and a
small, heavily regularised LightGBM, each with setup indicators. Two protocols:
  FIXED        fit on 2010-2016 once, score 2017-2020 and 2021-2025 (as G33)
  WALKFORWARD  for every year 2014-2025, fit on all earlier years, score that year
Reported per setup: AUC (0.5 = no skill), expectancy of the bottom / top third of the score
(thresholds from the training rows) and of "keep the top two thirds", next to random removal of
the same share (90th percentile of 300 draws).
"""
from __future__ import annotations

import warnings
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import scoring  # noqa: E402

warnings.filterwarnings("ignore")
SETUPS = scoring.SETUPS


def matrix(rows: list[dict]) -> np.ndarray:
    return np.array([[r["f"][k] for k in scoring.FEATURES] + [1.0 if r["setup"] == s else 0.0 for s in SETUPS[1:]]
                     for r in rows])


def models():
    return {
        "logistic": lambda: LogisticRegression(C=0.3, max_iter=2000),
        "lightgbm": lambda: lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=7, max_depth=3,
                                               min_child_samples=60, subsample=0.8, subsample_freq=1,
                                               colsample_bytree=0.8, reg_lambda=5.0, verbose=-1),
    }


def random_p90(r: np.ndarray, keep: int, rng: np.random.Generator) -> float:
    if keep <= 0 or keep >= len(r):
        return float("nan")
    sims = np.array([rng.choice(r, keep, replace=False).mean() for _ in range(300)])
    return float(np.quantile(sims, 0.9))


def report(rows: list[dict], scores: np.ndarray, train_scores: dict, rng) -> list[str]:
    """Per setup and period: AUC, bottom/top third, keep top 2/3 vs random."""
    out = []
    r_all = np.array([x["r"] for x in rows])
    for name in SETUPS:
        idx = np.array([x["setup"] == name for x in rows])
        if name not in train_scores or idx.sum() < 30:
            continue
        lo, hi = np.quantile(train_scores[name], [1 / 3, 2 / 3])
        cells = []
        for p in ("validate", "test"):
            m = idx & np.array([x["period"] == p for x in rows])
            if m.sum() < 10:
                cells.append("-")
                continue
            r, s = r_all[m], scores[m]
            y = (r > 0).astype(int)
            auc = roc_auc_score(y, s) if 0 < y.sum() < len(y) else float("nan")
            low, top, keep = r[s < lo], r[s >= hi], r[s >= lo]
            rp = random_p90(r, len(keep), rng)
            beat = "✓" if len(keep) and keep.mean() > rp else "✗"
            cells.append(f"AUC {auc:.2f}; tất cả {r.mean():+.2f}; thấp {low.mean() if len(low) else 0:+.2f}; "
                         f"cao {top.mean() if len(top) else 0:+.2f}; giữ 2/3 {keep.mean() if len(keep) else 0:+.2f} "
                         f"(ngẫu nhiên {rp:+.2f}) {beat}")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    return out


def main() -> None:
    usd = filters.usd_index()
    rows = [r for s in ls.SYMBOLS for r in scoring.rows_for(s, usd)]
    for r in rows:
        r["period"] = exits.period(r["utc"])
        r["year"] = datetime.fromtimestamp(r["utc"], timezone.utc).year
    X, y = matrix(rows), np.array([1 if r["r"] > 0 else 0 for r in rows])
    rng = np.random.default_rng(5)
    lines = ["# G33b: điểm chất lượng lệnh với mô hình mạnh hơn (scikit-learn, LightGBM; chỉ dữ liệu MT5)", "",
             f"{len(rows)} lệnh, {len(scoring.FEATURES)} đặc trưng + loại setup. ✓ = giữ 2/3 điểm cao thắng việc bỏ ngẫu nhiên (p90).", ""]
    train = np.array([r["period"] == "train" for r in rows])
    for mname, make in models().items():
        # FIXED: fit on 2010-2016.
        m = make().fit(X[train], y[train])
        s = m.predict_proba(X)[:, 1]
        tr = {n: s[train & np.array([r["setup"] == n for r in rows])] for n in SETUPS}
        lines += [f"## {mname}: học một lần trên 2010–2016", "", "| Setup | 2017–2020 | 2021–2025 |", "|---|---|---|"]
        lines += report(rows, s, tr, rng)
        # WALKFORWARD: each year scored by a model fitted on all earlier years.
        s_wf = np.full(len(rows), np.nan)
        years = np.array([r["year"] for r in rows])
        tr_wf = {n: [] for n in SETUPS}
        for yr in range(2014, 2026):
            fit_m = years < yr
            cur = years == yr
            if fit_m.sum() < 200 or cur.sum() == 0:
                continue
            mm = make().fit(X[fit_m], y[fit_m])
            s_wf[cur] = mm.predict_proba(X[cur])[:, 1]
            past = mm.predict_proba(X[fit_m])[:, 1]
            for n in SETUPS:
                tr_wf[n].extend(past[np.array([r["setup"] == n for r in rows])[fit_m]].tolist())
        ok = ~np.isnan(s_wf)
        sub = [r for r, k in zip(rows, ok) if k]
        lines += ["", f"## {mname}: học lại mỗi năm trên các năm trước (walk-forward 2014–2025)", "",
                  "| Setup | 2017–2020 | 2021–2025 |", "|---|---|---|"]
        lines += report(sub, s_wf[ok], {n: np.array(v) for n, v in tr_wf.items() if v}, rng)
        if mname == "lightgbm":
            imp = sorted(zip(scoring.FEATURES + [f"setup {x}" for x in SETUPS[1:]], m.feature_importances_), key=lambda x: -x[1])
            lines += ["", "Độ quan trọng (LightGBM, số lần dùng để chia): " + ", ".join(f"{k} {v}" for k, v in imp[:8])]
        lines.append("")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "scoring_ml.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
