"""G121: tick order flow (A) and volume profile (B) as stand-alone methods (plan docs/superpowers/plans/2026-10-15-g121-orderflow-profile.md).

  python g121_study.py            -> train / validate tables with controls (2026 test sealed)
  python g121_study.py test       -> open the test year for the cells that passed (run once, after the user agrees)
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from g97_forming_bar import dmi

HERE = Path(__file__).resolve().parent
TICKS = HERE / "data" / "ticks"
PER = {"train": ("2024-03-01", "2025-07-01"), "validate": ("2025-07-01", "2026-01-01"), "test": ("2026-01-01", "2027-01-01")}
BIN = 0.5
EXITS = ("TP2", "TP3", "STRUCT")
REPS = 200


def load():
    fl = pd.concat([pd.read_pickle(f) for f in sorted(glob.glob(str(TICKS / "m5flow_*.pkl")))], ignore_index=True)
    fl = fl.drop_duplicates("time").sort_values("time")
    m = fl.rename(columns={"hi": "high", "lo": "low"}).reset_index(drop=True)
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    _, _, _, m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), m["close"].to_numpy())
    m["act"] = m["n"] / m["n"].rolling(20).mean().shift(1)
    m["d"] = m["delta"] / m["n"].clip(lower=1)
    m["cpos"] = (m["close"] - m["low"]) / (m["high"] - m["low"]).replace(0, np.nan)
    m["hh24"] = m["high"].rolling(24).max().shift(1)
    m["ll24"] = m["low"].rolling(24).min().shift(1)
    m["cvd"] = m["delta"].cumsum()
    m["day"] = m["ts"].dt.normalize()
    m["hour"] = m["ts"].dt.hour
    return m


def in_period(m, p):
    a, b = PER[p]
    return ((m["ts"] >= a) & (m["ts"] < b)).to_numpy()


# --------------------------------------------------------------------------------------------- A: order flow
def signals_a(m, thr):
    h, l, c = m["high"].to_numpy(), m["low"].to_numpy(), m["close"].to_numpy()
    act, d, cpos = m["act"].to_numpy(), m["d"].to_numpy(), m["cpos"].to_numpy()
    hh, ll, cvd = m["hh24"].to_numpy(), m["ll24"].to_numpy(), m["cvd"].to_numpy()
    n = len(m)
    out = {"A1": np.zeros(n, int), "A2": np.zeros(n, int), "A3": np.zeros(n, int)}
    hiw = pd.Series(h).rolling(24).apply(np.argmax, raw=True).shift(1).to_numpy()
    low_w = pd.Series(l).rolling(24).apply(np.argmin, raw=True).shift(1).to_numpy()
    for i in range(50, n):
        if not np.isfinite(hh[i]) or not np.isfinite(act[i]):
            continue
        # A1 absorption
        if h[i] >= hh[i] and act[i] >= 1.5 and d[i] >= thr["d_hi"] and cpos[i] <= 0.5:
            out["A1"][i] = -1
        elif l[i] <= ll[i] and act[i] >= 1.5 and d[i] <= thr["d_lo"] and cpos[i] >= 0.5:
            out["A1"][i] = 1
        # A2 exhaustion (CVD divergence at a new 24-bar extreme)
        if h[i] > hh[i] and np.isfinite(hiw[i]):
            p = i - 24 + int(hiw[i])
            if cvd[i] < cvd[p]:
                out["A2"][i] = -1
        elif l[i] < ll[i] and np.isfinite(low_w[i]):
            q = i - 24 + int(low_w[i])
            if cvd[i] > cvd[q]:
                out["A2"][i] = 1
        # A3 initiative
        if c[i] > hh[i] and act[i] >= 1.5 and d[i] >= thr["d_top"]:
            out["A3"][i] = 1
        elif c[i] < ll[i] and act[i] >= 1.5 and d[i] <= thr["d_bot"]:
            out["A3"][i] = -1
    return out


def trade_a(m, i, d, ex):
    o, h, l, c, sp, a = (m[k].to_numpy() for k in ("open", "high", "low", "close", "sp", "atr"))
    e = i + 1
    if e >= len(o) - 2:
        return None
    entry = o[e] + (sp[e] if d == 1 else 0.0)
    stop = (l[i] - 0.1 * a[i]) if d == 1 else (h[i] + 0.1 * a[i])
    R = d * (entry - stop)
    if not (0.5 * a[i] <= R <= 4 * a[i]):
        return None
    k = {"TP2": 2.0, "TP3": 3.0, "STRUCT": None}[ex]
    tp = entry + d * k * R if k else None
    best = entry
    end = min(len(o) - 1, e + 48)
    for j in range(e, end + 1):
        if (d == 1 and l[j] <= stop) or (d == -1 and h[j] + sp[j] >= stop):
            return -1.0, j
        if tp is not None and ((d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp)):
            return float(k), j
        best = max(best, h[j]) if d == 1 else min(best, l[j])
        if tp is None and d * (best - entry) >= R and j > e:
            if (d == 1 and c[j] < l[j - 1]) or (d == -1 and c[j] > h[j - 1]):
                px = c[j] + (sp[j] if d == -1 else 0.0)
                return d * (px - entry) / R, j
    px = c[end] + (sp[end] if d == -1 else 0.0)
    return d * (px - entry) / R, end


def book_a(m, sig, ex, mask):
    rows, busy = [], -1
    for i in np.flatnonzero((sig != 0) & mask):
        if i <= busy:
            continue
        res = trade_a(m, i, int(sig[i]), ex)
        if res is None:
            continue
        r, j = res
        rows.append((i, int(sig[i]), r))
        busy = j
    return pd.DataFrame(rows, columns=["i", "d", "r"])


def control_a(m, real, ex, mask, rng, reps=200):
    """Random bars at the same hour of day and the same direction (stop = that bar's extreme)."""
    hours = m["hour"].to_numpy()
    pool = {hh: np.flatnonzero(mask & (hours == hh)) for hh in range(24)}
    means = []
    for _ in range(reps):
        rs = []
        for i, d in zip(real["i"], real["d"]):
            cand = pool[hours[i]]
            k = int(cand[rng.integers(len(cand))])
            res = trade_a(m, k, d, ex)
            if res is not None:
                rs.append(res[0])
        means.append(np.mean(rs) if rs else np.nan)
    return np.array(means)


# --------------------------------------------------------------------------------------------- B: volume profile
def load_profiles():
    days, los, cnts = [], [], []
    for f in sorted(glob.glob(str(TICKS / "profile_*.npz"))):
        z = np.load(f, allow_pickle=True)
        days += list(z["days"]); los += list(z["lo"]); cnts += list(z["counts"])
    return {pd.Timestamp(d, unit="s").normalize(): (lo, np.asarray(c)) for d, lo, c in zip(days, los, cnts)}


def levels(lo, c):
    poc = int(np.argmax(c))
    tot, va = c.sum(), c[poc]
    a = b = poc
    while va < 0.7 * tot:
        left = c[a - 1] if a > 0 else -1
        right = c[b + 1] if b < len(c) - 1 else -1
        if right >= left:
            b += 1; va += c[b]
        else:
            a -= 1; va += c[a]
    price = lambda k: lo + (k + 0.5) * BIN
    lvn = [price(k) for k in range(a + 1, b) if c[k] < 0.25 * c[poc] and c[k - 1] >= c[k] <= c[k + 1]]
    hvn = [price(k) for k in range(len(c)) if c[k] >= 0.7 * c[poc]]
    return dict(poc=price(poc), vah=lo + (b + 1) * BIN, val=lo + a * BIN, lvn=lvn, hvn=hvn)


def trade_b(m, e, d, stop, target, day_end):
    o, h, l, c, sp = (m[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
    if e >= len(o):
        return None
    entry = o[e] + (sp[e] if d == 1 else 0.0)
    R = d * (entry - stop)
    if R <= 0 or d * (target - entry) <= 0:
        return None
    for j in range(e, day_end + 1):
        if (d == 1 and l[j] <= stop) or (d == -1 and h[j] + sp[j] >= stop):
            return -1.0
        if (d == 1 and h[j] >= target) or (d == -1 and l[j] + sp[j] <= target):
            return d * (target - entry) / R
    px = c[day_end] + (sp[day_end] if d == -1 else 0.0)
    return d * (px - entry) / R


def day_trades_b(m, idx, L, shift=0.0):
    """idx: bar indices of one server day. L: prior-day levels. Returns list of (setup, i, d, r)."""
    o, h, l, c, a = (m[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    vah, val, poc = L["vah"] + shift, L["val"] + shift, L["poc"] + shift
    lvn = [x + shift for x in L["lvn"]]
    hvn = sorted(x + shift for x in L["hvn"])
    end = int(idx[-1])
    out, done = [], set()
    first = int(idx[0])
    open_out = 1 if o[first] > vah else (-1 if o[first] < val else 0)
    touched = set()
    for t, i in enumerate(idx[1:-1], 1):
        i = int(i)
        # B1: opened outside the value area, two closes back inside -> toward the far edge
        if "B1" not in done and open_out != 0 and val <= c[i] <= vah and val <= c[i - 1] <= vah and i - 1 >= first:
            d = -open_out
            stop = (vah + a[i]) if d == -1 else (val - a[i])
            r = trade_b(m, i + 1, d, stop, val if d == -1 else vah, end)
            if r is not None:
                out.append(("B1", i, d, r)); done.add("B1")
        # B2: first touch of VAH / VAL / POC, close back on the old side -> fade
        for name, lv in (("VAH", vah), ("VAL", val), ("POC", poc)):
            if name in touched or "B2" in done:
                continue
            if l[i] <= lv <= h[i]:
                touched.add(name)
                if c[i - 1] < lv and c[i] < lv:
                    d, stop = -1, lv + 0.5 * a[i]
                    target = poc if name == "VAH" else val
                elif c[i - 1] > lv and c[i] > lv:
                    d, stop = 1, lv - 0.5 * a[i]
                    target = poc if name == "VAL" else vah
                else:
                    continue
                r = trade_b(m, i + 1, d, stop, target, end)
                if r is not None:
                    out.append(("B2", i, d, r)); done.add("B2")
        # B3: close through a low-volume node -> next high-volume node
        if "B3" not in done:
            for x in lvn:
                if c[i - 1] < x < c[i]:
                    nxt = [y for y in hvn if y > c[i]]
                    tgt = nxt[0] if nxt else vah
                    r = trade_b(m, i + 1, 1, x - 0.5 * a[i], tgt, end)
                    if r is not None:
                        out.append(("B3", i, 1, r)); done.add("B3")
                    break
                if c[i - 1] > x > c[i]:
                    nxt = [y for y in hvn if y < c[i]]
                    tgt = nxt[-1] if nxt else val
                    r = trade_b(m, i + 1, -1, x + 0.5 * a[i], tgt, end)
                    if r is not None:
                        out.append(("B3", i, -1, r)); done.add("B3")
                    break
    return out


def run_b(m, prof, mask, rng=None):
    rows = []
    days = m.loc[mask, "day"].unique()
    di = m.groupby("day").indices
    prev_days = sorted(prof)
    for day in days:
        k = np.searchsorted(prev_days, day) - 1
        if k < 0:
            continue
        L = levels(*prof[prev_days[k]])
        shift = 0.0
        if rng is not None:
            shift = rng.choice((-1, 1)) * rng.uniform(1, 3) * (L["vah"] - L["val"])
        for s, i, d, r in day_trades_b(m, np.asarray(di[day]), L, shift):
            rows.append((s, i, d, r))
    return pd.DataFrame(rows, columns=["setup", "i", "d", "r"])


def summ(x):
    if len(x) == 0:
        return dict(n=0, R=np.nan)
    return dict(n=len(x), R=x["r"].mean(), win=(x["r"] > 0).mean(), buyR=x.loc[x.d == 1, "r"].mean(),
                sellR=x.loc[x.d == -1, "r"].mean(), tot=x["r"].sum())


def main(open_test=False):
    m = load()
    print(f"bars with tick flow: {len(m)}, {m.ts.min():%Y-%m-%d} .. {m.ts.max():%Y-%m-%d}", flush=True)
    tr = in_period(m, "train")
    thr = {"d_hi": np.nanpercentile(m.d[tr], 66.7), "d_lo": np.nanpercentile(m.d[tr], 33.3),
           "d_top": np.nanpercentile(m.d[tr], 90), "d_bot": np.nanpercentile(m.d[tr], 10)}
    print("thresholds (train):", {k: round(v, 3) for k, v in thr.items()})
    sig = signals_a(m, thr)
    periods = ("train", "validate") + (("test",) if open_test else ())
    rng = np.random.default_rng(121)
    rows = []
    for name, s in sig.items():
        for ex in EXITS:
            row = dict(method=name, exit=ex)
            for p in periods:
                mk = in_period(m, p)
                b = book_a(m, s, ex, mk)
                for k, v in summ(b).items():
                    row[f"{p[:3]}_{k}"] = v
                if p != "train" and len(b) >= 20:
                    ctl = control_a(m, b, ex, mk, rng, reps=REPS)
                    row[f"{p[:3]}_ctl"] = np.nanmedian(ctl)
                    row[f"{p[:3]}_p"] = float(np.nanmean(ctl >= b["r"].mean()))
            rows.append(row)
            print(name, ex, "done", flush=True)
    prof = load_profiles()
    brow = {k: dict(method=k, exit="level") for k in ("B1", "B2", "B3")}
    for p in periods:
        mk = in_period(m, p)
        real = run_b(m, prof, mk)
        fakes = [run_b(m, prof, mk, rng) for _ in range(REPS if p != "train" else 0)]
        for setup, row in brow.items():
            b = real[real.setup == setup]
            for k, v in summ(b).items():
                row[f"{p[:3]}_{k}"] = v
            if fakes and len(b) >= 20:
                ctl = np.array([f.loc[f.setup == setup, "r"].mean() if (f.setup == setup).any() else np.nan for f in fakes])
                row[f"{p[:3]}_ctl"] = np.nanmedian(ctl)
                row[f"{p[:3]}_p"] = float(np.nanmean(ctl >= b["r"].mean()))
        print("B", p, "done", flush=True)
    rows += list(brow.values())
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "out" / ("g121_test.csv" if open_test else "g121_study.csv"), index=False)
    pd.set_option("display.width", 250)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main(open_test=len(sys.argv) > 1 and sys.argv[1] == "test")
