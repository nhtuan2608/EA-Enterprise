"""G113 day-type audit: recompute the 10:00 features (Asia range / direction / efficiency, prior-day range and body,
weekday, prior type) and the day label of random days with plain loops.

  G108_SYMBOL=XAUUSD python g113_audit.py [n=40]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g113_daytype as gd


def main():
    n_s = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    df = g8.load_m5_raw()
    D = gd.day_table(df, gf.long_m30())
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    days = sorted(set((t // 86400).tolist()))
    day_of = t // 86400
    bad = 0
    S = D.sample(min(n_s, len(D)), random_state=8)
    for r in S.itertuples():
        today = np.nonzero(day_of == r.day)[0]
        k = days.index(r.day)
        prev = np.nonzero(day_of == days[k - 1])[0]
        asia = [i for i in today if (t[i] % 86400) // 3600 < 10]
        AH, AL = max(h[i] for i in asia), min(l[i] for i in asia)
        # Wilder ATR14 of the daily bars up to the prior day (loop)
        dh, dl, dc = [], [], []
        for d in days[:k]:
            m = np.nonzero(day_of == d)[0]
            dh.append(h[m].max()); dl.append(l[m].min()); dc.append(c[m[-1]])
        atr = dh[0] - dl[0]
        for q in range(1, len(dh)):
            tr = max(dh[q], dc[q - 1]) - min(dl[q], dc[q - 1])
            atr += (tr - atr) / 14
        exp = {"asia_rng": (AH - AL) / atr, "asia_dir": (c[asia[-1]] - o[today[0]]) / (AH - AL),
               "asia_eff": abs(c[asia[-1]] - o[today[0]]) / (AH - AL),
               "prev_rng": (h[prev].max() - l[prev].min()) / atr,
               "prev_body": abs(c[prev[-1]] - o[prev[0]]) / (h[prev].max() - l[prev].min()),
               "dow": pd.Timestamp(int(t[today[0]]), unit="s").dayofweek}
        body = abs(c[today[-1]] - o[today[0]]) / (h[today].max() - l[today].min())
        exp["body"] = body
        exp["type"] = 1 if body >= 0.6 else (-1 if body <= 0.3 else 0)
        pb = exp["prev_body"]
        exp["prev_type"] = 1 if pb >= 0.6 else (-1 if pb <= 0.3 else 0)
        probs = [(f, v, getattr(r, f)) for f, v in exp.items() if not np.isclose(v, getattr(r, f))]
        if probs:
            bad += 1
            print("  differs", pd.to_datetime(int(r.day) * 86400, unit="s").date(), probs[:3])
    print(f"{g8.SYMBOL} day types: {bad} mismatches of {len(S)}")


if __name__ == "__main__":
    main()
