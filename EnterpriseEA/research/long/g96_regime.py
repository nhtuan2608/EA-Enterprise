"""G96 part A: trend regime detectors for XAUUSD on D1 (plan docs/superpowers/plans/2026-10-11-g96-xau-regime.md).

  python g96_regime.py

Position from the open of day t = detector state at the close of day t-1, sized 1/ATR20 (one unit = 1 ATR of
risk), P/L in ATR units; the overnight gap belongs to the position held over it. Cost = spread on every change
of position (bar spread when the export has it, else 0.30 USD).
Periods: train 2010-2017 (selection), validate 2018-2021, test 2022-06/2026, examples 07/2026+.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW_D1 = Path(r"D:\Work\Private\AI APP\Trading-with-AI\input\raw\XAUUSD\XAUUSD_D1_201001040000_202510090000.csv")
OUT = HERE / "out" / "g96"
PERIODS = {"train": ("2010-01-01", "2018-01-01"), "validate": ("2018-01-01", "2022-01-01"),
           "test": ("2022-01-01", "2026-07-01"), "exam": ("2026-07-01", "2027-01-01")}


def load_d1() -> pd.DataFrame:
    d = pd.read_csv(RAW_D1, sep="\t")
    d = pd.DataFrame({"day": pd.to_datetime(d["<DATE>"], format="%Y.%m.%d"), "open": d["<OPEN>"],
                      "high": d["<HIGH>"], "low": d["<LOW>"], "close": d["<CLOSE>"],
                      "spread": d["<SPREAD>"] * 0.01})
    m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
    m["day"] = pd.to_datetime(m["time"], unit="s").dt.normalize()
    m = m[m["day"] > d["day"].max()].groupby("day").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        spread=("spread", "median")).reset_index()
    m["spread"] *= 0.01
    d = pd.concat([d, m], ignore_index=True)
    d["spread"] = d["spread"].where(d["spread"] > 0, 0.30)
    pc = d["close"].shift(1)
    d["atr"] = (np.maximum(d["high"], pc) - np.minimum(d["low"], pc)).rolling(20).mean()
    return d.reset_index(drop=True)


# ---------------------------------------------------------------- detectors (state at the close of each day)
def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def r1(d, n):
    e = ema(d["close"], n)
    slope = np.sign(e - e.shift(10))
    side = np.sign(d["close"] - e)
    return np.where(side == slope, side, 0.0)


def r2(d, n, m):
    c, hi, lo = d["close"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy()
    hh = pd.Series(hi).rolling(n).max().shift(1).to_numpy()
    ll = pd.Series(lo).rolling(n).min().shift(1).to_numpy()
    xh = pd.Series(hi).rolling(m).max().shift(1).to_numpy()
    xl = pd.Series(lo).rolling(m).min().shift(1).to_numpy()
    s = np.zeros(len(c))
    for i in range(1, len(c)):
        s[i] = s[i - 1]
        if s[i] == 1 and c[i] < xl[i]:
            s[i] = 0
        if s[i] == -1 and c[i] > xh[i]:
            s[i] = 0
        if c[i] > hh[i]:
            s[i] = 1
        elif c[i] < ll[i]:
            s[i] = -1
    return s


def dmi(d, n=14):
    h, l, c = d["high"], d["low"], d["close"]
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0))
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0))
    tr = np.maximum(h, c.shift(1)) - np.minimum(l, c.shift(1))
    w = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False).mean()
    a = w(tr)
    pdi, ndi = 100 * w(pdm) / a, 100 * w(ndm) / a
    return pdi, ndi, w(100 * (pdi - ndi).abs() / (pdi + ndi))


def r3(d, th):
    pdi, ndi, adx = dmi(d)
    return np.where(adx >= th, np.sign(pdi - ndi), 0.0)


def r4(d, n):
    c = d["close"]
    z = (c - c.shift(n)) / (d["atr"] * np.sqrt(n))
    return np.where(z.abs() >= 0.5, np.sign(z), 0.0)


def r5(d, n, th):
    c = d["close"]
    er = (c - c.shift(n)).abs() / c.diff().abs().rolling(n).sum()
    return np.where(er >= th, np.sign(c - c.shift(n)), 0.0)


def r6(d):
    c = d["close"]
    e = [ema(c, n) for n in (21, 55, 100, 200)]
    up = (e[0] > e[1]) & (e[1] > e[2]) & (e[2] > e[3])
    dn = (e[0] < e[1]) & (e[1] < e[2]) & (e[2] < e[3])
    return np.where(up, 1.0, np.where(dn, -1.0, 0.0))


def detectors(d):
    out = {}
    for n in (50, 100, 200):
        out[("R1", f"EMA{n}")] = r1(d, n)
    for n, m in ((20, 10), (55, 20), (100, 50)):
        out[("R2", f"DC{n}/{m}")] = r2(d, n, m)
    for th in (20, 25, 30):
        out[("R3", f"ADX{th}")] = r3(d, th)
    for n in (20, 60, 120, 250):
        out[("R4", f"MOM{n}")] = r4(d, n)
    for n, th in itertools.product((20, 60), (0.2, 0.3)):
        out[("R5", f"ER{n}/{th}")] = r5(d, n, th)
    out[("R6", "RIBBON")] = r6(d)
    return out


def apply_usage(s, usage):
    s = np.nan_to_num(np.asarray(s, dtype=float))
    if usage == "L":
        return np.where(s > 0, 1.0, 0.0)
    if usage == "S":
        return np.where(s < 0, -1.0, 0.0)
    return s


def chandelier(d, s, k=3.0):
    """Flat after a close k ATR beyond the best close since entry, until the detector changes state."""
    c, a = d["close"].to_numpy(), d["atr"].to_numpy()
    out = s.copy()
    best, blocked = np.nan, 0.0
    for i in range(len(s)):
        if s[i] != (s[i - 1] if i else 0):
            best, blocked = c[i], 0.0
        if s[i] == 0:
            continue
        if blocked == s[i]:
            out[i] = 0
            continue
        best = max(best, c[i]) if s[i] > 0 else min(best, c[i])
        if np.isfinite(a[i]) and s[i] * (c[i] - best) <= -k * a[i]:
            out[i] = 0
            blocked = s[i]
    return out


def pnl(d, state):
    """Daily P/L (ATR units) of a position = state of the previous close, sized by the ATR at that close."""
    o, c, a, sp = (d[k].to_numpy() for k in ("open", "close", "atr", "spread"))
    pos = np.concatenate([[0.0], state[:-1]])                  # held from the open of day t
    size = np.concatenate([[np.nan], 1.0 / a[:-1]])            # decided at the close of t-1
    prev_pos = np.concatenate([[0.0], pos[:-1]])
    prev_size = np.concatenate([[np.nan], size[:-1]])
    gap = np.nan_to_num(prev_pos * prev_size * (o - np.roll(c, 1)))
    intraday = np.nan_to_num(pos * size * (c - o))
    cost = np.nan_to_num(np.abs(pos - prev_pos) * size * sp)
    r = gap + intraday - cost
    r[0] = 0.0
    return r


def stats(r, pos, mask):
    x = r[mask]
    if len(x) < 50 or x.std() == 0:
        return dict(sharpe=np.nan, atr_per_year=np.nan, max_dd=np.nan, exposure=np.nan)
    eq = np.cumsum(x)
    return dict(sharpe=x.mean() / x.std() * np.sqrt(252), atr_per_year=x.mean() * 252,
                max_dd=float((np.maximum.accumulate(eq) - eq).max()), exposure=float((pos[mask] != 0).mean()))


def permute_runs(state, rng):
    """Shuffle the runs of equal state: same run lengths and exposure, random timing."""
    edges = np.flatnonzero(np.diff(state)) + 1
    runs = np.split(state, edges)
    rng.shuffle(runs)
    return np.concatenate(runs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_d1()
    masks = {p: ((d["day"] >= a) & (d["day"] < b)).to_numpy() for p, (a, b) in PERIODS.items()}
    rows, states = [], {}
    bh = np.ones(len(d))
    for p, m in masks.items():
        rows.append(dict(cell="B&H", family="B&H", usage="L", trail=0, period=p, **stats(pnl(d, bh), bh, m)))
    for (fam, par), raw in detectors(d).items():
        for usage, trail in itertools.product(("LS", "L", "S"), (0, 1)):
            s = apply_usage(raw, usage)
            if trail:
                s = chandelier(d, s)
            cell = f"{fam}-{par}-{usage}-{'T' if trail else 'N'}"
            states[cell] = s
            r = pnl(d, s)
            for p, m in masks.items():
                rows.append(dict(cell=cell, family=fam, param=par, usage=usage, trail=trail, period=p,
                                 **stats(r, s, m)))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "regime_cells.csv", index=False)
    w = t.pivot_table(index="cell", columns="period", values=["sharpe", "atr_per_year", "max_dd", "exposure"])
    w.columns = [f"{p}_{v}" for v, p in w.columns]
    cols = [f"{p}_{v}" for p in ("train", "validate", "test", "exam") for v in ("sharpe", "atr_per_year", "max_dd")]
    w = w[cols + ["train_exposure", "test_exposure"]].sort_values("train_sharpe", ascending=False)
    pd.set_option("display.width", 260)
    print(w.round(2).head(30).to_string())
    print("\nB&H:\n", w.loc[["B&H"]].round(2).to_string())
    for u in ("LS", "L", "S"):
        sub = w[w.index.str.contains(f"-{u}-")]
        print(f"usage {u}: test Sharpe > 0 in {(sub['test_sharpe'] > 0).mean():.0%} of {len(sub)} cells, "
              f"validate {(sub['validate_sharpe'] > 0).mean():.0%}, train {(sub['train_sharpe'] > 0).mean():.0%}")

    # pre-registered selection on train
    cand = w.drop(index="B&H")
    cand = cand[cand["train_exposure"] >= 0.25]
    pick = cand.index[0]
    print("\nselected on train:", pick)
    rng = np.random.default_rng(11)
    s = states[pick]
    real = {p: stats(pnl(d, s), s, masks[p])["sharpe"] for p in ("validate", "test")}
    perm = {p: [] for p in real}
    for _ in range(500):
        sp = permute_runs(s, rng)
        r = pnl(d, sp)
        for p in perm:
            perm[p].append(stats(r, sp, masks[p])["sharpe"])
    fam, par, usage, tr = pick.split("-")
    same_fam = [c for c in w.index if c.startswith(fam + "-") and c != pick]
    neigh = [c for c in same_fam if (c.split("-")[2:] == [usage, tr]) or
             (c.split("-")[1] == par and (c.split("-")[2] == usage) != (c.split("-")[3] == tr))]
    share = float((w.loc[neigh, "test_sharpe"] > 0).mean()) if neigh else np.nan
    for p in ("validate", "test"):
        pv = float((np.array(perm[p]) >= real[p]).mean())
        row, b = w.loc[pick], w.loc["B&H"]
        better = (row[f"{p}_sharpe"] >= b[f"{p}_sharpe"]) or (
            row[f"{p}_max_dd"] <= 0.7 * b[f"{p}_max_dd"] and row[f"{p}_atr_per_year"] >= 0.5 * b[f"{p}_atr_per_year"])
        print(f"{p}: Sharpe {real[p]:.2f} (B&H {b[f'{p}_sharpe']:.2f}) beats-B&H-rule {better}  permutation p {pv:.3f}")
    print(f"neighbours with test Sharpe > 0: {share:.0%} of {len(neigh)} ({', '.join(neigh)})")
    pd.DataFrame(states, index=d["day"]).to_csv(OUT / "regime_states.csv")


if __name__ == "__main__":
    main()
