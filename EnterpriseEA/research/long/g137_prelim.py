"""G137 PRELIMINARY: head-and-shoulders (G1), triangles (G2), harmonic Gartley / Bat (G3), Bollinger z-score in range (G4),
parallel-channel pullback (G5), and G136 P5 (pullback-channel break as an S07A add), on the VPS Lirunex bars.
Plan: docs/superpowers/plans/2026-10-21-g137-pattern-families.md. Not the plan's data source; not for decisions.

Usage: g137_prelim.py <a "data" dir with m30v/ m15v/ h1v/ h4v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

PER = [("sớm", g.ts(2019, 6, 1), g.ts(2021, 7, 1)), ("train", g.ts(2021, 7, 1), g.ts(2024, 1, 1)),
       ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)), ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1)),
       ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
DECIDE = ("train", "validate", "test")
MIN_N = {"H1": 30, "M30": 40}
RUNS = 200
SWING = 3


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def cell(rs):
    s = g.stats(list(rs))
    return f"{s['n']} / {s['exp']:+.3f} / {s['total']:+.1f}" if s["n"] else "—"


# ------------------------------------------------------------------------------------------- trade engine
def run_trade(D, e, d, entry, sl, tp, hold, zexit=None):
    """Position opened at bar e at `entry` (ask for buys). SL first when both touch. zexit(t) -> True closes at the close."""
    o, hi, lo, c, sp = D["o"], D["h"], D["l"], D["c"], D["sp"]
    n = len(c)
    dist = d * (entry - sl)
    if dist <= 0 or e >= n:
        return None
    end = min(n - 1, e + hold - 1)
    x, px = end, (c[end] if d == 1 else c[end] + sp[end])
    for t in range(e, end + 1):
        if d == 1:
            if lo[t] <= sl:
                x, px = t, min(sl, o[t]) if t > e else sl; break
            if hi[t] >= tp:
                x, px = t, max(tp, o[t]) if t > e else tp; break
        else:
            if hi[t] + sp[t] >= sl:
                x, px = t, max(sl, o[t] + sp[t]) if t > e else sl; break
            if lo[t] + sp[t] <= tp:
                x, px = t, min(tp, o[t] + sp[t]) if t > e else tp; break
        if zexit is not None and zexit(t):
            x, px = t, (c[t] if d == 1 else c[t] + sp[t]); break
    r = d * (px - entry) / dist - D["comm"] / dist
    t = {"d": d, "e": e, "x": x, "r": float(r), "risk": float(dist), "srv_in": int(D["t"][e]), "srv_out": int(D["t"][x]),
         "sp_in": float(D["sp"][e]), "sp_out": float(D["sp"][x]), "utc": int(D["utc"][e])}
    t["rh"] = h.harsh(t, D)
    t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
    t["p"] = period(t["utc"])
    return t


def market(D, i, d, sl, tp, hold, lo_atr, hi_atr, zexit=None):
    """Signal at the close of bar i, entry at the next open; None when the stop is outside lo..hi ATR."""
    e = i + 1
    if e >= len(D["c"]):
        return None
    entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
    dist = d * (entry - sl)
    a = D["atr"][i]
    if not (lo_atr * a <= dist <= hi_atr * a):
        return None
    if tp is None:
        return None
    if isinstance(tp, tuple):                 # ("R", k)
        tp = entry + d * tp[1] * dist
    if d * (tp - entry) <= 0:
        return None
    t = run_trade(D, e, d, entry, sl, tp, hold, zexit)
    if t:
        t.update(sig=i, k_atr=dist / a, tp_r=d * (tp - entry) / dist, hold=hold)
    return t


def one_at_a_time(cands):
    """cands sorted by signal bar; drops a trade while the previous one of the family is open."""
    out, free = [], -1
    for t in sorted((t for t in cands if t), key=lambda t: t["e"]):
        if t["e"] > free:
            out.append(t); free = t["x"]
    return out


def pivots(D):
    hi, lo = D["h"], D["l"]
    n = len(hi)
    ph = [k for k in range(SWING, n - SWING) if hi[k] == hi[k - SWING:k + SWING + 1].max()]
    pl = [k for k in range(SWING, n - SWING) if lo[k] == lo[k - SWING:k + SWING + 1].min()]
    return ph, pl


# ------------------------------------------------------------------------------------------------- G1
def g1_hs(D):
    hi, lo, c, a, e55 = D["h"], D["l"], D["c"], D["atr"], D["E"][55]
    ph, pl = pivots(D)
    out = []
    for d, lows, highs, ext, opp in ((1, pl, ph, lo, hi), (-1, ph, pl, hi, lo)):
        hs = np.array(highs)
        for q in range(len(lows) - 2):
            L1, L2, L3 = lows[q], lows[q + 1], lows[q + 2]
            if not (10 <= L3 - L1 <= 80) or L1 < 60:
                continue
            A = a[L3]
            if d == 1:
                ok = ext[L2] <= min(ext[L1], ext[L3]) - 0.5 * A
                trend = e55[L1] < e55[L1 - 48]
            else:
                ok = ext[L2] >= max(ext[L1], ext[L3]) + 0.5 * A
                trend = e55[L1] > e55[L1 - 48]
            if not ok or not trend or abs(ext[L1] - ext[L3]) > 1.0 * A:
                continue
            m1 = hs[(hs > L1) & (hs < L2)]
            m2 = hs[(hs > L2) & (hs < L3)]
            if not len(m1) or not len(m2):
                continue
            P1 = m1[np.argmax(d * opp[m1])]
            P2 = m2[np.argmax(d * opp[m2])]
            slope = (opp[P2] - opp[P1]) / (P2 - P1)
            neck = lambda t: opp[P1] + slope * (t - P1)
            for t in range(L3 + SWING, min(L3 + SWING + 20, len(c) - 1)):
                if d * (c[t] - ext[L3]) < 0:
                    break
                if d * (c[t] - neck(t)) > 0.1 * a[t]:
                    out.append(market(D, t, d, ext[L3] - d * 0.1 * a[t], ("R", 2.0), 120, 1.0, 4.0))
                    break
    return one_at_a_time(out)


# ------------------------------------------------------------------------------------------------- G2
def g2_triangle(D):
    hi, lo, c, a = D["h"], D["l"], D["c"], D["atr"]
    n = len(c)
    ph, pl = pivots(D)
    ph, pl = np.array(ph), np.array(pl)
    out, cool = [], -1
    for i in range(300, n - 1):
        if i <= cool:
            continue
        lo_k, hi_k = i - 39, i - 1 - SWING          # pivot k is known at k + 3 <= i - 1
        H = ph[(ph >= lo_k) & (ph <= hi_k)]
        L = pl[(pl >= lo_k) & (pl <= hi_k)]
        if len(H) < 2 or len(L) < 2:
            continue
        su, iu = np.polyfit(H, hi[H], 1)
        sl_, il = np.polyfit(L, lo[L], 1)
        A = a[i]
        if su > 0.01 * A or sl_ < -0.01 * A:
            continue
        up, dn = su * i + iu, sl_ * i + il
        w_now, w_start = up - dn, (su - sl_) * (i - 39) + (iu - il)
        if w_now < 1.0 * A or w_start <= 0 or w_now > 0.6 * w_start:
            continue
        d = 1 if c[i] > up + 0.1 * A else (-1 if c[i] < dn - 0.1 * A else 0)
        if d:
            t = market(D, i, d, 0.5 * (up + dn), ("R", 2.0), 120, 1.0, 4.0)
            if t:
                t["with200"] = (c[i] - D["E"][200][i]) * d > 0
            out.append(t)
            cool = i + 10
    return one_at_a_time(out)


# ------------------------------------------------------------------------------------------------- G3
def zigzag(D, k=2.0):
    hi, lo, a = D["h"], D["l"], D["atr"]
    piv, d, ext = [], 0, 0
    for t in range(300, len(hi)):
        if d == 0:
            d, ext = 1, t
            continue
        if d == 1:
            if hi[t] >= hi[ext]:
                ext = t
            elif hi[ext] - lo[t] >= k * a[ext]:
                piv.append((ext, hi[ext], 1, t)); d, ext = -1, t
        else:
            if lo[t] <= lo[ext]:
                ext = t
            elif hi[t] - lo[ext] >= k * a[ext]:
                piv.append((ext, lo[ext], -1, t)); d, ext = 1, t
    return piv


def g3_harmonic(D):
    hi, lo, c, a, sp = D["h"], D["l"], D["c"], D["atr"], D["sp"]
    n = len(c)
    piv = zigzag(D)
    out = []
    for q in range(3, len(piv)):
        (xi, X, xt, _), (ai, A_, at, _), (bi, B, bt, _), (ci, C, ct, conf) = piv[q - 3:q + 1]
        d = 1 if xt == -1 else -1                      # X low -> bullish (buy at D)
        XA = d * (A_ - X)
        AB = d * (A_ - B)
        BC = d * (C - B)
        if XA <= 0 or AB <= 0 or BC <= 0:
            continue
        ab, bc = AB / XA, BC / AB
        for name, (ab0, ab1), dr, (cd0, cd1) in (("Gartley", (0.568, 0.668), 0.786, (1.27, 1.618)),
                                                ("Bat", (0.382, 0.50), 0.886, (1.618, 2.618))):
            if not (ab0 <= ab <= ab1 and 0.382 <= bc <= 0.886):
                continue
            Dp = A_ - d * dr * XA
            cd = d * (C - Dp) / BC
            if not (cd0 <= cd <= cd1):
                continue
            sl = X - d * 0.1 * a[ci] if name == "Gartley" else A_ - d * 1.13 * XA
            dist = d * (Dp - sl)
            if not (0.5 * a[ci] <= dist <= 4.0 * a[ci]):
                continue
            tp = Dp + 0.382 * (A_ - Dp)
            for t in range(conf + 1, min(conf + 61, n - 1)):
                if (d == 1 and hi[t] > C) or (d == -1 and lo[t] < C):
                    break                              # beyond C against the pattern before D
                if (d == 1 and lo[t] + sp[t] <= Dp) or (d == -1 and hi[t] >= Dp):
                    entry = min(Dp, D["o"][t] + sp[t]) if d == 1 else max(Dp, D["o"][t])
                    tr = run_trade(D, t, d, entry, sl, tp, 120)
                    if tr:
                        tr.update(sig=t, k_atr=d * (entry - sl) / a[t], tp_r=d * (tp - entry) / (d * (entry - sl)),
                                  hold=120, name=name)
                    out.append(tr)
                    break
    return one_at_a_time(out)


# ------------------------------------------------------------------------------------------------- G4
def g4_bollinger(D):
    c, hi, lo, a, adx, e200 = D["c"], D["h"], D["l"], D["atr"], D["adx"], D["E"][200]
    n = len(c)
    W = np.lib.stride_tricks.sliding_window_view(c, 20)
    sma = np.full(n, np.nan); sd = np.full(n, np.nan)
    sma[19:] = W.mean(1); sd[19:] = W.std(1)
    z = (c - sma) / np.where(sd > 0, sd, np.nan)
    side = np.zeros(n, bool)
    side[48:] = (adx[48:] < 20) & (np.abs(e200[48:] - e200[:-48]) < 0.5 * a[48:])
    D["z"] = z
    out = []
    for i in range(300, n - 1):
        if not (side[i] and side[i - 1]):
            continue
        for d in (1, -1):
            if d * z[i - 1] <= -2 and d * z[i] > -2:
                sl = (min(lo[i - 1], lo[i]) if d == 1 else max(hi[i - 1], hi[i])) - d * 0.1 * a[i]
                out.append(market(D, i, d, sl, sma[i], 24, 0.5, 3.0, zexit=(lambda t, d=d: d * z[t] >= 0)))
    return one_at_a_time(out)


# ------------------------------------------------------------------------------------------------- G5
def regress(c, w):
    n = len(c)
    x = np.arange(w, dtype=float)
    W = np.lib.stride_tricks.sliding_window_view(c, w)            # row j = c[j .. j+w-1]
    xm = x.mean()
    sxx = ((x - xm) ** 2).sum()
    ym = W.mean(1)
    slope = ((W - ym[:, None]) * (x - xm)).sum(1) / sxx
    icpt = ym - slope * xm
    fit = icpt[:, None] + slope[:, None] * x
    res = W - fit
    sst = ((W - ym[:, None]) ** 2).sum(1)
    r2 = 1 - (res ** 2).sum(1) / np.where(sst > 0, sst, np.nan)
    sig = res.std(1)
    out = {k: np.full(n, np.nan) for k in ("slope", "proj", "r2", "sig")}
    # window ending at bar i-1 (rows j = i - w), projected to x = w (bar i)
    idx = np.arange(w, n)
    out["slope"][idx] = slope[idx - w]
    out["proj"][idx] = icpt[idx - w] + slope[idx - w] * w
    out["r2"][idx] = r2[idx - w]
    out["sig"][idx] = sig[idx - w]
    return out


def g5_channel(D):
    c, hi, lo, a = D["c"], D["h"], D["l"], D["atr"]
    e20 = g.ema(c, 20)
    R = regress(c, 60)
    out, cool = [], -1
    for i in range(300, len(c) - 1):
        if i <= cool or not (R["r2"][i] >= 0.6):
            continue
        A = a[i]
        if R["slope"][i] >= 0.02 * A:
            band = R["proj"][i] - 2 * R["sig"][i]
            if lo[i] <= band and c[i] > band and c[i] > e20[i]:
                out.append(market(D, i, 1, lo[i] - 0.1 * A, ("R", 2.0), 60, 0.5, 3.0)); cool = i + 10
        elif R["slope"][i] <= -0.02 * A:
            band = R["proj"][i] + 2 * R["sig"][i]
            if hi[i] >= band and c[i] < band and c[i] < e20[i]:
                out.append(market(D, i, -1, hi[i] + 0.1 * A, ("R", 2.0), 60, 0.5, 3.0)); cool = i + 10
    return one_at_a_time(out)


# --------------------------------------------------------------------------------------- random control
def p_random(D, rows, family):
    rows = [t for t in rows if t["p"] in ("train", "validate")]
    if not rows:
        return None
    actual = float(np.mean([t["rh"] for t in rows]))
    n = len(D["c"])
    pool = {}
    for j in range(300, n - 2):
        p = period(int(D["utc"][j]))
        if p in ("train", "validate"):
            pool.setdefault((p, int(D["t"][j] % 86400 // 3600)), []).append(j)
    z = D.get("z")
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in rows:
            cands = pool.get((t["p"], int(D["t"][t["sig"]] % 86400 // 3600)), [])
            for _ in range(30):
                j = random.choice(cands)
                d = t["d"]
                e = j + 1
                entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
                dist = t["k_atr"] * D["atr"][j]
                sl = entry - d * dist
                if family == "G4":
                    tp = float(np.mean(D["c"][j - 19:j + 1]))
                    if d * (tp - entry) <= 0:
                        continue
                    r = run_trade(D, e, d, entry, sl, tp, 24, lambda x, d=d: d * z[x] >= 0)
                else:
                    r = run_trade(D, e, d, entry, sl, entry + d * t["tp_r"] * dist, t["hold"])
                if r:
                    u.append(r["rh"]); break
        hits += float(np.mean(u)) >= actual
    return (hits + 1) / (RUNS + 1)


def verdict(rows, pval, tf):
    per = {p: [t["rh"] for t in rows if t["p"] == p] for p in DECIDE}
    tv = [t["rh15"] for t in rows if t["p"] in ("train", "validate")]
    ok = (all(len(v) >= MIN_N[tf] and np.mean(v) > 0 for v in per.values())
          and pval is not None and pval <= 0.005 and np.mean(tv) > 0)
    return "ĐẠT (sơ bộ)" if ok else "KHÔNG ĐẠT (sơ bộ)"


def families(root):
    res = {}
    for tf in ("H1", "M30"):
        g.set_tf(tf)
        g.DATA = root / f"{tf.lower()}v"
        D = g.load("XAUUSD")
        fams = {"G1 vai-đầu-vai": ("G1", g1_hs), "G2 tam giác": ("G2", g2_triangle), "G4 Bollinger sideway": ("G4", g4_bollinger),
                "G5 kênh song song": ("G5", g5_channel)}
        if tf == "H1":
            fams["G3 harmonic"] = ("G3", g3_harmonic)
        for name, (code, fn) in fams.items():
            rows = [t for t in fn(D) if t and t["p"]]
            pv = p_random(D, rows, code)
            r = {"per": {p: cell(t["rh"] for t in rows if t["p"] == p) for p, _, _ in PER},
                 "x1.5": {p: cell(t["rh15"] for t in rows if t["p"] == p) for p in DECIDE},
                 "mua": {p: cell(t["rh"] for t in rows if t["p"] == p and t["d"] == 1) for p in DECIDE},
                 "bán": {p: cell(t["rh"] for t in rows if t["p"] == p and t["d"] == -1) for p in DECIDE},
                 "p": pv, "kết luận": verdict(rows, pv, tf)}
            if code == "G2":
                r["cùng EMA200"] = {p: cell(t["rh"] for t in rows if t["p"] == p and t.get("with200")) for p in DECIDE}
            if code == "G3":
                for nm in ("Gartley", "Bat"):
                    r[nm] = {p: cell(t["rh"] for t in rows if t["p"] == p and t.get("name") == nm) for p in DECIDE}
            res[f"{name} {tf}"] = r
            print(name, tf, r["per"], r["p"], flush=True)
    return res


# ------------------------------------------------------------------------------------------------- P5
def p5(root):
    import g89_full_book as fb
    g.HERE = root.parent
    fb.SPLIT, fb.START = g.ts(2022, 9, 1), g.ts(2019, 6, 1)
    d = 1
    bases = []
    for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
        bases += fb.base_book(fb.e73.context(main, sub), d, t0, t1, early=True, re=True)
    clusters = [cl for cl in fb.attach_adds(bases, fb.add_pool(d)) if cl[0]["ein"] >= g.ts(2022, 9, 1)]
    g.set_tf("M15")
    D = g.load("XAUUSD")
    utc, hi, lo, c, a = D["utc"], D["h"], D["l"], D["c"], D["atr"]

    def channel_adds(b):
        s = int(np.searchsorted(utc, b["ein"]))
        x = int(np.searchsorted(utc, b["eout"]))
        entry, dist = b["entry"], b["risk"]
        out, t, reached, peak = [], s, False, s
        while t < min(x, len(c) - 2) and len(out) < 2:
            if not reached:
                reached = hi[t] >= entry + dist
                peak = t
                t += 1
                continue
            if hi[t] > hi[peak]:
                peak = t; t += 1; continue
            m = t - peak                                  # bars peak .. t-1
            if m >= 6:
                y = c[peak:t]
                xs = np.arange(m)
                sl_, ic = np.polyfit(xs, y, 1)
                fit = ic + sl_ * xs
                ss = ((y - y.mean()) ** 2).sum()
                r2 = 1 - ((y - fit) ** 2).sum() / ss if ss > 0 else 0
                depth = hi[peak] - lo[peak:t + 1].min()
                upper = ic + sl_ * m + (y - fit).std()
                if sl_ < 0 and r2 >= 0.6 and depth <= 0.618 * (hi[peak] - entry) and c[t] > upper:
                    stop = lo[peak:t + 1].min() - 0.1 * a[t]
                    e = t + 1
                    en = D["o"][e] + D["sp"][e]
                    if a[t] <= en - stop <= 4 * a[t]:
                        tr = run_trade(D, e, 1, en, stop, en + 8 * (en - stop), max(1, x - e + 1))
                        if tr:
                            tr["ein"] = int(utc[e]); out.append(tr)
                    peak = t + 1                          # a new channel starts after a break
            t += 1
        return out

    rows = {"A1": [], "C1": [], "C2": []}
    legs = {"A1": [], "C1": [], "C2": []}
    for cl in clusters:
        b = cl[0]
        wb = 1.0 if b.get("ord") else fb.W_UNORD
        a1 = [dict(ein=L["ein"], eout=L["eout"], r=L["rh"]) for L in cl[1:]]
        ch = [dict(ein=t["ein"], eout=int(utc[t["x"]]), r=t["rh"], r15=t["rh15"]) for t in channel_adds(b)]
        both, last = [], b["ein"]
        for L in sorted(a1 + ch, key=lambda z: z["ein"]):
            if len(both) < 2 and L["ein"] - last >= 3600:
                both.append(L); last = L["ein"]
        for k, adds in (("A1", a1), ("C1", ch), ("C2", both)):
            tot = wb * b["rh"] + fb.W_ADD * sum(L["r"] for L in adds)
            rows[k].append(dict(p=period(b["ein"]), tot=tot, nadd=len(adds)))
            legs[k] += [dict(t_in=b["ein"], t_out=b["eout"], r=b["rh"], risk=0.015 * wb)] + \
                       [dict(t_in=L["ein"], t_out=L["eout"], r=L["r"], risk=0.015 * fb.W_ADD) for L in adds]
    from g134_extensions import YEAR, sim
    out = {}
    for k in rows:
        dd = []
        a0 = g.ts(2022, 9, 1)
        while a0 + YEAR <= g.ts(2026, 7, 1) + 1:
            dd.append(sim(legs[k], a0, int(a0 + YEAR))[1]); a0 += 30 * 86400
        out[k] = {p: (f"{len([r for r in rows[k] if r['p'] == p])} gốc / {np.mean([r['tot'] for r in rows[k] if r['p'] == p]):+.3f}R"
                      f" / {sum(r['nadd'] for r in rows[k] if r['p'] == p)} bồi") if any(r["p"] == p for r in rows[k]) else "—"
                  for p in ("train", "validate", "test", "07/2026+")}
        out[k]["DD p90 1 năm (09/2022–06/2026)"] = round(float(np.percentile(dd, 90)), 4) if dd else None
    return out


def main():
    root = Path(sys.argv[1])
    random.seed(137)
    res = {"families": families(root), "P5": p5(root)}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
