"""G114 audit: for random decided trades, recompute with plain loops and other tools
  - the training set (exit known 1 day before the month), p0, Laplace LR per factor level (levels >= 30), the
    naive-Bayes score;
  - the isotonic calibration of each model by the closed-form max-min formula (p at x = max over lower ends a of the
    min over upper ends b of the mean of y on [a, b], equal scores pooled) on the earlier out-of-sample scores
    (sklearn's IsotonicRegression was tried first: on near-equal logistic scores its fit had a higher squared
    error than the exact solution, so it is not used as the reference),
    the block size, the Wilson 90 % lower bound (closed form), W / L, EV_lo and the 1/4 Kelly size;
  - the one-trade-at-a-time selection of a whole month with a plain loop.

  [G113_TF=15|30] G108_SYMBOL=XAUUSD python g114_audit.py [n=60]
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

import g108_data as g8
import g114_prob as gp
from g109_setups import SUF


def wilson(p, n, z=1.6448536269514722):
    return max(0.0, (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n))


def iso_minmax(x: np.ndarray, y: np.ndarray, at: float):
    """Exact isotonic value at score `at` and the number of points sharing that value."""
    u, inv = np.unique(x, return_inverse=True)
    sy = np.bincount(inv, weights=y)
    cn = np.bincount(inv).astype(float)
    S, C = np.r_[0, np.cumsum(sy)], np.r_[0, np.cumsum(cn)]
    m = len(u)
    a = np.arange(m)[:, None]
    b = np.arange(m)[None, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        M = np.where(b >= a, (S[b + 1] - S[a]) / (C[b + 1] - C[a]), np.nan)
    val = np.array([np.nanmax(np.nanmin(M[: k + 1, k:], axis=1)) for k in range(m)])
    k = int(np.searchsorted(u, at, side="right") - 1) if at >= u[0] else 0
    p = val[k]
    return p, int(cn[np.isclose(val, p, rtol=0, atol=1e-12)].sum())


def check_row(S: pd.DataFrame, r) -> list[str]:
    bad = []
    F = S[S["fam"] == r.fam]
    s = int(pd.Timestamp(int(r.time), unit="s").to_period("M").to_timestamp().timestamp())
    cut = s - 86400
    tr = [q for q in F.itertuples() if q.exit_t < cut]
    nw = sum(1 for q in tr if q.R > 0)
    nl = len(tr) - nw
    p0 = (nw + 1) / (len(tr) + 2)
    score = math.log(p0 / (1 - p0))
    for f in [c for c in F.columns if c.startswith("f_") and F[c].notna().all()]:
        K = len(set(getattr(q, f) for q in tr))
        v = getattr(r, f)
        a = sum(1 for q in tr if getattr(q, f) == v and q.R > 0)
        b = sum(1 for q in tr if getattr(q, f) == v and q.R <= 0)
        if a + b >= gp.MIN_LEVEL:
            score += math.log(((a + 1) / (nw + K)) / ((b + 1) / (nl + K)))
    if not np.isclose(score, r.nb_raw):
        bad.append(f"nb_raw {score:.6f} vs {r.nb_raw:.6f}")
    W = np.mean([q.R for q in tr if q.R > 0])
    L = -np.mean([q.R for q in tr if q.R <= 0])
    var = np.var([q.R for q in tr])
    if not (np.isclose(W, r.W) and np.isclose(L, r.L)):
        bad.append("W/L")
    for m in gp.MODELS:
        raw = getattr(r, f"{m}_raw")
        prev = [(getattr(q, f"{m}_raw"), q.R > 0) for q in F.itertuples()
                if not np.isnan(getattr(q, f"{m}_raw")) and q.exit_t < cut and q.time < s]
        ev = getattr(r, f"{m}_ev")
        if len(prev) < gp.MIN_CAL:
            if not np.isnan(ev):
                bad.append(f"{m}: decided with {len(prev)} < {gp.MIN_CAL} calibration points")
            continue
        x = np.array([a for a, _ in prev])
        y = np.array([b for _, b in prev], float)
        p, n = iso_minmax(x, y, raw)
        plo = wilson(p, n)
        evx = plo * W - (1 - plo) * L
        kel = 0.0 if evx <= 0 or var <= 0 else min(1.0, 0.25 * evx / var)
        got = (getattr(r, f"{m}_p"), getattr(r, f"{m}_n"), ev, getattr(r, f"{m}_kelly"))
        if not (np.isclose(p, got[0]) and n == int(got[1]) and np.isclose(evx, got[2]) and np.isclose(kel, got[3])):
            bad.append(f"{m}: p {p:.4f}/{got[0]:.4f} n {n}/{got[1]} ev {evx:.4f}/{got[2]:.4f} kelly {kel:.4f}/{got[3]:.4f}")
    return bad


def check_month(S: pd.DataFrame, model: str, month: str) -> bool:
    sel = gp.select(S, model)
    mine = sel[pd.to_datetime(sel["time"], unit="s").dt.strftime("%Y-%m") == month]
    c = S[(S[f"{model}_ev"] > 0)]                      # pool order: equal entry bar and EV -> the earlier row (stable sort)
    rows = sorted(c.itertuples(), key=lambda q: (q.i, -getattr(q, f"{model}_ev")))
    free, keep = -1, []
    for q in rows:
        if q.i >= free:
            keep.append(q.Index)
            free = q.i + q.bars
    loop = S.loc[keep]
    loop = loop[pd.to_datetime(loop["time"], unit="s").dt.strftime("%Y-%m") == month]
    key = lambda X: sorted(zip(X["fam"], X["i"], X["d"]))
    return key(mine) == key(loop)


def main():
    n_s = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    S = pd.read_pickle(g8.DATA / f"g114_pool_{g8.SYMBOL}{SUF}.pkl")
    D = S[S["nb_ev"].notna()]
    smp = D.sample(min(n_s, len(D)), random_state=114)
    bad = 0
    for r in smp.itertuples():
        b = check_row(S, r)
        if b:
            bad += 1
            print("  differs", r.fam, pd.to_datetime(int(r.time), unit="s"), b[:3])
    months = sorted(set(pd.to_datetime(D["time"], unit="s").dt.strftime("%Y-%m")))
    mbad = [(m, mo) for m in gp.MODELS for mo in months[-4:] if not check_month(S, m, mo)]
    print(f"{g8.SYMBOL}{SUF} G114: {bad} mismatches of {len(smp)} trades; selection differs in {len(mbad)} of {4 * len(gp.MODELS)} month-models {mbad[:3]}")


if __name__ == "__main__":
    main()
