"""G153: seven earlier candidates re-scored with a D1 trend-regime gate (XauRegime R1: close vs EMA50 D1 and the EMA50
10-day slope), a regime-aligned random control and a fresh BTC transfer. Plan: docs/superpowers/plans/2026-10-23-g153-regime-gated.md.

Usage: g153_regime_gated.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402
import g139_hybrid as hy  # noqa: E402
import g143_session_momentum as nm  # noqa: E402
import g147_risk_map as rm  # noqa: E402
import g148_layered_risk_map as lm  # noqa: E402
import g149_repeating as rp  # noqa: E402

PER = [("05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1))]
PVAL, RUNS = 0.007, 200


def regime(D):
    """Per bar: R1 state (+1 / -1 / 0) of the last closed server day."""
    t, c = D["t"], D["c"]
    day = t // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    dc, days = c[ends], day[ends]
    e = g.ema(dc, 50)
    st = np.zeros(len(dc), int)
    for k in range(60, len(dc)):
        up = dc[k] > e[k] and e[k] > e[k - 10]
        dn = dc[k] < e[k] and e[k] < e[k - 10]
        st[k] = 1 if up else (-1 if dn else 0)
    q = np.searchsorted(days, day, side="left") - 1
    return np.where(q >= 0, st[np.maximum(q, 0)], 0)


def norm(D, rows, kind):
    out = []
    for t in rows:
        if not t:
            continue
        e = int(t["e"])
        A = D["atr"][e - 1]
        risk = t["risk"]
        if kind == "gp":
            k_tp = t["tp_r"] * risk / A
        elif kind == "rp":
            k_tp = t["k_tp"]                                     # already in ATR of bar e-1 (g149 make)
        else:
            k_tp = None
        out.append(dict(e=e, d=int(t["d"]), rh=float(t["rh"]), rh15=float(t["rh15"]), srv=int(D["t"][e]), hour=int(D["hour"][e - 1]),
                        k_sl=risk / A, k_tp=k_tp, hold=int(t["x"]) - e + 1))
    return out


def period(srv):
    return next((pn for pn, a, z in PER if a <= srv < z), None)


def stat(x):
    x = list(x)
    return {"n": len(x), "mean": round(float(np.mean(x)), 3), "total": round(float(np.sum(x)), 1)} if x else {"n": 0}


def control(D, reg, gated, per_of):
    pool = {}
    n = len(D["c"])
    for j in range(300, n - 60):
        p = per_of(int(D["t"][j + 1]))
        if p is None:
            continue
        s = int(reg[j + 1])
        if s:
            pool.setdefault((p, s, int(D["hour"][j])), []).append(j)
    actual = float(np.mean([t["rh"] for t in gated]))
    rng = random.Random(153)
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in gated:
            cand = pool.get((per_of(t["srv"]), t["d"], t["hour"]))
            if not cand:
                continue
            for _ in range(20):
                j = rng.choice(cand)
                e, A, d = j + 1, D["atr"][j], t["d"]
                entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
                tp = entry + d * t["k_tp"] * A if t["k_tp"] else entry + d * 1e6
                r = gp.run_trade(D, e, d, entry, entry - d * t["k_sl"] * A, tp, t["hold"])
                if r:
                    u.append(r["rh"]); break
        hits += float(np.mean(u)) >= actual
    return (hits + 1) / (RUNS + 1)


def candidates(root, symbol):
    """{name: (D, rows)} for one symbol."""
    out = {}
    for tf in ("M30", "H1"):
        g.set_tf(tf)
        g.DATA = root / f"{tf.lower()}v"
        D = hy.prepare(g.load(symbol))
        out[f"A1-{tf}"] = (D, norm(D, [t for t in hy.a1(D) if t], "gp"))
        out[f"C-{tf}"] = (D, norm(D, [t for t in hy.csq(D) if t], "gp"))
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load(symbol))
    cx = rp.Ctx(D, lm.bar_context(D), lm.daily_context(D))
    out["K3"] = (D, norm(D, rp.k3(cx, 0), "rp"))
    out["W1"] = (D, norm(D, rp.w1(cx, 0), "rp"))
    if symbol == "XAUUSD":
        g.set_tf("M15")
        g.DATA = root / "m15v"
        D = g.load(symbol)
        D["hour"] = (D["t"] % 86400) // 3600
        rows, _, _ = nm.run_cell(D, nm.daily_atr(D), "NY", nm.THR)
        out["NY"] = (D, norm(D, rows, "none"))
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    res = {}
    xau = candidates(root, "XAUUSD")
    for name, (D, rows) in xau.items():
        reg = regime(D)
        for t in rows:
            t["reg"] = int(reg[t["e"]]) * t["d"]                  # +1 aligned, -1 against, 0 neutral
            t["p"] = period(t["srv"])
        rows = [t for t in rows if t["p"]]
        al = [t for t in rows if t["reg"] == 1]
        r = {"không lọc": {pn: stat(t["rh"] for t in rows if t["p"] == pn) for pn, _, _ in PER},
             "cùng chế độ": {pn: stat(t["rh"] for t in al if t["p"] == pn) for pn, _, _ in PER},
             "trung tính": stat(t["rh"] for t in rows if t["reg"] == 0),
             "ngược chế độ": stat(t["rh"] for t in rows if t["reg"] == -1),
             "cùng chế độ: mua / bán": [stat(t["rh"] for t in al if t["d"] == 1), stat(t["rh"] for t in al if t["d"] == -1)],
             "cùng chế độ: phí×1,5": stat(t["rh15"] for t in al),
             "cùng chế độ: bỏ 5 lệnh lớn nhất": stat(sorted(t["rh"] for t in al)[:-5]),
             "cùng chế độ theo năm": {str(y): stat(t["rh"] for t in al if g.ts(y, 1, 1) <= t["srv"] < g.ts(y + 1, 1, 1))
                                      for y in range(2018, 2027)}}
        r["p đối chứng (ngẫu nhiên cùng chế độ)"] = control(D, reg, al, period) if al else None
        min_n = 10 if name == "W1" else 20
        c1 = all(r["cùng chế độ"][pn]["n"] >= min_n and r["cùng chế độ"][pn]["mean"] > 0 for pn, _, _ in PER)
        c2 = sum((r["cùng chế độ"][pn].get("mean", -9) >= r["không lọc"][pn].get("mean", 9)) for pn, _, _ in PER) >= 2
        buy, sell = r["cùng chế độ: mua / bán"]
        c3 = buy.get("mean", -1) > 0 and (sell["n"] < 15 or sell["mean"] >= -0.05)
        c4 = r["cùng chế độ: phí×1,5"].get("mean", -1) > 0 and r["cùng chế độ: bỏ 5 lệnh lớn nhất"].get("mean", -1) > 0
        c5 = r["p đối chứng (ngẫu nhiên cùng chế độ)"] is not None and r["p đối chứng (ngẫu nhiên cùng chế độ)"] <= PVAL
        r["tiêu chí 1–5"] = [c1, c2, c3, c4, c5]
        res[name] = r
        print(name, r["cùng chế độ"], r["p đối chứng (ngẫu nhiên cùng chế độ)"], r["tiêu chí 1–5"], flush=True)
    btc = candidates(root, "BTCUSD")
    for name, (D, rows) in btc.items():
        reg = regime(D)
        al = [t for t in rows if int(reg[t["e"]]) * t["d"] == 1]
        res[name]["BTC cùng chế độ"] = stat(t["rh"] for t in al)
        res[name]["BTC không lọc"] = stat(t["rh"] for t in rows)
        print("BTC", name, res[name]["BTC cùng chế độ"], res[name]["BTC không lọc"], flush=True)
    for name, r in res.items():
        c6 = r.get("BTC cùng chế độ", {}).get("mean", -1) > 0 if name != "NY" else True
        r["tiêu chí 6 (BTC)"] = c6 if name != "NY" else "không áp"
        r["kết luận"] = "ĐẠT" if all(r["tiêu chí 1–5"]) and c6 else "KHÔNG ĐẠT"
    # reference: the S07 M30 book by the same regime
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    reg = regime(D)
    import g136_p1p4 as p1
    legs = p1.m30_book()
    ref = {}
    for lab, s in (("cùng", 1), ("trung tính", 0), ("ngược", -1)):
        sel = [x for x in legs if PER[0][1] <= x["srv"] < PER[-1][2]
               and int(reg[int(np.searchsorted(D["t"], x["srv"], side="right")) - 1]) * x["d"] == s]
        ref[lab] = {pn: stat(x["r"] for x in sel if a <= x["srv"] < z) for pn, a, z in PER}
    res["Tham chiếu S07 M30 theo chế độ"] = ref
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
