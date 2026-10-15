"""G96 part B: limit-order zones inside the trend regime (plan docs/superpowers/plans/2026-10-11-g96-xau-regime.md).

  python g96_limits.py

Part A did not pass, so per the plan the regime is R1 EMA100 (close and 10-day EMA slope on the same side),
buy and sell. Each day in the regime without a position: one limit order at the zone, valid for the day
(a buy limit at or above the open fills at the open). Stop = fill -/+ 1 ATR20 D1. Exit: the regime leaves the
direction (next open), a close 3 ATR from the best close (next open), or the stop (the open if it gaps through).
Fill and stop on the same day: H1 bars decide the order from 2018; before 2018 the stop counts first.
Spread from the export (0.30 USD where missing) at entry and exit. Z0 = market order at the open (control).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from g96_regime import HERE, OUT, PERIODS, ema, load_d1, r1

ZONES = ("Z0", "Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7", "Z8")


def h1_by_day():
    h = pd.read_csv(HERE / "data" / "h1v" / "XAUUSD.csv")
    h["ts"] = pd.to_datetime(h["time"], unit="s")
    h = h[h["ts"] >= "2018-03-01"]
    h["day"] = h["ts"].dt.normalize()
    h4 = h.set_index("ts")["close"].resample("4h").last().dropna()
    e21 = ema(h4, 21)
    return {k: (g["high"].to_numpy(), g["low"].to_numpy()) for k, g in h.groupby("day")}, e21


def zone_levels(d: pd.DataFrame, e21_h4: pd.Series) -> dict:
    """Level for a long (index 0) and a short (index 1) placed at the open of day t from data up to t-1."""
    c, h, l, a = d["close"], d["high"], d["low"], d["atr"]
    sh = lambda x: x.shift(1).to_numpy()
    e21, e50 = ema(c, 21), ema(c, 50)
    mid = (h + l) / 2
    # fractal swing: low[i] lowest of i-2..i+2, known at i+2
    fl = l.where((l == l.rolling(5, center=True).min())).shift(2).ffill()
    fh = h.where((h == h.rolling(5, center=True).max())).shift(2).ffill()
    h4 = e21_h4.reindex(pd.DatetimeIndex(d["day"]), method="ffill").to_numpy()  # last H4 EMA before the day
    return {
        "Z1": (sh(e21), sh(e21)), "Z2": (sh(e50), sh(e50)), "Z3": (sh(l), sh(h)), "Z4": (sh(mid), sh(mid)),
        "Z5": (sh(c - 0.5 * a), sh(c + 0.5 * a)), "Z6": (sh(c - 1.0 * a), sh(c + 1.0 * a)),
        "Z7": (fl.shift(1).to_numpy(), fh.shift(1).to_numpy()), "Z8": (h4, h4),
    }


def simulate(d, state, level_long, level_short, h1, offsets=None, rng=None):
    o, hi, lo, c, a, sp = (d[k].to_numpy() for k in ("open", "high", "low", "close", "atr", "spread"))
    days = d["day"].to_numpy()
    trades, placed = [], []
    pos = None
    for t in range(1, len(d)):
        s = state[t - 1]
        if pos is not None:
            dr, fill, stop, best = pos["d"], pos["fill"], pos["stop"], pos["best"]
            exit_px = None
            if (dr == 1 and o[t] <= stop) or (dr == -1 and o[t] >= stop):
                exit_px = o[t]
            elif s != dr or dr * (c[t - 1] - best) <= -3 * a[t - 1]:
                exit_px = o[t]
            elif (dr == 1 and lo[t] <= stop) or (dr == -1 and hi[t] >= stop):
                exit_px = stop
            if exit_px is not None:
                cost = sp[t] if dr == -1 else 0.0
                pos["r"] = (dr * (exit_px - fill) - cost - pos["entry_cost"]) / pos["risk"]
                pos["exit"] = days[t]
                trades.append(pos)
                pos = None
                if exit_px == stop and exit_px != o[t]:
                    continue                      # stopped intraday: no new order that day
            else:
                pos["best"] = max(best, c[t]) if dr == 1 else min(best, c[t])
                continue
        if s == 0 or not np.isfinite(a[t - 1]):
            continue
        dr = int(s)
        if offsets is not None:
            lv = o[t] - dr * rng.choice(offsets) * a[t - 1]
        elif level_long is None:
            lv = np.inf if dr == 1 else -np.inf
        else:
            lv = level_long[t] if dr == 1 else level_short[t]
        if not np.isfinite(lv) and level_long is not None:
            continue
        placed.append((o[t] - lv) * dr / a[t - 1] if np.isfinite(lv) else 0.0)
        if dr == 1:
            if lo[t] > lv:
                continue
            fill = min(o[t], lv)
        else:
            if hi[t] < lv:
                continue
            fill = max(o[t], lv)
        risk = a[t - 1]
        stop = fill - dr * risk
        entry_cost = sp[t] if dr == 1 else 0.0
        # same-day stop after the fill
        stopped = (dr == 1 and lo[t] <= stop) or (dr == -1 and hi[t] >= stop)
        if stopped and days[t] in h1 and np.isfinite(lv) and fill == lv:
            hh, ll = h1[days[t]]
            k = np.argmax(ll <= lv) if dr == 1 else np.argmax(hh >= lv)
            stopped = bool((ll[k:] <= stop).any()) if dr == 1 else bool((hh[k:] >= stop).any())
        pos = dict(d=dr, entry=days[t], fill=fill, stop=stop, risk=risk, best=c[t], entry_cost=entry_cost)
        if stopped:
            pos["r"] = (-risk - entry_cost - (sp[t] if dr == -1 else 0.0)) / risk
            pos["exit"] = days[t]
            trades.append(pos)
            pos = None
    return pd.DataFrame(trades), np.array(placed)


def per_period(t: pd.DataFrame) -> dict:
    out = {}
    for p, (a, b) in PERIODS.items():
        x = t[(t["entry"] >= a) & (t["entry"] < b)] if len(t) else t
        out[p] = (len(x), x["r"].mean() if len(x) else np.nan, x["r"].sum() if len(x) else 0.0,
                  (x["r"] > 0).mean() if len(x) else np.nan)
    return out


def main():
    d = load_d1()
    state = np.nan_to_num(r1(d, 100))
    h1, e21h4 = h1_by_day()
    lv = zone_levels(d, e21h4)
    rows, all_trades, offsets = [], {}, {}
    for z in ZONES:
        if z == "Z0":
            t, pl = simulate(d, state, None, None, h1)
        else:
            if z == "Z8":
                sub = d["day"] >= "2018-03-02"
                L, S = (np.where(sub, x, np.nan) for x in lv[z])
            else:
                L, S = lv[z]
            t, pl = simulate(d, state, L, S, h1)
        all_trades[z] = t
        offsets[z] = pl[np.isfinite(pl)]
        pp = per_period(t)
        row = dict(zone=z, fill_rate=len(t) / max(len(pl), 1), med_offset_atr=float(np.median(pl)) if len(pl) else np.nan)
        for p, (n, m, tot, win) in pp.items():
            row.update({f"{p}_n": n, f"{p}_meanR": m, f"{p}_totR": tot, f"{p}_win": win})
        for dr, name in ((1, "buy"), (-1, "sell")):
            x = t[t["d"] == dr] if len(t) else t
            row[f"{name}_n"], row[f"{name}_meanR"] = len(x), (x["r"].mean() if len(x) else np.nan)
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("zone")
    pd.set_option("display.width", 260)
    cols = ["fill_rate", "med_offset_atr"] + [f"{p}_{k}" for p in ("train", "validate", "test", "exam")
                                              for k in ("n", "meanR", "totR")] + ["buy_n", "buy_meanR", "sell_n", "sell_meanR"]
    print(tab[cols].round(3).to_string())
    tab.to_csv(OUT / "limit_zones.csv")
    # random-limit control on test for zones that pass the first two criteria
    rng = np.random.default_rng(5)
    a, b = PERIODS["test"]
    mkt_test = tab.loc["Z0", "test_totR"]
    print(f"\nZ0 market test total R {mkt_test:.1f}")
    for z in ZONES[1:]:
        r = tab.loc[z]
        pos3 = all(r[f"{p}_meanR"] > 0 for p in ("train", "validate", "test") if not (z == "Z8" and p == "train"))
        if not (pos3 and r["test_totR"] >= mkt_test):
            print(f"{z}: fails positive-in-every-period or test total >= market "
                  f"(train {r.train_meanR:+.3f} val {r.validate_meanR:+.3f} test {r.test_meanR:+.3f}, test tot {r.test_totR:.1f})")
            continue
        sims = []
        for _ in range(300):
            t, _ = simulate(d, state, None, None, h1, offsets=offsets[z], rng=rng)
            x = t[(t["entry"] >= a) & (t["entry"] < b)]
            sims.append(x["r"].sum())
        pv = float((np.array(sims) >= r["test_totR"]).mean())
        print(f"{z}: test total R {r.test_totR:.1f} vs random limits median {np.median(sims):.1f}, p {pv:.3f} "
              f"-> {'PASS' if pv < 0.10 else 'FAIL'}")
    for z, t in all_trades.items():
        if len(t):
            t.to_csv(OUT / f"limit_trades_{z}.csv", index=False)


if __name__ == "__main__":
    main()
