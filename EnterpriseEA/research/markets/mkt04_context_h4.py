"""MKT04: the MKT03 context forecast at H4 scale (A = ATR14 of the last closed H4 bar; SL 1 A, TP 2 A, up to 48 h;
limit 0.5 A within 4 h), decisions at full-hour M30 closes; US indices, big crypto and gold.
Pre-registered plan: docs/superpowers/plans/2026-10-11-mkt04-context-h4.md. MT5 data only.

  python mkt04_context_h4.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import mkt03_context as m3

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-mkt04-context-h4.md"
GROUPS = {"Chỉ số": {"syms": ("NAS100", "DJ30", "SP500"), "leader": "NAS100", "oos": (2025, 1)},
          "Crypto lớn": {"syms": ("BTCUSD", "ETHUSD"), "leader": "BTCUSD", "oos": (2021, 1)},
          "Vàng": {"syms": ("XAUUSD",), "leader": "XAUUSD", "oos": (2020, 1)}}
HOLD, LIMIT_BARS, SL, TP, PULL = 96, 8, 1.0, 2.0, 0.5
COMM = {"XAUUSD": 0.06}           # price units per round trip ($6/lot), G68
SFX = m3.SFX
PLANS = m3.PLANS


def load(sym):
    if sym != "XAUUSD":
        return m3.load(sym)
    df = pd.read_csv(m3.DATA / "m30v" / "XAUUSD.csv")
    df = df[df["time"] >= m3.ts(2018, 7)].reset_index(drop=True)   # real M30 bars start mid-2018
    df["sp"] = df["spread"] * 0.01
    med = float(df.loc[df["time"] >= m3.ts(2024, 3), "sp"].median())
    df["sp"] = df["sp"].clip(lower=med)
    df.attrs["med"] = med
    return df


def leader_frame(sym):
    df = load(sym)
    c = df["close"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(df["high"].to_numpy(), pc) - np.minimum(df["low"].to_numpy(), pc)
    atr = m3.wilder(tr, 14)
    return pd.DataFrame({"time": df["time"], "lead_r1": (c - pd.Series(c).shift(1).to_numpy()) / atr,
                         "lead_r4": (c - pd.Series(c).shift(4).to_numpy()) / atr})


def h4_atr(df):
    """ATR14 (Wilder) of the last COMPLETED H4 bar at each M30 bar."""
    t = df["time"].to_numpy()
    b = t // 14400
    g = df.groupby(b).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = np.r_[g["c"].iloc[0], g["c"].to_numpy()[:-1]]
    tr = np.maximum(g["h"].to_numpy(), pc) - np.minimum(g["l"].to_numpy(), pc)
    a = m3.wilder(tr, 14)
    pos = {k: j for j, k in enumerate(g.index.to_numpy())}
    idx = np.array([pos[k] - 1 for k in b])
    return np.where(idx >= 14, a[np.maximum(idx, 0)], np.nan)


def labels(df, A, sym, dec):
    o, h, l, c, sp = (df[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
    med, comm = df.attrs["med"], COMM.get(sym, 0.0)
    n = len(c)
    out = {}
    for plan in PLANS:
        for d in (1, -1):
            R = np.full(n, np.nan)
            X = np.full(n, -1, dtype=np.int64)
            for i in np.flatnonzero(dec):
                a = A[i]
                if not a > 0 or i + HOLD + LIMIT_BARS + 2 >= n:
                    continue
                cost = (0.5 * med + comm) / a
                if plan == "M":
                    e = i + 1
                    entry = o[e] + (sp[e] if d == 1 else 0.0) + d * 0.5 * med
                    j0 = e
                else:
                    level = c[i] - d * PULL * a
                    e = -1
                    for j in range(i + 1, i + 1 + LIMIT_BARS):
                        if (d == 1 and l[j] + sp[j] < level) or (d == -1 and h[j] > level):
                            e = j
                            break
                    if e < 0:
                        continue
                    entry = level
                    stop = entry - d * SL * a
                    if (d == 1 and l[e] <= stop) or (d == -1 and h[e] + sp[e] >= stop):
                        R[i], X[i] = -SL - cost, e
                        continue
                    j0 = e + 1
                stop, tgt = entry - d * SL * a, entry + d * TP * a
                px = None
                last = min(n - 1, e + HOLD - 1)
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
                R[i] = d * (px - entry) / a - cost
                X[i] = x
            out[(plan, d)] = (R, X)
    return out


def build_group(gname, g):
    lead = leader_frame(g["leader"])
    frames = []
    for k, sym in enumerate(g["syms"]):
        df = load(sym)
        f, atr = m3.context(df, lead)
        A = h4_atr(df)
        c = df["close"].to_numpy()
        f["r96"] = (c - pd.Series(c).shift(96).to_numpy()) / atr
        f["atr_vs_h4"] = atr / A
        dec = ((df["time"].to_numpy() + 1800) % 3600 == 0)
        lab = labels(df, A, sym, dec)
        f["sym"] = k
        f["sym_name"] = sym
        f["i"] = np.arange(len(f))
        for (plan, d), (R, X) in lab.items():
            f[f"R_{plan}_{SFX[d]}"] = R
            f[f"X_{plan}_{SFX[d]}"] = X
        frames.append(f[dec])
        print(gname, sym, int(dec.sum()), flush=True)
    return pd.concat(frames, ignore_index=True)


def main():
    mean = m3.mean
    L = ["# MKT04: dự báo theo ngữ cảnh ở quy mô H4 — chỉ số Mỹ, crypto và vàng — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-mkt04-context-h4.md`. Như MKT03 nhưng A = ATR14 H4: kế hoạch M (market, SL 1 A, TP 2 A, "
         "tối đa 48 giờ) và L (limit cách 0,5 A chờ 4 giờ, cùng SL/TP); quyết định mỗi giờ. LightGBM cuốn chiếu, mọi dự báo "
         "ngoài mẫu. Chi phí khắt khe; vàng có phí $6/lot, chỉ số/crypto phí 0. R theo A.", ""]
    cells = []
    for gname, g in GROUPS.items():
        F = build_group(gname, g)
        imp = m3.walk_forward(F, g)
        v0 = m3.ts(*g["oos"])
        L += [f"## {gname}", ""]
        for plan in PLANS:
            vp = pd.concat([F.loc[(F["time"] >= v0) & (F["time"] < m3.TEST0), f"P_{plan}_{SFX[d]}"] for d in (1, -1)]).dropna()
            best = None
            L += [f"**Kế hoạch {plan}** — chọn ngưỡng trên validate:", "", "| Phân vị | θ | Lệnh validate | R/lệnh validate |",
                  "|---|---|---|---|"]
            for q in (0.80, 0.90, 0.95):
                th = float(vp.quantile(q))
                tr_ = [x["r"] for x in m3.simulate(F, plan, th, v0, m3.TEST0) if x["r"] is not None]
                L.append(f"| {q:.0%} | {th:+.3f} | {len(tr_)} | {mean(tr_):+.3f} |")
                if len(tr_) >= 60 and (best is None or mean(tr_) > best[2]):
                    best = (q, th, mean(tr_))
            uncond_val = mean(pd.concat([F.loc[(F["time"] >= v0) & (F["time"] < m3.TEST0), f"R_{plan}_{SFX[d]}"]
                                         for d in (1, -1)]).dropna().tolist())
            L += ["", f"Không điều kiện trên validate: {uncond_val:+.3f}.", ""]
            if best is None:
                L += ["Không ngưỡng nào có ≥ 60 lệnh validate → ô dừng.", ""]
                cells.append((gname, plan, None, g))
                continue
            q, th, vbest = best
            sims = m3.simulate(F, plan, th, m3.TEST0, m3.TEST1)
            test = [x for x in sims if x["r"] is not None]
            rs = [x["r"] for x in test]
            res = {"q": q, "th": th, "n": len(rs), "fill": (len(test) / max(len(sims), 1)) if plan == "L" else None,
                   "vbest": vbest}
            if len(rs) >= 2:
                p, uncond = m3.perm_p(F, plan, len(rs), mean(rs), m3.TEST0, m3.TEST1)
                yrs = (m3.TEST1 - m3.TEST0) / (365.25 * 86400)
                eq = pk = dd = 0.0
                for x in sorted(test, key=lambda z: z["t"]):
                    eq += 0.5 * x["r"]
                    pk = max(pk, eq)
                    dd = max(dd, pk - eq)
                res.update(m=mean(rs), l90=m3.lower(rs, 0.10), lb=m3.lower(rs, 0.10 / 6), p=p, uncond=uncond,
                           py=0.5 * sum(rs) / yrs, dd=dd,
                           per={s: (len([x for x in test if x["sym"] == s]), mean([x["r"] for x in test if x["sym"] == s]))
                                for s in g["syms"]})
            cells.append((gname, plan, res, g))
            top = sorted(((sum(imp[(plan, d)].get(k, 0) for d in (1, -1)), k) for k in m3.FEATS), reverse=True)[:10]
            L += [f"Ngưỡng chọn: phân vị {q:.0%} (θ {th:+.3f}), validate {vbest:+.3f}. Ngữ cảnh quan trọng nhất: "
                  + ", ".join(k for _, k in top) + ".", ""]
            print(gname, plan, {k: v for k, v in res.items() if k != "per"}, flush=True)
    L += ["## Kiểm tra cuối (10/2025–10/2026)", "",
          "| Ô | Lệnh | Khớp limit | R/lệnh | Không điều kiện | p hoán vị | Cận dưới 90% | Cận dưới 98,3% | Sau trừ 0,10R | %/năm @0,5% | DD @0,5% | Theo symbol | Đạt? |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for gname, plan, res, g in cells:
        if not res or "m" not in res:
            L.append(f"| {gname} {plan} | {res['n'] if res else 0} | | | | | | | | | | | không |")
            continue
        ok = res["n"] >= 60 and res["m"] > 0 and res["l90"] > 0 and res["m"] - m3.PENALTY > 0 and res["p"] < 0.05
        per = ", ".join(f"{s} {n} {m:+.2f}" for s, (n, m) in res["per"].items())
        fill = f"{res['fill']:.0%}" if res["fill"] is not None else "—"
        L.append(f"| {gname} {plan} | {res['n']} | {fill} | {res['m']:+.3f} | {res['uncond']:+.3f} | {res['p']:.3f} | "
                 f"{res['l90']:+.3f} | {res['lb']:+.3f} | {res['m'] - m3.PENALTY:+.3f} | {res['py']:+.1f}% | {res['dd']:.1f}% | {per} | "
                 f"{'**ĐẠT**' + (' (cả Bonferroni)' if res['lb'] > 0 else '') if ok else 'không'} |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
