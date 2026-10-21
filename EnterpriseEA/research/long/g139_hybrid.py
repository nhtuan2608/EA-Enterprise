"""G139 parts A and C: the adviser's five-layer setups (A1 trend pullback, A2 Wyckoff range-spring-breakout, A3 morning /
evening star at support / resistance, A4a rising / falling wedge break, A4b channel pullback with trend + volume, A5 the
adviser's additive score >= 70) and C (Bollinger squeeze breakout in the D1 direction), on M30 and H1.
Plan: docs/superpowers/plans/2026-10-22-g139-hybrid-setups.md (pre-registered). Engine, costs and random control: g137_patterns.

Usage: g139_hybrid.py <data dir with m30v/ h1v/ m15v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402

PVAL = 0.003
MIN_N = {"H1": 30, "M30": 40}
DECIDE = ("train", "validate", "test")


# ------------------------------------------------------------------------------------------------ indicators
def prepare(D):
    c, o, h, l, v = D["c"], D["o"], D["h"], D["l"], D["v"]
    n = len(c)
    D["e20"], D["e50"], D["e200"] = g.ema(c, 20), g.ema(c, 50), D["E"][200]
    ch = np.diff(c, prepend=c[0])
    gain, loss = g.rma(np.maximum(ch, 0.0), 14), g.rma(np.maximum(-ch, 0.0), 14)
    D["rsi"] = 100 - 100 / (1 + gain / np.maximum(loss, 1e-12))
    va = np.full(n, np.nan)
    cs = np.concatenate([[0.0], np.cumsum(v)])
    va[20:] = (cs[20:n] - cs[0:n - 20]) / 20.0                 # mean of v[i-20 .. i-1]
    D["vavg"] = va
    W = np.lib.stride_tricks.sliding_window_view(c, 20)
    sma, sd = np.full(n, np.nan), np.full(n, np.nan)
    sma[19:], sd[19:] = W.mean(1), W.std(1)
    D["sma20"], D["bw"] = sma, 4 * sd
    D["hour"] = (D["t"] % 86400) // 3600
    ph, pl = gp.pivots(D)
    D["ph"], D["pl"] = np.array(ph), np.array(pl)
    # D1 state of the last closed server day (SMA50 / SMA200), as the EA
    day = D["t"] // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], n - 1]
    lc, days = c[ends], day[ends]
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    st = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0)
    q = np.searchsorted(days, day, side="left") - 1
    D["d1"] = np.where(q >= 0, st[np.maximum(q, 0)], 0)
    return D


def session_ok(D, i):
    return D["hour"][i] not in (23, 0)


def engulf(D, i, d):
    o, c = D["o"], D["c"]
    if d == 1:
        return c[i] > o[i] and c[i - 1] < o[i - 1] and min(o[i], c[i]) <= min(o[i - 1], c[i - 1]) and max(o[i], c[i]) >= max(o[i - 1], c[i - 1])
    return c[i] < o[i] and c[i - 1] > o[i - 1] and min(o[i], c[i]) <= min(o[i - 1], c[i - 1]) and max(o[i], c[i]) >= max(o[i - 1], c[i - 1])


def pin(D, i, d):
    o, c, h, l = D["o"], D["c"], D["h"], D["l"]
    rng, body = h[i] - l[i], abs(c[i] - o[i])
    if rng <= 0:
        return False
    wick = (min(o[i], c[i]) - l[i]) if d == 1 else (h[i] - max(o[i], c[i]))
    return wick >= 2 * body and wick >= 0.5 * rng


def star(D, i):
    """+1 morning star, -1 evening star ending at bar i (G136 P3 definition), else 0."""
    o, c, a = D["o"], D["c"], D["atr"]
    b1, b2, b3 = c[i - 2] - o[i - 2], c[i - 1] - o[i - 1], c[i] - o[i]
    mid1 = 0.5 * (o[i - 2] + c[i - 2])
    if abs(b2) > 0.3 * a[i] or abs(b1) < 0.6 * a[i] or abs(b3) < 0.5 * a[i]:
        return 0
    if b1 < 0 < b3 and c[i] > mid1:
        return 1
    if b3 < 0 < b1 and c[i] < mid1:
        return -1
    return 0


def trigger(D, i, d):
    return engulf(D, i, d) or pin(D, i, d) or star(D, i) == d


def confirmed(piv, i, back):
    """Pivot bars k known at bar i (k + 3 <= i - 1, as G137) within the last `back` bars."""
    lo = np.searchsorted(piv, i - back, side="left")
    hi = np.searchsorted(piv, i - 1 - gp.SWING, side="right")
    return piv[lo:hi]


# ------------------------------------------------------------------------------------------------ A1
def a1(D):
    c, o, h, l, a, adx, v = D["c"], D["o"], D["h"], D["l"], D["atr"], D["adx"], D["v"]
    e20, e50, e200, rsi, va = D["e20"], D["e50"], D["e200"], D["rsi"], D["vavg"]
    out = []
    for i in range(300, len(c) - 1):
        if not session_ok(D, i) or adx[i] < 25 or not (v[i] >= 1.1 * va[i]):
            continue
        for d in (1, -1):
            if d == 1:
                ok = (e20[i] > e50[i] > e200[i] and c[i] > e50[i] and e200[i] > e200[i - 10]
                      and min(l[i], l[i - 1]) <= e20[i] + 0.1 * a[i] and c[i] > o[i] and c[i] > e20[i] and 45 <= rsi[i] <= 60)
                sl = l[i - 2:i + 1].min() - 0.1 * a[i]
            else:
                ok = (e20[i] < e50[i] < e200[i] and c[i] < e50[i] and e200[i] < e200[i - 10]
                      and max(h[i], h[i - 1]) >= e20[i] - 0.1 * a[i] and c[i] < o[i] and c[i] < e20[i] and 40 <= rsi[i] <= 55)
                sl = h[i - 2:i + 1].max() + 0.1 * a[i]
            if ok and trigger(D, i, d):
                out.append(gp.market(D, i, d, sl, ("R", 2.0), 48, 0.5, 3.0))
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ A2
def a2(D):
    c, o, h, l, a, v = D["c"], D["o"], D["h"], D["l"], D["atr"], D["v"]
    e200, rsi, va = D["e200"], D["rsi"], D["vavg"]
    out, cool = [], -1
    for i in range(300, len(c) - 1):
        if i <= cool or not session_ok(D, i) or not (v[i] >= 1.2 * va[i]):
            continue
        RH, RL = h[i - 40:i].max(), l[i - 40:i].min()
        A = a[i]
        if not (2 * A <= RH - RL <= 6 * A):
            continue
        for d in (1, -1):
            if d == 1:
                if not (c[i] > RH and c[i] > o[i] and 50 <= rsi[i] <= 70 and e200[i] - e200[i - 40] <= 0.5 * A):
                    continue
                run, js = l[i - 40:i - 30].min(), None
                for j in range(i - 30, i):
                    if l[j] < run and c[j] > run and v[j] <= 1.5 * va[j]:
                        js = j
                    run = min(run, l[j])
                if js is None:
                    continue
                sl = l[js] - 0.1 * A
            else:
                if not (c[i] < RL and c[i] < o[i] and 30 <= rsi[i] <= 50 and e200[i] - e200[i - 40] >= -0.5 * A):
                    continue
                run, js = h[i - 40:i - 30].max(), None
                for j in range(i - 30, i):
                    if h[j] > run and c[j] < run and v[j] <= 1.5 * va[j]:
                        js = j
                    run = max(run, h[j])
                if js is None:
                    continue
                sl = h[js] + 0.1 * A
            t = gp.market(D, i, d, sl, ("R", 2.0), 96, 0.5, 4.0)
            out.append(t)
            cool = i + 10
            break
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ A3
def a3(D):
    c, h, l, a, adx, v = D["c"], D["h"], D["l"], D["atr"], D["adx"], D["v"]
    e50, rsi, va = D["e50"], D["rsi"], D["vavg"]
    out = []
    for i in range(300, len(c) - 1):
        d = star(D, i)
        if not d or not session_ok(D, i) or not (v[i] >= va[i]):
            continue
        if not (adx[i - 3] < 25 or adx[i - 3] < adx[i - 8]):
            continue
        A = a[i]
        if d == 1:
            piv = confirmed(D["pl"], i, 60)
            piv = piv[piv <= i - 4]
            near = abs(l[i - 1] - e50[i - 1]) <= 0.5 * A or bool(len(piv) and np.min(np.abs(l[piv] - l[i - 1])) <= 0.5 * A)
            ok = near and 35 <= rsi[i] <= 55 and rsi[i] > rsi[i - 2]
            sl = l[i - 1] - 0.1 * A
        else:
            piv = confirmed(D["ph"], i, 60)
            piv = piv[piv <= i - 4]
            near = abs(h[i - 1] - e50[i - 1]) <= 0.5 * A or bool(len(piv) and np.min(np.abs(h[piv] - h[i - 1])) <= 0.5 * A)
            ok = near and 45 <= rsi[i] <= 65 and rsi[i] < rsi[i - 2]
            sl = h[i - 1] + 0.1 * A
        if ok:
            out.append(gp.market(D, i, d, sl, ("R", 2.0), 48, 0.5, 3.0))
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ A4a
def a4a(D):
    c, o, h, l, a, v = D["c"], D["o"], D["h"], D["l"], D["atr"], D["v"]
    rsi, va = D["rsi"], D["vavg"]
    out, cool = [], -1
    for i in range(300, len(c) - 1):
        if i <= cool or not session_ok(D, i) or not (v[i] >= 1.2 * va[i]):
            continue
        H = confirmed(D["ph"], i, 60)
        L = confirmed(D["pl"], i, 60)
        if len(H) < 2 or len(L) < 2:
            continue
        su, iu = np.polyfit(H, h[H], 1)
        sl_, il = np.polyfit(L, l[L], 1)
        A = a[i]
        up, dn = su * i + iu, sl_ * i + il
        w_now, w_start = up - dn, (su - sl_) * (i - 60) + (iu - il)
        if w_now < A or w_start <= 0 or w_now > 0.7 * w_start:
            continue
        d = 0
        if su > 0 and sl_ > 0 and su < sl_ and c[i] < dn - 0.1 * A and c[i] < o[i]:
            k1, k2 = H[-2], H[-1]
            if h[k2] > h[k1] and rsi[k2] < rsi[k1]:
                d, sl = -1, h[i - 9:i + 1].max() + 0.1 * A
        elif su < 0 and sl_ < 0 and sl_ > su and c[i] > up + 0.1 * A and c[i] > o[i]:
            k1, k2 = L[-2], L[-1]
            if l[k2] < l[k1] and rsi[k2] > rsi[k1]:
                d, sl = 1, l[i - 9:i + 1].min() - 0.1 * A
        if d:
            out.append(gp.market(D, i, d, sl, ("R", 2.0), 60, 0.5, 4.0))
            cool = i + 10
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ A4b
def a4b(D):
    c, h, l, a, v = D["c"], D["h"], D["l"], D["atr"], D["v"]
    e20, e50, e200, va = D["e20"], D["e50"], D["e200"], D["vavg"]
    R = gp.regress(c, 60)
    out, cool = [], -1
    for i in range(300, len(c) - 1):
        if i <= cool or not session_ok(D, i) or not (R["r2"][i] >= 0.6) or not (v[i] >= 1.1 * va[i]):
            continue
        A = a[i]
        if R["slope"][i] >= 0.02 * A and e50[i] > e200[i] and c[i] > e200[i]:
            band = R["proj"][i] - 2 * R["sig"][i]
            if l[i] <= band and c[i] > band and c[i] > e20[i]:
                out.append(gp.market(D, i, 1, l[i] - 0.1 * A, ("R", 2.0), 60, 0.5, 3.0)); cool = i + 10
        elif R["slope"][i] <= -0.02 * A and e50[i] < e200[i] and c[i] < e200[i]:
            band = R["proj"][i] + 2 * R["sig"][i]
            if h[i] >= band and c[i] < band and c[i] < e20[i]:
                out.append(gp.market(D, i, -1, h[i] + 0.1 * A, ("R", 2.0), 60, 0.5, 3.0)); cool = i + 10
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ A5 score
def score(D, i, d, with_pattern=True, with_risk=True):
    """The adviser's additive score for direction d at bar i (bars <= i only)."""
    c, h, l, a, adx, v = D["c"], D["h"], D["l"], D["atr"], D["adx"], D["v"]
    e20, e50, e200, rsi, va = D["e20"], D["e50"], D["e200"], D["rsi"], D["vavg"]
    A = a[i]
    s = 0
    if d == 1:
        s += 15 * (e20[i] > e50[i] > e200[i]) + 5 * (c[i] > e20[i] and c[i] > e50[i]) + 5 * (e200[i] > e200[i - 10])
        piv = confirmed(D["pl"], i, 60)
        near = min(l[i], l[i - 1]) <= e20[i] + 0.5 * A or bool(len(piv) and abs(l[i] - l[piv[-1]]) <= 0.5 * A)
        Lp, Hp = confirmed(D["pl"], i, 200), confirmed(D["ph"], i, 200)
        hhhl = len(Lp) >= 2 and len(Hp) >= 2 and l[Lp[-1]] > l[Lp[-2]] and h[Hp[-1]] > h[Hp[-2]]
        mom = 5 * (45 <= rsi[i] <= 60)
        dist = c[i] - (l[i - 2:i + 1].min() - 0.1 * A)
    else:
        s += 15 * (e20[i] < e50[i] < e200[i]) + 5 * (c[i] < e20[i] and c[i] < e50[i]) + 5 * (e200[i] < e200[i - 10])
        piv = confirmed(D["ph"], i, 60)
        near = max(h[i], h[i - 1]) >= e20[i] - 0.5 * A or bool(len(piv) and abs(h[i] - h[piv[-1]]) <= 0.5 * A)
        Lp, Hp = confirmed(D["pl"], i, 200), confirmed(D["ph"], i, 200)
        hhhl = len(Lp) >= 2 and len(Hp) >= 2 and l[Lp[-1]] < l[Lp[-2]] and h[Hp[-1]] < h[Hp[-2]]
        mom = 5 * (40 <= rsi[i] <= 55)
        dist = (h[i - 2:i + 1].max() + 0.1 * A) - c[i]
    s += 10 * near + 10 * hhhl
    if with_pattern:
        s += 20 * trigger(D, i, d)
    s += 10 * (v[i] >= 1.1 * va[i]) + 5 * (v[i] >= 1.5 * va[i])
    s += mom + 5 * (adx[i] >= 25)
    if with_risk:
        s += 10 * (0.5 * A <= dist <= 3 * A)
    return int(s)


