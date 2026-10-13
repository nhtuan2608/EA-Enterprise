"""G108 step 1: decision points inside the forming M30 bar (every closed M5 bar), structure / liquidity plans
and their labels (docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md).

  python g108_data.py            # builds data/g108_decisions.pkl

Plan of a direction at the close of M5 bar i (entry at the open of bar i+1, server time):
  invalidation  the latest confirmed M5 swing low (buy) / high (sell), fractal 2 bars each side, confirmed at the close
                of the second bar after it; buy stop = swing low - spread, sell stop = swing high + spread
  target        the nearest UNTAKEN liquidity level in the trade direction: prior server-day high / low, highs / lows
                of the sessions completed in the last 24 h (Asia h<10, London 10-14, New York h>=15 server time),
                confirmed H1 swing highs / lows of the last 5 days; untaken = no price beyond it since it formed
  valid         a target exists, the risk is >= 3 spreads and RR = reward / risk >= 2
  label R       target first: +RR; invalidation first (also when both touch in the same M5 bar): -1; neither within
                HORIZON = 288 M5 bars (24 trading hours): the close there. Buys exit at bid, sells at ask (bid + spread).
                (First run used the end of the server day: plans made in the New York afternoon had an hour or less,
                so the horizon is now fixed; changed on train/validate before the test was opened.)
Features use bars <= i only (closed M30 bars for EMA / ATR). MT5 data only: the research M5 export up to
2025-05-21, then the running terminal (read-only).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = DATA / "g108_decisions.pkl"
SPLIT_TERMINAL = int(pd.Timestamp("2025-05-22").timestamp())
START = int(pd.Timestamp("2024-07-01").timestamp())          # after ~1100 M30 bars of EMA warm-up
TRAIN_END = int(pd.Timestamp("2025-04-01").timestamp())
VALID_END = int(pd.Timestamp("2026-01-01").timestamp())      # test = 2026-01-01 onward, sealed in step 2
MIN_RR, MIN_RISK_SPREADS, FRACTAL, H1_DAYS, HORIZON = 2.0, 3.0, 2, 5, 288
DIRS = (1, -1)


# --------------------------------------------------------------------------------------------- data
def load_m5(terminal: pd.DataFrame | None = None) -> pd.DataFrame:
    f = pd.read_csv(DATA / "bars_XAUUSD_M5.csv")
    f = f[f["time"] < SPLIT_TERMINAL]
    if terminal is None:
        import MetaTrader5 as mt5
        mt5.initialize()
        r = mt5.copy_rates_from_pos("XAUUSD-VIP", mt5.TIMEFRAME_M5, 1, 99000)     # closed bars only
        mt5.shutdown()
        terminal = pd.DataFrame(r)[["time", "open", "high", "low", "close", "spread"]]
    t = terminal[terminal["time"] >= SPLIT_TERMINAL]
    df = pd.concat([f[["time", "open", "high", "low", "close", "spread"]], t], ignore_index=True)
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df["sp"] = df["spread"] * 0.01
    return df


# --------------------------------------------------------------------------------------------- pure helpers
def fractals(h: np.ndarray, l: np.ndarray, k: int = FRACTAL):
    """Swing highs / lows (index j) with k bars each side; usable from index j + k (confirmation)."""
    n = len(h)
    sh, sl = [], []
    for j in range(k, n - k):
        if all(h[j] > h[j - m] for m in range(1, k + 1)) and all(h[j] >= h[j + m] for m in range(1, k + 1)):
            sh.append(j)
        if all(l[j] < l[j - m] for m in range(1, k + 1)) and all(l[j] <= l[j + m] for m in range(1, k + 1)):
            sl.append(j)
    return np.array(sh, dtype=np.int64), np.array(sl, dtype=np.int64)


def last_two_confirmed(idx: np.ndarray, level: np.ndarray, n: int, k: int = FRACTAL):
    """For every bar i: the latest and the previous confirmed swing level (NaN when none)."""
    last = np.full(n, np.nan)
    prev = np.full(n, np.nan)
    cur = pr = np.nan
    p = 0
    for i in range(n):
        while p < len(idx) and idx[p] + k <= i:
            pr, cur = cur, level[idx[p]]
            p += 1
        last[i], prev[i] = cur, pr
    return last, prev


class RangeExt:
    """O(1) max / min of an array slice [a, b] (sparse table)."""

    def __init__(self, x: np.ndarray, fn):
        self.fn = fn
        self.t = [x.astype(float)]
        j = 1
        while (1 << j) <= len(x):
            p = self.t[-1]
            self.t.append(fn(p[:-(1 << (j - 1))], p[(1 << (j - 1)):]))
            j += 1

    def q(self, a: int, b: int) -> float:
        k = int(math.log2(b - a + 1))
        return float(self.fn(self.t[k][a], self.t[k][b - (1 << k) + 1]))


def first_touch(d: int, entry: float, stop: float, target: float, h: np.ndarray, l: np.ndarray, sp: np.ndarray,
                c_end: float, sp_end: float):
    """Label of one plan on the forward bars (entry bar first). Returns (R, outcome, offset of the exit bar)."""
    risk = d * (entry - stop)
    if d == 1:
        hit_s = np.nonzero(l <= stop)[0]
        hit_t = np.nonzero(h >= target)[0]
    else:
        hit_s = np.nonzero(h + sp >= stop)[0]
        hit_t = np.nonzero(l + sp <= target)[0]
    s = hit_s[0] if len(hit_s) else 10 ** 9
    t = hit_t[0] if len(hit_t) else 10 ** 9
    if s == t == 10 ** 9:
        px = c_end if d == 1 else c_end + sp_end
        return d * (px - entry) / risk, 0, len(h) - 1
    if s <= t:
        return -1.0, -1, int(s)
    return d * (target - entry) / risk, 1, int(t)


def nearest_target(d: int, entry: float, cands: list[tuple[float, int]], taken) -> float:
    """Nearest untaken level beyond the entry. cands: (level, index of the last bar of its formation)."""
    best = np.nan
    for lev, end in cands:
        if d * (lev - entry) <= 0 or taken(d, lev, end):
            continue
        if best != best or d * (lev - best) < 0:
            best = lev
    return best


# --------------------------------------------------------------------------------------------- build
def ema(x: np.ndarray, p: int) -> np.ndarray:
    k = 2.0 / (p + 1)
    out = np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + k * (x[i] - out[i - 1])
    return out


def wilder_atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    out = np.empty(len(c))
    out[0] = tr[0]
    for i in range(1, len(c)):
        out[i] = out[i - 1] + (tr[i] - out[i - 1]) / n
    return out


def session_of(hour: int) -> int:
    return 0 if hour < 10 else (1 if hour < 15 else 2)          # Asia / London / New York (server time)


def build(df: pd.DataFrame, start: int = START, end: int | None = None) -> pd.DataFrame:
    t = df["time"].to_numpy(np.int64)
    o, h, l, c, sp = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "sp"))
    n = len(t)
    T = t + 300                                                  # close time of each M5 bar
    hmax, lmin = RangeExt(h, np.maximum), RangeExt(l, np.minimum)

    # M5 swings (invalidation + structure)
    sh, sl = fractals(h, l)
    sh_last, sh_prev = last_two_confirmed(sh, h, n)
    sl_last, sl_prev = last_two_confirmed(sl, l, n)

    # closed M30 bars built from M5: EMA band and ATR14
    b30 = t // 1800
    g = pd.DataFrame({"b": b30, "h": h, "l": l, "c": c}).groupby("b").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    m30_end = (g.index.to_numpy(np.int64) + 1) * 1800
    m30_c = g["c"].to_numpy(float)
    e = [ema(m30_c, p) for p in (21, 55, 100, 200)]
    band_hi, band_lo = np.maximum.reduce(e), np.minimum.reduce(e)
    atr30 = wilder_atr(g["h"].to_numpy(float), g["l"].to_numpy(float), m30_c)
    k30 = np.searchsorted(m30_end, T, side="right") - 1          # last M30 bar closed at T
    m30_open_idx = np.searchsorted(t, b30 * 1800)                 # first M5 bar of the forming M30 bucket

    # liquidity candidates: prior day, completed sessions, H1 swings -> (level, last bar index, available from T)
    day = t // 86400
    hour = (t % 86400) // 3600
    sess = np.array([session_of(int(x)) for x in hour])
    lv = pd.DataFrame({"i": np.arange(n), "day": day, "sess": sess, "h": h, "l": l})
    dg = lv.groupby("day").agg(h=("h", "max"), l=("l", "min"), last=("i", "max"))
    sg = lv.groupby(["day", "sess"]).agg(h=("h", "max"), l=("l", "min"), last=("i", "max")).reset_index()
    b1 = t // 3600
    hg = pd.DataFrame({"b": b1, "i": np.arange(n), "h": h, "l": l}).groupby("b").agg(h=("h", "max"), l=("l", "min"), last=("i", "max"))
    h1h, h1l, h1last = hg["h"].to_numpy(float), hg["l"].to_numpy(float), hg["last"].to_numpy(np.int64)
    h1sh, h1sl = fractals(h1h, h1l)
    # (level, last bar of its formation, first bar index at whose close it is known, kind 0 H1 / 1 session / 2 day)
    hi_c, lo_c = [], []
    for j in h1sh:
        hi_c.append((h1h[j], h1last[j], h1last[j + FRACTAL] + 1, 0))
    for j in h1sl:
        lo_c.append((h1l[j], h1last[j], h1last[j + FRACTAL] + 1, 0))
    for _, r in sg.iterrows():
        hi_c.append((r["h"], int(r["last"]), int(r["last"]) + 1, 1))
        lo_c.append((r["l"], int(r["last"]), int(r["last"]) + 1, 1))
    days = dg.index.to_numpy()
    for k in range(len(days) - 1):
        last = int(dg["last"].iloc[k])
        hi_c.append((dg["h"].iloc[k], last, last + 1, 2))
        lo_c.append((dg["l"].iloc[k], last, last + 1, 2))
    hi_c.sort(key=lambda x: x[2])
    lo_c.sort(key=lambda x: x[2])
    hi_from = np.array([x[2] for x in hi_c])
    lo_from = np.array([x[2] for x in lo_c])
    pday_last = {int(days[k + 1]): int(dg["last"].iloc[k]) for k in range(len(days) - 1)}   # prior day's last bar
    look = {0: H1_DAYS * 86400, 1: 86400}

    def window(cands, frm, i):
        """Candidates known at the close of bar i: H1 swings of the last 5 days, sessions of the last 24 h, prior day."""
        k = np.searchsorted(frm, i, side="right")                # known from index <= i
        a = np.searchsorted(frm, np.searchsorted(T, T[i] - H1_DAYS * 86400 - 86400), side="left")
        pl = pday_last.get(int(day[i]), -1)
        out = []
        for lev, last, _, kind in cands[a:k]:
            if (kind == 2 and last == pl) or (kind != 2 and T[last] >= T[i] - look[kind]):
                out.append((lev, last))
        return out

    def taken(d, lev, last, i):
        if last + 1 > i:
            return False
        return (hmax.q(last + 1, i) > lev) if d == 1 else (lmin.q(last + 1, i) < lev)

    rows = []
    for i in range(n - 1):
        if t[i] < start or (end is not None and t[i] >= end):
            continue
        if t[i + 1] - t[i] > 900 or k30[i] < 0 or i + HORIZON > n - 1:   # gap, no closed M30, horizon past the data
            continue
        k = k30[i]
        base = dict(i=i, time=int(t[i]), close=c[i], pos=int((t[i] % 1800) // 300) + 1, sess=int(sess[i]),
                    atr30=atr30[k], band=(1 if c[i] > band_hi[k] else (-1 if c[i] < band_lo[k] else 0)),
                    m30_up=int(np.sign(c[i] - o[m30_open_idx[i]])))
        # M5 structure and slope (bars <= i)
        if not (sh_prev[i] == sh_prev[i] and sl_prev[i] == sl_prev[i]):
            continue
        up = sh_last[i] > sh_prev[i] and sl_last[i] > sl_prev[i]
        dn = sh_last[i] < sh_prev[i] and sl_last[i] < sl_prev[i]
        base["struct"] = 1 if up else (-1 if dn else 0)
        y = c[i - 11:i + 1]
        base["slope"] = float(np.polyfit(np.arange(12), y, 1)[0] / atr30[k]) if i >= 11 and atr30[k] > 0 else np.nan
        for d in DIRS:
            swing = sl_last[i] if d == 1 else sh_last[i]
            if swing != swing:
                continue
            entry = o[i + 1] + (sp[i + 1] if d == 1 else 0.0)
            stop = swing - sp[i] if d == 1 else swing + sp[i]
            risk = d * (entry - stop)
            if risk < MIN_RISK_SPREADS * sp[i]:
                continue
            cands = window(hi_c if d == 1 else lo_c, hi_from if d == 1 else lo_from, i)
            target = nearest_target(d, entry, cands, lambda dd, lev, last: taken(dd, lev, last, i))
            if target != target:
                continue
            rr = d * (target - entry) / risk
            if rr < MIN_RR:
                continue
            j = i + HORIZON
            R, outcome, k_exit = first_touch(d, entry, stop, target, h[i + 1:j + 1], l[i + 1:j + 1], sp[i + 1:j + 1], c[j], sp[j])
            w = min(n - 1, i + 48)
            mfe = (d * ((hmax.q(i + 1, w) if d == 1 else lmin.q(i + 1, w)) - entry)) / risk
            mae = (d * (entry - (lmin.q(i + 1, w) if d == 1 else hmax.q(i + 1, w)))) / risk
            rows.append(dict(base, d=d, entry=entry, stop=stop, target=target, risk=risk, rr=rr, R=R, outcome=outcome, exit_i=i + 1 + k_exit,
                             mfe4h=mfe, mae4h=mae))
    return pd.DataFrame(rows)


def period(ts: pd.Series) -> pd.Series:
    return pd.Series(np.where(ts < TRAIN_END, "train", np.where(ts < VALID_END, "validate", "test")), index=ts.index)


def main():
    df = load_m5()
    print("M5", len(df), pd.to_datetime(df["time"].iloc[0], unit="s"), "->", pd.to_datetime(df["time"].iloc[-1], unit="s"))
    D = build(df)
    D["period"] = period(D["time"])
    D.to_pickle(OUT)
    print("plans", len(D), D.groupby(["period", "d"]).size().to_dict(), "->", OUT)


if __name__ == "__main__":
    main()
