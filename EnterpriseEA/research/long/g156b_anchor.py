"""G156b: quantitative anchor per question (M0 base rate, M1 shrunk strata table, M2 logistic / linear, M3 shallow LightGBM),
walk-forward by year, Brier skill vs M0 with week-block bootstrap; Q2 scored by R. Plan: docs/superpowers/plans/2026-10-24-g156b-anchor.md.

Usage: g156b_anchor.py <g156a results dir> <out dir> [--repose]
  --repose (G156a2): only Q1 and Q4 with the symmetric first-passage labels; Q1 drops LƯỠNG LỰ / CẢ HAI, Q4 keeps every open leg and
  drops ĐÓNG TRƯỚC / CẢ HAI.
"""
import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
SELECT, CHECK, AFTER = [2020, 2021, 2022, 2023], [2024, 2025, 2026], "sau"
CHECK_END = pd.Timestamp("2026-07-01").timestamp()
K_SHRINK, BOOT, SEED = 50, 1000, 156
DIRECTIONAL = ["chế độ D1", "SMA50/200 D1", "h4_side", "dải EMA xếp", "di_gap", "cách VWAP/atr", "cách biên Á trên/atr",
               "cách biên Á dưới/atr", "cách PDH/atr", "cách PDL/atr", "cách PWH/atr", "cách PWL/atr", "EMA200 D1 /atr",
               "lợi nhuận 4 nến/atr", "lợi nhuận 16 nến/atr"]
PLAIN = ["giờ", "thứ", "adx", "atr14/atr100", "phân vị atr 1 năm", "phạm vi ngày/ADR20", "biên Á/ADR20", "spread/atr"]
LGB = dict(max_depth=3, n_estimators=200, learning_rate=0.05, min_child_samples=200, verbose=-1, random_state=SEED)


def prepare(df, q):
    df = df.copy()
    t = df["giờ server đóng"]
    df["năm"] = pd.to_datetime(t, unit="s").dt.year
    df["nhóm"] = np.where(t >= CHECK_END, AFTER, df["năm"].astype(str))
    d = df["chiều"]
    X = pd.DataFrame(index=df.index)
    for c in DIRECTIONAL:
        X[c + " ×chiều"] = df[c] * d
    for c in PLAIN:
        X[c] = df[c]
    for c in ("phút tới tin USD HIGH", "phút từ tin USD HIGH"):
        X["log " + c] = np.log1p(df[c].clip(lower=0, upper=720).fillna(720))
    cats = ["phiên"]
    if q == "Q1":
        X["vượt mức/atr"] = df["vượt mức/atr"]
        cats.append("mức")
        y = (df["đáp án"] == "ĐI TIẾP").astype(float)
        strata = df["mức"] + "|" + df["phiên"] + "|" + (df["chế độ D1"] * d).astype(int).astype(str)
    elif q == "Q2":
        cats.append("loại lệnh")
        y = df["R"].astype(float)
        strata = df["loại lệnh"] + "|" + (df["chế độ D1"] * d).astype(int).astype(str)
    elif q == "Q3":
        miss = df["điều kiện S07"].astype(str).str.zfill(5).map(lambda s: "thiếu " + "".join(str(k + 1) for k, ch in enumerate(s) if ch == "0"))
        df["thiếu"] = miss
        cats.append("thiếu")
        y = (df["đáp án"] == "S07 VÀO").astype(float)
        strata = miss + "|" + df["phiên"]
    else:
        X["R đang có"] = df["R đang có"]
        X["giờ đã giữ"] = df["giờ đã giữ"]
        X["lệnh gốc"] = df["lệnh gốc"].astype(float)
        y = (df["đáp án"] == "ĐI TIẾP").astype(float)
        rb = pd.cut(df["R đang có"], [0, 1, 2, 4, np.inf], labels=["0-1R", "1-2R", "2-4R", ">4R"], include_lowest=True).astype(str)
        strata = rb + "|" + (df["chế độ D1"] * d).astype(int).astype(str)
    X = pd.concat([X, pd.get_dummies(df[cats].astype(str), prefix=cats, dtype=float)], axis=1)
    return df, X.astype(float), y, strata


