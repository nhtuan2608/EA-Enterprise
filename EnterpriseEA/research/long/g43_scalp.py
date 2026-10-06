"""G43 part E: SCALP / intraday on M15, held to the same controls as SWING. MT5 data only.

  python g43_scalp.py

Data: M15 of the five original symbols 2021-10 .. 2025-10 (BTCUSD from 2022-10); chosen on 2021-10 .. 2023-06,
validated on 2023-07 .. 2024-06 and tested on 2024-07 .. 2025-10. Out-of-sample by symbol: 12 FX pairs and
XAG/ETH/oil/SP500 on M15 2024-02 .. 2026-10, never used for a choice. Costs: the bar's spread (entry at the ask
for a long, exits through pyramid.walk) and commission per leg (replay.COMMISSION; the extra FX pairs get the
EURUSD / USDJPY rate). One open trade per symbol and family; time stop in bars.
Families (trend side = previous day's close vs the D1 EMA50, the trend edge is the one that held in G38):
  E1  pullback in the D1 trend: close back beyond the M15 EMA20 after a pullback that touched it, stop beyond the
      lowest low / highest high of the last 6 bars (at least 0.5 ATR), fixed R or ATR trail, time stop
  E2  compression -> expansion on M15 (the S06B idea): N-bar box narrower than k x ATR x sqrt(N), close outside
      the box in the D1 trend direction (or any), stop at the far side of the box, fixed R
  E3  break of the previous day's high / low in the D1 trend direction between 07 and 16 UTC, stop 1.5 ATR,
      fixed R or ATR trail, out by the time stop
Checks for the best set of each family (by train expectancy, at least 80 train trades): positive in validate and
test, random entries (same stop, same exit, 300 runs), neighbours, out-of-sample symbols, commission x2 + 0.1R.
"""
from __future__ import annotations

import itertools
import statistics
import sys
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402

TF = "M15"
SYMBOLS = ls.SYMBOLS
OOS = dv.NEW + ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
for s in dv.NEW:
    replay.COMMISSION.setdefault(s, 0.009 if s.endswith("JPY") else 0.00006)
VAL = int(datetime(2023, 7, 1, tzinfo=timezone.utc).timestamp())
TST = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp())
OOS_START = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())
RUNS = 300


def grid(d):
    return [dict(zip(d, v)) for v in itertools.product(*d.values())]


def ema(x, n):
    return dv.ema(x, n)


def sig_e1(B, p):
    side = dv.d1_side(B, 50)
    e = B.setdefault("ema20", ema(B["c"], 20))
    c, h, lo, atr = B["c"], B["h"], B["l"], B["atr"]
    out = []
    for i in range(30, len(c)):
        d = side[i]
        if d == 0 or atr[i] <= 0:
            continue
        touched = (lo[i - 3:i] <= e[i - 3:i]).any() if d == 1 else (h[i - 3:i] >= e[i - 3:i]).any()
        crossed = (c[i] > e[i] and c[i - 1] <= e[i - 1]) if d == 1 else (c[i] < e[i] and c[i - 1] >= e[i - 1])
        if touched and crossed:
            ext = lo[i - 6:i + 1].min() if d == 1 else h[i - 6:i + 1].max()
            stop_atr = max(abs(c[i] - ext) / atr[i], p["min_stop"]) + 0.1
            out.append((i, d, stop_atr))
    return out


def sig_e2(B, p):
    side = dv.d1_side(B, 50)
    n = p["n"]
    hi, lo = dv.roll_max(B["h"], n), dv.roll_min(B["l"], n)
    c, atr = B["c"], B["atr"]
    out, last = [], -10 ** 9
    for i in range(n + 1, len(c)):
        if atr[i] <= 0 or np.isnan(hi[i]):
            continue
        width = hi[i] - lo[i]
        if width > p["k"] * atr[i - 1] * n ** 0.5 or i - last < n:
            continue
        d = 1 if c[i] > hi[i] else -1 if c[i] < lo[i] else 0
        if d == 0 or (p["trend"] and side[i] != d):
            continue
        anchor = lo[i] if d == 1 else hi[i]
        out.append((i, d, abs(c[i] - anchor) / atr[i] + 0.1))
        last = i
    return out