def a5(D, lo=70, hi=101):
    c, h, l, a = D["c"], D["h"], D["l"], D["atr"]
    out = []
    prev = {1: 0, -1: 0}
    for i in range(300, len(c) - 1):
        for d in (1, -1):
            s = score(D, i, d)
            if lo <= s < hi and not (lo <= prev[d] < hi) and session_ok(D, i):
                sl = l[i - 2:i + 1].min() - 0.1 * a[i] if d == 1 else h[i - 2:i + 1].max() + 0.1 * a[i]
                t = gp.market(D, i, d, sl, ("R", 2.0), 48, 0.5, 3.0)
                if t:
                    t["score"] = s
                out.append(t)
            prev[d] = s
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ C
def csq(D):
    c, o, h, l, a = D["c"], D["o"], D["h"], D["l"], D["atr"]
    e200, bw, sma, d1 = D["e200"], D["bw"], D["sma20"], D["d1"]
    n = len(c)
    W = np.lib.stride_tricks.sliding_window_view(bw, 120)        # row r = bw[r .. r+119]
    rank = np.full(n, np.nan)
    rank[119:] = (W <= W[:, -1:]).mean(1)                        # rank of bw[k] among bw[k-119 .. k]
    out, cool = [], -1
    for i in range(300, n - 1):
        if i <= cool or not session_ok(D, i) or not (rank[i - 1] <= 0.2):
            continue
        A = a[i]
        if c[i] > h[i - 20:i].max() and c[i] > o[i] and c[i] > e200[i] and d1[i] == 1:
            out.append(gp.market(D, i, 1, sma[i] - 0.1 * A, ("R", 3.0), 96, 0.5, 3.0)); cool = i + 10
        elif c[i] < l[i - 20:i].min() and c[i] < o[i] and c[i] < e200[i] and d1[i] == -1:
            out.append(gp.market(D, i, -1, sma[i] + 0.1 * A, ("R", 3.0), 96, 0.5, 3.0)); cool = i + 10
    return gp.one_at_a_time(out)