def fit_predict(model, Xtr, ytr, str_tr, Xte, str_te, regression):
    if model == "M0":
        return np.full(len(Xte), ytr.mean())
    if model == "M1":
        base = ytr.mean()
        g = pd.DataFrame({"s": str_tr.values, "y": ytr.values}).groupby("s")["y"].agg(["sum", "count"])
        est = (g["sum"] + K_SHRINK * base) / (g["count"] + K_SHRINK)
        return str_te.map(est).fillna(base).to_numpy()
    med = Xtr.median()
    if model == "M2":
        A, B = Xtr.fillna(med), Xte.fillna(med)
        mu, sd = A.mean(), A.std().replace(0, 1)
        A, B = (A - mu) / sd, (B - mu) / sd
        if regression:
            return Ridge(alpha=1.0).fit(A, ytr).predict(B)
        return LogisticRegression(max_iter=2000, C=1.0).fit(A, ytr).predict_proba(B)[:, 1]
    if regression:
        return lgb.LGBMRegressor(**LGB).fit(Xtr, ytr).predict(Xte)
    return lgb.LGBMClassifier(**LGB).fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def walk(df, X, y, strata, regression):
    """Out-of-sample predictions for every test group (expanding window by year)."""
    preds = {m: pd.Series(np.nan, index=df.index) for m in ("M0", "M1", "M2", "M3")}
    for grp in [str(x) for x in SELECT + CHECK] + [AFTER]:
        te = df["nhóm"] == grp
        if not te.any():
            continue
        first = df.loc[te, "giờ server đóng"].min()
        tr = df["giờ server đóng"] < first
        if tr.sum() < 300 or y[tr].nunique() < 2:
            continue
        for m in preds:
            preds[m][te] = fit_predict(m, X[tr], y[tr], strata[tr], X[te], strata[te], regression)
    return preds


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def week_boot(df, f, rng):
    """95 % interval of statistic f(index) over week blocks."""
    wk = (df["giờ server đóng"] // (7 * 86400)).to_numpy()
    blocks = {}
    for i, w in zip(df.index, wk):
        blocks.setdefault(w, []).append(i)
    keys = list(blocks)
    out = []
    for _ in range(BOOT):
        pick = rng.choice(len(keys), len(keys))
        idx = [i for k in pick for i in blocks[keys[k]]]
        out.append(f(idx))
    return [round(float(np.percentile(out, 2.5)), 4), round(float(np.percentile(out, 97.5)), 4)]


def evaluate_class(df, y, preds, rng):
    res = {}
    sel = df["nhóm"].isin([str(x) for x in SELECT])
    chk = df["nhóm"].isin([str(x) for x in CHECK])
    for m, p in preds.items():
        r = {}
        for name, mask in (("chọn", sel), ("kiểm", chk), (AFTER, df["nhóm"] == AFTER)):
            mk = mask & p.notna()
            if not mk.any():
                continue
            b, b0 = brier(p[mk], y[mk]), brier(preds["M0"][mk], y[mk])
            auc = roc_auc_score(y[mk], p[mk]) if y[mk].nunique() == 2 and m != "M0" else None
            r[name] = {"n": int(mk.sum()), "Brier": round(b, 4), "kỹ năng vs M0": round(1 - b / b0, 4) if b0 > 0 else None,
                       "AUC": round(float(auc), 3) if auc is not None else None}
        r["kiểm theo năm (kỹ năng)"] = {}
        for yr in CHECK:
            mk = (df["nhóm"] == str(yr)) & p.notna()
            if mk.any():
                r["kiểm theo năm (kỹ năng)"][str(yr)] = round(1 - brier(p[mk], y[mk]) / brier(preds["M0"][mk], y[mk]), 4)
        res[m] = r
    best = min(preds, key=lambda m: (round(res[m].get("chọn", {}).get("Brier", 9), 4), ["M0", "M1", "M2", "M3"].index(m)))
    mk = chk & preds[best].notna()
    sub = df[mk]
    pb, p0, yy = preds[best], preds["M0"], y

    def skill(idx):
        return 1 - brier(pb[idx], yy[idx]) / brier(p0[idx], yy[idx])

    ci = week_boot(sub, skill, rng) if best != "M0" else None
    yrs = res[best]["kiểm theo năm (kỹ năng)"]
    ok = best != "M0" and ci is not None and ci[0] > 0 and sum(v > 0 for v in yrs.values()) >= 2
    cal = []
    if best != "M0":
        q = pd.qcut(pb[mk], 10, duplicates="drop")
        for b_, grp in pd.DataFrame({"p": pb[mk], "y": yy[mk], "b": q}).groupby("b", observed=True):
            cal.append({"dự báo TB": round(float(grp["p"].mean()), 3), "thực tế": round(float(grp["y"].mean()), 3), "n": int(len(grp))})
    return res, best, {"mô hình mỏ neo": best, "kỹ năng kiểm 95 %": ci, "bối cảnh có giá trị": bool(ok), "hiệu chỉnh (kiểm)": cal}


def evaluate_reg(df, y, preds, rng):
    res = {}
    sel = df["nhóm"].isin([str(x) for x in SELECT])
    chk = df["nhóm"].isin([str(x) for x in CHECK])

    def tercile(p, yy):
        q = pd.qcut(p.rank(method="first"), 3, labels=False)
        return float(yy[q == 2].mean() - yy[q == 0].mean())

    for m, p in preds.items():
        r = {}
        for name, mask in (("chọn", sel), ("kiểm", chk), (AFTER, df["nhóm"] == AFTER)):
            mk = mask & p.notna()
            if not mk.any():
                continue
            rho = spearmanr(p[mk], y[mk]).correlation if m != "M0" else 0.0
            r[name] = {"n": int(mk.sum()), "Spearman": round(float(rho), 3),
                       "R 1/3 cao − 1/3 thấp": round(tercile(p[mk], y[mk]), 3) if m != "M0" else 0.0,
                       "R TB": round(float(y[mk].mean()), 3)}
        r["kiểm theo năm (Spearman)"] = {str(yr): round(float(spearmanr(p[(df["nhóm"] == str(yr)) & p.notna()],
                                                                    y[(df["nhóm"] == str(yr)) & p.notna()]).correlation), 3)
                                         for yr in CHECK if m != "M0" and ((df["nhóm"] == str(yr)) & p.notna()).sum() > 10}
        res[m] = r
    best = max(preds, key=lambda m: (res[m].get("chọn", {}).get("Spearman", -9), -["M0", "M1", "M2", "M3"].index(m)))
    mk = chk & preds[best].notna()
    sub = df[mk]
    ci = week_boot(sub, lambda idx: spearmanr(preds[best][idx], y[idx]).correlation, rng) if best != "M0" else None
    yrs = res[best].get("kiểm theo năm (Spearman)", {})
    ok = best != "M0" and ci is not None and ci[0] > 0 and sum(v > 0 for v in yrs.values()) >= 2
    return res, best, {"mô hình mỏ neo": best, "Spearman kiểm 95 %": ci, "bối cảnh có giá trị": bool(ok)}


def importance(df, X, y, regression):
    """Permutation importance of M3 trained before 2024, measured on the check years."""
    tr = df["giờ server đóng"] < pd.Timestamp("2024-01-01").timestamp()
    te = df["nhóm"].isin([str(x) for x in CHECK])
    if regression:
        m = lgb.LGBMRegressor(**LGB).fit(X[tr], y[tr])
        score = lambda Z: -float(np.mean((m.predict(Z) - y[te]) ** 2))  # noqa: E731
    else:
        m = lgb.LGBMClassifier(**LGB).fit(X[tr], y[tr])
        score = lambda Z: -brier(m.predict_proba(Z)[:, 1], y[te])  # noqa: E731
    base = score(X[te])
    rng = np.random.default_rng(SEED)
    out = {}
    for c in X.columns:
        Z = X[te].copy()
        Z[c] = rng.permutation(Z[c].to_numpy())
        out[c] = base - score(Z)
    top = sorted(out.items(), key=lambda kv: -kv[1])[:10]
    return [{"trường": k, "mất khi xáo": round(v, 5)} for k, v in top]


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    repose = "--repose" in sys.argv
    summary = {}
    for q in (("Q1", "Q4") if repose else ("Q1", "Q2", "Q3", "Q4")):
        df = pd.read_csv(src / f"{q}.csv", encoding="utf-8")
        if q == "Q1":
            df = df[~df["đáp án"].isin(["LƯỠNG LỰ", "CẢ HAI"])]
        if q == "Q4":
            df = df[~df["đáp án"].isin(["ĐÓNG TRƯỚC", "CẢ HAI"])] if repose else df[df["đang lời"]]
        df = df.reset_index(drop=True)
        df, X, y, strata = prepare(df, q)
        regression = q == "Q2"
        preds = walk(df, X, y, strata, regression)
        res, best, verdict = (evaluate_reg if regression else evaluate_class)(df, y, preds, rng)
        s = {"n": int(len(df)), "các mô hình": res, "kết luận": verdict, "trường quan trọng (M3, kiểm)": importance(df, X, y, regression)}
        if q == "Q3":
            chk = df["nhóm"].isin([str(x) for x in CHECK])
            prec = {}
            for m in ("M1", "M2", "M3"):
                p = preds[m][chk]
                yy = y[chk]
                for frac in (0.01, 0.05):
                    k = max(1, int(len(p) * frac))
                    top = p.sort_values(ascending=False).index[:k]
                    prec[f"{m} top {int(frac * 100)} %"] = {"n": k, "độ chính xác": round(float(yy[top].mean()), 3)}
            s["độ chính xác nhóm dự báo cao (kiểm)"] = prec
            s["tỷ lệ nền (kiểm)"] = round(float(y[chk].mean()), 3)
        summary[q] = s
        print(q, best, json.dumps(verdict, ensure_ascii=False, default=float)[:400], flush=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
