"""G27 (step 3): intermarket and regime filters, single and in pairs, per setup and per symbol,
chosen for steadiness ("middle way": modest, even, low risk) on 2010-2016 only.

  python filters.py

Base signals (SWING H1, research/long data, same models as G23):
  S04, S06 (live config), S06B (24-bar box, entry on release), S02 (MARKET only),
  S02INV (S02 reversed: fade the break, stop 1.5 ATR, target 2R)
Filters, using only what is known at the entry bar's close:
  ADX_LOW (ADX14 H1 < 20), ADX_HIGH (> 25), D1_TREND (side of EMA200 on closed daily bars),
  USD_FLOW (side of a USD index built from EURUSD, GBPUSD, USDJPY vs its EMA50 on H1),
  VOL_MID (ATR not in its lowest or highest third)
Every filter alone and every pair is applied to all symbols and to each symbol.
Selection on TRAIN (2010-2016): expectancy > 0, then share of positive years, then max drawdown,
then return / drawdown; VALIDATE (2017-2020) and TEST (2021-2025) are reported, never used to
choose. A filter must also beat random removal of the same share of trades (90th percentile).
The real DXY (from 2021-09) is reported as a check of USD_FLOW on 2021-2025. US10Y (from 2024)
is too short to validate and is not used.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import long_study as ls  # sets the data path and sys.path first
import context  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

FILTERS = ["ADX_LOW", "ADX_HIGH", "D1_TREND", "USD_FLOW", "VOL_MID"]
USD_SIGN = {"EURUSD": -1, "GBPUSD": -1, "XAUUSD": -1, "BTCUSD": -1, "USDJPY": 1}
S06B = {"box": 24, "max_box_atr": 3.0, "contraction": 0.85, "mode": "immediate", "sl": "far"}


def ema(values: list[float], n: int) -> list[float]:
    out, k, e = [], 2.0 / (n + 1), None
    for v in values:
        e = v if e is None else e + k * (v - e)
        out.append(e)
    return out


def adx(bars: list[dict], n: int = 14) -> list[float]:
    """Wilder ADX on the entry bars (value at each bar's close)."""
    out = [0.0] * len(bars)
    tr_s = pdm_s = mdm_s = 0.0
    dx_s = None
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        up, dn = h - bars[i - 1]["high"], bars[i - 1]["low"] - l
        pdm = up if up > dn and up > 0 else 0.0
        mdm = dn if dn > up and dn > 0 else 0.0
        tr = max(h, pc) - min(l, pc)
        tr_s, pdm_s, mdm_s = tr_s - tr_s / n + tr, pdm_s - pdm_s / n + pdm, mdm_s - mdm_s / n + mdm
        if i < n or tr_s <= 0:
            continue
        pdi, mdi = 100 * pdm_s / tr_s, 100 * mdm_s / tr_s
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi > 0 else 0.0
        dx_s = dx if dx_s is None else dx_s + (dx - dx_s) / n
        out[i] = dx_s
    return out


def d1_trend(bars: list[dict]) -> list[int]:
    """+1 / -1: previous closed day's close above / below the EMA200 of daily closes."""
    days, closes = [], []
    for b in bars:
        d = b["time"] // 86400
        if days and days[-1] == d:
            closes[-1] = b["close"]
        else:
            days.append(d)
            closes.append(b["close"])
    e = ema(closes, 200)
    sign_by_day = {}
    for k in range(1, len(days)):
        sign_by_day[days[k]] = 1 if closes[k - 1] > e[k - 1] else -1 if k - 1 >= 199 else 0
    return [sign_by_day.get(b["time"] // 86400, 0) for b in bars]


def usd_index() -> dict:
    """time -> +1 / -1: USD index (mean of -log EURUSD, -log GBPUSD, +log USDJPY) vs its EMA50 (H1)."""
    series = {}
    for s, sgn in (("EURUSD", -1), ("GBPUSD", -1), ("USDJPY", 1)):
        for b in context.load_bars(s, "H1"):
            series.setdefault(b["time"], {})[s] = sgn * math.log(b["close"])
    times = sorted(t for t, v in series.items() if len(v) == 3)
    values = [sum(series[t].values()) / 3 for t in times]
    e = ema(values, 50)
    return {t: (1 if v > m else -1) for t, v, m in zip(times, values, e)}


def real_dxy() -> dict:
    path = context.DATA / "bars_DXY_H1.csv"
    if not path.exists():
        return {}
    bars = context.load_bars("DXY", "H1")
    e = ema([b["close"] for b in bars], 50)
    return {b["time"]: (1 if b["close"] > m else -1) for b, m in zip(bars, e)}


def base_rows(name: str, symbol: str) -> list[dict]:
    c = ls.ctx(symbol, "SWING")
    if c is None:
        return []
    if name == "S04":
        rows = [(x, replay.evaluate(c, x, "S04", "SWING", "tm", {"costs": True}))
                for x in replay.candidates(c, "S04", replay.engine_params("S04", "SWING"))]
    elif name in ("S06", "S06B"):
        p = ls.S06_LIVE if name == "S06" else S06B
        t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "aligned" if name == "S06" else "any", "costs": True}
        rows = [(x, replay.evaluate(c, x, "S06", "SWING", "tm", t)) for x in setups.s06(c, p)]
    else:
        cands = [x for x in replay.candidates(c, "S02", replay.engine_params("S02", "SWING")) if x.get("kind") != "LIMIT"]
        if name == "S02":
            rows = [(x, replay.evaluate(c, x, "S02", "SWING", "tm", {"costs": True})) for x in cands]
        else:   # S02INV: fade the break
            rows = []
            for x in cands:
                b = c["entry"][x["i"]]
                d = -x["direction"]
                y = dict(x, direction=d, extreme=b["close"] - d * 1.5 * x["signal_atr"])
                rows.append((y, replay.evaluate(c, y, "S02INV", "SWING", "tm",
                                                {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0, "costs": True})))
    bars = c["entry"]
    shift = bars[0]["time"] - bars[0]["utc"]
    out = []
    for x, r in rows:
        if r["status"] != "EVALUATED":
            continue
        out.append({"symbol": symbol, "i": x["i"], "time": bars[x["i"]]["time"], "utc": bars[x["i"]]["time"] - shift,
                    "dir": x["direction"], "r": r["r"]})
    return out


def tag(rows: list[dict], symbol: str, usd: dict, dxy: dict) -> None:
    c = ls.ctx(symbol, "SWING")
    bars = c["entry"]
    a = adx(bars)
    trend = d1_trend(bars)
    atrs = sorted(b["atr"] for b in bars if b["atr"] > 0)
    q1, q2 = atrs[len(atrs) // 3], atrs[2 * len(atrs) // 3]
    for t in rows:
        i, d = t["i"], t["dir"]
        flow = usd.get(t["time"], 0)
        t["f"] = {"ADX_LOW": a[i] < 20, "ADX_HIGH": a[i] > 25, "D1_TREND": trend[i] == d,
                  "USD_FLOW": flow != 0 and d * USD_SIGN[symbol] == flow,
                  "VOL_MID": q1 < bars[i]["atr"] <= q2}
        real = dxy.get(t["time"], 0)
        t["dxy_ok"] = None if real == 0 else d * USD_SIGN[symbol] == real


def period(utc: int) -> str:
    return "train" if utc < ls.VALIDATE else "validate" if utc < ls.TEST else "test"


def stats(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "exp": 0.0, "pos_years": 0.0, "dd": 0.0, "ret_dd": 0.0, "month_sd": 0.0}
    rows = sorted(rows, key=lambda t: t["utc"])
    eq = peak = dd = 0.0
    years, months = defaultdict(float), defaultdict(float)
    for t in rows:
        eq += t["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        dt = datetime.fromtimestamp(t["utc"], timezone.utc)
        years[dt.year] += t["r"]
        months[(dt.year, dt.month)] += t["r"]
    total = sum(t["r"] for t in rows)
    return {"n": len(rows), "exp": total / len(rows), "total": total,
            "pos_years": sum(1 for v in years.values() if v > 0) / len(years), "dd": dd,
            "ret_dd": total / dd if dd > 0 else float("inf") if total > 0 else 0.0,
            "month_sd": statistics.pstdev(months.values()) if len(months) > 1 else 0.0}


def random_p90(pool: list[dict], keep: int, seed: int) -> float:
    if keep == 0 or keep >= len(pool):
        return float("-inf")
    rnd = random.Random(seed)
    sims = sorted(statistics.fmean(t["r"] for t in rnd.sample(pool, keep)) for _ in range(200))
    return sims[int(0.9 * len(sims))]


def evaluate(rows: list[dict], combo: tuple) -> dict:
    kept = [t for t in rows if all(t["f"][f] for f in combo)]
    by = {p: stats([t for t in kept if period(t["utc"]) == p]) for p in ("train", "validate", "test")}
    train_pool = [t for t in rows if period(t["utc"]) == "train"]
    by["random_p90_train"] = random_p90(train_pool, by["train"]["n"], 11) if combo else float("-inf")
    by["all"] = stats(kept)
    return by


def score(v: dict):
    t = v["train"]
    return (t["exp"] > 0 and t["exp"] > v["random_p90_train"], round(t["pos_years"], 2), -t["dd"], t["ret_dd"])


def main() -> None:
    usd, dxy = usd_index(), real_dxy()
    combos = [()] + [(f,) for f in FILTERS] + [p for p in itertools.combinations(FILTERS, 2)
                                               if set(p) != {"ADX_LOW", "ADX_HIGH"}]
    results, lines = {}, ["# G27: bộ lọc liên thị trường và chế độ thị trường (chọn trên 2010–2016)", ""]
    for name in ("S04", "S06", "S06B", "S02", "S02INV"):
        per_symbol = {}
        for s in ls.SYMBOLS:
            rows = base_rows(name, s)
            if rows:
                tag(rows, s, usd, dxy)
                per_symbol[s] = rows
        everything = [t for v in per_symbol.values() for t in v]
        scopes = {"ALL": everything, **per_symbol}
        res = {}
        for scope, rows in scopes.items():
            for combo in combos:
                res[(scope, combo)] = evaluate(rows, combo)
        results[name] = res
        ranked = sorted(res.items(), key=lambda kv: score(kv[1]), reverse=True)
        base = res[("ALL", ())]
        lines += [f"## {name}", f"Không lọc (5 symbol): train {fmt(base['train'])} | validate {fmt(base['validate'])} | test {fmt(base['test'])}", "",
                  "| Phạm vi | Bộ lọc | Train | Validate | Test | Năm dương (cả kỳ) | DD cả kỳ (R) | Thắng ngẫu nhiên |",
                  "|---|---|---|---|---|---|---|---|"]
        shown = 0
        for (scope, combo), v in ranked:
            if not combo or v["train"]["n"] < 25:
                continue
            beat = "có" if v["train"]["exp"] > v["random_p90_train"] else "không"
            lines.append(f"| {scope} | {'+'.join(combo)} | {fmt(v['train'])} | {fmt(v['validate'])} | {fmt(v['test'])} | "
                         f"{v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} | {beat} |")
            shown += 1
            if shown >= 8:
                break
        if dxy:
            real = [t for t in everything if t["dxy_ok"] is not None]
            ok = stats([t for t in real if t["dxy_ok"]])
            proxy = stats([t for t in real if t["f"]["USD_FLOW"]])
            lines.append(f"\nĐối chiếu DXY thật (2021-09..2025-10): cùng chiều DXY {fmt(ok)}; cùng chiều USD đại diện {fmt(proxy)}")
        lines.append("")
    ls.OUT.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (ls.OUT / "filters.md").write_text(text, encoding="utf-8")
    (ls.OUT / "filters.json").write_text(json.dumps({k: {f"{s}|{'+'.join(c)}": v for (s, c), v in r.items()}
                                                     for k, r in results.items()}, default=str), encoding="utf-8")
    print(text)


def fmt(s: dict) -> str:
    return f"n={s['n']} {s['exp']:+.3f}" if s["n"] else "n=0"


if __name__ == "__main__":
    main()
