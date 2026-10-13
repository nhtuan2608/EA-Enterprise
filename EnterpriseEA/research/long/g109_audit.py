"""G109 audit: recompute zone candidates of random days and the labels of random zones with plain loops
(no g109_zones helpers), and compare with data/g109_*_<SYMBOL>.pkl. EMA candidates are not recomputed here
(they come from the long higher-frame history; the M30 EMA path is audited in G108).

  G108_SYMBOL=XAUUSD python g109_audit.py [days=40] [zones=300]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import g108_data as g8
import g109_zones as gz


def hbars(t, h, l, sec, upto):
    """Buckets (start, high, low, last index) of bars with index < upto, by loops."""
    out = []
    for i in range(upto):
        b = t[i] // sec
        if out and out[-1][0] == b:
            out[-1][1] = max(out[-1][1], h[i]); out[-1][2] = min(out[-1][2], l[i]); out[-1][3] = i
        else:
            out.append([b, h[i], l[i], i])
    return out


def slow_candidates(df, day_id, symbol, p0, ad, a):
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    tv = df["tickvol"].to_numpy(float)
    day = t // 86400
    prev_day = max(d for d in set(day[:a].tolist()))
    P = [i for i in range(a) if day[i] == prev_day]
    PH, PL = max(h[i] for i in P), min(l[i] for i in P)
    out = {("PDH", PH), ("PDL", PL), ("PDM", (PH + PL) / 2), ("PDC", c[P[-1]])}
    s_tv = sum(tv[i] for i in P)
    if s_tv > 0:
        out.add(("VWAP", sum((h[i] + l[i] + c[i]) / 3 * tv[i] for i in P) / s_tv))
    wk = (day + 3) // 7
    W = [i for i in range(a) if wk[i] == wk[a] - 1]
    if W:
        WH, WL = max(h[i] for i in W), min(l[i] for i in W)
        after = range(W[-1] + 1, a)
        if all(h[i] <= WH for i in after):
            out.add(("PWH", WH))
        if all(l[i] >= WL for i in after):
            out.add(("PWL", WL))
    t0 = t[a]
    for sec, look, tag in ((3600, 5, "H1"), (14400, 10, "H4")):
        B = hbars(t, h, l, sec, a)
        for j in range(2, len(B) - 2):
            if t[B[j][3]] < t0 - look * 86400:
                continue
            hh = [B[j + m][1] for m in (-2, -1, 0, 1, 2)]
            ll = [B[j + m][2] for m in (-2, -1, 0, 1, 2)]
            after = range(B[j][3] + 1, a)
            if hh[2] > hh[0] and hh[2] > hh[1] and hh[2] >= hh[3] and hh[2] >= hh[4] and all(h[i] <= hh[2] for i in after):
                out.add((f"{tag}SH", hh[2]))
            if ll[2] < ll[0] and ll[2] < ll[1] and ll[2] <= ll[3] and ll[2] <= ll[4] and all(l[i] >= ll[2] for i in after):
                out.add((f"{tag}SL", ll[2]))
    B = hbars(t, h, l, 3600, a)
    for j in range(2, len(B)):
        if t[B[j][3]] < t0 - 5 * 86400:
            continue
        after = range(B[j][3] + 1, a)
        if B[j][2] > B[j - 2][1] and all(l[i] >= B[j][2] for i in after):
            out.add(("FVG", (B[j - 2][1] + B[j][2]) / 2))
        if B[j][1] < B[j - 2][2] and all(h[i] <= B[j][1] for i in after):
            out.add(("FVG", (B[j][1] + B[j - 2][2]) / 2))
    for st in gz.ROUND.get(symbol, gz.ROUND["XAUUSD"]):
        out.add((f"R{st:g}", np.floor(p0 / st) * st)); out.add((f"R{st:g}", np.ceil(p0 / st) * st))
    return {(k, round(v, 6)) for k, v in out if abs(v - p0) <= gz.NEAR_D1 * ad}


def slow_label(h, l, c, center, w, side):
    k = None
    for i in range(len(h)):
        if h[i] >= center - w and l[i] <= center + w:
            k = i; break
    if k is None:
        return False, -1, 0
    if side == 0:
        return True, k, 0
    near, far = center - side * w, center + side * w
    for j in range(k, min(len(c), k + gz.REACT_BARS)):
        if j >= k + 1 and side * (c[j] - far) > 0 and side * (c[j - 1] - far) > 0:
            return True, k, -1
        if (side == 1 and l[j] <= near - gz.BOUNCE_W * w) or (side == -1 and h[j] >= near + gz.BOUNCE_W * w):
            return True, k, 1
    return True, k, 0


def main():
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n_zones = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    df = g8.load_m5_raw()
    Z, C, D = pd.read_pickle(gz.OUT_Z), pd.read_pickle(gz.OUT_C), pd.read_pickle(gz.OUT_D)
    t = df["time"].to_numpy(np.int64)
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    print(gz.SYMBOL, "== data checks: days", len(D), "| zones", len(Z), "| NaN centre", int(Z["center"].isna().sum()),
          "| touched share real/fake", round(float(Z.loc[~Z["fake"] & Z["map"], "touched"].mean()), 3),
          round(float(Z.loc[Z["fake"], "touched"].mean()), 3))
    rng = np.random.default_rng(5)
    bad_c = 0
    for d in rng.choice(D["day"].to_numpy(), size=min(n_days, len(D)), replace=False):
        rec = D[D["day"] == d].iloc[0]
        a = int(np.nonzero(t // 86400 == d)[0][0])
        mine = slow_candidates(df, int(d), gz.SYMBOL, rec["p0"], rec["atr_d1"], a)
        theirs = {(k, round(v, 6)) for k, v in C.loc[(C["day"] == d) & ~C["kind"].str.startswith("EMA"), ["kind", "level"]].itertuples(index=False)}
        if mine != theirs:
            bad_c += 1
            print("  candidates differ", pd.to_datetime(int(d) * 86400, unit="s").date(), "only loops:", sorted(mine - theirs)[:4],
                  "only module:", sorted(theirs - mine)[:4])
    print(f"candidates: {bad_c} days differ of {min(n_days, len(D))}")
    bad_z = 0
    S = Z.sample(min(n_zones, len(Z)), random_state=11)
    for r in S.itertuples():
        s0 = int(r.from_i)
        e = int(np.nonzero(t // 86400 == r.day)[0][-1])
        got = slow_label(h[s0:e + 1], l[s0:e + 1], c[s0:e + 1], r.center, r.w, int(r.side))
        exp = (bool(r.touched), (int(r.touch_i) - s0) if r.touched else -1, int(r.reaction))
        if got != exp:
            bad_z += 1
            print("  label differs", pd.to_datetime(int(r.t0), unit="s").date(), r.kinds, got, exp)
    print(f"labels: {bad_z} mismatches of {len(S)}")


if __name__ == "__main__":
    main()
