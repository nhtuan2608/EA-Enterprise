"""G45: price zones, market structure and reversal patterns that the EA does not have yet. MT5 data only.

  python g45_zones.py              # every family
  python g45_zones.py Z1 Z3        # some families

Plan: docs/superpowers/plans/2026-10-06-g45-zones-structure.md. H1, five symbols 2010-2025 (XAU/BTC from 2018);
chosen on 2010-2016, validated 2017-2020 and 2021-2025; out-of-sample on 16 other symbols (H1 2024-02 .. 2026-10).
Swings are 3-bar fractals, used only once confirmed (3 bars later). Limit orders fill when the bar's low plus the
spread (buy) / high (sell) reaches the level, at the level or at a better open; a fill bar that also reaches the
stop counts as a full loss (conservative). Market orders enter at the close (ask for a buy). Exits through
pyramid.walk (stop first, gap fills at the open, commission per leg). One trade per symbol and family at a time.
  Z1 supply / demand: base of 1-3 bars (range <= k ATR) before an impulse bar (range >= m ATR, body >= 60%)
     that closes at least 1 ATR beyond the base; buy limit at the base high (sell: base low), stop beyond the
     far side, first return only, valid 120 bars
  Z2 order block + break of structure: close beyond the last confirmed swing high / low; the last opposite bar
     in the 10 bars before is the block; limit at its near edge, stop beyond its far edge
  Z3 fair value gap: low[i] > high[i-2] after an impulse bar (sell: mirror); limit at the gap top or middle,
     stop 0.5 ATR below the gap
  Z4 liquidity sweep + change of character: a bar trades below the last confirmed swing low and closes back
     above it; within 6 bars a close above that bar's high enters at market; stop below the sweep low
  Z5 Fibonacci OTE: a leg from a confirmed swing low to the next confirmed swing high of at least k ATR; limit at
     61.8% or 70.5%; stop below the swing low; target the swing high or 2R; cancelled on a new high / low
  Z6 RSI divergence: a confirmed swing low below the previous one (<= 40 bars) with RSI14 at least 3 higher;
     market entry at the confirmation; stop below the swing low
  Z7 double bottom / top: two confirmed swing lows within tol ATR, 8-60 bars apart; a close above the highest
     high between them enters at market (within 30 bars); stop below the lower low
Every family also with the D1 EMA200 side as a trend filter. Checks for the best set (by train expectancy, at
least 60 train trades): validate and test positive, random entries (same stop in ATR, same exit, 300 runs),
neighbours, the 16 out-of-sample symbols, commission x2 + 0.1R.
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

TF = "H1"
SYMBOLS = ls.SYMBOLS
OOS = dv.NEW + ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
for _s in dv.NEW:
    replay.COMMISSION.setdefault(_s, 0.009 if _s.endswith("JPY") else 0.00006)
VAL, TST = ls.VALIDATE, ls.TEST
OOS_START = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())
RUNS = 300
FRACTAL = 3


def grid(d):
    return [dict(zip(d, v)) for v in itertools.product(*d.values())]


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
def prep(B):
    if "z_ready" in B:
        return B
    h, lo = B["h"], B["l"]
    n = len(h)
    sh = np.zeros(n, bool)
    sl = np.zeros(n, bool)
    k = FRACTAL
    for i in range(k, n - k):
        if h[i] > h[i - k:i].max() and h[i] >= h[i + 1:i + k + 1].max():
            sh[i] = True
        if lo[i] < lo[i - k:i].min() and lo[i] <= lo[i + 1:i + k + 1].min():
            sl[i] = True
    B["sh"], B["sl"] = sh, sl
    B["side200"] = dv.d1_side(B, 200)
    B["rsi14"] = dv.rsi(B["c"], 14)
    B["sp"] = np.array([b["spread"] * B["point"] for b in B["bars"]])
    B["z_ready"] = True
    return B


def trend_ok(B, i, d, p):
    return not p.get("trend") or B["side200"][i] == d


# ---------------------------------------------------------------------------
# Orders: (created_i, d, kind, level, stop, target_price or None, expiry_bars)
# ---------------------------------------------------------------------------
def orders_z1(B, p):
    o, h, l, c, atr = B["o"], B["h"], B["l"], B["c"], B["atr"]
    out = []
    nb = p["base"]
    for i in range(nb + 20, len(c) - 1):
        a = atr[i - 1]
        if a <= 0:
            continue
        rng, body = h[i] - l[i], abs(c[i] - o[i])
        if rng < p["imp"] * a or body < 0.6 * rng:
            continue
        bh, bl = h[i - nb:i].max(), l[i - nb:i].min()
        if bh - bl > p["basek"] * a:
            continue
        d = 1 if c[i] > o[i] else -1
        if (d == 1 and c[i] < bh + a) or (d == -1 and c[i] > bl - a):
            continue
        if not trend_ok(B, i, d, p):
            continue
        level, stop = (bh, bl - 0.1 * a) if d == 1 else (bl, bh + 0.1 * a)
        out.append((i, d, "limit", level, stop, None, 120))
    return out


def last_swing(B, i, high: bool):
    """Last swing confirmed by bar i (its index <= i - FRACTAL)."""
    arr = B["sh"] if high else B["sl"]
    j = i - FRACTAL
    while j > 0 and not arr[j]:
        j -= 1
    return j if j > 0 else None


def orders_z2(B, p):
    o, h, l, c, atr = B["o"], B["h"], B["l"], B["c"], B["atr"]
    out = []
    sh_idx = sl_idx = None
    for i in range(30, len(c) - 1):
        a = atr[i - 1]
        if B["sh"][i - FRACTAL]:
            sh_idx = i - FRACTAL
        if B["sl"][i - FRACTAL]:
            sl_idx = i - FRACTAL
        if a <= 0:
            continue
        for d, idx in ((1, sh_idx), (-1, sl_idx)):
            if idx is None:
                continue
            lvl = h[idx] if d == 1 else l[idx]
            if not ((d == 1 and c[i] > lvl and c[i - 1] <= lvl) or (d == -1 and c[i] < lvl and c[i - 1] >= lvl)):
                continue
            if abs(c[i] - o[i]) < p["imp"] * a or not trend_ok(B, i, d, p):
                continue
            ob = None
            for k in range(i - 1, max(i - 11, 0), -1):
                if (d == 1 and c[k] < o[k]) or (d == -1 and c[k] > o[k]):
                    ob = k
                    break
            if ob is None:
                continue
            level, stop = (h[ob], l[ob] - 0.1 * a) if d == 1 else (l[ob], h[ob] + 0.1 * a)
            out.append((i, d, "limit", level, stop, None, 120))
    return out


def orders_z3(B, p):
    o, h, l, c, atr = B["o"], B["h"], B["l"], B["c"], B["atr"]
    out = []
    for i in range(20, len(c) - 1):
        a = atr[i - 1]
        if a <= 0 or (h[i - 1] - l[i - 1]) < p["imp"] * a:
            continue
        for d in (1, -1):
            if d == 1 and l[i] > h[i - 2]:
                top, bot = l[i], h[i - 2]
            elif d == -1 and h[i] < l[i - 2]:
                top, bot = l[i - 2], h[i]
            else:
                continue
            if (top - bot) < 0.2 * a or not trend_ok(B, i, d, p):
                continue
            mid = (top + bot) / 2
            if d == 1:
                level = top if p["entry"] == "edge" else mid
                stop = bot - 0.5 * a
            else:
                level = bot if p["entry"] == "edge" else mid
                stop = top + 0.5 * a
            out.append((i, d, "limit", level, stop, None, 60))
    return out


def orders_z4(B, p):
    h, l, c, atr = B["h"], B["l"], B["c"], B["atr"]
    out = []
    sh_idx = sl_idx = None
    armed = []      # (expires_i, d, trigger, stop)
    for i in range(30, len(c) - 1):
        if B["sh"][i - FRACTAL]:
            sh_idx = i - FRACTAL
        if B["sl"][i - FRACTAL]:
            sl_idx = i - FRACTAL
        a = atr[i - 1]
        if a <= 0:
            continue
        keep = []
        for exp, d, trig, stop in armed:
            if i > exp:
                continue
            if (d == 1 and c[i] > trig) or (d == -1 and c[i] < trig):
                out.append((i, d, "market", c[i], stop, None, 0))
                continue
            keep.append((exp, d, trig, stop))
        armed = keep
        if sl_idx is not None and l[i] < l[sl_idx] and c[i] > l[sl_idx] and trend_ok(B, i, 1, p):
            armed.append((i + p["window"], 1, h[i], l[i] - 0.1 * a))
            sl_idx = None
        if sh_idx is not None and h[i] > h[sh_idx] and c[i] < h[sh_idx] and trend_ok(B, i, -1, p):
            armed.append((i + p["window"], -1, l[i], h[i] + 0.1 * a))
            sh_idx = None
    return out


def orders_z5(B, p):
    h, l, c, atr = B["h"], B["l"], B["c"], B["atr"]
    out = []
    lows, highs = [], []
    for i in range(30, len(c) - 1):
        j = i - FRACTAL
        if B["sl"][j]:
            lows.append(j)
        if B["sh"][j]:
            highs.append(j)
            if lows and lows[-1] < j:
                lo_i = lows[-1]
                leg = h[j] - l[lo_i]
                a = atr[i - 1]
                if a > 0 and leg >= p["leg"] * a and trend_ok(B, i, 1, p):
                    level = h[j] - p["fib"] * leg
                    tgt = h[j] if p["target"] == "zero" else None
                    out.append((i, 1, "limit", level, l[lo_i] - 0.1 * a, tgt, 60))
        if B["sl"][j] and highs and highs[-1] < j:
            hi_i = highs[-1]
            leg = h[hi_i] - l[j]
            a = atr[i - 1]
            if a > 0 and leg >= p["leg"] * a and trend_ok(B, i, -1, p):
                level = l[j] + p["fib"] * leg
                tgt = l[j] if p["target"] == "zero" else None
                out.append((i, -1, "limit", level, h[hi_i] + 0.1 * a, tgt, 60))
    return out


def orders_z6(B, p):
    h, l, c, atr, r = B["h"], B["l"], B["c"], B["atr"], B["rsi14"]
    out = []
    lows, highs = [], []
    for i in range(40, len(c) - 1):
        j = i - FRACTAL
        a = atr[i - 1]
        if a <= 0:
            continue
        if B["sl"][j]:
            if lows and j - lows[-1] <= 40 and l[j] < l[lows[-1]] and r[j] >= r[lows[-1]] + p["gap"] and trend_ok(B, i, 1, p):
                out.append((i, 1, "market", c[i], l[j] - 0.1 * a, None, 0))
            lows.append(j)
        if B["sh"][j]:
            if highs and j - highs[-1] <= 40 and h[j] > h[highs[-1]] and r[j] <= r[highs[-1]] - p["gap"] and trend_ok(B, i, -1, p):
                out.append((i, -1, "market", c[i], h[j] + 0.1 * a, None, 0))
            highs.append(j)
    return out


def orders_z7(B, p):
    h, l, c, atr = B["h"], B["l"], B["c"], B["atr"]
    out = []
    lows, highs = [], []
    armed = []
    for i in range(40, len(c) - 1):
        j = i - FRACTAL
        a = atr[i - 1]
        if a <= 0:
            continue
        keep = []
        for exp, d, neck, stop, height in armed:
            if i > exp:
                continue
            if (d == 1 and c[i] > neck) or (d == -1 and c[i] < neck):
                tgt = (c[i] + d * height) if p["target"] == "measured" else None
                out.append((i, d, "market", c[i], stop, tgt, 0))
                continue
            keep.append((exp, d, neck, stop, height))
        armed = keep
        if B["sl"][j]:
            for k in reversed(lows):
                if 8 <= j - k <= 60 and abs(l[j] - l[k]) <= p["tol"] * a:
                    neck = h[k:j + 1].max()
                    if trend_ok(B, i, 1, p):
                        armed.append((i + 30, 1, neck, min(l[j], l[k]) - 0.1 * a, neck - min(l[j], l[k])))
                    break
            lows.append(j)
        if B["sh"][j]:
            for k in reversed(highs):
                if 8 <= j - k <= 60 and abs(h[j] - h[k]) <= p["tol"] * a:
                    neck = l[k:j + 1].min()
                    if trend_ok(B, i, -1, p):
                        armed.append((i + 30, -1, neck, max(h[j], h[k]) + 0.1 * a, max(h[j], h[k]) - neck))
                    break
            highs.append(j)
    return out


EXITS = ["R2", "R3", "trail"]
FAMILIES = {
    "Z1": (orders_z1, grid({"base": [1, 3], "basek": [1.0], "imp": [1.5, 2.5], "trend": [False, True], "exit": ["R2", "R3"]})),
    "Z2": (orders_z2, grid({"imp": [0.5, 1.0], "trend": [False, True], "exit": EXITS})),
    "Z3": (orders_z3, grid({"imp": [1.5, 2.5], "entry": ["edge", "mid"], "trend": [False, True], "exit": ["R2", "R3"]})),
    "Z4": (orders_z4, grid({"window": [3, 6], "trend": [False, True], "exit": EXITS})),
    "Z5": (orders_z5, grid({"leg": [3.0, 5.0], "fib": [0.618, 0.705], "trend": [False, True], "target": ["zero", "R2"]})),
    "Z6": (orders_z6, grid({"gap": [3.0, 6.0], "trend": [False, True], "exit": EXITS})),
    "Z7": (orders_z7, grid({"tol": [0.3, 0.6], "trend": [False, True], "target": ["measured", "R2"]})),
}


def rule_for(p):
    ex = p.get("exit") or p.get("target")
    if ex == "trail":
        return {"target": None, "be": None, "partial": None, "trail": ("ATR", 0.0, 3.0), "timeout": 120, "struct_exit": False}
    return {"target": "plan", "be": None, "partial": None, "trail": None, "timeout": 72, "struct_exit": False}


def target_r(p):
    ex = p.get("exit") or p.get("target")
    return 3.0 if ex == "R3" else 2.0


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------
def fill(B, created, d, level, stop, expiry):
    """Fill bar and price of a limit order, or None (expired / zone broken first)."""
    o, h, l, c, sp = B["o"], B["h"], B["l"], B["c"], B["sp"]
    for j in range(created + 1, min(created + 1 + expiry, len(c) - 1)):
        if d == 1:
            if l[j] + sp[j] <= level:
                return j, min(level, o[j] + sp[j])
            if c[j] < stop:
                return None
        else:
            if h[j] >= level:
                return j, max(level, o[j])
            if c[j] + sp[j] > stop:
                return None
    return None


def trades(fam: str, p: dict, symbol: str, start: int = 0) -> list[dict]:
    B = dv.load(symbol, TF)
    if B is None:
        return []
    prep(B)
    gen, _ = FAMILIES[fam]
    rule = rule_for(p)
    fee = replay.COMMISSION.get(symbol, 0.0)
    out, busy = [], -1
    for created, d, kind, level, stop, tgt, expiry in gen(B, p):
        if B["utc"][created] < start or created <= busy:
            continue
        if kind == "market":
            j, entry = created, B["c"][created] + (B["sp"][created] if d == 1 else 0.0)
        else:
            f = fill(B, created, d, level, stop, expiry)
            if f is None:
                continue
            j, entry = f
        if j <= busy or j >= len(B["c"]) - 2:
            continue
        risk = d * (entry - stop)
        a = B["atr"][j]
        if a <= 0 or risk < 0.2 * a or risk > 8 * a:
            continue
        target = tgt if tgt is not None and d * (tgt - entry) > 0.5 * risk else entry + d * target_r(p) * risk
        if kind == "limit" and ((d == 1 and B["l"][j] <= stop) or (d == -1 and B["h"][j] + B["sp"][j] >= stop)):
            r, exit_i = -1.0 - fee / risk, j            # the fill bar also reaches the stop
        else:
            t = {"symbol": symbol, "i": j, "dir": d, "entry": entry, "stop": stop, "target": target, "zl": 0.0, "zh": 0.0}
            res = pyramid.run(B["ctx"], t, rule)
            r, exit_i = res["r"], res["exit_i"]
        busy = exit_i
        out.append({"symbol": symbol, "utc": int(B["utc"][j]), "i": j, "dir": d, "r": r, "stop_atr": risk / a,
                    "exit_i": exit_i, "tr": d * (target - entry) / risk})
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
    rule = rule_for(p)
    rng = np.random.default_rng(seed)
    pools = {}
    for s in SYMBOLS:
        B = dv.load(s, TF)
        years = (B["utc"] // (365.25 * 86400)).astype(int)
        ok = np.where((B["atr"] > 0) & (np.arange(len(years)) > 300) & (np.arange(len(years)) < len(years) - 2))[0]
        pools[s] = {y: ok[years[ok] == y] for y in np.unique(years[ok])}
    out = []
    for _ in range(runs):
        tot = 0.0
        for x in rows:
            B = dv.load(x["symbol"], TF)
            pool = pools[x["symbol"]].get(int(x["utc"] // (365.25 * 86400)))
            if pool is None or len(pool) == 0:
                continue
            j = int(pool[rng.integers(len(pool))])
            d = 1 if rng.random() < 0.5 else -1
            b = B["bars"][j]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = x["stop_atr"] * B["atr"][j]
            t = {"symbol": x["symbol"], "i": j, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * x["tr"] * risk, "zl": 0.0, "zh": 0.0}
            tot += pyramid.run(B["ctx"], t, rule)["r"]
        out.append(tot / len(rows))
    return out


def neighbours(fam, p, res):
    keys = [k for k in p if len({tuple(sorted(r["p"].items())) for r in res if r["fam"] == fam}) > 1]
    near = [r for r in res if r["fam"] == fam and sum(r["p"][k] != p[k] for k in p) == 1]
    ok = [r for r in near if all(r[k]["exp"] > 0 for k in ("train", "validate", "test"))]
    return len(ok), len(near)


def main(argv):
    pyramid.GAP_FILL = True
    fams = [f for f in (argv or FAMILIES) if f in FAMILIES]
    lines = ["# G45: vùng giá, cấu trúc thị trường, mô hình đảo chiều (chỉ dữ liệu MT5)", "",
             "H1, chọn trên 2010–2016; kiểm chứng 2017–2020 và 2021–2025; ngoài mẫu 16 symbol 2024–2026.", "",
             "## 1. Quét", "", "| Họ | Bộ dương cả 3 kỳ | Bộ chọn | Train | Validate | Test |", "|---|---|---|---|---|---|"]
    jobs = [(f, p) for f in fams for p in FAMILIES[f][1]]
    with Pool(12) as pool:
        res = pool.map(scan_job, jobs)
        best = {}
        for f in fams:
            rs = [r for r in res if r["fam"] == f]
            pos = sum(1 for r in rs if all(r[k]["exp"] > 0 and r[k]["n"] > 0 for k in ("train", "validate", "test")))
            cand = [r for r in rs if r["train"]["n"] >= 60] or rs
            b = max(cand, key=lambda r: r["train"]["exp"])
            best[f] = b
            lines.append(f"| {f} | {pos}/{len(rs)} | {b['p']} | {fmt(b['train'])} | {fmt(b['validate'])} | {fmt(b['test'])} |")
        lines += ["", "## 2. Kiểm chứng bộ chọn", "",
                  "| Họ | Ngẫu nhiên p | Láng giềng dương 3 kỳ | Phí ×2 + 0,1R | Ngoài mẫu 16 symbol | Theo symbol | Đạt |",
                  "|---|---|---|---|---|---|---|"]
        for f, b in best.items():
            rows = b["rows"]
            if not rows:
                lines.append(f"| {f} | - | - | - | - | - | không |")
                continue
            real = statistics.fmean(t["r"] for t in rows)
            sims = [v for ch in pool.map(random_job, [(f, b["p"], rows, 4500 + k, RUNS // 10) for k in range(10)]) for v in ch]
            p_rand = float(np.mean(np.array(sims) >= real))
            nb_ok, nb_n = neighbours(f, b["p"], res)
            fee = []
            for t in rows:
                B = dv.load(t["symbol"], TF)
                risk = t["stop_atr"] * B["atr"][t["i"]]
                fee.append(t["r"] - replay.COMMISSION.get(t["symbol"], 0.0) / max(risk, 1e-12) - 0.1)
            oos = [t["r"] for s in OOS for t in trades(f, b["p"], s, OOS_START)]
            per_sym = ", ".join(f"{s} {statistics.fmean([t['r'] for t in rows if t['symbol'] == s]):+.2f}"
                                for s in SYMBOLS if any(t["symbol"] == s for t in rows))
            passed = (all(b[k]["exp"] > 0 for k in ("train", "validate", "test")) and p_rand < 0.05 / 7
                      and nb_n and nb_ok / nb_n >= 0.6 and statistics.fmean(fee) > 0 and stats(oos)["exp"] > -0.05)
            lines.append(f"| {f} | {p_rand:.3f} | {nb_ok}/{nb_n} | {statistics.fmean(fee):+.3f} | {fmt(stats(oos))} | "
                         f"{per_sym} | {'**có**' if passed else 'không'} |")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / f"g45_{'_'.join(fams)}.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv[1:])