# ------------------------------------------------------------------------------------------------ run
def verdict(rows, pval, tf):
    per = {p: [t["rh"] for t in rows if t["p"] == p] for p in DECIDE}
    tv = [t["rh15"] for t in rows if t["p"] in ("train", "validate")]
    ok = (all(len(x) >= MIN_N[tf] and np.mean(x) > 0 for x in per.values())
          and pval is not None and pval <= PVAL and tv and np.mean(tv) > 0)
    return "ĐẠT" if ok else "KHÔNG ĐẠT"


def main():
    root = Path(sys.argv[1]).resolve()
    random.seed(139)
    g.HERE = root.parent
    res, trades = {}, {}
    for tf in ("M30", "H1"):
        g.set_tf(tf)
        g.DATA = root / f"{tf.lower()}v"
        D = prepare(g.load("XAUUSD"))
        fams = {"A1 trend pullback": a1, "A2 Wyckoff spring-breakout": a2, "A3 star ở S/R": a3, "A4a wedge": a4a,
                "A4b kênh + xu hướng + volume": a4b, "A5 điểm ≥ 70": a5, "C squeeze breakout": csq}
        for name, fn in fams.items():
            rows = [t for t in fn(D) if t and t["p"]]
            pv = gp.p_random(D, rows, "X")
            r = {"per": {p: gp.cell(t["rh"] for t in rows if t["p"] == p) for p, _, _ in gp.PER},
                 "x1.5": {p: gp.cell(t["rh15"] for t in rows if t["p"] == p) for p in DECIDE},
                 "mua": {p: gp.cell(t["rh"] for t in rows if t["p"] == p and t["d"] == 1) for p in DECIDE},
                 "bán": {p: gp.cell(t["rh"] for t in rows if t["p"] == p and t["d"] == -1) for p in DECIDE},
                 "p": pv, "kết luận": verdict(rows, pv, tf)}
            res[f"{name} {tf}"] = r
            trades[f"{name} {tf}"] = [dict(d=t["d"], ein=t["utc"], eout=int(D["utc"][t["x"]]), r=t["rh"]) for t in rows]
            print(name, tf, r["per"], r["p"], r["kết luận"], flush=True)
        mid = [t for t in a5(D, 50, 70) if t and t["p"]]
        res[f"A5 điểm 50–69 {tf} (báo cáo)"] = {"per": {p: gp.cell(t["rh"] for t in mid if t["p"] == p) for p, _, _ in gp.PER}}
    # overlap with the S07 M30 legs (same direction, open at the entry) for C and any passing cell
    import g136_p1p4 as p1
    legs = p1.m30_book()
    for name, rows in trades.items():
        if name.startswith("C ") or res[name]["kết luận"] == "ĐẠT":
            ov = [any(x["d"] == t["d"] and x["ein"] <= t["ein"] < x["eout"] for x in legs) for t in rows]
            res[name]["trùng chân S07 M30 cùng chiều"] = round(float(np.mean(ov)), 3) if ov else None
            res[name]["R không trùng (train/validate/test)"] = {
                p: gp.cell(t["r"] for t, o_ in zip(rows, ov) if not o_ and gp.period(t["ein"]) == p) for p in DECIDE}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
