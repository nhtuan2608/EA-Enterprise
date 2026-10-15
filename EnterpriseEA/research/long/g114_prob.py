"""G114: setup selection by calibrated probability and lower-bound expected value
(docs/superpowers/plans/2026-10-14-g114-probability-selection.md). Train + validate only; the 2026 test stays sealed.

  [G113_TF=15|30] python g114_prob.py [XAUUSD EURUSD GBPUSD USDJPY]
      -> docs/superpowers/reports/2026-10-14-g114-prob[_m15|_m30].md, data/g114_pool_<SYMBOL>[suffix].pkl

Pool    every trade of the G109-G112 tables of the run (G109 S1 / S2 real zones with the fixed 2R target, G110 follow /
        fade, G111 real-level tests, G112 chases C1-C3 with exit X1), one family each, with its R (spread paid) and
        a few categorical factors fixed in advance (side, session, D1 / H4 with the trade, ADX H1 band, volume band,
        divergence, ...; the G113 day-type route from 10:00 as "day type agrees with the setup kind").
Month m (walk-forward)
        training = trades of the family whose exit is known 1 day before m starts (asserted)
        (a) naive Bayes: logit p0 + sum of log LR of the factor levels seen >= 30 times (Laplace counts)
        (b) L2 logistic regression and (c) LightGBM on the same one-hot factors
        calibration = pool-adjacent-violators (isotonic, step function) fitted on the earlier months' out-of-sample
        scores of the family whose result was known 1 day before m; at least 200 of them, else no decision
Decision  p = calibrated probability, n = size of its isotonic block, p_lo = Wilson 90 % lower bound;
          W / L = mean win / loss R of the training trades; EV_lo = p_lo W - (1 - p_lo) L; take when EV_lo > 0;
          one trade per symbol at a time (earliest first, ties by the higher EV_lo); size = 1/4 Kelly
          (EV_lo / var R, capped at 1 R) next to the fixed 1 R
Controls  rule (every trade of a family, no overlap), uncalibrated top 20 % (cut-off from earlier months), random
          trades of the same month on days the strategy did not trade (same count, 200 draws)
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g108_patterns import boot_lower
from g109_setups import SUF, run_label

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-14-g114-prob{g8.TFSUF}.md"
MIN_LEVEL, PRIOR_N, MIN_CAL, Z90, KELLY, CAP_R = 30, 30, 200, 1.6448536269514722, 0.25, 1.0
MODELS = ("nb", "logit", "lgbm")
KIND = {"S1": "rev", "S2": "mom", "G110F": "mom", "G110A": "rev", "T": "rev", "C1": "mom", "C2": "mom", "C3": "mom"}
FAM_NAME = {"S1": "G109 S1 quét & lấy lại", "S2": "G109 S2 phá & retest", "G110F": "G110 theo cú phá",
            "G110A": "G110 ngược cú phá", "T": "G111 đảo chiều khi test mức", "C1": "G112 đuổi xung lực",
            "C2": "G112 đuổi phá cực trị ngày", "C3": "G112 đuổi phá giữ"}


# --------------------------------------------------------------------------------------------- pure helpers
def band(x, cuts) -> np.ndarray:
    """0, 1, ... by fixed cut-offs (NaN -> -1)."""
    x = np.asarray(x, float)
    out = np.searchsorted(np.asarray(cuts, float), x, side="right").astype(int)
    out[np.isnan(x)] = -1
    return out


def wilson_lower(p: float, n: float, z: float = Z90) -> float:
    if n <= 0:
        return 0.0
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return max(0.0, (centre - rad) / den)


def pav_fit(score: np.ndarray, y: np.ndarray):
    """Isotonic (non-decreasing) step function: list of blocks (lowest score, p, n), sorted by score."""
    u, inv = np.unique(np.asarray(score, float), return_inverse=True)     # equal scores form one block first
    sy = np.bincount(inv, weights=np.asarray(y, float), minlength=len(u))
    cn = np.bincount(inv, minlength=len(u)).astype(float)
    blocks: list[list[float]] = []                      # [lo score, sum y, n]
    for v, t, c in zip(u, sy, cn):
        blocks.append([v, t, c])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] >= blocks[-1][1] / blocks[-1][2]:
            lo, sy, n = blocks.pop()
            blocks[-1][1] += sy
            blocks[-1][2] += n
    return [(b[0], b[1] / b[2], b[2]) for b in blocks]


def pav_predict(blocks, score: np.ndarray):
    """p and block size for each score (step function; below the first block -> the first block)."""
    los = np.array([b[0] for b in blocks])
    k = np.clip(np.searchsorted(los, np.asarray(score, float), side="right") - 1, 0, len(blocks) - 1)
    return np.array([blocks[i][1] for i in k]), np.array([blocks[i][2] for i in k])


def nb_table(F: pd.DataFrame, win: np.ndarray, min_level: int = MIN_LEVEL):
    """p0 and log LR per (factor, level) for levels seen >= min_level times (Laplace counts); others absent (LR 1)."""
    nw, nl = int(win.sum()), int((~win).sum())
    p0 = (nw + 1) / (nw + nl + 2)
    tab = {}
    for f in F.columns:
        v = F[f].to_numpy()
        lev = np.unique(v)
        K = len(lev)
        for x in lev:
            m = v == x
            if m.sum() < min_level:
                continue
            a, b = int((m & win).sum()), int((m & ~win).sum())
            tab[(f, int(x))] = math.log(((a + 1) / (nw + K)) / ((b + 1) / (nl + K)))
    return p0, tab


def nb_score(F: pd.DataFrame, p0: float, tab: dict) -> np.ndarray:
    s = np.full(len(F), math.log(p0 / (1 - p0)))
    for f in F.columns:
        v = F[f].to_numpy()
        s = s + np.array([tab.get((f, int(x)), 0.0) for x in v])
    return s


def shrunk_p(a: int, n: int, p0: float, k: int = PRIOR_N) -> float:
    return (a + k * p0) / (n + k)


def ev_lower(p_lo: float, W: float, L: float) -> float:
    return p_lo * W - (1 - p_lo) * L


def kelly_size(ev_lo: float, var_r: float, frac: float = KELLY, cap: float = CAP_R) -> float:
    if ev_lo <= 0 or var_r <= 0:
        return 0.0
    return float(min(cap, frac * ev_lo / var_r))


def one_at_a_time(i: np.ndarray, bars: np.ndarray, key: np.ndarray) -> np.ndarray:
    """Indices taken: earliest entry first, ties by the higher key, then the earlier row; a trade blocks entries until
    i + bars."""
    o = np.lexsort((-np.asarray(key, float), np.asarray(i)))
    free, keep = -1, []
    for q in o:
        if i[q] >= free:
            keep.append(q)
            free = i[q] + bars[q]
    return np.array(sorted(keep, key=lambda q: (i[q], q)), int)


def lr_ci(a: int, nw: int, b: int, nl: int, z: float = Z90):
    """LR = P(f | win) / P(f | loss) with a 90 % interval (log scale, +0.5 counts)."""
    a, b = a + 0.5, b + 0.5
    nw, nl = nw + 1, nl + 1
    lr = (a / nw) / (b / nl)
    se = math.sqrt(max(1 / a - 1 / nw + 1 / b - 1 / nl, 1e-12))
    return lr, lr * math.exp(-z * se), lr * math.exp(z * se)


# --------------------------------------------------------------------------------------------- pool
def _with(x, d):
    return (np.asarray(x, float) * np.asarray(d, float)).round().astype(int)


def pool(sym: str, df: pd.DataFrame, day_route: dict | None = None, i10: dict | None = None) -> pd.DataFrame:
    """Every trade of the run's G109-G112 tables, one family each, with R, entry index, bars and factors f_*.
    f_d1 / f_h4 are relative to the trade direction (+1 with the trade); the G110-G112 tables already store
    d1_with / h4_side relative to the break or trade direction."""
    D = g8.DATA
    parts = []
    A = pd.read_pickle(D / f"g109_trades_{sym}{SUF}.pkl")
    A = A[(~A["fake"]) & (A["target"] == "2R")]
    for s in ("S1", "S2"):
        x = A[A["setup"] == s]
        parts.append(pd.DataFrame({
            "fam": s, "day": x["day"], "i": x["i"].astype(int), "bars": x["bars"].astype(int), "d": x["d"].astype(int),
            "R": x["Ra"], "risk": x["risk"], "f_side": x["d"].astype(int), "f_sess": [g8.session_of(int(h)) for h in x["hour"]],
            "f_d1": _with(x["regime"], x["d"]), "f_adx": band(x["adx_h1"], [20, 30]),
            "f_zones": np.minimum(x["n"].astype(int), 2), "f_risk": band(x["risk_atr30"], [0.5, 1.0])}))
    E = pd.read_pickle(D / f"g110_events_{sym}{SUF}.pkl")
    for pre, fam, sgn in (("fo", "G110F", 1), ("fa", "G110A", -1)):
        x = E[E[f"{pre}_Ra"].notna()]
        d = (x["s"] * sgn).astype(int)
        parts.append(pd.DataFrame({
            "fam": fam, "day": x["day"], "i": x[f"{pre}_i"].astype(int), "bars": x[f"{pre}_bars"].astype(int), "d": d,
            "R": x[f"{pre}_Ra"], "risk": x[f"{pre}_risk"], "f_side": d, "f_sess": x["sess"].astype(int), "f_d1": (x["d1_with"] * sgn).astype(int),
            "f_h4": (x["h4_side"] * sgn).round().astype(int), "f_adx": band(x["adx_h1"], [20, 30]), "f_vol": band(x["tv_break"], [1.0, 2.0]),
            "f_div": x["diverg"].astype(int), "f_bos": x["bos_h1"].astype(int), "f_type": x["type"].map({"G": 0, "Z": 1, "F": 2}).astype(int)}))
    T = pd.read_pickle(D / f"g111_tests_{sym}{SUF}.pkl")
    T = T[~T["fake"]]
    parts.append(pd.DataFrame({
        "fam": "T", "day": T["day"], "i": T["k"].astype(int), "bars": T["bars"].astype(int), "d": T["d"].astype(int),
        "R": T["Ra"], "risk": T["risk"], "f_side": T["d"].astype(int), "f_sess": [g8.session_of(int(h)) for h in T["hour"]],
        "f_d1": T["d1_with"].astype(int), "f_h4": T["h4_side"].round().astype(int), "f_adx": band(T["adx_h1"], [20, 30]),
        "f_vol": band(T["rv12"], [0.7, 1.3]), "f_div": T["diverg"].astype(int), "f_conf": np.minimum(T["conf"].astype(int), 2),
        "f_lvl": T["fam"].map({"ZONE": 0, "AFIB": 1, "DFIB": 2, "PFIB": 3}).fillna(4).astype(int)}))
    C = pd.read_pickle(D / f"g112_chase_{sym}{SUF}.pkl")
    for typ in ("C1", "C2", "C3"):
        x = C[C["typ"] == typ]
        parts.append(pd.DataFrame({
            "fam": typ, "day": x["day"], "i": x["e"].astype(int), "bars": x["X1_none_bars"].astype(int), "d": x["d"].astype(int),
            "R": x["X1_none"], "risk": x["risk"], "f_side": x["d"].astype(int), "f_sess": x["sess"].astype(int), "f_d1": x["d1_with"].astype(int),
            "f_h4": x["h4_side"].round().astype(int), "f_adx": band(x["adx_h1"], [20, 30]), "f_vol": band(x["rv6"], [0.9, 1.3]),
            "f_div": x["diverg"].astype(int), "f_pos": band(x["day_pos"], [0.33, 0.67])}))
    P = dedupe(pd.concat(parts, ignore_index=True))
    t = df["time"].to_numpy(np.int64)
    n = len(t)
    P["time"] = t[P["i"].clip(0, n - 1)]
    P["exit_t"] = t[(P["i"] + P["bars"]).clip(0, n - 1)]
    P["kind"] = P["fam"].map(KIND)
    P["period"] = g8.period(P["time"]).to_numpy()
    P = P[P["period"] != "test"].reset_index(drop=True)            # the 2026 test stays sealed
    if day_route is not None:
        r = P["day"].map(day_route).fillna(0).to_numpy(int)
        after = P["i"].to_numpy() >= P["day"].map(i10 or {}).fillna(1e18).to_numpy()
        sgn = np.where(P["kind"] == "mom", 1, -1)
        P["f_dtype"] = np.where(after, r * sgn, 0).astype(int)
    P["win"] = P["R"] > 0
    return P


def dedupe(P: pd.DataFrame) -> pd.DataFrame:
    """One row per trade: several G110 events on the same bar (different levels) give the same trade; keep the first."""
    P = P[P["R"].notna()]
    return P.drop_duplicates(["fam", "i", "d", "bars", "R"]).reset_index(drop=True)


def factors(X: pd.DataFrame) -> list[str]:
    return [c for c in X.columns if c.startswith("f_") and X[c].notna().all()]


# --------------------------------------------------------------------------------------------- walk-forward
def months(P: pd.DataFrame):
    first = pd.Timestamp(int(P["time"].min()), unit="s").to_period("M").to_timestamp() + pd.offsets.MonthBegin(2)
    last = pd.Timestamp(int(P["time"].max()), unit="s").to_period("M").to_timestamp()
    return list(pd.date_range(first, last, freq="MS"))


def onehot(F: pd.DataFrame, cols: list[tuple[str, int]]) -> np.ndarray:
    return np.column_stack([(F[f].to_numpy() == v).astype(float) for f, v in cols]) if cols else np.zeros((len(F), 0))


def walk_family(X: pd.DataFrame) -> pd.DataFrame:
    """Out-of-sample raw scores, calibrated p, block size, EV_lo and Kelly size per model for one family."""
    X = X.sort_values(["time", "i"]).reset_index(drop=True)
    fs = factors(X)
    out = {f"{m}_{k}": np.full(len(X), np.nan) for m in MODELS for k in ("raw", "p", "n", "plo", "ev", "kelly", "top")}
    out["W"] = np.full(len(X), np.nan)
    out["L"] = np.full(len(X), np.nan)
    out["p0"] = np.full(len(X), np.nan)
    t, ex = X["time"].to_numpy(np.int64), X["exit_t"].to_numpy(np.int64)
    win, R = X["win"].to_numpy(bool), X["R"].to_numpy(float)
    for m0 in months(X):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        cut = s - 86400
        tr = ex < cut
        te = (t >= s) & (t < e)
        if te.sum() == 0 or tr.sum() < 100 or win[tr].sum() < 10 or (~win[tr]).sum() < 10:
            continue
        assert ex[tr].max() < cut <= t[te].min()
        Ftr, Fte = X.loc[tr, fs], X.loc[te, fs]
        W = float(R[tr & win].mean())
        L = float(-R[tr & ~win].mean())
        var = float(R[tr].var())
        out["W"][te], out["L"][te], out["p0"][te] = W, L, float(win[tr].mean())
        p0, tab = nb_table(Ftr, win[tr])
        cols = sorted(set((f, v) for f, v in tab))
        raw = {"nb": nb_score(Fte, p0, tab)}
        Xtr, Xte = onehot(Ftr, cols), onehot(Fte, cols)
        if Xtr.shape[1]:
            from sklearn.linear_model import LogisticRegression
            raw["logit"] = LogisticRegression(C=0.5, max_iter=500).fit(Xtr, win[tr]).decision_function(Xte)
            import lightgbm as lgb
            gbm = lgb.LGBMClassifier(n_estimators=120, learning_rate=0.03, num_leaves=7, min_child_samples=MIN_LEVEL,
                                     verbose=-1, random_state=114)
            raw["lgbm"] = gbm.fit(Xtr, win[tr]).predict_proba(Xte)[:, 1]
        else:
            raw["logit"] = raw["lgbm"] = np.zeros(te.sum())
        for m in MODELS:
            out[f"{m}_raw"][te] = raw[m]
            prev = ~np.isnan(out[f"{m}_raw"]) & (ex < cut) & (t < s)        # earlier out-of-sample, result known
            if prev.sum() >= MIN_CAL:
                past = out[f"{m}_raw"][prev]
                out[f"{m}_top"][te] = (raw[m] >= np.quantile(past, 0.8)).astype(float)
                blocks = pav_fit(past, win[prev])
                p, nb = pav_predict(blocks, raw[m])
                plo = np.array([wilson_lower(a, b) for a, b in zip(p, nb)])
                ev = plo * W - (1 - plo) * L
                out[f"{m}_p"][te], out[f"{m}_n"][te], out[f"{m}_plo"][te], out[f"{m}_ev"][te] = p, nb, plo, ev
                out[f"{m}_kelly"][te] = [kelly_size(v, var) for v in ev]
    for k, v in out.items():
        X[k] = v
    return X


def walk_all(P: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([walk_family(g) for _, g in P.groupby("fam") if len(g) >= 150], ignore_index=True)


# --------------------------------------------------------------------------------------------- selection
def select(S: pd.DataFrame, model: str) -> pd.DataFrame:
    c = S[S[f"{model}_ev"] > 0]
    if len(c) == 0:
        return c
    k = one_at_a_time(c["i"].to_numpy(), c["bars"].to_numpy(), c[f"{model}_ev"].to_numpy())
    return c.iloc[k]


def select_top(S: pd.DataFrame, model: str) -> pd.DataFrame:
    c = S[S[f"{model}_top"] == 1]
    if len(c) == 0:
        return c
    k = one_at_a_time(c["i"].to_numpy(), c["bars"].to_numpy(), c[f"{model}_raw"].rank(pct=True).to_numpy())
    return c.iloc[k]


def rule(S: pd.DataFrame, fam: str) -> pd.DataFrame:
    c = S[S["fam"] == fam]
    k = one_at_a_time(c["i"].to_numpy(), c["bars"].to_numpy(), np.zeros(len(c)))
    return c.iloc[k]


def random_control(S: pd.DataFrame, taken: pd.DataFrame, n_draw: int = 200, seed: int = 114) -> np.ndarray:
    """Mean R of random trades: per month, as many as taken, from that month's pool on days without a taken trade."""
    rng = np.random.default_rng(seed)
    mon = pd.to_datetime(S["time"], unit="s").dt.strftime("%Y-%m").to_numpy()
    tmon = pd.to_datetime(taken["time"], unit="s").dt.strftime("%Y-%m").value_counts().to_dict()
    tdays = set(taken["day"].tolist())
    R, day = S["R"].to_numpy(float), S["day"].to_numpy()
    pools = {}
    for m, k in tmon.items():
        idx = np.nonzero((mon == m) & ~np.isin(day, list(tdays)))[0]
        pools[m] = (idx if len(idx) >= k else np.nonzero(mon == m)[0], k)
    out = []
    for _ in range(n_draw):
        v = [R[rng.choice(idx, k, replace=len(idx) < k)] for idx, k in pools.values() if len(idx)]
        out.append(np.concatenate(v).mean() if v else np.nan)
    return np.array(out)


