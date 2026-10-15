"""G99: which context chains raise the odds of a large gold sell-off? (XAUUSD H1 since 2018, MT5 data only)

User (11/10, charts 03/03 and 12/03/2026): loose EMA conditions, find a chain of context that gives confidence
in a sell; ignore risk sizing for now; the goal is a higher hit rate of big moves.

  python g99_sell_context.py

Outcome at the close of H1 bar t (entry = close): BIG6 = the low reaches close - 6 ATR(H1) before the high
reaches close + 2 ATR(H1), within 120 H1 bars; BIG10 the same with 10 ATR (both are "3:1" / "5:1" moves).
Episodes: the first qualifying bar in a 24-bar cluster (no overlapping counts).
Periods: train 2018-03..2021-12, validate 2022-01..2025-06 (2022 sell-off, 2024-25 rally),
test 07/2025..06/2026 sealed (holds the user's examples), examples 07/2026+.
Features (all known at the bar close):
  F1  top_recent    the 120-bar high was printed within the last 48 bars
  F2  lower_high    last confirmed H1 swing high < the one before
  F3  stretched     in the last 5 days the D1 close stood >= 3 ATR(D1) above the D1 EMA50
  F4  ribbon_turn   H1 EMA21 crossed below EMA55 within the last 12 bars
  F5  below_e100    close < H1 EMA100
  F6  compressed    min H1 ADX of the last 24 bars <= 20
  F7  di_down       DI- > DI+ and ADX rising
  F8  day_low_break close < the prior server day's low
  F9  impulse       bar range >= 1.8 ATR and close in its lowest 25%
  F10 volume        tick volume >= 1.5x the mean of the same hour over the last 20 days
  F11 session       VN 14:00-23:59 (London + New York)
  F12 failed_break  a new 20-day high in the last 48 bars, now closed back below that prior 20-day high
  F13 h4_below_e55  H4 close < H4 EMA55
  F14 d1_reject     yesterday's D1 made a higher high than the day before and closed in its lowest third
  F15 usd_up_24h    USD index (-EURUSD + USDJPY, log) up over 24 H1 bars
  F16 usd_trend     EURUSD below and USDJPY above their 120-bar EMA
  F17 gold_vs_usd   gold up over 120 bars while the USD index is up too
  F18 usd_strong    24-bar USD index move >= 1 sigma
Base for every chain: "loose sell" = close < H1 EMA21 and DI- > DI+ (no EMA order).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from g96_regime import load_d1
from g97_forming_bar import dmi, ema
from g95_xau_read import DATA

PERIODS = {"train": ("2018-03-01", "2022-01-01"), "validate": ("2022-01-01", "2025-07-01"),
           "test": ("2025-07-01", "2026-07-01")}
HORIZON = 120


def h1() -> pd.DataFrame:
    h = pd.read_csv(DATA / "h1v" / "XAUUSD.csv")
    h["ts"] = pd.to_datetime(h["time"], unit="s")
    h = h[h["ts"] >= "2018-03-01"].reset_index(drop=True)
    o, hi, lo, c = (h[k].to_numpy() for k in ("open", "high", "low", "close"))
    for n in (21, 55, 100):
        h[f"e{n}"] = ema(c, n)
    h["pdi"], h["mdi"], h["adx"], h["atr"] = dmi(hi, lo, c)
    return h


def features(h: pd.DataFrame) -> pd.DataFrame:
    c, hi, lo, o = (h[k] for k in ("close", "high", "low", "open"))
    F = pd.DataFrame(index=h.index)
    hh120 = hi.rolling(120).max()
    age = hi.rolling(120).apply(lambda x: 119 - int(np.argmax(x)), raw=True)
    F["F1"] = (age <= 48)
    # confirmed swing highs (2 bars each side, known 2 bars later)
    sw = hi.where(hi == hi.rolling(5, center=True).max()).shift(2)
    last = sw.ffill()
    prev = sw.where(sw.notna()).ffill().shift(1)
    prev = sw.dropna().shift(1).reindex(h.index).ffill()
    F["F2"] = last < prev
    # D1 stretch (server days, prior days only)
    d = load_d1()
    d["e50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["str"] = (d["close"] - d["e50"]) / d["atr"]
    stretch = d.set_index("day")["str"].rolling(5).max().shift(1)
    day = h["ts"].dt.normalize()
    F["F3"] = day.map(stretch) >= 3
    cross = (h["e21"] < h["e55"]) & (h["e21"].shift(1) >= h["e55"].shift(1))
    F["F4"] = cross.rolling(12).max().astype(bool) & (h["e21"] < h["e55"])
    F["F5"] = c < h["e100"]
    F["F6"] = h["adx"].rolling(24).min() <= 20
    F["F7"] = (h["mdi"] > h["pdi"]) & (h["adx"] > h["adx"].shift(1))
    dl = h.groupby(day)["low"].min()
    F["F8"] = c < day.map(dl.shift(1))
    rng = hi - lo
    F["F9"] = (rng >= 1.8 * h["atr"]) & ((c - lo) <= 0.25 * rng)
    hour = h["ts"].dt.hour
    vmean = h.groupby(hour)["tickvol"].transform(lambda s: s.shift(1).rolling(20, min_periods=10).mean())
    F["F10"] = h["tickvol"] >= 1.5 * vmean
    vn_hour = (h["ts"] + pd.Timedelta(hours=4)).dt.hour        # server + 4 (summer) / + 5: VN 14-23 either way ~
    F["F11"] = vn_hour >= 14
    dh20 = h.groupby(day)["high"].max()
    prior20 = dh20.rolling(20).max().shift(1)
    newhigh = hi > day.map(prior20)
    F["F12"] = newhigh.rolling(48).max().astype(bool) & (c < day.map(prior20))
    h4 = h.set_index("ts")["close"].resample("4h").last().dropna()
    h4e = h4.ewm(span=55, adjust=False).mean()
    below = (h4 < h4e).shift(1)                                # last completed H4 bar
    F["F13"] = h["ts"].dt.floor("4h").map(below).fillna(False).astype(bool)
    dd = d.set_index("day")
    rej = (dd["high"] > dd["high"].shift(1)) & ((dd["close"] - dd["low"]) <= (dd["high"] - dd["low"]) / 3)
    F["F14"] = day.map(rej.shift(1)).fillna(False).astype(bool)
    # cross-market USD (EURUSD and USDJPY H1, same broker clock): USD up = EURUSD down and USDJPY up
    fx = {}
    for s in ("EURUSD", "USDJPY"):
        x = pd.read_csv(DATA / "h1v" / f"{s}.csv")
        x["ts"] = pd.to_datetime(x["time"], unit="s")
        fx[s] = x.set_index("ts")["close"].reindex(h["ts"], method="ffill").to_numpy()
    eu, uj = pd.Series(np.log(fx["EURUSD"])), pd.Series(np.log(fx["USDJPY"]))
    usd = (-eu + uj) / 2                                    # USD strength index (log)
    F["F15"] = (usd - usd.shift(24)) > 0                     # USD up over the last 24 h
    F["F16"] = (pd.Series(fx["EURUSD"]) < pd.Series(fx["EURUSD"]).ewm(span=120).mean()) &                (pd.Series(fx["USDJPY"]) > pd.Series(fx["USDJPY"]).ewm(span=120).mean())   # USD trend up (5 days)
    g120 = c - c.shift(120)
    F["F17"] = (g120 > 0) & ((usd - usd.shift(120)) > 0)    # gold rose over 5 days while the USD also rose
    usd_z = (usd - usd.shift(24)) / (usd.diff().rolling(500).std() * np.sqrt(24))
    F["F18"] = usd_z >= 1.0                                  # strong USD day (>= 1 sigma)
    return F.fillna(False).astype(bool)


def outcomes(h: pd.DataFrame) -> pd.DataFrame:
    c, hi, lo, a = (h[k].to_numpy() for k in ("close", "high", "low", "atr"))
    n = len(c)
    big6 = np.zeros(n, bool)
    big10 = np.zeros(n, bool)
    drop = np.full(n, np.nan)
    for i in range(n - 1):
        if not a[i] > 0:
            continue
        up = c[i] + 2 * a[i]
        end = min(n, i + 1 + HORIZON)
        seg_h, seg_l = hi[i + 1:end], lo[i + 1:end]
        hit_up = np.flatnonzero(seg_h >= up)
        k = hit_up[0] if len(hit_up) else len(seg_h)
        low_before = seg_l[:k].min() if k > 0 else c[i]
        drop[i] = (c[i] - low_before) / a[i]
        big6[i] = drop[i] >= 6
        big10[i] = drop[i] >= 10
    return pd.DataFrame({"big6": big6, "big10": big10, "drop": drop}, index=h.index)


def episodes(mask: np.ndarray, gap: int = 24) -> np.ndarray:
    idx = np.flatnonzero(mask)
    keep, last = [], -10**9
    for i in idx:
        if i - last >= gap:
            keep.append(i)
        last = i if i - last >= gap else last
    return np.array(keep, dtype=int)


def rate(idx, Y):
    if len(idx) == 0:
        return 0, np.nan, np.nan, np.nan
    y = Y.iloc[idx]
    return len(idx), y["big6"].mean(), y["big10"].mean(), y["drop"].median()


def main():
    h = h1()
    F = features(h)
    Y = outcomes(h)
    loose = ((h["close"] < h["e21"]) & (h["mdi"] > h["pdi"])).to_numpy()
    per = {p: ((h["ts"] >= a) & (h["ts"] < b)).to_numpy() for p, (a, b) in PERIODS.items()}
    rows = []
    names = list(F.columns)
    chains = [()] + [(f,) for f in names] + list(itertools.combinations(names, 2)) + list(itertools.combinations(names, 3))
    base = {}
    for p in ("train", "validate"):
        base[p] = rate(episodes(loose & per[p]), Y)
    for ch in chains:
        mk = loose.copy()
        for f in ch:
            mk &= F[f].to_numpy()
        row = {"chain": "+".join(ch) if ch else "loose sell (base)", "k": len(ch)}
        for p in ("train", "validate"):
            n, r6, r10, md = rate(episodes(mk & per[p]), Y)
            row.update({f"{p}_n": n, f"{p}_big6": r6, f"{p}_big10": r10, f"{p}_lift6": r6 / base[p][1] if n else np.nan,
                        f"{p}_lift10": r10 / base[p][2] if n else np.nan})
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv("out/g99_chains.csv", index=False)
    pd.set_option("display.width", 250)
    print("base 'loose sell' episodes:", {p: tuple(round(x, 3) if isinstance(x, float) else x for x in v) for p, v in base.items()},
          "(n, P(big6), P(big10), median drop ATR)")
    cols = ["chain", "train_n", "train_big6", "train_lift6", "train_big10", "validate_n", "validate_big6",
            "validate_lift6", "validate_big10", "validate_lift10"]
    print("\nsingle features:")
    print(t[t.k == 1][cols].round(3).sort_values("train_lift6", ascending=False).to_string(index=False))
    ok = t[(t.k >= 2) & (t.train_n >= 25) & (t.validate_n >= 25)].copy()
    ok["min_lift6"] = ok[["train_lift6", "validate_lift6"]].min(axis=1)
    print(f"\nchains of 2-3 with >= 25 episodes in both periods: {len(ok)}; lift6 >= 1.5 in both: "
          f"{int((ok.min_lift6 >= 1.5).sum())}")
    print(ok.sort_values("min_lift6", ascending=False)[cols + ["min_lift6"]].head(25).round(3).to_string(index=False))
    # how many chains would pass by chance: shuffle the feature rows in time blocks (same chain count)
    rng = np.random.default_rng(1)
    best_null = []
    for _ in range(30):
        shift = rng.integers(500, len(h) - 500)
        Fs = F.apply(lambda s: np.roll(s.to_numpy(), shift))
        vals = []
        for ch in [c for c in chains if len(c) >= 2][::7]:
            mk = loose.copy()
            for f in ch:
                mk &= Fs[f].to_numpy()
            l6 = []
            for p in ("train", "validate"):
                n, r6, _, _ = rate(episodes(mk & per[p]), Y)
                l6.append(r6 / base[p][1] if n >= 25 else np.nan)
            vals.append(np.nanmin(l6) if not np.isnan(l6).any() else np.nan)
        best_null.append(np.nanmax(vals))
    print(f"\nnull (features shifted in time, every 7th chain): best min-lift6 median {np.median(best_null):.2f}, "
          f"90th pct {np.percentile(best_null, 90):.2f}")


if __name__ == "__main__":
    main()
