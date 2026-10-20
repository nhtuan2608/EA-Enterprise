"""G135: S07 exits on M5 / M15 / M30 / H1 - fixed TP, break-even, ATR trail, EMA exits, partial, time stop, a context
rule (quick target against the D1 wave) and a learned continuation model at +1R, all on the same S07 entries.
Pre-registered plan: docs/superpowers/plans/2026-10-21-g135-exits-continuation.md. MT5 data only.

  python g135_exits.py
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g67_dmi_ema as g  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-21-g135-exits-continuation.md"
TFS = {"M5": (16, 8, 1440), "M15": (16, 8, 480), "M30": (8, 4, 240), "H1": (4, 2, 120)}


def ts(s):
    return int(pd.Timestamp(s).timestamp())


PER = {"M5": [("train", ts("2024-05-01"), ts("2025-03-01")), ("validate", ts("2025-03-01"), ts("2025-10-01")),
              ("test", ts("2025-10-01"), ts("2026-10-10"))],
       "M15": [("train", ts("2021-07-20"), ts("2024-01-01")), ("validate", ts("2024-01-01"), ts("2025-07-01")),
               ("test", ts("2025-07-01"), ts("2026-10-10"))]}
PER["M30"] = PER["H1"] = [("train", ts("2018-09-01"), ts("2024-01-01")), ("validate", ts("2024-01-01"), ts("2025-07-01")),
                          ("test", ts("2025-07-01"), ts("2026-10-10"))]

RULES = {
    "CUR": dict(ema="E2X", tp=8.0),
    "TP1": dict(tp=1.0), "TP1.5": dict(tp=1.5), "TP2": dict(tp=2.0), "TP3": dict(tp=3.0), "TP5": dict(tp=5.0),
    "BE3": dict(be=1.0, tp=3.0), "BE5": dict(be=1.0, tp=5.0),
    "TR1.5": dict(trail=1.5), "TR2.5": dict(trail=2.5),
    "EMA21": dict(ema=21, tp=8.0),
    "PART": dict(ema="E2X", tp=8.0, part=(0.5, 1.5)),
    "TIME": dict(ema="E2X", tp=8.0, time=(8, 0.5)),
}


def period(tf, u):
    for p, a, b in PER[tf]:
        if a <= u < b:
            return p
    return None


def d1_state():
    m = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
    D = m.assign(day=m["time"] // 86400).groupby("day")["close"].last()
    s = np.sign((D.rolling(50).mean() - D.rolling(200).mean()).fillna(0).to_numpy())
    return D.index.to_numpy(), s


def rsi(c, n=14):
    ch = np.diff(c, prepend=c[0])
    def w(x):
        out, a = np.empty(len(x)), None
        for i, v in enumerate(x):
            a = v if a is None else a + (v - a) / n
            out[i] = a
        return out
    gg, ll = w(np.maximum(ch, 0)), w(np.maximum(-ch, 0))
    return 100 - 100 / (1 + gg / np.maximum(ll, 1e-12))


class Exits:
    def __init__(self, D, max_hold):
        self.D, self.H = D, max_hold
        self.med = float(D["sp_med"])
        self.comm = float(D["comm"])

    def run(self, t, rule, cut_at=None):
        """R after harsh costs for trade t under rule. cut_at: exit at the open of this bar (learned exit)."""
        D = self.D
        o, h, l, c, sp, atr, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"], D["E"]
        d, e0, dist = t["d"], t["e0"], t["risk"]
        n = len(c)
        entry = o[e0] + (sp[e0] if d == 1 else 0.0)
        sl = entry - d * dist
        tp = entry + d * rule["tp"] * dist if rule.get("tp") else None
        best, frac, realized = entry, 1.0, 0.0
        part_done = False
        reached_half = False
        for j in range(e0, min(n, e0 + self.H)):
            if cut_at is not None and j == cut_at:
                px = o[j] + (sp[j] if d == -1 else 0.0)
                return self._r(realized, frac, d, px, entry, dist)
            s = sp[j] if d == -1 else 0.0
            bh, bl, bo = h[j] + s, l[j] + s, o[j] + s
            if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
                px = min(sl, bo) if d == 1 else max(sl, bo)
                return self._r(realized, frac, d, px, entry, dist)
            if tp is not None and ((d == 1 and bh >= tp) or (d == -1 and bl <= tp)):
                px = max(tp, bo) if d == 1 else min(tp, bo)
                return self._r(realized, frac, d, px, entry, dist)
            if rule.get("part") and not part_done:
                f, at = rule["part"]
                lvl = entry + d * at * dist
                if (d == 1 and bh >= lvl) or (d == -1 and bl <= lvl):
                    realized += f * at
                    frac -= f
                    part_done = True
            best = max(best, h[j]) if d == 1 else min(best, l[j] + s)
            fav = d * (best - entry) / dist
            if rule.get("be") and fav >= rule["be"] and d * (sl - entry) < 0:
                sl = entry + d * sp[j] if d == 1 else entry - d * 0.0
            if rule.get("trail") and fav >= 1.0:
                tr = best - d * rule["trail"] * atr[j]
                if d * (tr - sl) > 0:
                    sl = tr
            if rule.get("time"):
                N, thr = rule["time"]
                reached_half = reached_half or fav >= thr
                if j - e0 + 1 >= N and not reached_half and j + 1 < n:
                    px = o[j + 1] + (sp[j + 1] if d == -1 else 0.0)
                    return self._r(realized, frac, d, px, entry, dist)
            em = rule.get("ema")
            if em is not None:
                ema = (E[100] if d * (best - entry) >= 3 * dist else E[55]) if em == "E2X" else E[em]
                if d * (c[j] - ema[j]) < 0 and j + 1 < n:
                    px = o[j + 1] + (sp[j + 1] if d == -1 else 0.0)
                    return self._r(realized, frac, d, px, entry, dist)
        x = min(n - 1, e0 + self.H - 1)
        return self._r(realized, frac, d, c[x] + (sp[x] if d == -1 else 0.0), entry, dist)

    def _r(self, realized, frac, d, px, entry, dist):
        return realized + frac * d * (px - entry) / dist - (self.comm + self.med) / dist

    def checkpoint(self, t):
        """First bar closing >= +1R before the stop; features there; label +3R before back to entry; label time."""
        D = self.D
        o, h, l, c, sp, atr = D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"]
        d, e0, dist = t["d"], t["e0"], t["risk"]
        n = len(c)
        entry = o[e0] + (sp[e0] if d == 1 else 0.0)
        sl = entry - d * dist
        for j in range(e0, min(n - 1, e0 + self.H)):
            s = sp[j] if d == -1 else 0.0
            if (d == 1 and l[j] + s <= sl) or (d == -1 and h[j] + s >= sl):
                return None
            if d * (c[j] - entry) >= dist:
                lab, lab_j = 0, min(n - 1, e0 + self.H)
                for k in range(j + 1, min(n, e0 + self.H)):
                    s2 = sp[k] if d == -1 else 0.0
                    if (d == 1 and l[k] + s2 <= entry) or (d == -1 and h[k] + s2 >= entry):
                        lab, lab_j = 0, k
                        break
                    if (d == 1 and h[k] >= entry + 3 * dist) or (d == -1 and l[k] + s2 <= entry - 3 * dist):
                        lab, lab_j = 1, k
                        break
                E, adx = D["E"], D["adx"]
                a = atr[j]
                f = dict(adx=adx[j], adx_slope=adx[j] - adx[max(j - 3, 0)], di=d * (D["pdi"][j] - D["mdi"][j]),
                         rsi=50 + d * (D["rsi"][j] - 50), d21=d * (c[j] - E[21][j]) / a, d55=d * (c[j] - E[55][j]) / a,
                         ordered=float(d * (E[21][j] - E[55][j]) > 0 and d * (E[55][j] - E[100][j]) > 0),
                         wave=t["wave"], h4=float(D["h4_side"][j] * d), bars=j - e0, dist_atr=t["dist_atr"],
                         hour=((D["utc"][j] // 3600) % 24), rv=D["rv"][j] if not np.isnan(D["rv"][j]) else 1.0)
                return dict(j=j, f=f, label=lab, label_utc=int(D["utc"][lab_j]))
        return None


def mean(x):
    return statistics.fmean(x) if x else 0.0


def metrics(rows):
    if not rows:
        return dict(n=0, r=0.0, tot=0.0, dd=0.0, mar=0.0)
    rs = [x for _, x in sorted(rows)]
    eq = np.cumsum(rs)
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]))
    tot = float(eq[-1])
    return dict(n=len(rs), r=float(np.mean(rs)), tot=tot, dd=dd, mar=tot / dd if dd > 0 else (tot if tot > 0 else 0.0))


def fm(m):
    return f"{m['n']} / {m['r']:+.3f} / {m['tot']:+.0f} / {m['mar']:.1f}" if m["n"] else "—"


def learned(tf_trades, cps, ex):
    """Quarterly walk-forward LightGBM on checkpoints; returns {trade index: R under LRN}."""
    import lightgbm as lgb
    keys = list(cps[0]["f"].keys()) if cps else []
    out = {}
    qs = pd.date_range("2018-01-01", "2026-12-31", freq="QS")
    for q0, q1 in zip(qs[:-1], qs[1:]):
        a, b = int(q0.timestamp()), int(q1.timestamp())
        train = [c for c in cps if c["label_utc"] < a]
        test = [c for c in cps if a <= c["utc"] < b]
        if not test:
            continue
        if len(train) < 100 or len({c["label"] for c in train}) < 2:
            for c in test:
                out[c["k"]] = None
            continue
        X = np.array([[c["f"][k] for k in keys] for c in train])
        y = np.array([c["label"] for c in train])
        mdl = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=135)
        mdl.fit(X, y)
        p = mdl.predict_proba(np.array([[c["f"][k] for k in keys] for c in test]))[:, 1]
        for c, pi in zip(test, p):
            out[c["k"]] = float(pi)
    return out


def main():
    days, st = d1_state()
    L = ["# G135: TP / SL, chốt lời, tiếp diễn hay đảo chiều — S07 ở M5 / M15 / M30 / H1 — kết quả", "",
         "Kế hoạch: `plans/2026-10-21-g135-exits-continuation.md`. Cùng điểm vào S07 (G67), chỉ đổi cách thoát. Chi phí khắt khe "
         "(spread vào/ra + trượt 0,5 × spread trung vị mỗi chiều + phí). Ô: lệnh / R mỗi lệnh / tổng R / **R-MAR** (tổng R ÷ DD theo R). "
         "Kỳ test đã từng xem cho điểm vào S07, chưa từng cho các cách thoát này (bán-sạch).", ""]
    summary = []
    for tf, (comp, cool, hold) in TFS.items():
        g.set_tf(tf)
        g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = comp, cool, hold
        D = g.load("XAUUSD")
        D["rsi"] = rsi(D["c"])
        sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
        base = g.trades("XAUUSD", "E2X", 8.0, None, sig)
        ex = Exits(D, hold)
        trades = []
        for k, t in enumerate(base):
            p = period(tf, t["utc"])
            if p is None:
                continue
            day = int(D["t"][t["i"]] // 86400)
            q = np.searchsorted(days, day, side="left") - 1
            s = st[q] if q >= 0 else 0
            t = dict(t, p=p, wave=int(s * t["d"]), k=k)
            trades.append(t)
        print(tf, "trades", len(trades), flush=True)
        res = {name: {} for name in list(RULES) + ["CTX", "LRN"]}
        for t in trades:
            for name, rule in RULES.items():
                res[name][t["k"]] = ex.run(t, rule)
            res["CTX"][t["k"]] = ex.run(t, RULES["TP1.5"] if t["wave"] == -1 else RULES["CUR"])
        cps = []
        for t in trades:
            c = ex.checkpoint(t)
            if c:
                c.update(k=t["k"], utc=int(D["utc"][c["j"]]), wave=t["wave"], p=t["p"])
                cps.append(c)
        probs = learned(trades, cps, ex)
        cp_by = {c["k"]: c for c in cps}
        for t in trades:
            c = cp_by.get(t["k"])
            pr = probs.get(t["k"]) if c else None
            res["LRN"][t["k"]] = ex.run(t, RULES["CUR"], cut_at=c["j"] + 1) if (c and pr is not None and pr < 0.5) \
                else res["CUR"][t["k"]]
        # descriptive continuation table
        L += [f"## {tf} ({len(trades)} lệnh S07)", "", "**Tiếp diễn hay đảo chiều sau khi lệnh đạt +1R** (mọi kỳ):", "",
              "| Nhóm sóng D1 | Lệnh | Đạt +1R | Đạt +1R rồi tới +3R | Đạt +1R rồi về giá vào |", "|---|---|---|---|---|"]
        for wname, wv in (("cùng sóng", 1), ("ngược sóng", -1), ("chưa rõ", 0)):
            ts_ = [t for t in trades if t["wave"] == wv]
            cc = [c for c in cps if c["wave"] == wv]
            if not ts_:
                continue
            L.append(f"| {wname} | {len(ts_)} | {len(cc) / len(ts_):.0%} | {mean([c['label'] for c in cc]):.0%} | "
                     f"{1 - mean([c['label'] for c in cc]):.0%} |")
        L += ["", "| Cách thoát | Nhóm | Train | Validate | Test |", "|---|---|---|---|---|"]
        for gname, gf in (("tất cả", lambda t: True), ("cùng sóng", lambda t: t["wave"] == 1), ("ngược sóng", lambda t: t["wave"] == -1)):
            best, bscore, cur = None, None, None
            mets = {}
            for name in res:
                m = {p: metrics([(t["utc"], res[name][t["k"]]) for t in trades if t["p"] == p and gf(t)])
                     for p in ("train", "validate", "test")}
                mets[name] = m
            cur = mets["CUR"]
            for name, m in mets.items():
                if name == "CUR":
                    continue
                if m["train"]["mar"] > cur["train"]["mar"] and m["validate"]["mar"] > cur["validate"]["mar"]:
                    sc = min(m["train"]["mar"], m["validate"]["mar"])
                    if bscore is None or sc > bscore:
                        best, bscore = name, sc
            for name in ["CUR"] + ([best] if best else []):
                m = mets[name]
                tag = "" if name == "CUR" else " **(chọn)**"
                L.append(f"| {name}{tag} | {gname} | {fm(m['train'])} | {fm(m['validate'])} | {fm(m['test'])} |")
            if best:
                ok = mets[best]["test"]["mar"] > cur["test"]["mar"] and mets[best]["test"]["tot"] > 0
                summary.append((tf, gname, best, mets[best], cur, ok))
                bd = {dd: metrics([(t["utc"], res[best][t["k"]]) for t in trades if t["p"] == "test" and gf(t) and t["d"] == dd])
                      for dd in (1, -1)}
                L.append(f"| ↳ {best} test mua · bán | {gname} | | | {fm(bd[1])} · {fm(bd[-1])} |")
            else:
                summary.append((tf, gname, None, None, cur, False))
        # full grid (train / validate R-MAR) for transparency
        L += ["", "<details><summary>Mọi cách thoát (tất cả lệnh): R-MAR train / validate / test</summary>", "",
              "| Cách thoát | Train | Validate | Test |", "|---|---|---|---|"]
        for name in res:
            m = {p: metrics([(t["utc"], res[name][t["k"]]) for t in trades if t["p"] == p]) for p in ("train", "validate", "test")}
            L.append(f"| {name} | {fm(m['train'])} | {fm(m['validate'])} | {fm(m['test'])} |")
        L += ["", "</details>", ""]
        print(tf, "done", flush=True)
    L += ["## Tổng hợp", "", "| Khung | Nhóm | Cách thoát chọn | Test: chọn so với CUR (R/lệnh · R-MAR) | Đạt test? |", "|---|---|---|---|---|"]
    for tf, gname, best, m, cur, ok in summary:
        if best:
            L.append(f"| {tf} | {gname} | {best} | {m['test']['r']:+.3f} · {m['test']['mar']:.1f} so với "
                     f"{cur['test']['r']:+.3f} · {cur['test']['mar']:.1f} | {'**đạt**' if ok else 'không'} |")
        else:
            L.append(f"| {tf} | {gname} | — (không cách nào hơn CUR ở cả train và validate) | | |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