def stats(x: pd.DataFrame, w: str | None = None) -> dict:
    if len(x) == 0:
        return {"n": 0}
    x = x.sort_values(["time", "i"])
    R = x["R"].to_numpy(float)
    eq = np.cumsum(R)
    out = {"n": len(x), "win": float((R > 0).mean()), "R": float(R.mean()), "lo": boot_lower(R, x["day"].to_numpy()),
           "sum": float(R.sum()), "dd": float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())}
    if w is not None:
        k = x[w].to_numpy(float)
        out["ksum"] = float((k * R).sum())
        out["kavg"] = float(k.mean())
    return out


def fmt(s: dict, kelly: bool = False) -> str:
    if s.get("n", 0) == 0:
        return "0 | | | | |" + (" |" if kelly else "")
    base = f"{s['n']} | {s['win']:.0%} | {s['R']:+.3f} | {s['lo']:+.3f} | {s['sum']:+.1f} / DD {s['dd']:.1f}"
    return base + (f" | {s['ksum']:+.1f} (cỡ TB {s['kavg']:.2f})" if kelly else "")


def calib(S: pd.DataFrame, model: str):
    """Brier / log loss of the calibrated p vs the training base rate, on rows with a decision."""
    x = S[S[f"{model}_p"].notna()]
    if len(x) < 30:
        return None
    y = x["win"].to_numpy(float)
    p = x[f"{model}_p"].clip(0.01, 0.99).to_numpy()
    base = x["p0"].clip(0.01, 0.99).to_numpy()                      # training win rate of the family that month
    br, bb = float(((p - y) ** 2).mean()), float(((base - y) ** 2).mean())
    ll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    q = pd.qcut(x[f"{model}_p"].rank(method="first"), 10, labels=False)
    rel = x.assign(q=q).groupby("q").agg(p=(f"{model}_p", "mean"), y=("win", "mean"), n=("win", "size"))
    return {"brier": br, "brier_base": bb, "logloss": ll, "rel": rel, "n": len(x)}


