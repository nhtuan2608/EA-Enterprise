"""G113 part 3: day type at the London open (10:00 server) and setup routing
(docs/superpowers/plans/2026-10-14-g113-gross-htf-daytype.md).

  python g113_daytype.py XAUUSD EURUSD GBPUSD USDJPY      # M5 raw; writes docs/superpowers/reports/2026-10-14-g113-daytype.md

Label (after the day): body ratio = |close - open| / (high - low) of the server day; trend >= 0.6, range <= 0.3.
Features at 10:00 (bars before 10:00 and earlier days only): Asia range / ATR14 D1, Asia direction and efficiency,
prior-day range / ATR and body ratio, ADX14 D1, D1 regime, H4 EMA200 side, Asia relative tick volume, weekday,
prior day's type. Walk-forward monthly logistic regression and LightGBM for P(trend day).
Routing (trades entered from 10:00): predicted trend (P >= 60th percentile of the earlier months) -> momentum setups
(G110 follow, G112 chase X1); predicted range (P <= 40th percentile) -> reversal setups (G110 fade, G111 test T).
Compared with all trades, random routing (day predictions shuffled, 200 times) and the oracle (true labels).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g110_breaks as gb
from g108_patterns import boot_lower

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-14-g113-daytype.md"
FEATS = ["asia_rng", "asia_dir", "asia_eff", "prev_rng", "prev_body", "prev_dir", "adx_d1", "regime", "h4_side", "asia_rv", "dow", "prev_type"]
OPEN_H = 10


def day_table(df: pd.DataFrame, hist: pd.DataFrame | None = None) -> pd.DataFrame:
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    hour = (t % 86400) // 3600
    day = t // 86400
    rv = gb.rel_volume(t, df["tickvol"].to_numpy(float))
    g = pd.DataFrame({"day": day, "i": np.arange(len(t))}).groupby("day")["i"].agg(["min", "max"])
    days = g.index.to_numpy(np.int64)
    dh = np.array([h[a:b + 1].max() for a, b in zip(g["min"], g["max"])])
    dl = np.array([l[a:b + 1].min() for a, b in zip(g["min"], g["max"])])
    do = o[g["min"].to_numpy()]; dc = c[g["max"].to_numpy()]
    atr = g8.wilder_atr(dh, dl, dc)
    P, M, A = gf.dmi(dh, dl, dc)
    e50 = g8.ema(dc, 50)
    b4, c4 = gf.htf_closes(df, hist, 14400)
    e4 = g8.ema(c4, 200)
    body = np.abs(dc - do) / np.maximum(dh - dl, 1e-12)
    typ = np.where(body >= 0.6, 1, np.where(body <= 0.3, -1, 0))
    rows = []
    for k in range(60, len(days)):
        a, b = int(g["min"].iloc[k]), int(g["max"].iloc[k])
        asia = np.arange(a, b + 1)[hour[a:b + 1] < OPEN_H]
        if len(asia) < 6 or asia[-1] >= b:
            continue
        cut = int(asia[-1])                                        # last bar before 10:00
        AH, AL = h[asia].max(), l[asia].min()
        ad = atr[k - 1]
        side = np.sign(dc[k - 1] - e50[k - 1]); slope = np.sign(e50[k - 1] - e50[k - 11])
        k4 = np.searchsorted((b4 + 1) * 14400, t[cut] + 300, side="right") - 1
        rows.append(dict(day=int(days[k]), t10=int(t[cut] + 300), i10=cut + 1,
                         asia_rng=(AH - AL) / ad, asia_dir=(c[cut] - o[a]) / max(AH - AL, 1e-12),
                         asia_eff=abs(c[cut] - o[a]) / max(AH - AL, 1e-12),
                         prev_rng=(dh[k - 1] - dl[k - 1]) / ad, prev_body=body[k - 1], prev_dir=float(np.sign(dc[k - 1] - do[k - 1])),
                         adx_d1=A[k - 1], regime=float(side if side == slope else 0), h4_side=float(np.sign(c[cut] - e4[k4])) if k4 >= 0 else 0.0,
                         asia_rv=float(np.nanmean(rv[asia])), dow=int((days[k] + 3) % 7), prev_type=int(typ[k - 1]),
                         body=body[k], type=int(typ[k]), trend=int(typ[k] == 1)))
    D = pd.DataFrame(rows)
    D["period"] = g8.period(D["t10"])
    return D[D["period"] != "test"].reset_index(drop=True)


def walk(D: pd.DataFrame, kind: str) -> np.ndarray:
    p = np.full(len(D), np.nan)
    for m0 in pd.date_range("2024-12-01", "2025-12-01", freq="MS"):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = (D["t10"] < s - 86400).to_numpy(); te = ((D["t10"] >= s) & (D["t10"] < e)).to_numpy()
        if te.sum() == 0 or tr.sum() < 60:
            continue
        assert D.loc[tr, "t10"].max() < s - 86400 <= D.loc[te, "t10"].min()
        X, y = D.loc[tr, FEATS].fillna(0).to_numpy(), D.loc[tr, "trend"].to_numpy()
        if kind == "logit":
            from sklearn.linear_model import LogisticRegression
            mu, sd = X.mean(0), X.std(0) + 1e-9
            m = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, y)
            p[te] = m.predict_proba((D.loc[te, FEATS].fillna(0).to_numpy() - mu) / sd)[:, 1]
        else:
            import lightgbm as lgb
            m = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.03, num_leaves=7, min_child_samples=20, verbose=-1, random_state=113)
            p[te] = m.fit(X, y).predict_proba(D.loc[te, FEATS].fillna(0).to_numpy())[:, 1]
    return p


def route(D: pd.DataFrame, p: np.ndarray) -> np.ndarray:
    """Day -> +1 (trend: momentum setups), -1 (range: reversal setups), 0 (none), from the predictions only."""
    mon = pd.to_datetime(D["t10"], unit="s").dt.strftime("%Y-%m").to_numpy()
    out = np.zeros(len(D), int)
    for m in sorted(set(mon)):
        past = p[(mon < m) & ~np.isnan(p)]
        if len(past) < 40:
            continue
        hi, lo = np.quantile(past, 0.6), np.quantile(past, 0.4)
        cur = mon == m
        out[cur & (p >= hi)] = 1
        out[cur & (p <= lo)] = -1
    return out


def trades(sym: str, suf: str) -> pd.DataFrame:
    """Trades entered from 10:00 server: kind momentum / reversal, entry index, bars, R."""
    parts = []
    E = pd.read_pickle(g8.DATA / f"g110_events_{sym}{suf}.pkl")
    for pre, kind in (("fo", "mom"), ("fa", "rev")):
        x = E[E[f"{pre}_Ra"].notna()]
        parts.append(pd.DataFrame({"day": x["day"], "i": x[f"{pre}_i"].astype(int), "bars": x[f"{pre}_bars"].astype(int),
                                   "R": x[f"{pre}_Ra"], "kind": kind, "src": f"G110 {'theo' if pre == 'fo' else 'ngược'}"}))
    T = pd.read_pickle(g8.DATA / f"g111_tests_{sym}{suf}.pkl")
    parts.append(pd.DataFrame({"day": T["day"], "i": T["k"].astype(int), "bars": T["bars"].astype(int), "R": T["Ra"], "kind": "rev", "src": "G111 test"}))
    C = pd.read_pickle(g8.DATA / f"g112_chase_{sym}{suf}.pkl")
    parts.append(pd.DataFrame({"day": C["day"], "i": C["e"].astype(int), "bars": C["X1_none_bars"].astype(int), "R": C["X1_none"], "kind": "mom", "src": "G112 đuổi"}))
    return pd.concat(parts, ignore_index=True)


def taken(T: pd.DataFrame, D: pd.DataFrame, day_route: dict) -> pd.DataFrame:
    """Trades on routed days (after 10:00, matching kind), no overlap per source."""
    i10 = dict(zip(D["day"], D["i10"]))
    want = T["day"].map(day_route).fillna(0).to_numpy()
    ok = (T["i"].to_numpy() >= T["day"].map(i10).fillna(1e18).to_numpy()) & (
        ((want == 1) & (T["kind"] == "mom").to_numpy()) | ((want == -1) & (T["kind"] == "rev").to_numpy()))
    X = T[ok]
    keep = []
    for src, g in X.groupby("src"):
        free = -1
        for r in g.sort_values("i").itertuples():
            if r.i >= free:
                keep.append(r.Index); free = r.i + r.bars
    return X.loc[keep]


def line(x: pd.DataFrame) -> str:
    if len(x) < 20:
        return f"{len(x)} | |"
    return f"{len(x)} | {x['R'].mean():+.3f} ({boot_lower(x['R'].to_numpy(), x['day'].to_numpy()):+.3f})"


def section(sym: str, df: pd.DataFrame) -> list[str]:
    D = day_table(df, gf.long_m30())
    from sklearn.metrics import roc_auc_score
    L = [f"## {sym}", "", f"Ngày (train + validate): {len(D)}; tỉ lệ ngày xu hướng train {100 * D.loc[D['period'] == 'train', 'trend'].mean():.0f}%, "
         f"validate {100 * D.loc[D['period'] == 'validate', 'trend'].mean():.0f}%; ngày đi ngang {100 * (D['type'] == -1).mean():.0f}%.", "",
         "### A. Dự báo ngày xu hướng lúc 10:00", "", "| Cách | Kỳ | Ngày | AUC | Đúng (ngưỡng 0,5) |", "|---|---|---|---|---|"]
    P = {k: walk(D, k) for k in ("logit", "lgbm")}
    for per in ("train", "validate"):
        m = (D["period"] == per).to_numpy()
        y = D["trend"].to_numpy()[m]
        prev = (D["prev_type"].to_numpy()[m] == 1).astype(int)
        L.append(f"| lặp lại kiểu ngày hôm trước | {per} | {m.sum()} | {roc_auc_score(y, prev) if len(set(y)) > 1 else float('nan'):.3f} | {100 * (prev == y).mean():.0f}% |")
        L.append(f"| luôn đoán 'không xu hướng' | {per} | {m.sum()} | 0.500 | {100 * (y == 0).mean():.0f}% |")
        for k in P:
            pm = P[k][m]; ok = ~np.isnan(pm)
            if ok.sum() > 20 and len(set(y[ok])) > 1:
                L.append(f"| {k} | {per} | {ok.sum()} | {roc_auc_score(y[ok], pm[ok]):.3f} | {100 * ((pm[ok] > 0.5).astype(int) == y[ok]).mean():.0f}% |")
    L += ["", "### B. Chọn setup theo kiểu ngày (lệnh từ 10:00, không chồng theo nguồn; R/lệnh và cận dưới 90%)", ""]
    for suf, nm in (("", "spread thật, có lọc chi phí"), ("_nc", "spread = 0")):
        try:
            T = trades(sym, suf)
        except FileNotFoundError:
            continue
        L += [f"**{nm}**", "", "| Cách chọn | Kỳ | Lệnh · R/lệnh (cận dưới) |", "|---|---|---|"]
        rng = np.random.default_rng(13)
        rt = route(D, P["lgbm"])
        for per in ("train", "validate"):
            Dp = D[D["period"] == per]
            idx = (D["period"] == per).to_numpy()
            all_mom = taken(T, Dp, {d: 1 for d in Dp["day"]}); all_rev = taken(T, Dp, {d: -1 for d in Dp["day"]})
            L.append(f"| mọi ngày, chỉ lệnh theo đà | {per} | {line(all_mom)} |")
            L.append(f"| mọi ngày, chỉ lệnh đảo chiều | {per} | {line(all_rev)} |")
            L.append(f"| mọi ngày, cả hai | {per} | {line(pd.concat([all_mom, all_rev]))} |")
            X = taken(T, Dp, dict(zip(Dp["day"], rt[idx])))
            L.append(f"| **theo dự báo (LightGBM)** | {per} | {line(X)} |")
            draws = []
            for _ in range(200):
                sh = rng.permutation(rt[idx])
                draws.append(taken(T, Dp, dict(zip(Dp["day"], sh)))["R"].mean())
            L.append(f"| phân loại ngẫu nhiên (200 lần) | {per} | trung bình {np.nanmean(draws):+.3f}; tỉ lệ ≥ dự báo **{np.mean(np.array(draws) >= X['R'].mean()) if len(X) else float('nan'):.3f}** |")
            orc = taken(T, Dp, dict(zip(Dp["day"], Dp["type"])))
            L.append(f"| phân loại hoàn hảo (nhãn sau ngày, chỉ tham khảo) | {per} | {line(orc)} |")
        L.append("")
    return L


def main(symbols):
    import importlib
    import os
    L = ["# G113 phần 3: kiểu ngày lúc mở phiên Âu và chọn setup theo kiểu ngày", "",
         "Ngày 14/10/2026. Plan: docs/superpowers/plans/2026-10-14-g113-gross-htf-daytype.md. Dữ liệu raw MT5 M5. Chỉ train và validate; "
         "**test 2026 niêm phong**. Script: research/long/g113_daytype.py, g113_audit.py.", ""]
    for s in symbols:
        os.environ["G108_SYMBOL"] = s
        importlib.reload(g8)
        importlib.reload(gf)
        L += section(s, g8.load_m5_raw())
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
