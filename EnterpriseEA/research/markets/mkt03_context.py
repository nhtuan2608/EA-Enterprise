"""MKT03: context features on M30 -> walk-forward LightGBM forecast of the R of a market plan (M) and a limit plan (L),
both directions, for US indices and big crypto. Pre-registered plan: docs/superpowers/plans/2026-10-11-mkt03-context-forecast.md.
MT5 data only (research/long/data/m30v, built by mkt01_data.py).

  python mkt03_context.py
"""
from __future__ import annotations

import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "long" / "data"
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-mkt03-context-forecast.md"
GROUPS = {"Chỉ số": {"syms": ("NAS100", "DJ30", "SP500"), "leader": "NAS100", "oos": (2025, 1)},
          "Crypto lớn": {"syms": ("BTCUSD", "ETHUSD"), "leader": "BTCUSD", "oos": (2021, 1)}}
BAR = 1800
HOLD, LIMIT_BARS, SL, TP, PULL = 16, 4, 1.0, 1.5, 0.5
EMBARGO = 20 * BAR
TEST0 = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp())
TEST1 = int(datetime(2026, 10, 10, tzinfo=timezone.utc).timestamp())
PENALTY = 0.10
PARAMS = dict(objective="regression", num_leaves=15, min_data_in_leaf=200, learning_rate=0.03, n_estimators=300,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1, seed=103)
PLANS = ("M", "L")
SFX = {1: "p", -1: "n"}


def ts(y, m):
    return int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# data and context
# ---------------------------------------------------------------------------
def wilder(x, n):
    out = np.empty_like(x)
    a = x[0]
    for i, v in enumerate(x):
        a = v if i == 0 else a + (v - a) / n
        out[i] = a
    return out


def load(sym):
    meta = json.loads((DATA / "mkt01_meta.json").read_text())
    df = pd.read_csv(DATA / "m30v" / f"{sym}.csv")
    pt = float(meta[sym]["point"])
    df["sp"] = df["spread"] * pt
    med = float(df.loc[df["time"] >= ts(2024, 3), "sp"].median())
    df["sp"] = df["sp"].clip(lower=med)
    df.attrs["med"] = med
    return df.reset_index(drop=True)