# --------------------------------------------------------------------------------------------- report
def section(sym: str, S: pd.DataFrame) -> tuple[list[str], dict]:
    L = [f"## {sym}", ""]
    res = {}
    if len(S) == 0:
        return L + ["Không có setup nào đủ 150 lệnh.", ""], res
    days = S.groupby("period")["day"].nunique().to_dict()
    L += ["### 1. Phân phối: mỗi loại setup xuất hiện bao nhiêu (lệnh/ngày) và kết quả thô", "",
          "| Loại | Kiểu | Lệnh/ngày train | Lệnh/ngày validate | Luật (mọi lệnh, không chồng) train: lệnh · thắng · R · cận dưới · tổng | Validate |",
          "|---|---|---|---|---|---|"]
    for fam, g in S.groupby("fam"):
        per = {p: len(g[g["period"] == p]) / max(days.get(p, 1), 1) for p in ("train", "validate")}
        rr = rule(S, fam)
        L.append(f"| {FAM_NAME[fam]} | {'xung lực' if KIND[fam] == 'mom' else 'đảo chiều'} | {per['train']:.2f} | {per['validate']:.2f} | "
                 f"{fmt(stats(rr[rr['period'] == 'train']))} | {fmt(stats(rr[rr['period'] == 'validate']))} |")
    L += ["", "### 2. Chọn theo cận dưới EV (mỗi mã một lệnh mỗi lúc) so với đối chứng", "",
          "Cột: lệnh · thắng · R/lệnh · cận dưới 90% (bootstrap theo ngày) · tổng R / DD; cột Kelly = tổng R khi cỡ lệnh = 1/4 Kelly (trần 1R). "
          "\"Ngẫu nhiên ≥\" = tỉ lệ 200 lần chọn ngẫu nhiên (cùng số lệnh mỗi tháng, ngày khác) có R/lệnh ≥ chiến lược.", "",
          "| Cách chọn | Train | Train Kelly | Validate | Validate Kelly | Ngẫu nhiên ≥ (validate) |", "|---|---|---|---|---|---|"]
    for m in MODELS:
        x = select(S, m)
        st = {p: stats(x[x["period"] == p], f"{m}_kelly") for p in ("train", "validate")}
        xv = x[x["period"] == "validate"]
        rc = random_control(S[S["period"] == "validate"], xv) if len(xv) else np.array([np.nan])
        pr = float(np.mean(rc >= st["validate"]["R"])) if st["validate"].get("n", 0) else float("nan")
        res[m] = {"train": st["train"], "validate": st["validate"], "p_random": pr}
        name = {"nb": "(a) cộng log-LR", "logit": "(b) logistic", "lgbm": "(c) LightGBM"}[m]
        L.append(f"| EV_lo > 0, {name} | {fmt(st['train'], True)} | {fmt(st['validate'], True)} | {pr:.3f} |")
    for m in MODELS:
        x = select_top(S, m)
        L.append(f"| top 20% không hiệu chỉnh, {m} | {fmt(stats(x[x['period'] == 'train']))} | | {fmt(stats(x[x['period'] == 'validate']))} | | |")
    allr = S.iloc[one_at_a_time(S["i"].to_numpy(), S["bars"].to_numpy(), np.zeros(len(S)))]
    L.append(f"| mọi lệnh, không chồng | {fmt(stats(allr[allr['period'] == 'train']))} | | {fmt(stats(allr[allr['period'] == 'validate']))} | | |")
    L += ["", "Theo chiều (EV_lo > 0):", "", "| Mô hình | Chiều | Train | Validate |", "|---|---|---|---|"]
    for m in MODELS:
        x = select(S, m)
        for d, nm in ((1, "MUA"), (-1, "BÁN")):
            y = x[x["d"] == d]
            L.append(f"| {m} | {nm} | {fmt(stats(y[y['period'] == 'train']))} | {fmt(stats(y[y['period'] == 'validate']))} |")
    L += ["", "### 3. Độ khớp xác suất (mọi lệnh có quyết định)", "",
          "| Mô hình | Kỳ | Lệnh | Brier | Brier mức chung | Log loss | Khớp 10 nhóm: p dự báo → tỉ lệ thắng thật |", "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for per in ("train", "validate"):
            c = calib(S[S["period"] == per], m)
            res.setdefault(m, {})[f"cal_{per}"] = c and {k: v for k, v in c.items() if k != "rel"}
            if c is None:
                L.append(f"| {m} | {per} | <30 | | | | |")
                continue
            rel = " · ".join(f"{a:.2f}→{b:.2f}" for a, b in zip(c["rel"]["p"], c["rel"]["y"]))
            L.append(f"| {m} | {per} | {c['n']} | {c['brier']:.4f} | {c['brier_base']:.4f} | {c['logloss']:.4f} | {rel} |")
    L += ["", "### 4. Tỉ số hợp lý (LR) từng yếu tố: ổn định khi LR cùng phía 1 ở cả hai kỳ và khoảng 90% không chứa 1", "",
          "| Loại | Yếu tố = mức | Lần train | LR train [90%] | Lần validate | LR validate [90%] | Ổn định |", "|---|---|---|---|---|---|---|"]
    stable = []
    for fam, g in S.groupby("fam"):
        for f in factors(g):
            for v in sorted(g[f].unique()):
                row, ok = [], []
                for per in ("train", "validate"):
                    h = g[g["period"] == per]
                    w = h["win"].to_numpy(bool)
                    m_ = h[f].to_numpy() == v
                    lr, lo, hi = lr_ci(int((m_ & w).sum()), int(w.sum()), int((m_ & ~w).sum()), int((~w).sum()))
                    row.append((int(m_.sum()), lr, lo, hi))
                    ok.append(1 if lo > 1 else (-1 if hi < 1 else 0))
                st = ok[0] == ok[1] != 0 and min(row[0][0], row[1][0]) >= MIN_LEVEL
                if st or (row[0][0] >= MIN_LEVEL and abs(math.log(row[0][1])) > 0.15):
                    L.append(f"| {FAM_NAME[fam]} | {f[2:]} = {v} | {row[0][0]} | {row[0][1]:.2f} [{row[0][2]:.2f}–{row[0][3]:.2f}] | "
                             f"{row[1][0]} | {row[1][1]:.2f} [{row[1][2]:.2f}–{row[1][3]:.2f}] | {'**có**' if st else ''} |")
                if st:
                    stable.append((fam, f, int(v), row[0][1], row[1][1]))
    res["stable"] = stable
    L.append("")
    return L, res


def passes(r: dict) -> bool:
    """Plan section 4: lower bound > 0 in both periods, >= 100 trades, beats random, calibrated in both periods."""
    tr, va = r.get("train", {}), r.get("validate", {})
    if tr.get("n", 0) + va.get("n", 0) < 100 or tr.get("n", 0) == 0 or va.get("n", 0) == 0:
        return False
    cal = [r.get(f"cal_{p}") for p in ("train", "validate")]
    return (tr["lo"] > 0 and va["lo"] > 0 and r.get("p_random", 1) < 0.05
            and all(c is not None and c["brier"] < c["brier_base"] for c in cal))


def build(sym: str) -> pd.DataFrame:
    import importlib
    os.environ["G108_SYMBOL"] = sym
    importlib.reload(g8)
    import g108_features as gf
    import g113_daytype as gd
    importlib.reload(gf)
    importlib.reload(gd)
    df = g8.load_m5_raw()
    D = gd.day_table(df, gf.long_m30())
    r = gd.route(D, gd.walk(D, "logit"))
    P = pool(sym, df, dict(zip(D["day"], r)), dict(zip(D["day"], D["i10"])))
    S = walk_all(P)
    S.to_pickle(g8.DATA / f"g114_pool_{sym}{SUF}.pkl")
    return S


def main(symbols):
    L = ["# G114: chọn setup theo xác suất đã hiệu chỉnh và cận dưới kỳ vọng (EV)", "",
         "Ngày 14/10/2026. Plan: docs/superpowers/plans/2026-10-14-g114-probability-selection.md. Dữ liệu raw MT5. Chỉ train "
         "07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); **test 2026 niêm phong**. " + run_label() +
         " Script: research/long/g114_prob.py, g114_audit.py.", "",
         "Cách làm: mỗi tháng, với từng loại setup, học xác suất thắng (R > 0) từ các lệnh đã biết kết quả trước tháng ít nhất "
         "1 ngày (có assert) bằng (a) cộng log-LR, (b) logistic, (c) LightGBM trên cùng các yếu tố rời rạc đặt trước; hiệu chỉnh "
         f"bằng hồi quy isotonic trên dự báo ngoài mẫu của các tháng trước (cần ≥ {MIN_CAL}). Vào lệnh khi cận dưới Wilson 90% của "
         "p cho EV > 0, EV = p × R thắng TB − (1 − p) × R thua TB (của dữ liệu học). Mỗi mã một lệnh mỗi lúc. "
         "Tiêu chí đạt: cận dưới > 0 ở cả train và validate, ≥ 100 lệnh, hơn chọn ngẫu nhiên (p < 0,05), Brier tốt hơn mức chung "
         "ở cả hai kỳ.", ""]
    verdict = []
    for s in symbols:
        S = build(s)
        sec, res = section(s, S)
        L += sec
        for m in MODELS:
            if m in res and passes(res[m]):
                verdict.append((s, m, res[m]))
        print(s, "done", {m: (res.get(m, {}).get("validate", {}).get("n"), round(res.get(m, {}).get("validate", {}).get("R", float("nan")), 3))
                          for m in MODELS}, flush=True)
    L += ["## Kết luận theo tiêu chí đăng ký trước", ""]
    if verdict:
        for s, m, r in verdict:
            L.append(f"- **ĐẠT:** {s}, mô hình {m}: train {fmt(r['train'])}; validate {fmt(r['validate'])}; ngẫu nhiên ≥ {r['p_random']:.3f}.")
    else:
        L.append("- **Không có mã/mô hình nào đạt đủ tiêu chí.**")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
