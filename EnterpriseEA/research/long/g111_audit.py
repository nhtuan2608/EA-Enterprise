"""G111 audit: recompute random zone-test events (Fibonacci level price, test bar, entry, stop, trade T exit a,
6-bar relative volume) from the raw M5 bars with plain loops.

  G108_SYMBOL=XAUUSD python g111_audit.py [n=200]
"""
from __future__ import annotations

import sys
from statistics import median

import numpy as np
import pandas as pd

import g108_data as g8
import g111_levels as gl


def main():
    n_s = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    df = g8.load_m5_raw()
    T = pd.read_pickle(gl.OUT_T)
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float)
    day = t // 86400
    hour = (t % 86400) // 3600
    mod = t % 86400
    idx_by_min: dict[int, list[int]] = {}
    for i, m in enumerate(mod):
        idx_by_min.setdefault(int(m), []).append(i)
    pos = {i: k for lst in idx_by_min.values() for k, i in enumerate(lst)}

    def rv(i):
        lst = idx_by_min[int(mod[i])]; k = pos[i]
        prev = [tv[q] for q in lst[max(0, k - 20):k]]
        return tv[i] / median(prev) if len(prev) >= 10 else float("nan")

    S = T.sample(min(n_s, len(T)), random_state=9)
    bad = 0
    for r in S.itertuples():
        probs = []
        today = list(np.nonzero(day == r.day)[0])
        a, e_day = today[0], today[-1]
        prevd = max(d for d in set(day[:a].tolist()))
        P = list(np.nonzero(day == prevd)[0])
        # level price
        if r.fam.startswith(("P", "A", "D")) and r.fam not in ("ZONE", "ZFAKE"):
            if r.fam[0] == "P":
                lo, hi, up = min(l[i] for i in P), max(h[i] for i in P), c[P[-1]] >= o[P[0]]
            elif r.fam[0] == "A":
                A = [i for i in today if hour[i] < 10]
                lo, hi, up = min(l[i] for i in A), max(h[i] for i in A), c[A[-1]] >= o[a]
            else:
                B = [i for i in today if hour[i] < 15]
                lo, hi, up = min(l[i] for i in B), max(h[i] for i in B), c[B[-1]] >= o[a]
            px = hi - r.ratio * (hi - lo) if up else lo + r.ratio * (hi - lo)
            if not np.isclose(px, r.center):
                probs.append(("level", px, r.center))
        # test bar: the first reach of the near edge after the level is known (the stored k must be that bar)
        side, w, px = int(r.side), r.w, r.center
        near, far = px - side * w, px + side * w
        k = int(r.k)
        earlier = [q for q in range(int(r.fi), k) if ((h[q] >= near) if side == 1 else (l[q] + sp[q] <= near))]
        if earlier:
            probs.append(("not the first reach", earlier[0], k))
        if not ((h[k] >= near) if side == 1 else (l[k] + sp[k] <= near)) or side * (c[k] - far) > 0:
            probs.append(("test bar", k))
        # entry, stop, trade a
        d = -side
        entry = near
        stop = px + side * (w + gl.STOP_W * w) + side * sp[k - 1]
        if not (np.isclose(entry, r.entry) and np.isclose(stop, r.stop)):
            probs.append(("levels", entry, r.entry, stop, r.stop))
        risk = d * (entry - stop)
        target = entry + d * gl.RR * risk
        if (d == 1 and l[k] <= stop) or (d == -1 and h[k] + sp[k] >= stop):
            R = -1.0
        else:
            R = None
            for q in range(k + 1, min(len(t), k + 1 + 48)):
                if (d == 1 and l[q] <= stop) or (d == -1 and h[q] + sp[q] >= stop):
                    R = -1.0; break
                if (d == 1 and h[q] >= target) or (d == -1 and l[q] + sp[q] <= target):
                    R = gl.RR; break
            if R is None:
                q = min(len(t), k + 1 + 48) - 1
                R = d * ((c[q] if d == 1 else c[q] + sp[q]) - entry) / risk
        if not np.isclose(R, r.Ra):
            probs.append(("Ra", R, r.Ra))
        v6 = np.nanmean([rv(q) for q in range(k - 6, k)])
        if not np.isclose(v6, r.rv6, equal_nan=True):
            probs.append(("rv6", v6, r.rv6))
        if probs:
            bad += 1
            print("  differs", pd.to_datetime(int(r.time), unit="s"), r.fam, r.ratio, probs[:3])
    print(f"{gl.gz.SYMBOL} tests: {bad} mismatches of {len(S)}")


if __name__ == "__main__":
    main()
