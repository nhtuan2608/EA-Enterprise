"""G106: simplified entry "context switches on" + BOX hold on the higher timeframe, buy and sell, several timeframes.

User (11/10): enter when the context turns on (price beyond the four EMAs + the higher timeframe on the right side
of its EMA200), hold on the higher-timeframe pause box, both directions; then try M5 / M30 / H1.

  python g106_ctx_box.py

Timeframe pairs (entry -> higher): M5 -> M30, M15 -> H1, M30 -> H4, H1 -> H4.
Rule (sell; buy mirrored), at an entry-bar close:
  context = close below EMA21/55/100/200 of the entry TF AND the last closed higher-TF bar below its EMA200;
  entry when the context is on now and was off on the previous entry bar (the switch), next bar open.
Protection: the 16-bar entry-TF high + 0.1 ATR (hard). Hold (G103 BOX on the higher TF): from +1R the level is the
high of the last higher-TF pause box (8 bars, width <= 2.5 ATR) that price closed below; exit on a higher-TF close
above level + 0.25 ATR; hard stop at level + 1.5 ATR, only tightening. No take-profit. One trade per direction.
Control: entries at random bars where the context is on (not only the switch), same count, 100 runs.
Periods: train / validate / test as in G98 for M15 (test already opened in G105: reported, not a clean test);
other TFs: every year available, M5 only from 05/2024.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from g95_xau_read import DATA
from g97_forming_bar import dmi, ema

PAIRS = {"M5": ("m5v", "30min"), "M15": ("m15v", "1h"), "M30": ("m30v", "4h"), "H1": ("h1v", "4h")}
PERIODS = {"train": ("2021-07-20", "2024-01-01"), "validate": ("2024-01-01", "2025-07-01"),
           "test": ("2025-07-01", "2026-07-01"), "exam": ("2026-07-01", "2027-01-01")}


def load(tf: str, start: str = "2018-03-01") -> pd.DataFrame:
    folder, hi_rule = PAIRS[tf]
    m = pd.read_csv(DATA / folder / "XAUUSD.csv")
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    m = m[m["ts"] >= start].reset_index(drop=True)
    step = int(np.median(np.diff(m["time"].to_numpy())))
    m = m[m["time"].diff().fillna(step) > 0].reset_index(drop=True)
    return prepare(m, hi_rule)


def prepare(m: pd.DataFrame, hi_rule: str) -> pd.DataFrame:
    c = m["close"].to_numpy()
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    _, _, _, m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    key = m["ts"].dt.floor(hi_rule)
    m["hkey"] = key
    m["hdone"] = (key != key.shift(-1)).to_numpy()
    Hb = m.groupby(key).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    Hb["e200"] = ema(Hb["c"].to_numpy(), 200)
    pc = Hb["c"].shift(1)
    Hb["atr"] = (np.maximum(Hb["h"], pc) - np.minimum(Hb["l"], pc)).rolling(14).mean()
    bh, bl = Hb["h"].rolling(8).max(), Hb["l"].rolling(8).min()
    Hb["box_ok"] = (bh - bl) <= 2.5 * Hb["atr"]
    Hb["box_hi"], Hb["box_lo"] = bh, bl
    idx = pd.Series(np.arange(len(Hb)), index=Hb.index)
    m["hk"] = key.map(idx).to_numpy()
    side = np.sign(Hb["c"] - Hb["e200"]).to_numpy()
    prev = m["hk"].to_numpy() - 1
    m["h_side"] = np.where(prev >= 0, side[np.clip(prev, 0, None)], 0)
    m.attrs["H"] = Hb.reset_index(drop=True)
    return m


def context(m: pd.DataFrame, d: int) -> np.ndarray:
    c = m["close"]
    E = [m[f"e{n}"] for n in (21, 55, 100, 200)]
    beyond = (c < np.minimum.reduce(E)) if d == -1 else (c > np.maximum.reduce(E))
    return (beyond & (m["h_side"] == d)).to_numpy() & (np.arange(len(m)) >= 400)


class Sim:
    def __init__(self, m):
        self.m, self.H = m, m.attrs["H"]
        self.o, self.h, self.l, self.c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy() * 0.01
        self.atr = m["atr"].to_numpy()
        self.hh16 = pd.Series(self.h).rolling(16).max().to_numpy()
        self.ll16 = pd.Series(self.l).rolling(16).min().to_numpy()
        self.hk, self.hdone = m["hk"].to_numpy(), m["hdone"].to_numpy()
        self.Hc, self.Hatr = self.H["c"].to_numpy(), self.H["atr"].to_numpy()
        self.ok, self.bh, self.bl = self.H["box_ok"].to_numpy(), self.H["box_hi"].to_numpy(), self.H["box_lo"].to_numpy()

    def run(self, i, d):
        e = i + 1
        if e >= len(self.c):
            return None
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0)
        hard = (self.ll16[i] - 0.1 * self.atr[i]) if d == 1 else (self.hh16[i] + 0.1 * self.atr[i])
        risk = d * (entry - hard)
        if not risk > 0:
            return None
        level, best, last_box = None, entry, None
        j = e
        while j < len(self.c):
            if (d == 1 and self.l[j] <= hard) or (d == -1 and self.h[j] + self.sp[j] >= hard):
                return d * (hard - entry) / risk, j, "hard"
            best = max(best, self.h[j]) if d == 1 else min(best, self.l[j])
            if self.hdone[j]:
                k = self.hk[j]
                hc, at = self.Hc[k], self.Hatr[k]
                if k >= 1 and self.ok[k - 1]:
                    bx = (self.bh[k - 1], self.bl[k - 1])
                    if d * (hc - (bx[1] if d == -1 else bx[0])) > 0:
                        last_box = bx
                if last_box is not None and d * (best - entry) / risk >= 1:
                    new = last_box[0] if d == -1 else last_box[1]
                    if level is None or d * (new - level) > 0:
                        level = new
                        cand = level + (1.5 * at if d == -1 else -1.5 * at)
                        if d * (cand - hard) > 0:
                            hard = cand
                if level is not None and d * (hc - (level + (0.25 * at if d == -1 else -0.25 * at))) < 0:
                    px = self.c[j] + (self.sp[j] if d == -1 else 0.0)
                    return d * (px - entry) / risk, j, "level"
            j += 1
        return d * (self.c[-1] - entry) / risk, len(self.c) - 1, "open"


def book(S, m, d, mask):
    rows, free = [], 0
    ts = m["ts"].to_numpy()
    for i in np.flatnonzero(mask):
        if i < free:
            continue
        res = S.run(i, d)
        if res is None:
            continue
        r, jx, why = res
        rows.append((ts[i], d, r, why, (ts[jx] - ts[i]) / np.timedelta64(1, "D"), ts[jx], m["open"].iat[i + 1]))
        free = jx + 1
    return pd.DataFrame(rows, columns=["t", "d", "r", "why", "days", "exit_t", "entry"])


def summ(x):
    if x.empty:
        return dict(n=0)
    eq = x["r"].cumsum().to_numpy()
    return dict(n=len(x), R=round(x["r"].mean(), 3), totR=round(x["r"].sum(), 1), win=round((x["r"] > 0).mean(), 2),
                big10=int((x["r"] >= 10).sum()), ddR=round(float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()), 1),
                days=round(x["days"].median(), 1))


def evaluate(tf: str, control_runs: int = 100):
    m = load(tf)
    S = Sim(m)
    rng = np.random.default_rng(106)
    out = []
    for d in (-1, 1):
        ctx = context(m, d)
        sw = ctx & ~np.concatenate([[False], ctx[:-1]])
        t = book(S, m, d, sw)
        name = "SELL" if d == -1 else "BUY"
        per = dict(PERIODS)
        if tf != "M15":
            per = {str(y): (f"{y}-01-01", f"{y + 1}-01-01") for y in range(2018, 2027)}
        for p, (a, b) in per.items():
            x = t[(t["t"] >= a) & (t["t"] < b)]
            if x.empty:
                continue
            row = dict(tf=tf, dir=name, period=p, **summ(x))
            if control_runs:
                tsr = m["ts"]
                win = ((tsr >= a) & (tsr < b)).to_numpy()
                pool = np.flatnonzero(ctx & win)
                dens = (sw & win).sum() / max(len(pool), 1)
                sims = []
                for _ in range(control_runs):
                    pick = np.zeros(len(m), bool)
                    pick[pool[rng.random(len(pool)) < dens]] = True
                    y = book(S, m, d, pick)
                    y = y[(y["t"] >= a) & (y["t"] < b)]
                    sims.append(y["r"].mean() if len(y) else np.nan)
                sims = np.array(sims)
                row["rand_R"] = round(float(np.nanmedian(sims)), 3)
                row["p"] = round(float(np.nanmean(sims >= row["R"])), 2)
            out.append(row)
    return pd.DataFrame(out)


def main():
    tfs = sys.argv[1:] or ["M15", "M5", "M30", "H1"]
    pd.set_option("display.width", 220)
    res = []
    for tf in tfs:
        r = evaluate(tf, control_runs=40 if tf in ("M5",) else 60)
        print(f"\n=== {tf} -> higher {PAIRS[tf][1]} ===")
        print(r.to_string(index=False))
        res.append(r)
    pd.concat(res).to_csv("out/g106_ctx_box.csv", index=False)


if __name__ == "__main__":
    main()
