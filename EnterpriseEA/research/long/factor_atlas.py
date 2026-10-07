"""G56 phase A: factor atlas (plan docs/superpowers/plans/2026-10-07-g56-factor-atlas.md, registered before any number).

  python factor_atlas.py           # writes results/factor_atlas.md and results/factor_atlas.json

Every factor is an event at the close of bar i with a hypothesised direction d. Forward move d*(close[i+k]-close[i])
in ATR14[i] units, minus the symbol's mean move per bar over the same period and horizon (drift). Statistic per
(timeframe, factor, horizon): mean over (symbol, day) clusters, t-test, two-sided p. Selection on train only:
Benjamini-Hochberg q < 0.10 over every test of the timeframe, |effect| >= 0.05 ATR, same sign on >= 60% of the
symbols with >= 30 events. Survival: validate same sign with one-sided p < 0.10, test same sign, and the mean net of
costs (spread + commission, ATR units, without drift removal) > 0 in validate and test.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone

import numpy as np
from scipy import stats as sst

import long_study as ls  # noqa: F401  (research data path first)
import context  # noqa: E402
import replay  # noqa: E402

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]
TF = {
    "H1": {"horizons": (1, 4, 12, 24), "periods": (("train", 2010, 2016), ("validate", 2017, 2020), ("test", 2021, 2025))},
    "M15": {"horizons": (2, 8, 24), "periods": (("train", 2022, 2023), ("validate", 2024, 2024), ("test", 2025, 2025))},
}
ROUND = {"EURUSD": 0.01, "GBPUSD": 0.01, "USDJPY": 1.0, "XAUUSD": 10.0, "BTCUSD": 1000.0}
Q_MAX, MIN_EFFECT, SIGN_SHARE, MIN_SYMBOL_EVENTS = 0.10, 0.05, 0.60, 30


# ---------------------------------------------------------------------------
# indicators (numpy, causal: value at i uses bars <= i)
# ---------------------------------------------------------------------------
def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.empty(len(x))
    k = 2.0 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + k * (x[i] - out[i - 1])
    return out


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = np.empty(len(c)), np.empty(len(c))
    au[0], ad[0] = up[0], dn[0]
    for i in range(1, len(c)):                  # Wilder
        au[i] = au[i - 1] + (up[i] - au[i - 1]) / n
        ad[i] = ad[i - 1] + (dn[i] - ad[i - 1]) / n
    return 100 - 100 / (1 + au / np.where(ad == 0, 1e-12, ad))


def adx(h, l, c, n: int = 14) -> np.ndarray:
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    uh, dl = h - np.roll(h, 1), np.roll(l, 1) - l
    uh[0] = dl[0] = 0
    pdm = np.where((uh > dl) & (uh > 0), uh, 0.0)
    ndm = np.where((dl > uh) & (dl > 0), dl, 0.0)
    a, p, m = ema(tr, 2 * n - 1), ema(pdm, 2 * n - 1), ema(ndm, 2 * n - 1)
    pdi, ndi = 100 * p / np.where(a == 0, 1e-12, a), 100 * m / np.where(a == 0, 1e-12, a)
    dx = 100 * abs(pdi - ndi) / np.where(pdi + ndi == 0, 1e-12, pdi + ndi)
    return ema(dx, 2 * n - 1)


def rolling_max(x: np.ndarray, n: int) -> np.ndarray:
    """max of x[i-n+1 .. i]"""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(len(x), np.nan)
    out[n - 1:] = sliding_window_view(x, n).max(axis=1)
    return out


def rolling_min(x: np.ndarray, n: int) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(len(x), np.nan)
    out[n - 1:] = sliding_window_view(x, n).min(axis=1)
    return out


def shift(x: np.ndarray, k: int = 1, fill=np.nan) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    if k > 0:
        out[:k] = fill
        out[k:] = x[:-k]
    else:
        out[:] = x
    return out


def run_length(cond: np.ndarray) -> np.ndarray:
    """number of consecutive True values ending at i"""
    out = np.zeros(len(cond), dtype=int)
    for i in range(len(cond)):
        out[i] = out[i - 1] + 1 if cond[i] and i > 0 else (1 if cond[i] else 0)
    return out


def slopes(x: np.ndarray, n: int) -> np.ndarray:
    """OLS slope of x over the last n bars and the fitted value at i."""
    from numpy.lib.stride_tricks import sliding_window_view
    t = np.arange(n) - (n - 1) / 2
    sl, fit = np.full(len(x), np.nan), np.full(len(x), np.nan)
    w = sliding_window_view(x, n)
    b = (w * t).sum(axis=1) / (t * t).sum()
    sl[n - 1:] = b
    fit[n - 1:] = w.mean(axis=1) + b * (n - 1) / 2
    return sl, fit


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load(symbol: str, tf: str) -> dict | None:
    if not (context.DATA / f"bars_{symbol}_{tf}.csv").exists():
        return None
    bars = context.load_bars(symbol, tf)
    m = context.meta()
    now_off, now = int(m["server_offset_now"]), int(m["exported_at_utc"])
    t = np.array([b["time"] for b in bars], dtype=np.int64)
    utc = np.array([x - context.server_offset_at(x - now_off, now_off, now) for x in t], dtype=np.int64)
    d = {"symbol": symbol, "tf": tf, "time": t, "utc": utc}
    for k in ("open", "high", "low", "close", "spread"):
        d[k] = np.array([b[k] for b in bars], dtype=float)
    o, h, l, c = d["open"], d["high"], d["low"], d["close"]
    pc = shift(c, 1, c[0])
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    d["atr"] = sma(tr, 14)
    point = float(m["by_symbol"][symbol]["point"])
    d["cost"] = (d["spread"] * point + replay.COMMISSION.get(symbol, 0.0)) / np.where(d["atr"] > 0, d["atr"], np.nan)
    d["hour"] = (utc % 86400) // 3600
    d["day"] = utc // 86400
    d["dow"] = (d["day"] + 3) % 7                 # 0 = Monday (1970-01-01 was a Thursday)
    d["year"] = np.array([datetime.fromtimestamp(int(x), timezone.utc).year for x in utc])
    if tf == "H1":
        tv = context.DATA / f"tickvol_{symbol}_H1.csv"
        vol = {}
        if tv.exists():
            for line in tv.read_text(encoding="utf-8").splitlines()[1:]:
                a, b = line.split(",")
                vol[int(a)] = int(b)
        d["tickvol"] = np.array([vol.get(int(x), 0) for x in t], dtype=float)
    return d


# ---------------------------------------------------------------------------
# factors: name -> (event mask, direction array)
# ---------------------------------------------------------------------------
def factors(d: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    o, h, l, c, atr, hour, dow, day = d["open"], d["high"], d["low"], d["close"], d["atr"], d["hour"], d["dow"], d["day"]
    n = len(c)
    ok = np.isfinite(atr) & (atr > 0)
    ones = np.ones(n)
    body = np.sign(c - o)
    rng = h - l
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for hh in range(24):
        out[f"HOUR_{hh:02d}"] = (ok & (hour == hh) & (d["time"] % 3600 == 0), ones)   # the bar opening at hh:00

    # --- day level (first bar of the UTC day) ---
    first = np.r_[True, day[1:] != day[:-1]]
    day_ids, idx_first = np.unique(day, return_index=True)
    day_open = dict(zip(day_ids, o[idx_first]))
    last_idx = np.r_[idx_first[1:] - 1, n - 1]
    day_close = dict(zip(day_ids, c[last_idx]))
    # Friday before a Monday = day - 3
    fri_body = np.array([np.sign(day_close.get(x - 3, np.nan) - day_open.get(x - 3, np.nan)) if (x - 3) in day_open else 0.0
                         for x in day])
    out["MON"] = (ok & first & (dow == 0), ones)
    out["FRI"] = (ok & first & (dow == 4), ones)
    out["MON_AFTER_RED_FRI"] = (ok & first & (dow == 0) & (fri_body < 0), ones)          # d = up (reversal of red)
    out["MON_AFTER_GREEN_FRI"] = (ok & first & (dow == 0) & (fri_body > 0), -ones)
    week_move = np.array([np.sign(day_close.get(x - 1, np.nan) - day_open.get(x - 4, np.nan))
                          if (x - 4) in day_open and (x - 1) in day_close else 0.0 for x in day])
    out["FRI_FADE_WEEK"] = (ok & first & (dow == 4) & (week_move != 0), -week_move)
    fri_close = np.array([day_close.get(x - 3, np.nan) for x in day])
    gap = (o - fri_close) / np.where(ok, atr, np.nan)
    out["MON_GAP_FILL"] = (ok & first & (dow == 0) & (abs(np.nan_to_num(gap)) >= 0.3), -np.sign(np.nan_to_num(gap)))

    # --- sessions ---
    asia_hi = np.full(n, np.nan)
    asia_lo = np.full(n, np.nan)
    london_open = np.full(n, np.nan)
    cur_day, hi, lo, lo_open = None, -np.inf, np.inf, np.nan
    for i in range(n):
        if day[i] != cur_day:
            cur_day, hi, lo, lo_open = day[i], -np.inf, np.inf, np.nan
        if hour[i] < 7:
            hi, lo = max(hi, h[i]), min(lo, l[i])
        elif np.isnan(lo_open):
            lo_open = o[i]
        if hour[i] >= 7 and np.isfinite(hi):
            asia_hi[i], asia_lo[i], london_open[i] = hi, lo, lo_open
    pc = shift(c, 1)
    brk_up = (c > asia_hi) & ~(pc > asia_hi)
    brk_dn = (c < asia_lo) & ~(pc < asia_lo)
    win = (hour >= 7) & (hour < 10)
    out["ASIA_BREAK"] = (ok & win & (brk_up | brk_dn), np.where(brk_up, 1.0, -1.0))
    is16 = (hour == 16) & (d["time"] % 3600 == 0)
    mv = np.sign(c - london_open)
    out["NY_FADE_16"] = (ok & is16 & np.isfinite(london_open) & (mv != 0), -mv)
    out["OVERLAP_MOM"] = (ok & (hour >= 12) & (hour < 16) & (body != 0), body)

    # --- round numbers ---
    step = ROUND[d["symbol"]]
    lvl_up = np.floor(np.nan_to_num(pc) / step + 1) * step          # first round level above the previous close
    lvl_dn = np.ceil(np.nan_to_num(pc) / step - 1) * step
    touch_up = h >= lvl_up
    touch_dn = l <= lvl_dn
    out["ROUND_REJECT"] = (ok & ((touch_up & (c < lvl_up)) ^ (touch_dn & (c > lvl_dn))),
                           np.where(touch_up & (c < lvl_up), -1.0, 1.0))
    out["ROUND_BREAK"] = (ok & ((c > lvl_up) ^ (c < lvl_dn)), np.where(c > lvl_up, 1.0, -1.0))

    # --- streaks and pressure ---
    up_run, dn_run = run_length(body > 0), run_length(body < 0)
    for k in (4, 5, 6):
        out[f"STREAK_{k}"] = (ok & ((up_run == k) | (dn_run == k)), np.where(up_run == k, 1.0, -1.0))
    pos = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1), 0.5)
    big = rng >= 0.5 * np.nan_to_num(atr)
    pr_up, pr_dn = run_length((pos >= 0.75) & big), run_length((pos <= 0.25) & big)
    for k in (3, 4):
        out[f"PRESSURE_{k}"] = (ok & ((pr_up == k) | (pr_dn == k)), np.where(pr_up == k, 1.0, -1.0))

    # --- sideways box (24 bars before i) ---
    bh, bl = shift(rolling_max(h, 24)), shift(rolling_min(l, 24))
    narrow = (bh - bl) <= 2.0 * atr
    out["RANGE_BREAK"] = (ok & narrow & ((c > bh) | (c < bl)), np.where(c > bh, 1.0, -1.0))
    fade_hi = narrow & (h >= bh) & (c <= bh) & (c >= bl)
    fade_lo = narrow & (l <= bl) & (c >= bl) & (c <= bh)
    out["RANGE_FADE"] = (ok & (fade_hi ^ fade_lo), np.where(fade_hi, -1.0, 1.0))

    # --- wedges (30 bars before i) ---
    sh, _ = slopes(shift(h, 1, h[0]), 30)
    sl, fit_l = slopes(shift(l, 1, l[0]), 30)
    _, fit_h = slopes(shift(h, 1, h[0]), 30)
    rising = (sl > sh) & (sh > 0)
    falling = (sh < sl) & (sl < 0)
    out["RISING_WEDGE_BREAK"] = (ok & rising & (c < fit_l + sl) & (pc >= shift(fit_l + sl)), -ones)
    out["FALLING_WEDGE_BREAK"] = (ok & falling & (c > fit_h + sh) & (pc <= shift(fit_h + sh)), ones)

    # --- previous day high / low sweep ---
    pdh = np.array([0.0] * n)
    pdl = np.array([0.0] * n)
    day_hi = {x: h[idx_first[k]:last_idx[k] + 1].max() for k, x in enumerate(day_ids)}
    day_lo = {x: l[idx_first[k]:last_idx[k] + 1].min() for k, x in enumerate(day_ids)}
    prev = {x: day_ids[k - 1] for k, x in enumerate(day_ids) if k > 0}
    for i in range(n):
        p = prev.get(day[i])
        pdh[i], pdl[i] = (day_hi[p], day_lo[p]) if p is not None else (np.nan, np.nan)
    sw_hi = (h > pdh) & (c < pdh)
    sw_lo = (l < pdl) & (c > pdl)
    out["PDHL_SWEEP"] = (ok & (sw_hi ^ sw_lo), np.where(sw_hi, -1.0, 1.0))

    # --- indicators ---
    r = rsi(c)
    pr = shift(r)
    up30, dn70 = (pr < 30) & (r >= 30), (pr > 70) & (r <= 70)
    out["RSI_REVERT"] = (ok & (up30 | dn70), np.where(up30, 1.0, -1.0))
    mid, sd = sma(c, 20), np.sqrt(np.maximum(sma(c * c, 20) - sma(c, 20) ** 2, 0))
    width = 4 * sd / np.where(mid == 0, 1, mid)
    from numpy.lib.stride_tricks import sliding_window_view
    pct = np.full(n, np.nan)
    wv = sliding_window_view(width, 120)
    pct[119:] = (wv < wv[:, -1:]).mean(axis=1)
    sq = shift(pct) < 0.10
    ub, lb = mid + 2 * sd, mid - 2 * sd
    out["BB_SQUEEZE_BREAK"] = (ok & sq & ((c > ub) | (c < lb)), np.where(c > ub, 1.0, -1.0))
    macd = ema(c, 12) - ema(c, 26)
    hist = macd - ema(macd, 9)
    e200 = ema(c, 200)
    flip_up = (shift(hist) <= 0) & (hist > 0) & (c > e200)
    flip_dn = (shift(hist) >= 0) & (hist < 0) & (c < e200)
    out["MACD_FLIP_TREND"] = (ok & (flip_up | flip_dn), np.where(flip_up, 1.0, -1.0))
    a = adx(h, l, c)
    e20, e50 = ema(c, 20), ema(c, 50)
    pb_up = (a > 25) & (e20 > e50) & (l <= e20) & (c > e20)
    pb_dn = (a > 25) & (e20 < e50) & (h >= e20) & (c < e20)
    out["ADX_PULLBACK"] = (ok & (pb_up ^ pb_dn), np.where(pb_up, 1.0, -1.0))
    nr7 = rng <= rolling_min(rng, 7)
    prev_nr7 = shift(nr7.astype(float)) == 1
    ph, plo = shift(h), shift(l)
    out["NR7_BREAK"] = (ok & prev_nr7 & ((c > ph) ^ (c < plo)), np.where(c > ph, 1.0, -1.0))
    if "tickvol" in d:
        tv = d["tickvol"]
        base = shift(sma(tv, 24))
        out["VOL_SPIKE"] = (ok & (tv > 2.5 * base) & (body != 0) & (base > 0), body)
        # last trading day of the month, 15-16 UTC (London fix)
        months = np.array([datetime.fromtimestamp(int(x), timezone.utc).strftime("%Y%m") for x in d["utc"]])
        mday = {}
        for k in range(n):
            mday[months[k]] = day[k]
        last_day = np.array([day[k] == mday[months[k]] for k in range(n)])
        out["MONTH_END_FIX"] = (ok & last_day & ((hour == 15) | (hour == 16)) & (d["time"] % 3600 == 0), ones)
    return out


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def forward(d: dict, k: int) -> tuple[np.ndarray, np.ndarray]:
    """raw forward move in ATR units and its value net of costs"""
    c, atr = d["close"], d["atr"]
    f = np.full(len(c), np.nan)
    f[:-k] = (c[k:] - c[:-k]) / np.where(atr[:-k] > 0, atr[:-k], np.nan)
    return f, d["cost"]


def period_mask(d: dict, a: int, b: int) -> np.ndarray:
    return (d["year"] >= a) & (d["year"] <= b)


def cluster_stats(vals: np.ndarray, sym: np.ndarray, days: np.ndarray) -> tuple[float, float, int, int]:
    """mean of (symbol, day) cluster means, t-test p (two-sided), clusters, events"""
    if len(vals) == 0:
        return 0.0, 1.0, 0, 0
    key = sym.astype(np.int64) * 10 ** 7 + days.astype(np.int64)
    uniq, inv = np.unique(key, return_inverse=True)
    sums = np.bincount(inv, weights=vals)
    cnt = np.bincount(inv)
    m = sums / cnt
    if len(m) < 3:
        return float(m.mean()), 1.0, len(m), len(vals)
    t = m.mean() / (m.std(ddof=1) / math.sqrt(len(m))) if m.std(ddof=1) > 0 else 0.0
    p = 2 * sst.t.sf(abs(t), len(m) - 1)
    return float(m.mean()), float(p), len(m), len(vals)


def cluster_mean(vals: np.ndarray, sym: np.ndarray, days: np.ndarray) -> float:
    """the same (symbol, day) clustering as cluster_stats, for the gross move and the cost"""
    if len(vals) == 0:
        return 0.0
    key = sym.astype(np.int64) * 10 ** 7 + days.astype(np.int64)
    _, inv = np.unique(key, return_inverse=True)
    return float((np.bincount(inv, weights=vals) / np.bincount(inv)).mean())


def bh(pvals: list[float]) -> list[float]:
    p = np.array(pvals)
    order = np.argsort(p)
    q = np.empty(len(p))
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[i] * len(p) / rank)
        q[i] = prev
    return q.tolist()


def atlas(tf: str) -> list[dict]:
    spec = TF[tf]
    data = [x for x in (load(s, tf) for s in SYMBOLS) if x is not None]
    rows: dict[tuple[str, int], dict] = {}
    for si, d in enumerate(data):
        fac = factors(d)
        for k in spec["horizons"]:
            f, cost = forward(d, k)
            for pname, a, b in spec["periods"]:
                pm = period_mask(d, a, b) & np.isfinite(f)
                drift = np.nanmean(f[pm]) if pm.any() else 0.0
                for name, (mask, dirn) in fac.items():
                    ev = mask & pm & np.isfinite(f)
                    if not ev.any():
                        continue
                    sig = dirn[ev] * f[ev]
                    adj = sig - dirn[ev] * drift
                    r = rows.setdefault((name, k), {"factor": name, "tf": tf, "h": k, "periods": {}})
                    pr = r["periods"].setdefault(pname, {"adj": [], "gross": [], "cost": [], "sym": [], "day": []})
                    pr["adj"].append(adj); pr["gross"].append(sig); pr["cost"].append(np.nan_to_num(cost[ev]))
                    pr["sym"].append(np.full(len(adj), si)); pr["day"].append(d["day"][ev])
    out = []
    for (name, k), r in rows.items():
        res = {"factor": name, "tf": tf, "h": k}
        for pname, pr in r["periods"].items():
            adj, gross, cst = np.concatenate(pr["adj"]), np.concatenate(pr["gross"]), np.concatenate(pr["cost"])
            sym, days = np.concatenate(pr["sym"]), np.concatenate(pr["day"])
            mean, p, ncl, nev = cluster_stats(adj, sym, days)
            per_sym = [float(adj[sym == s].mean()) for s in np.unique(sym) if (sym == s).sum() >= MIN_SYMBOL_EVENTS]
            # G56 fix (before any setup): the net uses the same (symbol, day) clusters as the statistic, i.e. each
            # day's events share one unit of risk; the event-level mean let days with many events dominate.
            res[pname] = {"mean": mean, "p": p, "clusters": ncl, "events": nev,
                          "gross": cluster_mean(gross, sym, days), "cost": cluster_mean(cst, sym, days),
                          "gross_events": float(gross.mean()), "sym_means": per_sym}
        out.append(res)
    train = [r for r in out if "train" in r]
    qs = bh([r["train"]["p"] for r in train])
    for r, q in zip(train, qs):
        r["q"] = q
        t = r["train"]
        sign = math.copysign(1, t["mean"]) if t["mean"] != 0 else 0
        share = (sum(1 for m in t["sym_means"] if m * sign > 0) / len(t["sym_means"])) if t["sym_means"] else 0
        r["sign"] = sign
        r["selected"] = bool(q < Q_MAX and abs(t["mean"]) >= MIN_EFFECT and share >= SIGN_SHARE)
        v, te = r.get("validate"), r.get("test")
        for per in (v, te):
            if per:
                per["net"] = sign * per["gross"] - per["cost"]       # trading the selected side pays the cost
        r["survived"] = bool(r["selected"] and v and te and v["mean"] * sign > 0 and v["p"] / 2 < 0.10 and
                             te["mean"] * sign > 0 and v["net"] > 0 and te["net"] > 0)
    return out


def main(argv: list[str]) -> None:
    result = {}
    lines = ["# G56 A: bản đồ yếu tố (chỉ dữ liệu MT5)", "",
             "Kế hoạch: `docs/superpowers/plans/2026-10-07-g56-factor-atlas.md` (đăng ký trước). Hiệu ứng = lợi nhuận tiến "
             "theo hướng giả thuyết, đơn vị ATR, đã trừ trôi giá; dấu âm = chiều ngược lại. q = Benjamini–Hochberg trên train.", ""]
    for tf in ("H1", "M15"):
        rows = atlas(tf)
        result[tf] = rows
        tested = len([r for r in rows if "q" in r])
        sel = [r for r in rows if r.get("selected")]
        surv = [r for r in rows if r.get("survived")]
        lines += [f"## {tf}: {tested} phép thử, chọn trên train {len(sel)}, sống sót validate + test + chi phí {len(surv)}", "",
                  "| Yếu tố | Tầm | Hướng | Train (q) | Validate (p) | Test | Sau phí val / test | Sống sót |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in sorted(sel, key=lambda r: r["q"]):
            t, v, te = r["train"], r.get("validate", {}), r.get("test", {})
            side = "theo giả thuyết" if r["sign"] > 0 else "ngược giả thuyết"
            lines.append(f"| {r['factor']} | {r['h']} | {side} | {t['mean']:+.3f} ({r['q']:.3f}) | "
                         f"{v.get('mean', 0):+.3f} ({v.get('p', 1):.3f}) | {te.get('mean', 0):+.3f} | "
                         f"{v.get('net', 0):+.3f} / {te.get('net', 0):+.3f} | {'**CÓ**' if r['survived'] else 'không'} |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "factor_atlas.md").write_text(text, encoding="utf-8")
    (ls.OUT / "factor_atlas.json").write_text(json.dumps(result, default=float), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
