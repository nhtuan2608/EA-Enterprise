"""G123: A1 turned around - follow the aggressive side at a 24-bar extreme (plan docs/superpowers/plans/2026-10-15-g123-a1-follow.md).

  python g123_a1_follow.py

F1: 24-bar high touched, activity >= 1.5x, d in the top tercile, close in the lower half -> BUY (mirror at lows -> SELL)
F2: same but close in the upper half -> BUY (mirror -> SELL)
Data, thresholds, trade handling and the random same-hour control come from G121. 2026 is opened only for cells
whose train and validate are both > 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g121_study as g

PER = dict(g.PER)


def signals(m, thr):
    h, l = m["high"].to_numpy(), m["low"].to_numpy()
    act, d, cpos = m["act"].to_numpy(), m["d"].to_numpy(), m["cpos"].to_numpy()
    hh, ll = m["hh24"].to_numpy(), m["ll24"].to_numpy()
    ok = np.isfinite(hh) & np.isfinite(act) & np.isfinite(cpos) & (act >= 1.5)
    top = ok & (h >= hh) & (d >= thr["d_hi"])
    bot = ok & (l <= ll) & (d <= thr["d_lo"])
    out = {"F1": np.zeros(len(m), int), "F2": np.zeros(len(m), int)}
    out["F1"][top & (cpos <= 0.5)] = 1
    out["F1"][bot & (cpos >= 0.5)] = -1
    out["F2"][top & (cpos > 0.5)] = 1
    out["F2"][bot & (cpos < 0.5)] = -1
    out["F1"][top & bot] = 0
    out["F2"][top & bot] = 0
    return out


def main():
    m = g.load()
    tr = g.in_period(m, "train")
    thr = {"d_hi": np.nanpercentile(m.d[tr], 66.7), "d_lo": np.nanpercentile(m.d[tr], 33.3)}
    print("thresholds (train):", {k: round(v, 3) for k, v in thr.items()}, flush=True)
    sig = signals(m, thr)
    rng = np.random.default_rng(123)
    rows, books = [], {}
    for name, s in sig.items():
        for ex in g.EXITS:
            row = dict(signal=name, exit=ex)
            for p in ("train", "validate"):
                mk = g.in_period(m, p)
                b = g.book_a(m, s, ex, mk)
                for k, v in g.summ(b).items():
                    row[f"{p[:3]}_{k}"] = v
                if p == "validate" and len(b) >= 20:
                    ctl = g.control_a(m, b, ex, mk, rng, reps=g.REPS)
                    row["val_ctl"], row["val_p"] = np.nanmedian(ctl), float(np.nanmean(ctl >= b["r"].mean()))
            if row["tra_R"] > 0 and row.get("val_R", -1) > 0:
                mk = g.in_period(m, "test")
                b = g.book_a(m, s, ex, mk)
                books[(name, ex)] = b
                for k, v in g.summ(b).items():
                    row[f"tes_{k}"] = v
                if len(b) >= 20:
                    ctl = g.control_a(m, b, ex, mk, rng, reps=g.REPS)
                    row["tes_ctl"], row["tes_p"] = np.nanmedian(ctl), float(np.nanmean(ctl >= b["r"].mean()))
            rows.append(row)
            print(name, ex, "done", flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(g.HERE / "out" / "g123_a1_follow.csv", index=False)
    pd.set_option("display.width", 260)
    print(T.round(3).to_string(index=False))
    for (name, ex), b in books.items():
        b = b.assign(month=m["ts"].to_numpy()[b["i"]].astype("datetime64[M]"))
        print(name, ex, "2026 by month (sum R):", " ".join(f"{str(k)[:7]}:{v:+.1f}" for k, v in b.groupby("month")["r"].sum().items()))


if __name__ == "__main__":
    main()
