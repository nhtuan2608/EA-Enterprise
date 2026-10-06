"""G37 part 2: calibrate the edge monitor (research/g10/edge_monitor.py) on the research trades. MT5 data only.

  python edge_calibrate.py

Streams (SWING H1 2010-2025, current Trade Manager, gap fills): S04, S06B with the USD flow, and the same
with the +1R add. For each stream, from its own trade results (in R):
  CUSUM     downward CUSUM S_n = max(0, S_{n-1} + k - r_n), k = mean/2 (half way between the research
            mean and zero). h_alarm: smallest h whose mean run length to a false alarm, on trades drawn
            from the research results, is at least 250 trades; h_warn: at least 60 trades. Detection
            delay is measured on the same trades shifted to a mean of 0 and of -0.1R.
  DRAWDOWN  95th and 99th percentile of the largest drawdown (R) after n trades, n = 5 .. 300, drawn
            from the research results: a live drawdown beyond the 99th percentile is not bad luck.
Writes research/g10/edge_params.json, read by the monitor.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import pyramid  # noqa: E402
import discovery  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "g10" / "edge_params.json"
SIMS = 4000
CAP = 1500
DD_N = [5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300]


def run_length(r: np.ndarray, k: float, h: float) -> np.ndarray:
    """Trades until the downward CUSUM first exceeds h, per row of r (CAP when never)."""
    s = np.zeros(r.shape[0])
    out = np.full(r.shape[0], CAP)
    alive = np.ones(r.shape[0], dtype=bool)
    for n in range(r.shape[1]):
        s = np.maximum(0.0, s + k - r[:, n])
        hit = alive & (s > h)
        out[hit] = n + 1
        alive &= ~hit
        if not alive.any():
            break
    return out


def calibrate(r: np.ndarray, rng) -> dict:
    mu, sd = float(r.mean()), float(r.std(ddof=1))
    k = mu / 2
    draws = rng.choice(r, size=(SIMS, CAP))
    hs = np.arange(0.5, 40.01, 0.5)
    arl0 = {}
    for h in hs:
        rl = run_length(draws, k, h)
        arl0[float(h)] = float(rl.mean())
        if rl.mean() >= 250:
            break
    h_alarm = next(h for h, v in arl0.items() if v >= 250)
    h_warn = next(h for h, v in arl0.items() if v >= 60)
    det = {}
    for shift, label in ((mu, "mean_0"), (mu + 0.1, "mean_-0.1")):
        rl = run_length(draws - shift, k, h_alarm)
        det[label] = {"median": float(np.median(rl)), "p90": float(np.quantile(rl, 0.9))}
        rlw = run_length(draws - shift, k, h_warn)
        det[label]["warn_median"] = float(np.median(rlw))
    dd = {}
    for n in DD_N:
        eq = np.cumsum(draws[:, :n], axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.zeros((SIMS, 1)), eq], axis=1), axis=1)[:, 1:]
        mdd = (peak - eq).max(axis=1)
        dd[n] = {"p95": float(np.quantile(mdd, 0.95)), "p99": float(np.quantile(mdd, 0.99))}
    return {"n": int(len(r)), "mean": mu, "sd": sd, "k": k, "h_warn": h_warn, "h_alarm": h_alarm,
            "arl0_warn": arl0[h_warn], "arl0_alarm": arl0[h_alarm], "detection": det, "drawdown": dd}


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    streams = {
        "S04_SWING": [pyramid.run(c[t["symbol"]], t, pyramid.CURRENT)["r"] for t in sig["S04"]],
        "S06B_SWING_USD": [pyramid.run(c[t["symbol"]], t, pyramid.CURRENT)["r"] for t in sig["S06B_USD"]],
        "S06B_SWING_USD_ADD": [pyramid.run(c[t["symbol"]], t, pyramid.CURRENT, 1.0)["r"] for t in sig["S06B_USD"]],
        # G38: T2 as chosen by discovery.py (H4 Donchian 60, D1 EMA200 side, stop 2 ATR, ATR trail 3)
        "T2_POSITION": [t["r"] for s in ls.SYMBOLS for t in discovery.trades(
            "T2", {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}, s)],
        # G41: T2 on the trend assets it may trade live (InpT2LiveSymbols default)
        "T2_POSITION_TREND": [t["r"] for s in ("XAUUSD", "BTCUSD") for t in discovery.trades(
            "T2", {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}, s)],
    }
    rng = np.random.default_rng(37)
    params = {"version": "edge-params-v1", "source": "research/long/edge_calibrate.py (G37)",
              "streams": {k: calibrate(np.array(v), rng) for k, v in streams.items()}}
    OUT.write_text(json.dumps(params, indent=1), encoding="utf-8")
    for k, p in params["streams"].items():
        d0 = p["detection"]["mean_0"]
        print(f"{k}: n={p['n']} mean={p['mean']:+.3f} sd={p['sd']:.2f} k={p['k']:.3f} h_warn={p['h_warn']} "
              f"h_alarm={p['h_alarm']} ARL0={p['arl0_alarm']:.0f} | edge gone: alarm after median {d0['median']:.0f} "
              f"(p90 {d0['p90']:.0f}), warn {d0['warn_median']:.0f} | DD99 n=20 {p['drawdown'][20]['p99']:.1f}R "
              f"n=50 {p['drawdown'][50]['p99']:.1f}R")


if __name__ == "__main__":
    main()
