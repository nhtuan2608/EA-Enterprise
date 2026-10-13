"""G110 audit: recompute random break events (relative volume, close-location delta, break bar, hold label,
follow and fade trades with exit a) from the raw M5 bars with plain loops.

  G108_SYMBOL=XAUUSD python g110_audit.py [n=200]
"""
from __future__ import annotations

import sys
from statistics import median

import numpy as np
import pandas as pd

import g108_data as g8
import g110_breaks as gb


def main():
    n_s = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    df = g8.load_m5_raw()
    E = pd.read_pickle(gb.OUT_E)
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float)
    mod = t % 86400
    by_minute: dict[int, list[int]] = {}
    for i, m in enumerate(mod):
        by_minute.setdefault(int(m), []).append(i)
    pos_in = {i: k for m, lst in by_minute.items() for k, i in enumerate(lst)}

    def rv(i):
        lst = by_minute[int(mod[i])]
        k = pos_in[i]
        prev = [tv[q] for q in lst[max(0, k - 20):k]]
        return tv[i] / median(prev) if len(prev) >= 10 else float("nan")

    def clv(i):
        r = h[i] - l[i]
        return ((c[i] - l[i]) - (h[i] - c[i])) / r if r > 0 else 0.0

    def sim_a(d, entry, stop, e):
        risk = d * (entry - stop)
        target = entry + d * gb.RR * risk
        for k in range(e, min(len(t), e + 48)):
            if (d == 1 and l[k] <= stop) or (d == -1 and h[k] + sp[k] >= stop):
                return d * (stop - entry) / risk
            if (d == 1 and h[k] >= target) or (d == -1 and l[k] + sp[k] <= target):
                return d * (target - entry) / risk
        k = min(len(t), e + 48) - 1
        return d * ((c[k] if d == 1 else c[k] + sp[k]) - entry) / risk

    S = E.sample(min(n_s, len(E)), random_state=4)
    bad = 0
    for r in S.itertuples():
        j, s, far = int(r.j), int(r.s), r.far
        e_day = int(np.nonzero(t // 86400 == r.day)[0][-1])
        problems = []
        # break bar
        jj = None
        for q in range(r.s0 + 1, e_day + 1):
            if s * (c[q] - far) > 0 and s * (c[q - 1] - far) > 0:
                jj = q; break
        if jj != j:
            problems.append(("j", jj, j))
        # relative volume and delta
        tvb = np.nanmean([rv(j - 1), rv(j)])
        if not (np.isclose(tvb, r.tv_break, equal_nan=True)):
            problems.append(("tv_break", tvb, r.tv_break))
        num = sum(clv(q) * rv(q) for q in range(j - 11, j + 1) if np.isfinite(rv(q)))
        den = sum(rv(q) for q in range(j - 11, j + 1) if np.isfinite(rv(q)))
        d12 = s * num / den if den > 0 else float("nan")
        if not np.isclose(d12, r.delta12, equal_nan=True):
            problems.append(("delta12", d12, r.delta12))
        # hold
        back = None
        for k in range(j + 1, min(e_day, j + 6) + 1):
            if s * (c[k] - far) <= 0:
                back = k; break
        if int(back is None) != r.hold:
            problems.append(("hold", back, r.hold))
        # follow
        if np.isfinite(getattr(r, "fo_Ra", np.nan)):
            fill = None
            for k in range(j + 1, min(e_day, j + 12) + 1):
                if (s == 1 and l[k] + sp[k] <= far) or (s == -1 and h[k] >= far):
                    fill = k; break
            stop = (r.center - r.w - sp[j]) if s == 1 else (r.center + r.w + sp[j])
            R = sim_a(s, far, stop, fill)
            if fill != r.fo_i or not np.isclose(R, r.fo_Ra):
                problems.append(("follow", fill, r.fo_i, R, r.fo_Ra))
        # fade
        if np.isfinite(getattr(r, "fa_Ra", np.nan)):
            e = back + 1
            ext = max(h[j - 1:back + 1]) if s == 1 else min(l[j - 1:back + 1])
            d = -s
            entry = o[e] + (sp[e] if d == 1 else 0.0)
            stop = ext - sp[back] if d == 1 else ext + sp[back]
            R = sim_a(d, entry, stop, e)
            if e != r.fa_i or not np.isclose(R, r.fa_Ra):
                problems.append(("fade", e, r.fa_i, R, r.fa_Ra))
        # price action, plain loops
        a30 = abs((c[j - 12] - c[j - 36]) / r.pole) if r.pole not in (0, 0.0) else None
        if a30:
            def ls(y):
                m = len(y); xs = list(range(m)); mx = sum(xs) / m; my = sum(y) / m
                return sum((x - mx) * (v - my) for x, v in zip(xs, y)) / sum((x - mx) ** 2 for x in xs)
            seg = range(j - 13, j - 1)
            rng_ = (max(h[q] for q in seg) - min(l[q] for q in seg)) / a30
            cons = s * ls([c[q] for q in seg]) / a30
            flag = int(r.pole >= 1.5 and rng_ <= 1.0 and cons <= 0)
            if flag != r.flag_pat or not np.isclose(cons, r.cons_slope):
                problems.append(("flag", flag, r.flag_pat, cons, r.cons_slope))
            wseg = range(j - 25, j - 1)
            sh_, sl_ = ls([h[q] for q in wseg]) / a30, ls([l[q] for q in wseg]) / a30
            conv = sl_ - sh_
            ok = conv > 0.25 * max(abs(sh_), abs(sl_))
            wt = 1 if (sh_ > 0 and sl_ > 0 and ok) else (-1 if (sh_ < 0 and sl_ < 0 and ok) else 0)
            if wt != r.wedge_type or -s * wt != r.wedge_with:
                problems.append(("wedge", wt, r.wedge_type))
            rngs = [h[q] - l[q] for q in range(j - 8, j - 1)]
            if int(rngs[-1] <= min(rngs)) != r.nr7:
                problems.append(("nr7",))
            best = None
            gaps = []
            for k in range(max(2, j - 288), j + 1):
                if l[k] > h[k - 2]:
                    gaps.append((k, h[k - 2], l[k]))
                if h[k] < l[k - 2]:
                    gaps.append((k, h[k], l[k - 2]))
            for k, lo, hi in gaps:
                if s == 1 and lo > c[j] and all(h[q] < lo for q in range(k + 1, j + 1)):
                    dd = (lo - c[j]) / a30
                elif s == -1 and hi < c[j] and all(l[q] > hi for q in range(k + 1, j + 1)):
                    dd = (c[j] - hi) / a30
                else:
                    continue
                best = dd if best is None else min(best, dd)
            if not np.isclose(best if best is not None else 9.0, r.void_ahead):
                problems.append(("void", best, r.void_ahead))
        if problems:
            bad += 1
            print("  differs", pd.to_datetime(int(r.time), unit="s"), r.type, problems[:3])
    print(f"{gb.gz.SYMBOL} events: {bad} mismatches of {len(S)} | NaN share tv_break {E['tv_break'].isna().mean():.3f}")


if __name__ == "__main__":
    main()