def htf(df, sec, n=200):
    """Side and distance (in M30 ATR) of the last COMPLETED higher-timeframe close vs its EMA(n)."""
    b = (df["time"] // sec).to_numpy()
    last = np.r_[b[1:] != b[:-1], True]
    closes = df["close"].to_numpy()[last]
    buckets = b[last]
    ema = pd.Series(closes).ewm(span=n, adjust=False).mean().to_numpy()
    pos = {k: j for j, k in enumerate(buckets)}
    idx = np.array([pos[k] - 1 for k in b])
    ok = idx >= n
    c = np.where(ok, closes[np.maximum(idx, 0)], np.nan)
    e = np.where(ok, ema[np.maximum(idx, 0)], np.nan)
    return c, e


def context(df, leader):
    o, h, l, c, v = (df[k].to_numpy() for k in ("open", "high", "low", "close", "tickvol"))
    t = df["time"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    atr = wilder(tr, 14)
    atr100 = wilder(tr, 100)
    up, dn = h - np.r_[h[0], h[:-1]], np.r_[l[0], l[:-1]] - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    trs, pds, mds = wilder(tr, 14), wilder(pdm, 14), wilder(mdm, 14)
    pdi, mdi = 100 * pds / np.maximum(trs, 1e-12), 100 * mds / np.maximum(trs, 1e-12)
    adx = wilder(100 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9), 14)
    ch = np.diff(c, prepend=c[0])
    g, ls_ = wilder(np.maximum(ch, 0), 14), wilder(np.maximum(-ch, 0), 14)
    rsi = 100 - 100 / (1 + g / np.maximum(ls_, 1e-12))
    cs = pd.Series(c)
    e21, e55, e200 = (cs.ewm(span=n, adjust=False).mean().to_numpy() for n in (21, 55, 200))
    f = pd.DataFrame({"time": t})
    for k in (1, 4, 16, 48):
        f[f"r{k}"] = (c - cs.shift(k).to_numpy()) / atr
    f["d_e21"], f["e21_e55"], f["e55_e200"] = (c - e21) / atr, (e21 - e55) / atr, (e55 - e200) / atr
    for name, sec in (("h4", 14400), ("d1", 86400)):
        hc, he = htf(df, sec)
        f[f"{name}_side"] = np.sign(hc - he)
        f[f"{name}_dist"] = (c - he) / atr
    f["adx"], f["di"], f["rsi"] = adx, pdi - mdi, rsi
    f["atr_ratio"] = atr / atr100
    f["comp16"] = (pd.Series(h).rolling(16).max() - pd.Series(l).rolling(16).min()).to_numpy() / atr
    day = t // 86400
    dser = pd.Series(day)
    dh = pd.Series(h).groupby(dser).max()
    dl = pd.Series(l).groupby(dser).min()
    days = dh.index.to_numpy()
    prev = {d: days[k - 1] for k, d in enumerate(days) if k}
    pdh = np.array([dh[prev[d]] if d in prev else np.nan for d in day])
    pdl = np.array([dl[prev[d]] if d in prev else np.nan for d in day])
    f["d_pdh"], f["d_pdl"] = (c - pdh) / atr, (c - pdl) / atr
    cmax = pd.Series(h).groupby(dser).cummax().to_numpy()
    cmin = pd.Series(l).groupby(dser).cummin().to_numpy()
    f["day_pos"] = (c - cmin) / np.maximum(cmax - cmin, 1e-12)
    tp_ = (h + l + c) / 3
    w = np.maximum(v, 1.0)
    vw = (pd.Series(tp_ * w).groupby(dser).cumsum() / pd.Series(w).groupby(dser).cumsum()).to_numpy()
    f["d_vwap"] = (c - vw) / atr
    step = 10.0 ** (np.floor(np.log10(c)) - 2)
    f["round"] = (c % step) / step
    sod = t % 86400
    f["ny_hour"] = ((sod // 3600) - 7) % 24
    f["dow"] = ((t - 7 * 3600) // 86400 + 3) % 7
    f["ny_min"] = np.where((sod >= 16 * 3600 + 1800) & (sod <= 23 * 3600), (sod - (16 * 3600 + 1800)) / 60, -1)
    slot = pd.Series(sod)
    vs = pd.Series(v, dtype=float)
    mean20 = vs.groupby(slot).transform(lambda x: x.shift(1).rolling(20, min_periods=10).mean())
    f["vol_ratio"] = (vs / mean20).to_numpy()
    f = f.merge(leader, on="time", how="left")
    return f, atr


def leader_frame(sym):
    df = load(sym)
    c = df["close"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(df["high"].to_numpy(), pc) - np.minimum(df["low"].to_numpy(), pc)
    atr = wilder(tr, 14)
    return pd.DataFrame({"time": df["time"], "lead_r1": (c - pd.Series(c).shift(1).to_numpy()) / atr,
                         "lead_r4": (c - pd.Series(c).shift(4).to_numpy()) / atr})


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------
def labels(df, atr):
    """R and exit index of plan M (market) and L (limit) for d = +1 / -1 at every bar close; NaN when not taken."""
    o, h, l, c, sp = (df[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
    med = df.attrs["med"]
    n = len(c)
    out = {}
    for plan in PLANS:
        for d in (1, -1):
            R = np.full(n, np.nan)
            X = np.full(n, -1, dtype=np.int64)
            for i in range(n - HOLD - LIMIT_BARS - 2):
                A = atr[i]
                if not A > 0:
                    continue
                if plan == "M":
                    e = i + 1
                    entry = o[e] + (sp[e] if d == 1 else 0.0) + d * 0.5 * med
                    j0 = e
                else:
                    level = c[i] - d * PULL * A
                    e = -1
                    for j in range(i + 1, i + 1 + LIMIT_BARS):
                        if (d == 1 and l[j] + sp[j] < level) or (d == -1 and h[j] > level):
                            e = j
                            break
                    if e < 0:
                        continue
                    entry = level
                    stop = entry - d * SL * A
                    # fill bar: a stop touch after the fill counts as a loss; its target touch does not count
                    if (d == 1 and l[e] <= stop) or (d == -1 and h[e] + sp[e] >= stop):
                        R[i], X[i] = -SL - 0.5 * med / A, e
                        continue
                    j0 = e + 1
                stop, tgt = entry - d * SL * A, entry + d * TP * A
                px, x = None, None
                last = min(n - 1, (e if plan == "M" else e) + HOLD - 1)
                for j in range(j0, last + 1):
                    s = sp[j] if d == -1 else 0.0
                    hi, lo, op = h[j] + s, l[j] + s, o[j] + s
                    if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
                        px, x = (min(stop, op) if d == 1 else max(stop, op)), j
                        break
                    if (d == 1 and hi >= tgt) or (d == -1 and lo <= tgt):
                        px, x = (max(tgt, op) if d == 1 else min(tgt, op)), j
                        break
                if px is None:
                    x = last
                    px = c[x] + (sp[x] if d == -1 else 0.0)
                R[i] = d * (px - entry) / A - 0.5 * med / A
                X[i] = x
            out[(plan, d)] = (R, X)
    return out


# ---------------------------------------------------------------------------
def build_group(gname, g):
    lead = leader_frame(g["leader"])
    frames = []
    for k, sym in enumerate(g["syms"]):
        df = load(sym)
        f, atr = context(df, lead)
        lab = labels(df, atr)
        f["sym"] = k
        f["sym_name"] = sym
        f["i"] = np.arange(len(f))
        for (plan, d), (R, X) in lab.items():
            f[f"R_{plan}_{SFX[d]}"] = R
            f[f"X_{plan}_{SFX[d]}"] = X
        frames.append(f)
        print(gname, sym, len(f), flush=True)
    return pd.concat(frames, ignore_index=True)


FEATS = None


def walk_forward(F, g):
    """Out-of-sample predictions, refit every 3 months on everything before the block (embargo 20 bars)."""
    global FEATS
    FEATS = [c for c in F.columns if not c.startswith(("R_", "X_")) and c not in ("time", "sym_name", "i")]
    y0, m0 = g["oos"]
    blocks = []
    y, m = y0, m0
    while ts(y, m) < TEST1:
        b0 = ts(y, m)
        m2 = m + 3
        y2, m2 = (y + (m2 - 1) // 12, (m2 - 1) % 12 + 1)
        blocks.append((b0, min(ts(y2, m2), TEST1)))
        y, m = y2, m2
    for plan in PLANS:
        for d in (1, -1):
            F[f"P_{plan}_{SFX[d]}"] = np.nan
    imp = {}
    for b0, b1 in blocks:
        tr_mask = F["time"] < b0 - EMBARGO
        pr_mask = (F["time"] >= b0) & (F["time"] < b1)
        if not pr_mask.any():
            continue
        for plan in PLANS:
            for d in (1, -1):
                y_ = F[f"R_{plan}_{SFX[d]}"]
                m_ = tr_mask & y_.notna()
                if m_.sum() < 2000:
                    continue
                mdl = lgb.LGBMRegressor(**PARAMS)
                mdl.fit(F.loc[m_, FEATS], y_[m_].clip(-1.5, 2.0))
                F.loc[pr_mask, f"P_{plan}_{SFX[d]}"] = mdl.predict(F.loc[pr_mask, FEATS])
                imp[(plan, d)] = dict(zip(FEATS, mdl.booster_.feature_importance("gain")))
    return imp


def simulate(F, plan, theta, t0, t1):
    """Chronological per symbol: take the better side when its forecast > theta and > 0; one trade at a time."""
    out = []
    for sym, G in F[(F["time"] >= t0) & (F["time"] < t1)].groupby("sym_name"):
        busy = -1
        for row in G.itertuples(index=False):
            i = row.i
            if i <= busy:
                continue
            pl, ps = getattr(row, f"P_{plan}_p"), getattr(row, f"P_{plan}_n")
            cands = [(p, d) for p, d in ((pl, 1), (ps, -1)) if p == p and p > theta and p > 0]
            if not cands:
                continue
            p, d = max(cands)
            r = getattr(row, f"R_{plan}_{SFX[d]}")
            if r != r:
                if plan == "L":
                    out.append({"sym": sym, "t": row.time, "r": None, "d": d})   # not filled: placed only
                continue
            out.append({"sym": sym, "t": row.time, "r": float(r), "d": d})
            busy = int(getattr(row, f"X_{plan}_{SFX[d]}"))
    return out


def mean(x):
    return statistics.fmean(x) if x else 0.0


def lower(xs, q, runs=4000, seed=103):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(q * runs)]


def perm_p(F, plan, n, obs, t0, t1, runs=2000, seed=7):
    pool = []
    sub = F[(F["time"] >= t0) & (F["time"] < t1)]
    for d in (1, -1):
        pool += sub[f"R_{plan}_{SFX[d]}"].dropna().tolist()
    rng = random.Random(seed)
    hits = sum(1 for _ in range(runs) if statistics.fmean(rng.sample(pool, n)) >= obs)
    return hits / runs, statistics.fmean(pool)


def main():
    L = ["# MKT03: dự báo theo ngữ cảnh → lệnh limit / market cho chỉ số Mỹ và crypto — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-mkt03-context-forecast.md`. M30, LightGBM huấn luyện cuốn chiếu (mỗi 3 tháng, bỏ 20 nến "
         "sát mốc), mọi dự báo ngoài mẫu. Kế hoạch M: market, SL 1 ATR / TP 1,5 ATR / tối đa 16 nến. Kế hoạch L: limit cách "
         "0,5 ATR chờ 4 nến, cùng SL/TP. Chi phí khắt khe, phí hoa hồng 0. R theo 1 ATR.", ""]
    cells = []
    for gname, g in GROUPS.items():
        F = build_group(gname, g)
        imp = walk_forward(F, g)
        v0 = ts(*g["oos"])
        L += [f"## {gname}", ""]
        for plan in PLANS:
            vp = pd.concat([F.loc[(F["time"] >= v0) & (F["time"] < TEST0), f"P_{plan}_{SFX[d]}"] for d in (1, -1)]).dropna()
            best = None
            L += [f"**Kế hoạch {plan}** — chọn ngưỡng trên validate:", "", "| Phân vị | θ | Lệnh validate | R/lệnh validate |",
                  "|---|---|---|---|"]
            for q in (0.80, 0.90, 0.95):
                th = float(vp.quantile(q))
                tr_ = [x["r"] for x in simulate(F, plan, th, v0, TEST0) if x["r"] is not None]
                L.append(f"| {q:.0%} | {th:+.3f} | {len(tr_)} | {mean(tr_):+.3f} |")
                if len(tr_) >= 60 and (best is None or mean(tr_) > best[2]):
                    best = (q, th, mean(tr_))
            L.append("")
            if best is None:
                L += ["Không ngưỡng nào có ≥ 60 lệnh validate → ô dừng.", ""]
                cells.append((gname, plan, None))
                continue
            q, th, _ = best
            sims = simulate(F, plan, th, TEST0, TEST1)
            test = [x for x in sims if x["r"] is not None]
            fill = len(test) / max(len(sims), 1) if plan == "L" else None
            rs = [x["r"] for x in test]
            res = {"q": q, "th": th, "n": len(rs), "fill": fill}
            if len(rs) >= 2:
                p, uncond = perm_p(F, plan, len(rs), mean(rs), TEST0, TEST1)
                res.update(m=mean(rs), l90=lower(rs, 0.10), lb=lower(rs, 0.10 / 4), p=p, uncond=uncond,
                           per={s: (len([x for x in test if x["sym"] == s]), mean([x["r"] for x in test if x["sym"] == s]))
                                for s in g["syms"]})
                if gname == "Crypto lớn":
                    btc = [x["r"] for x in simulate(F, plan, th, v0, TEST0) if x["r"] is not None and x["sym"] == "BTCUSD"]
                    res["btc_val"] = (len(btc), mean(btc))
            cells.append((gname, plan, res))
            top = sorted(((sum(imp[(plan, d)].get(k, 0) for d in (1, -1)), k) for k in FEATS), reverse=True)[:10]
            L += [f"Ngưỡng chọn: phân vị {q:.0%} (θ {th:+.3f}). 10 thành phần ngữ cảnh quan trọng nhất (mô hình cuối): "
                  + ", ".join(k for _, k in top) + ".", ""]
            print(gname, plan, res, flush=True)
    L += ["## Kiểm tra cuối (10/2025–10/2026)", "",
          "| Ô | Lệnh | Khớp limit | R/lệnh | Không điều kiện | p hoán vị | Cận dưới 90% | Cận dưới 97,5% | Sau trừ 0,10R | Theo symbol | Đạt? |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for gname, plan, res in cells:
        if not res or "m" not in res:
            L.append(f"| {gname} {plan} | {res['n'] if res else 0} | | | | | | | | | không |")
            continue
        ok = res["n"] >= 60 and res["m"] > 0 and res["l90"] > 0 and res["m"] - PENALTY > 0 and res["p"] < 0.05
        per = ", ".join(f"{s} {n} {m:+.2f}" for s, (n, m) in res["per"].items())
        fill = f"{res['fill']:.0%}" if res["fill"] is not None else "—"
        L.append(f"| {gname} {plan} | {res['n']} | {fill} | {res['m']:+.3f} | {res['uncond']:+.3f} | {res['p']:.3f} | "
                 f"{res['l90']:+.3f} | {res['lb']:+.3f} | {res['m'] - PENALTY:+.3f} | {per} | "
                 f"{'**ĐẠT**' + (' (cả Bonferroni)' if res['lb'] > 0 else '') if ok else 'không'} |")
    L.append("")
    btc = [(p, r["btc_val"]) for g_, p, r in cells if r and "btc_val" in r]
    if btc:
        L.append("BTC validate dài (01/2021–09/2025, ngưỡng chọn trên chính kỳ này nên chỉ là bằng chứng phụ): "
                 + "; ".join(f"{p}: {n} lệnh {m:+.3f}" for p, (n, m) in btc) + ".")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
