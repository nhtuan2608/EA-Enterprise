"""G108 audit: recompute a random sample of plans from the raw M5 bars with plain loops (no g108_data helpers)
and compare with data/g108_decisions.pkl; plus data checks.

  python g108_audit.py [sample=400]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g

HERE = Path(__file__).resolve().parent


def slow_plan(df, i, d):
    t = df["time"].to_numpy(np.int64)
    o, h, l, c, sp = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "sp"))
    now = t[i] + 300                                           # close of bar i
    # latest M5 swing confirmed by bar i (fractal 2/2): scan back from i-2
    swing = None
    for j in range(i - 2, 1, -1):
        if d == 1 and l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
            swing = l[j]; break
        if d == -1 and h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
            swing = h[j]; break
    entry = o[i + 1] + (sp[i + 1] if d == 1 else 0.0)
    stop = swing - sp[i] if d == 1 else swing + sp[i]
    ext = h if d == 1 else l
    levels = []                                                # (level, end time of its formation)
    day = t // 86400
    # prior trading day
    prev_days = np.unique(day[day < day[i]])
    if len(prev_days):
        m = day == prev_days[-1]
        levels.append(((h[m].max() if d == 1 else l[m].min()), t[m].max() + 300))
    # sessions completed in the last 24 h (and known: ended at or before the close of bar i - 1)
    hour = (t % 86400) // 3600
    sess = np.where(hour < 10, 0, np.where(hour < 15, 1, 2))
    for dd in np.unique(day[(t >= now - 3 * 86400) & (t <= t[i])]):
        for s in (0, 1, 2):
            m = (day == dd) & (sess == s)
            if not m.any():
                continue
            last = np.nonzero(m)[0].max()
            if last + 1 <= i and t[last] + 300 >= now - 86400:
                levels.append(((h[m].max() if d == 1 else l[m].min()), t[last] + 300))
    # H1 swings (fractal 2/2 on H1 bars built from M5), confirmed before bar i, formed in the last 5 days
    hb = t // 3600
    ids = np.unique(hb[(t >= now - 7 * 86400) & (t <= t[i])])
    H = []
    for b in ids:
        m = np.nonzero(hb == b)[0]
        H.append((b, h[m].max(), l[m].min(), m.max()))
    for k in range(2, len(H) - 2):
        b, hh, ll, last = H[k]
        if H[k + 2][3] + 1 > i:
            continue
        x = [z[1] if d == 1 else z[2] for z in H[k - 2:k + 3]]
        ok = (x[2] > x[0] and x[2] > x[1] and x[2] >= x[3] and x[2] >= x[4]) if d == 1 else \
             (x[2] < x[0] and x[2] < x[1] and x[2] <= x[3] and x[2] <= x[4])
        if ok and t[last] + 300 >= now - 5 * 86400:
            levels.append((x[2], t[last] + 300))
    risk0 = d * (entry - stop)
    if g.LABEL in g.FIXED_RR:
        levels = []
    min_dist = 1.5 * risk0 if g.LABEL == "liq15" else 0.0
    best = entry + d * g.FIXED_RR[g.LABEL] * risk0 if g.LABEL in g.FIXED_RR else None
    for lev, end in levels:
        if d * (lev - entry) <= min_dist:
            continue
        after = (t + 300 > end) & (np.arange(len(t)) <= i)
        if after.any() and (ext[after].max() > lev if d == 1 else ext[after].min() < lev):
            continue                                           # taken since it formed
        if best is None or d * (lev - best) < 0:
            best = lev
    risk = d * (entry - stop)
    # label: bars i+1 .. i+288 (24 trading hours)
    end_i = i + 288
    R = None
    for b in range(i + 1, end_i + 1):
        stop_hit = l[b] <= stop if d == 1 else h[b] + sp[b] >= stop
        tgt_hit = h[b] >= best if d == 1 else l[b] + sp[b] <= best
        if stop_hit:
            R = -1.0; break
        if tgt_hit:
            R = d * (best - entry) / risk; break
    if R is None:
        px = c[end_i] if d == 1 else c[end_i] + sp[end_i]
        R = d * (px - entry) / risk
    return entry, stop, best, R


def audit_features(n_sample=200):
    """Recompute path / forming-M30 / prior-day / M30 EMA / time features with plain loops."""
    import g108_features as gf
    from g108_patterns import dedupe
    D = pd.read_pickle(g.OUT)
    D = dedupe(D[D["period"] != "test"]).reset_index(drop=True)
    df = g.load_m5()
    S = D.sample(n_sample, random_state=7).reset_index(drop=True)
    F = gf.features(df, S, gf.long_m30())
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    # own closed-M30 series, EMA and Wilder ATR with loops
    buckets, closes, highs, lows = [], [], [], []
    for k in range(len(t)):
        b = t[k] // 1800
        if not buckets or buckets[-1] != b:
            buckets.append(b); closes.append(c[k]); highs.append(h[k]); lows.append(l[k])
        else:
            closes[-1] = c[k]; highs[-1] = max(highs[-1], h[k]); lows[-1] = min(lows[-1], l[k])
    def ema_loop(x, p):
        e = [x[0]]
        for v in x[1:]:
            e.append(e[-1] + 2 / (p + 1) * (v - e[-1]))
        return e
    e21, e200 = ema_loop(closes, 21), ema_loop(closes, 200)
    atr = [highs[0] - lows[0]]
    for k in range(1, len(closes)):
        tr = max(highs[k], closes[k - 1]) - min(lows[k], closes[k - 1])
        atr.append(atr[-1] + (tr - atr[-1]) / 14)
    bad = 0
    for r, f in zip(S.itertuples(), F.itertuples()):
        i, d = int(r.i), int(r.d)
        k = max(j for j in range(len(buckets)) if (buckets[j] + 1) * 1800 <= t[i] + 300)
        a = atr[k]
        first = min(j for j in range(i, -1, -1) if t[j] // 1800 == t[i] // 1800 and (j == 0 or t[j - 1] // 1800 != t[i] // 1800))
        hi_so_far, lo_so_far = h[first:i + 1].max(), l[first:i + 1].min()
        day = t[i] // 86400
        prev = [j for j in range(i) if t[j] // 86400 < day]
        pday = t[prev[-1]] // 86400
        pm = [j for j in prev[-400:] if t[j] // 86400 == pday]
        exp = {"p1": d * (c[i] - c[i - 1]) / a, "p12": d * (c[i] - c[i - 12]) / a, "f_move": d * (c[i] - o[first]) / a,
               "f_room_up": ((hi_so_far - c[i]) if d == 1 else (c[i] - lo_so_far)) / a,
               "pdh": d * (c[i] - max(h[j] for j in pm)) / a, "pdl": d * (c[i] - min(l[j] for j in pm)) / a,
               "e21": d * (c[i] - e21[k]) / a, "e200": d * (c[i] - e200[k]) / a,
               "hour": (t[i] % 86400) // 3600, "dow": pd.Timestamp(int(t[i]), unit="s").dayofweek}
        for key, v in exp.items():
            if abs(getattr(f, key) - v) > 1e-6:
                bad += 1
                print("  feature mismatch", pd.to_datetime(r.time, unit="s"), d, key, getattr(f, key), v)
                break
    print(f"features: {bad} mismatches of {n_sample}; NaN share in all features: {float(F.isna().mean().mean()):.4f}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "features":
        audit_features(int(sys.argv[2]) if len(sys.argv) > 2 else 200)
        return
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    D = pd.read_pickle(g.OUT)
    df = g.load_m5()
    t = df["time"].to_numpy(np.int64)
    print("== data checks")
    print("rows", len(D), "| periods", D["period"].value_counts().to_dict(), "| by dir", D["d"].value_counts().to_dict())
    print("NaN in label/levels:", int(D[["entry", "stop", "target", "rr", "R"]].isna().sum().sum()))
    print("time strictly increasing within dir:", bool(all((D[D.d == d]["time"].diff().dropna() > 0).all() for d in (1, -1))))
    print("decision times on the M5 grid:", bool((D["time"] % 300 == 0).all()), "| bar index matches time:",
          bool((t[D["i"].to_numpy()] == D["time"].to_numpy()).all()))
    print("rr range:", round(float(D["rr"].min()), 3), round(float(D["rr"].max()), 3), "| label", g.LABEL, "| outcomes", D["outcome"].value_counts().to_dict())
    print("first decision", pd.to_datetime(D["time"].min(), unit="s"), "last", pd.to_datetime(D["time"].max(), unit="s"))
    print("== recompute", n_sample, "random plans with plain loops")
    S = D.sample(n_sample, random_state=108)
    bad = []
    for r in S.itertuples():
        e, s, tg, R = slow_plan(df, int(r.i), int(r.d))
        ok = abs(e - r.entry) < 1e-9 and abs(s - r.stop) < 1e-9 and tg is not None and abs(tg - r.target) < 1e-9 and abs(R - r.R) < 1e-9
        if not ok:
            bad.append((pd.to_datetime(r.time, unit="s"), r.d, (r.entry, e), (r.stop, s), (r.target, tg), (r.R, R)))
    print("mismatches:", len(bad), "of", n_sample)
    for b in bad[:15]:
        print("  ", b)


if __name__ == "__main__":
    main()