def sig_e3(B, p):
    side = dv.d1_side(B, 50)
    day = B["t"] // 86400
    hours = (B["utc"] // 3600) % 24
    c, h, lo, atr = B["c"], B["h"], B["l"], B["atr"]
    out = []
    prev_hi = prev_lo = None
    cur_hi, cur_lo, cur_day, done = -np.inf, np.inf, None, False
    for i in range(len(c)):
        if day[i] != cur_day:
            if cur_day is not None:
                prev_hi, prev_lo = cur_hi, cur_lo
            cur_day, cur_hi, cur_lo, done = day[i], -np.inf, np.inf, False
        if prev_hi is not None and not done and 7 <= hours[i] < 16 and atr[i] > 0:
            d = side[i]
            if d == 1 and c[i] > prev_hi:
                out.append((i, 1, p["stop"])); done = True
            elif d == -1 and c[i] < prev_lo:
                out.append((i, -1, p["stop"])); done = True
        cur_hi, cur_lo = max(cur_hi, h[i]), min(cur_lo, lo[i])
    return out


def rule_of(p):
    if p["exit"] == "trail":
        return {"target": None, "be": None, "partial": None, "trail": ("ATR", 0.0, p.get("trail", 2.0)),
                "timeout": p["timeout"], "struct_exit": False}
    return {"target": p["exit"], "be": None, "partial": None, "trail": None, "timeout": p["timeout"], "struct_exit": False}


FAMILIES = {
    "E1": (sig_e1, grid({"min_stop": [0.5, 1.0], "exit": [1.5, 2.0, 3.0, "trail"], "trail": [2.0], "timeout": [32, 64]})),
    "E2": (sig_e2, grid({"n": [16, 24, 32], "k": [0.6, 0.8], "trend": [True, False], "exit": [2.0, 3.0], "timeout": [48]})),
    "E3": (sig_e3, grid({"stop": [1.0, 1.5, 2.0], "exit": [1.5, 2.0, 3.0, "trail"], "trail": [2.0], "timeout": [32]})),
}


def trades(fam: str, p: dict, symbol: str, start: int = 0) -> list[dict]:
    B = dv.load(symbol, TF)
    if B is None:
        return []
    sig, _ = FAMILIES[fam]
    rule = rule_of(p)
    bars, out, busy = B["bars"], [], -1
    for i, d, stop_atr in sig(B, p):
        if i <= busy or B["utc"][i] < start or i >= len(bars) - 2:
            continue
        b = bars[i]
        entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
        risk = stop_atr * B["atr"][i]
        if risk <= 0:
            continue
        tgt = p["exit"] if p["exit"] != "trail" else 3.0
        t = {"symbol": symbol, "i": i, "dir": d, "entry": entry, "stop": entry - d * risk,
             "target": entry + d * tgt * risk, "zl": 0.0, "zh": 0.0}
        res = pyramid.run(B["ctx"], t, dict(rule, target="plan") if p["exit"] != "trail" else rule)
        busy = res["exit_i"]
        out.append({"symbol": symbol, "utc": int(B["utc"][i]), "i": i, "dir": d, "r": res["r"], "stop_atr": stop_atr,
                    "exit_i": res["exit_i"]})
    return out


def period(u):
    return "train" if u < VAL else "validate" if u < TST else "test"


def stats(rs):
    if not rs:
        return {"n": 0, "exp": 0.0, "rr": 0.0, "win": 0.0}
    w = [r for r in rs if r > 0]
    l_ = [-r for r in rs if r <= 0]
    return {"n": len(rs), "exp": statistics.fmean(rs), "win": len(w) / len(rs),
            "rr": statistics.fmean(w) / statistics.fmean(l_) if w and l_ else 0.0}


def fmt(s):
    return f"{s['exp']:+.3f} (RR {s['rr']:.2f}, {s['win']:.0%}, n={s['n']})" if s["n"] else "n=0"


def scan_job(job):
    fam, p = job
    pyramid.GAP_FILL = True
    rows = [t for s in SYMBOLS for t in trades(fam, p, s)]
    by = {k: stats([t["r"] for t in rows if period(t["utc"]) == k]) for k in ("train", "validate", "test")}
    return {"fam": fam, "p": p, **by, "rows": rows}


def random_job(job):
    fam, p, rows, seed, runs = job
    pyramid.GAP_FILL = True
    rule = rule_of(p)
    rng = np.random.default_rng(seed)
    pools = {}
    for s in SYMBOLS:
        B = dv.load(s, TF)
        days = (B["utc"] // 86400).astype(int)
        ok = np.where((B["atr"] > 0) & (np.arange(len(days)) > 300) & (np.arange(len(days)) < len(days) - 2))[0]
        months = days[ok] // 30
        pools[s] = {m: ok[months == m] for m in np.unique(months)}
    out = []
    for _ in range(runs):
        tot = 0.0
        for x in rows:
            B = dv.load(x["symbol"], TF)
            pool = pools[x["symbol"]].get(int(x["utc"] // 86400) // 30)
            if pool is None or len(pool) == 0:
                continue
            j = int(pool[rng.integers(len(pool))])
            d = 1 if rng.random() < 0.5 else -1
            b = B["bars"][j]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = x["stop_atr"] * B["atr"][j]
            tgt = p["exit"] if p["exit"] != "trail" else 3.0
            t = {"symbol": x["symbol"], "i": j, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * tgt * risk, "zl": 0.0, "zh": 0.0}
            tot += pyramid.run(B["ctx"], t, dict(rule, target="plan") if p["exit"] != "trail" else rule)["r"]
        out.append(tot / len(rows))
    return out


def main() -> None:
    pyramid.GAP_FILL = True
    lines = ["# G43 phần E: SCALP / trong ngày trên M15 (chỉ dữ liệu MT5)", "",
             "Chọn trên 2021-10..2023-06, kiểm chứng 2023-07..2024-06 và 2024-07..2025-10; ngoài mẫu: 16 symbol khác 2024–2026.", ""]
    jobs = [(f, p) for f, (_, g) in FAMILIES.items() for p in g]
    with Pool(12) as pool:
        res = pool.map(scan_job, jobs)
        lines += ["## 1. Quét", "", "| Họ | Bộ dương cả 3 kỳ | Bộ chọn | Train | Validate | Test |", "|---|---|---|---|---|---|"]
        best = {}
        for f in FAMILIES:
            rs = [r for r in res if r["fam"] == f]
            pos = sum(1 for r in rs if all(r[k]["exp"] > 0 and r[k]["n"] > 0 for k in ("train", "validate", "test")))
            cand = [r for r in rs if r["train"]["n"] >= 80] or rs
            b = max(cand, key=lambda r: r["train"]["exp"])
            best[f] = b
            lines.append(f"| {f} | {pos}/{len(rs)} | {b['p']} | {fmt(b['train'])} | {fmt(b['validate'])} | {fmt(b['test'])} |")
        lines += ["", "## 2. Kiểm chứng bộ chọn", "",
                  "| Họ | Ngẫu nhiên p | Phí ×2 + trượt 0,1R (tất cả) | Ngoài mẫu 16 symbol | Theo symbol (tất cả kỳ) |", "|---|---|---|---|---|"]
        for f, b in best.items():
            rows = b["rows"]
            real = statistics.fmean(t["r"] for t in rows) if rows else 0.0
            sims = [v for ch in pool.map(random_job, [(f, b["p"], rows, 4300 + k, RUNS // 10) for k in range(10)]) for v in ch]
            p_rand = float(np.mean(np.array(sims) >= real)) if sims else 1.0
            fee = []
            for t in rows:
                B = dv.load(t["symbol"], TF)
                risk = t["stop_atr"] * B["atr"][t["i"]]
                fee.append(t["r"] - replay.COMMISSION.get(t["symbol"], 0.0) / max(risk, 1e-12) - 0.1)
            oos = [t["r"] for s in OOS for t in trades(f, b["p"], s, OOS_START)]
            per_sym = ", ".join(f"{s} {statistics.fmean([t['r'] for t in rows if t['symbol'] == s]):+.2f}"
                                for s in SYMBOLS if any(t["symbol"] == s for t in rows))
            lines.append(f"| {f} | {p_rand:.3f} | {statistics.fmean(fee) if fee else 0:+.3f} | {fmt(stats(oos))} | {per_sym} |")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "g43_scalp.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
