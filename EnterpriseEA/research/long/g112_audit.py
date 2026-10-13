"""G112 audit: recompute random chase signals with plain loops - signal condition (C1 / C2), latest confirmed M5 swing,
entry, stop, risk, MFE, +2R-before--1R, exit X1 (2R) and X3 (1.5 ATR trailing) without adds, and X1 with the rule
adds (add logic rewritten here; the stop-adding flags come from g112_chase.stop_adding, audited in G110).

  G108_SYMBOL=XAUUSD [G109_NOFILTER=1] python g112_audit.py [n=150]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import g108_data as g8
import g112_chase as gc


def main():
    n_s = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    df = g8.load_m5_raw()
    C = pd.read_pickle(gc.OUT)
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    day = t // 86400
    P = gc.per_bar(df)
    S = C.sample(min(n_s, len(C)), random_state=12)
    bad = 0
    for r in S.itertuples():
        j, s, e = int(r.j), int(r.d), int(r.e)
        probs = []
        a30 = r.a30
        if r.typ == "C1":
            mv = c[j] - c[j - 6]
            ok = abs(mv) >= a30 and np.sign(mv) == s and ((s == 1 and c[j] > max(h[j - 24:j])) or (s == -1 and c[j] < min(l[j - 24:j])))
            if not ok:
                probs.append("C1 condition")
        if r.typ == "C2":
            a = int(np.nonzero(day == day[j])[0][0])
            ok = (s == 1 and c[j] > max(h[a:j])) or (s == -1 and c[j] < min(l[a:j]))
            if not ok:
                probs.append("C2 condition")
        # latest confirmed swing on the stop side as of j (fractal 2/2, confirmed 2 bars later)
        sw = None
        for q in range(j - 2, 2, -1):
            if s == 1 and l[q] < l[q - 1] and l[q] < l[q - 2] and l[q] <= l[q + 1] and l[q] <= l[q + 2]:
                sw = l[q]; break
            if s == -1 and h[q] > h[q - 1] and h[q] > h[q - 2] and h[q] >= h[q + 1] and h[q] >= h[q + 2]:
                sw = h[q]; break
        entry = o[e] + (sp[e] if s == 1 else 0.0)
        stop = (sw - sp[j]) if s == 1 else (sw + sp[j])
        if s * (entry - stop) < 0.5 * a30:
            stop = entry - s * 0.5 * a30
        risk = s * (entry - stop)
        if not (np.isclose(entry, r.entry) and np.isclose(stop, r.stop)):
            probs.append(("entry/stop", entry, r.entry, stop, r.stop))
        end = min(len(t), e + 48)

        def exit_loop(trail, adds_on):
            units = [entry]; st = stop; best = entry; ext = entry; pulled = False; last = 0; adds = 0
            sa = gc.stop_adding(s, np.arange(e, end), r.t_ahead if r.t_ahead is not None and np.isfinite(r.t_ahead) else None, a30, P)
            open_ = adds_on
            tgt = entry + s * 2 * risk if not trail else None
            for k in range(end - e):
                q = e + k
                if (s == 1 and l[q] <= st) or (s == -1 and h[q] + sp[q] >= st):
                    return sum(s * (st - u) for u in units) / risk
                if tgt is not None and ((s == 1 and h[q] >= tgt) or (s == -1 and l[q] + sp[q] <= tgt)):
                    return sum(s * (tgt - u) for u in units) / risk
                best = max(best, h[q]) if s == 1 else min(best, l[q] + sp[q])
                if trail:
                    st = max(st, best - 1.5 * a30) if s == 1 else min(st, best + 1.5 * a30)
                new = s * (c[q] - ext) > 0
                if new:
                    ext = c[q]
                elif s * (ext - c[q]) >= 0.3 * a30:
                    pulled = True
                if open_ and sa[k]:
                    open_ = False
                if open_ and adds < 2 and q + 1 < end and k - last >= 6 and s * (c[q] - units[0]) / risk >= 1 and pulled and new:
                    units.append(o[q + 1] + (sp[q + 1] if s == 1 else 0.0)); adds += 1; last = k; pulled = False
                    st = max(st, units[0]) if s == 1 else min(st, units[0])
                    if adds >= 2:
                        open_ = False
            q = end - 1
            px = c[q] if s == 1 else c[q] + sp[q]
            return sum(s * (px - u) for u in units) / risk

        for name, val in (("X1_none", exit_loop(False, False)), ("X3_none", exit_loop(True, False)), ("X1_rule", exit_loop(False, True))):
            if not np.isclose(val, getattr(r, name)):
                probs.append((name, val, getattr(r, name)))
        hit2 = 0
        for q in range(e, end):
            if (s == 1 and l[q] <= entry - risk) or (s == -1 and h[q] + sp[q] >= entry + risk):
                break
            if (s == 1 and h[q] >= entry + 2 * risk) or (s == -1 and l[q] + sp[q] <= entry - 2 * risk):
                hit2 = 1; break
        if hit2 != r.hit2:
            probs.append(("hit2", hit2, r.hit2))
        if probs:
            bad += 1
            print("  differs", pd.to_datetime(int(r.time), unit="s"), r.typ, probs[:3])
    print(f"{gc.gz.SYMBOL}{gc.gs.SUF} chase: {bad} mismatches of {len(S)}")


if __name__ == "__main__":
    main()
